"""Deterministic tests for the R5 Developer-Hermes DX contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from r5_developer_hermes.container.contract import (
    AUTHORITY_ENV_NAMES,
    BIND_MOUNTS,
    CONTAINER_HERMES_HOME,
    DEVELOPER_IMAGE,
    DEVELOPER_IMAGE_FROM,
    DEDICATED_MODEL_ENV_FILE,
    FORBIDDEN_HOST_SOURCES,
    HERMES_HOME_VOLUME,
    MODEL_KEY_ALLOWLIST,
    PINNED_DIGEST,
    PINNED_IMAGE,
    REPO_A_CONTAINER,
    REPO_B_CONTAINER,
    docker_run_argv,
    is_forbidden_host_source,
    parse_dedicated_model_env,
)
from r5_developer_hermes.harness import REPO_ROOT


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"
LAUNCHER = CONTAINER_DIR / "launch-developer-hermes.ps1"


def test_developer_image_is_built_from_the_pinned_digest() -> None:
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("#")
    assert f"FROM {PINNED_IMAGE}" in dockerfile
    assert PINNED_DIGEST in dockerfile
    assert "nousresearch/hermes-agent:latest" not in dockerfile
    assert "FROM " + PINNED_IMAGE.split("@")[0] + ":latest" not in dockerfile
    assert DEVELOPER_IMAGE_FROM == PINNED_IMAGE
    assert DEVELOPER_IMAGE.startswith("r5-developer-hermes:")


def test_fullstack_image_contract_is_container_local() -> None:
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "npm install -g typescript" in dockerfile
    assert "nvm" not in dockerfile.lower()
    assert r"C:\nvm4w" not in dockerfile
    assert "C:/Users" not in dockerfile
    text = (CONTAINER_DIR / "entrypoint.sh").read_text(encoding="utf-8")
    assert "HERMES_HOME" in text
    assert "/opt/r5-developer/seed_home.py" in text


def test_persistent_hermes_home_is_a_named_volume() -> None:
    assert CONTAINER_HERMES_HOME == "/opt/data"
    assert HERMES_HOME_VOLUME == "r5-developer-hermes-home"
    argv = docker_run_argv()
    joined = " ".join(argv)
    assert f"type=volume,src={HERMES_HOME_VOLUME},dst={CONTAINER_HERMES_HOME}" in argv
    assert "/tmp/r5-hermes-home" not in joined
    assert "--tmpfs" not in argv


def test_launcher_mount_policy_is_exactly_two_repo_binds() -> None:
    argv = docker_run_argv()
    bind_mounts = [item for item in argv if item.startswith("type=bind,")]
    assert bind_mounts == [
        f"type=bind,src={BIND_MOUNTS[0][0]},dst={REPO_A_CONTAINER}",
        f"type=bind,src={BIND_MOUNTS[1][0]},dst={REPO_B_CONTAINER}",
    ]
    assert argv.count("--mount") == 3


def test_forbidden_bind_mounts_and_host_roots_are_rejected() -> None:
    for source in (
        r"C:\Users\User",
        r"C:\Users\User\.powerunits\secrets",
        r"W:\Workbench",
        "W:\\",
        "C:\\",
        "D:\\",
        "/var/run/docker.sock",
    ):
        assert is_forbidden_host_source(source) is True
    for source, _dst in BIND_MOUNTS:
        assert is_forbidden_host_source(source) is False
    assert is_forbidden_host_source(HERMES_HOME_VOLUME) is False


def test_docker_run_argv_forbids_credential_passthrough() -> None:
    argv = docker_run_argv()
    joined = " ".join(argv)
    assert "--env-file" not in argv
    assert "HERMES_WRITE_SAFE_ROOT=/workspace:/opt/data" in argv
    assert "--privileged=false" in argv
    assert "--pid" not in argv
    assert f"--user" in argv
    assert "0:0" in argv
    assert "/var/run/docker.sock" not in joined
    assert r"\\.\pipe\docker_engine" not in joined
    assert "C:\\Users" not in joined
    assert "W:\\Workbench" not in joined
    assert str(DEDICATED_MODEL_ENV_FILE) not in joined
    for name in AUTHORITY_ENV_NAMES:
        assert name not in joined


def test_dedicated_model_file_rejects_production_and_unknown_keys(tmp_path: Path) -> None:
    good = tmp_path / "good.env"
    good.write_text("OPENROUTER_API_KEY=test-not-a-real-key\n", encoding="utf-8")
    parsed = parse_dedicated_model_env(good)
    assert list(parsed) == ["OPENROUTER_API_KEY"]
    assert "RAILWAY_TOKEN" not in parsed

    bad_prod = tmp_path / "prod.env"
    bad_prod.write_text("RAILWAY_TOKEN=nope\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="production-authority"):
        parse_dedicated_model_env(bad_prod)

    bad_extra = tmp_path / "extra.env"
    bad_extra.write_text("NOT_A_MODEL_KEY=nope\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="non-allowlisted"):
        parse_dedicated_model_env(bad_extra)

    assert MODEL_KEY_ALLOWLIST == (
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    )


def test_git_identity_is_isolated_and_has_no_host_credentials() -> None:
    seed = (CONTAINER_DIR / "seed_home.py").read_text(encoding="utf-8")
    assert "R5 Developer Hermes" in seed
    assert "r5-developer-hermes@local" in seed
    assert "helper =" in seed
    assert ".gitconfig" in seed
    assert "gpt-5.6-terra" in seed
    assert "reasoning_effort: medium" in seed
    assert "C:\\Users" not in seed
    assert "credential.helper" not in seed or "helper =" in seed
    assert "gh auth" not in seed
    assert "id_rsa" not in seed


def test_one_command_launcher_does_not_accept_raw_host_mounts() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "param(" in text
    assert "Mode" in text
    assert "W:\\hermes-dev\\workspace\\hermes-agent" in text
    assert "W:\\hermes-dev\\workspace\\EU-PP-Database" in text
    assert "-RepoA" not in text
    assert "-Mount" not in text
    assert "C:\\Users\\User" not in text
    assert "docker.sock" not in text
    assert "Linux containers required" in text


def test_compose_keeps_the_security_boundary() -> None:
    text = (CONTAINER_DIR / "compose.yaml").read_text(encoding="utf-8")
    assert "r5-developer-hermes:dx-v1" in text
    assert PINNED_DIGEST in (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "privileged: false" in text
    assert "network_mode: bridge" in text
    assert "pid: host" not in text
    assert "env_file:" not in text
    assert "/var/run/docker.sock" not in text
    assert "C:/Users" not in text
    assert "W:/Workbench" not in text
    assert "source: r5-developer-hermes-home" in text
    assert "target: /opt/data" in text
    assert text.count("type: bind") == 2
    assert "user: \"0:0\"" in text
    assert "HERMES_WRITE_SAFE_ROOT: /workspace:/opt/data" in text


def test_versioned_skill_is_safe_and_not_powerunits() -> None:
    skill = (CONTAINER_DIR / "skills" / "r5-dev-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: r5-dev-skill" in skill
    assert "PowerUnits production" in skill or "not a" in skill.lower()
    assert "RAILWAY" not in skill
    assert "DATABASE_URL" not in skill


def test_dx_files_add_no_hermes_core() -> None:
    hermes_core = REPO_ROOT / "model_tools.py"
    assert hermes_core.is_file()
    names = {path.name for path in CONTAINER_DIR.iterdir()}
    assert "launch.py" in names
    assert "Dockerfile" in names
    assert "launch-developer-hermes.ps1" in names
    assert (CONTAINER_DIR / "dx_probe.py").is_file()
    assert (CONTAINER_DIR / "seed_home.py").is_file()
