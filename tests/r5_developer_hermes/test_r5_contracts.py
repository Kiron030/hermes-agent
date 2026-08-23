"""R5 contracts: isolation, authority absence, developer policy."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from r5_developer_hermes.harness import (
    PIN_PATH,
    REPO_ROOT,
    SAFE_ENV_PASSTHROUGH,
    WEB_KEY_ENV,
    assert_authority_absent,
    blocked_names,
    container_boundary_status,
    isolated_env,
    load_pin,
    production_authority_names,
    proof_root,
    write_developer_home,
)


ALWAYS_BLOCKED = (
    "DATABASE_URL_TIMESCALE",
    "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET",
)


def test_pin_matches_r1_immutable_identities() -> None:
    pin = load_pin()
    assert pin["slice"] == "R5"
    assert pin["gate_1"] == "CLOSED"
    assert pin["upstream_release"] == "v2026.8.19"
    assert pin["upstream_release_sha"] == "fcbd1076a93841fa88855acce810e342a5b78101"
    assert (
        pin["upstream_image_digest"]
        == "sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09"
    )
    assert "latest" not in pin["upstream_image_ref"]
    assert pin["approvals_mode"] == "off"
    assert pin["ordinary_workspace_approvals"] == 0
    assert pin["isolation_boundary"] == "PROCESS_CONSTRUCTED_ENV"


def test_pin_json_contains_no_secret_values() -> None:
    raw = PIN_PATH.read_text(encoding="utf-8").lower()
    for needle in ("sk-", "bearer ", "postgres://", "postgresql://", "ghp_"):
        assert needle not in raw
    assert "password" not in raw


def test_isolated_env_strips_parent_production_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin = load_pin()
    for name in production_authority_names(pin):
        monkeypatch.setenv(name, "should-never-leak")
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://prod/should-not-leak")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "prod-secret")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://prod.example")
    env = isolated_env(tmp_path / "home")
    assertion = assert_authority_absent(env, pin)
    assert assertion["pass"] is True
    for name in ALWAYS_BLOCKED:
        assert name not in env
    assert "POWERUNITS_INTERNAL_EXECUTE_BASE_URL" not in env


def test_isolated_env_refuses_to_inject_authority(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="production-authority"):
        isolated_env(
            tmp_path / "home",
            extra={"POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET": "nope"},
        )


def test_safe_passthrough_excludes_provider_and_deploy_keys() -> None:
    forbidden = {
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "TAVILY_API_KEY",
        "DATABASE_URL",
        "RAILWAY_TOKEN",
        "VERCEL_TOKEN",
        WEB_KEY_ENV,
    }
    assert forbidden.isdisjoint(SAFE_ENV_PASSTHROUGH)
    assert "RAILWAY_TOKEN" in blocked_names()
    assert "VERCEL_TOKEN" in blocked_names()
    assert "TAVILY_API_KEY" not in SAFE_ENV_PASSTHROUGH


def test_web_key_is_opt_in_not_ambient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "ambient-must-not-passthrough")
    monkeypatch.setenv(WEB_KEY_ENV, "r5-dedicated-not-a-real-secret")
    bare = isolated_env(tmp_path / "home")
    child = isolated_env(tmp_path / "home", include_web_key=True)
    assert "TAVILY_API_KEY" not in bare
    assert child["TAVILY_API_KEY"] == "r5-dedicated-not-a-real-secret"


def test_developer_config_is_powerful_and_approval_free(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_R5_PROOF_ROOT", str(tmp_path / "proof"))
    home = write_developer_home()
    text = (home / "config.yaml").read_text(encoding="utf-8")
    assert "mode: off" in text
    assert "allow_lazy_installs: false" in text
    assert "- file" in text
    assert "- terminal" in text
    assert "- skills" in text
    assert "allowlist" not in text
    assert "first_safe" not in text


def test_proof_root_is_not_default_hermes_home() -> None:
    root = proof_root()
    assert root == REPO_ROOT / ".r5-dev" or os.environ.get("HERMES_R5_PROOF_ROOT")
    assert ".hermes" not in root.parts


def test_isolated_env_uses_synthetic_home_not_host_profile(tmp_path: Path) -> None:
    env = isolated_env(tmp_path / "home")
    isolated = Path(env["HOME"])
    assert isolated == (tmp_path / "process-home")
    assert isolated != Path.home()
    assert env["USERPROFILE"] == str(isolated)
    assert not (isolated / ".railway").exists()
    assert not (isolated / ".vercel").exists()
    stub_dir = isolated / "bin"
    assert env["PATH"].startswith(str(stub_dir))
    assert (stub_dir / "railway.cmd").is_file()
    assert (stub_dir / "vercel.cmd").is_file()


def test_container_status_does_not_claim_fake_isolation() -> None:
    status = container_boundary_status()
    assert status["ISOLATION_BOUNDARY"] == "PROCESS_CONSTRUCTED_ENV"
    assert status["container_used"] is False
    assert "env.update" in status["note"]


def test_r1_decision_docs_remain_tracked() -> None:
    report = REPO_ROOT / "docs" / "architecture" / "hermes_r1_proof_report_v1.md"
    assert report.is_file()
    assert "GATE_1_STATUS = CLOSED" in report.read_text(encoding="utf-8")
