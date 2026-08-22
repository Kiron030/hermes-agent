"""R1 acceptance contracts: pin, isolation, clamp, no production authority."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from r1_modern_hermes_proof.harness import (
    MODEL_KEY_ENV,
    PIN_PATH,
    REPO_ROOT,
    SAFE_ENV_PASSTHROUGH,
    SMOKE_PROMPT,
    assert_authority_absent,
    isolated_env,
    load_pin,
    model_smoke_cli_args,
    model_smoke_command,
    operator_home,
    production_authority_names,
    proof_root,
    resolve_model_smoke_target,
    upstream_src,
    verify_pin,
    write_model_smoke_operator_config,
    write_proof_homes,
)


ALWAYS_BLOCKED = (
    "DATABASE_URL_TIMESCALE",
    "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET",
)


def test_canonical_decision_documents_are_tracked() -> None:
    files = (
        REPO_ROOT / "docs/architecture/hermes_modernisation_execution_roadmap_v1.md",
        REPO_ROOT / "docs/architecture/hermes_upstream_reassessment_v1.md",
        REPO_ROOT / "docs/architecture/hermes_upstream_reassessment_red_team_v1.md",
    )
    starts = (
        "# PowerUnits × Hermes: Modernisierungs-Execution-Roadmap v1",
        "# PowerUnits × Hermes: Upstream Reassessment v1",
        "# PowerUnits × Hermes: Red-Team Review v1",
    )
    for path, prefix in zip(files, starts):
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").startswith(prefix)


def test_pin_file_matches_declared_identities() -> None:
    pin = load_pin()
    assert pin["upstream_release"] == "v2026.8.19"
    assert pin["upstream_project_version"] == "0.20.5"
    assert pin["upstream_release_sha"] == "fcbd1076a93841fa88855acce810e342a5b78101"
    assert pin["upstream_tag_object"] == "b05e680e63d39d5a8e3ec0f5842a41d1c4209c03"
    assert (
        pin["upstream_image_digest"]
        == "sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09"
    )
    assert pin["upstream_image_ref"].startswith("nousresearch/hermes-agent@sha256:")
    assert "latest" not in pin["upstream_image_ref"]


def test_pin_json_contains_no_secret_values() -> None:
    raw = PIN_PATH.read_text(encoding="utf-8").lower()
    for needle in ("sk-", "bearer ", "postgres://", "postgresql://", "ghp_", "railway"):
        if needle == "railway":
            continue
        assert needle not in raw
    assert "password" not in raw


def test_offline_pin_verify_does_not_need_network() -> None:
    result = verify_pin(live=False)
    assert result["pass"] is True


@pytest.mark.skipif(
    os.environ.get("HERMES_R1_SKIP_LIVE_PIN") == "1",
    reason="live pin check disabled",
)
def test_live_pin_identities_match_upstream_metadata() -> None:
    try:
        result = verify_pin(live=True)
    except OSError as exc:
        pytest.skip(f"upstream metadata unreachable: {exc}")
    assert result["pass"] is True, result


def test_isolated_env_strips_production_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pin = load_pin()
    for name in production_authority_names(pin):
        monkeypatch.setenv(name, "should-never-leak")
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://prod/should-not-leak")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "prod-secret")
    env = isolated_env(tmp_path / "home")
    assertion = assert_authority_absent(env, pin)
    assert assertion["pass"] is True
    for name in ALWAYS_BLOCKED:
        assert name not in env
        assert env.get(name) in {None, ""}


def test_isolated_env_refuses_to_inject_authority(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="production-authority"):
        isolated_env(
            tmp_path / "home",
            extra={"POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET": "nope"},
        )


def test_model_key_env_is_not_a_production_name() -> None:
    assert MODEL_KEY_ENV == "HERMES_R1_MODEL_API_KEY"
    assert MODEL_KEY_ENV not in production_authority_names()


def test_safe_passthrough_does_not_include_openai_key() -> None:
    assert "OPENAI_API_KEY" not in SAFE_ENV_PASSTHROUGH
    assert "OPENROUTER_API_KEY" not in SAFE_ENV_PASSTHROUGH
    assert MODEL_KEY_ENV not in SAFE_ENV_PASSTHROUGH


def test_model_smoke_maps_r1_key_not_ambient_openai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = "r1-sentinel-not-a-real-secret"
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-must-not-passthrough")
    monkeypatch.setenv(MODEL_KEY_ENV, sentinel)
    monkeypatch.setenv("HERMES_R1_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("HERMES_R1_MODEL", "gpt-4.1-mini")
    child = isolated_env(tmp_path / "home", include_model_key=True)
    bare = isolated_env(tmp_path / "home")
    assert child["OPENAI_API_KEY"] == sentinel
    assert child["HERMES_INFERENCE_PROVIDER"] == "openai-api"
    assert child["HERMES_INFERENCE_MODEL"] == "gpt-4.1-mini"
    assert "OPENAI_API_KEY" not in bare
    assert "HERMES_INFERENCE_PROVIDER" not in bare


def test_model_smoke_pins_openai_api_not_openrouter(tmp_path: Path) -> None:
    target = resolve_model_smoke_target("openai", "gpt-4.1-mini")
    assert target["hermes_provider"] == "openai-api"
    assert target["key_env"] == "OPENAI_API_KEY"
    assert target["base_url_host"] == "api.openai.com"
    assert target["path_class"] == "/v1/chat/completions"
    hermes = tmp_path / "hermes"
    hermes.write_text("", encoding="utf-8")
    python = tmp_path / "python"
    cmd = model_smoke_command(hermes, python)
    assert cmd[0] == str(python)
    assert cmd[1].endswith("model_smoke_run.py")
    assert model_smoke_cli_args() == [
        "--provider",
        "openai-api",
        "--model",
        "gpt-4.1-mini",
        "-z",
        SMOKE_PROMPT,
    ]


def _pinned_top_level_parser():
    import importlib.util

    parser_path = upstream_src() / "hermes_cli" / "_parser.py"
    if not parser_path.is_file():
        pytest.skip("pinned upstream parser missing; run prepare-source")
    spec = importlib.util.spec_from_file_location("r1_pinned_hermes_parser", parser_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser, _subparsers, _chat = module.build_top_level_parser()
    return parser


def test_model_smoke_argv_matches_pinned_oneshot_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parser = _pinned_top_level_parser()
    broken = [
        "-z",
        "--provider",
        "openai-api",
        "--model",
        "gpt-4.1-mini",
        SMOKE_PROMPT,
    ]
    with pytest.raises(SystemExit):
        parser.parse_args(broken)

    parsed = parser.parse_args(model_smoke_cli_args())
    assert parsed.oneshot == SMOKE_PROMPT
    assert parsed.oneshot.strip()
    assert parsed.provider == "openai-api"
    assert parsed.model == "gpt-4.1-mini"
    assert model_smoke_cli_args()[model_smoke_cli_args().index("-z") + 1] == SMOKE_PROMPT

    sentinel = "r1-sentinel-not-a-real-secret"
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-must-not-passthrough")
    monkeypatch.setenv(MODEL_KEY_ENV, sentinel)
    monkeypatch.setenv("HERMES_R1_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("HERMES_R1_MODEL", "gpt-4.1-mini")
    child = isolated_env(tmp_path / "home", include_model_key=True)
    bare = isolated_env(tmp_path / "home")
    assert child["OPENAI_API_KEY"] == sentinel
    assert "OPENAI_API_KEY" not in bare
    assert "OPENAI_API_KEY" not in SAFE_ENV_PASSTHROUGH


def test_model_smoke_operator_config_pins_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_R1_PROOF_ROOT", str(tmp_path / "proof"))
    write_proof_homes()
    target = write_model_smoke_operator_config(operator_home())
    text = (operator_home() / "config.yaml").read_text(encoding="utf-8")
    assert "provider: openai-api" in text
    assert "default: gpt-4.1-mini" in text
    assert "reasoning_effort: none" in text
    assert "gpt-4.1-mini: none" in text
    assert "sk-" not in text
    assert target["hermes_provider"] == "openai-api"


def test_model_smoke_harness_is_ready_without_reading_credentials() -> None:
    from r1_modern_hermes_proof.harness import model_smoke

    result = model_smoke()
    assert result["MODEL_SMOKE"] == "HUMAN_CREDENTIAL_REQUIRED"
    assert result["MODEL_SMOKE_HARNESS"] == "READY"
    assert "DO NOT ATTACH RAW MODEL-SMOKE ARTIFACT" in result["notes"]
    assert MODEL_KEY_ENV in result["human_command"]


def test_operator_policy_uses_upstream_toolset_names() -> None:
    pin = load_pin()
    assert "memory" in pin["operator_allowed_toolsets"]
    assert "todo" in pin["operator_allowed_toolsets"]
    assert "web" in pin["operator_allowed_toolsets"]
    forbidden = set(pin["operator_forbidden_toolsets"])
    assert {
        "terminal",
        "file",
        "session_search",
        "delegation",
        "browser",
        "cronjob",
        "computer_use",
        "skills",
    } <= forbidden


def test_proof_root_is_not_default_hermes_home() -> None:
    root = proof_root()
    assert root == REPO_ROOT / ".r1-proof" or os.environ.get("HERMES_R1_PROOF_ROOT")
    assert ".hermes" not in root.parts


def _source_ready() -> bool:
    src = upstream_src()
    return src.exists() and (src / "model_tools.py").exists()


@pytest.mark.skipif(not _source_ready(), reason="run harness prepare-source first")
def test_prepared_source_matches_pin() -> None:
    import subprocess

    src = upstream_src()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=src, text=True).strip()
    assert sha == load_pin()["upstream_release_sha"]


@pytest.mark.skipif(not _source_ready(), reason="run harness prepare-source first")
def test_upstream_model_tools_has_no_powerunits_final_cap() -> None:
    text = (upstream_src() / "model_tools.py").read_text(encoding="utf-8")
    assert "first_safe" not in text
    assert "POWERUNITS" not in text
    assert "disabled_toolsets" in text


@pytest.mark.skipif(not _source_ready(), reason="run harness prepare-source first")
def test_upstream_oneshot_does_not_pass_disabled_toolsets() -> None:
    text = (upstream_src() / "hermes_cli" / "oneshot.py").read_text(encoding="utf-8")
    assert "enabled_toolsets=toolsets_list" in text
    assert "disabled_toolsets=" not in text


@pytest.mark.skipif(not _source_ready(), reason="run harness prepare-source first")
def test_operator_home_is_isolated_from_repo_root() -> None:
    home = operator_home()
    if not home.exists():
        pytest.skip("run harness isolate-env first")
    assert proof_root() in home.parents or home == proof_root() / "homes" / "operator"
    assert not (REPO_ROOT / ".env").samefile(home / ".env") if (home / ".env").exists() else True
