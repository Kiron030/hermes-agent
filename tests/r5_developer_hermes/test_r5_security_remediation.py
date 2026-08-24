"""Targeted regressions for the independent R5 red-team findings."""

from __future__ import annotations

import inspect
import json
import ntpath
import os
from pathlib import PureWindowsPath

import pytest

from r5_developer_hermes.container.contract import (
    BIND_MOUNTS,
    BOT_MODE_CONTAINER_COMPATIBILITY,
    CANONICAL_LAUNCH_CONTRACT,
    COMPOSE_FILE_ROLE,
    DEVELOPER_HERMES_CONTROLLER,
    DEVELOPER_RUNTIME_SOURCE,
    DESKTOP_CONTAINER_COMPATIBILITY,
    DUPLICATE_MODEL_KEY_POLICY,
    GENERIC_FINAL_TOOLSET_CAP_ACTIVE,
    GIT_HOOKS_POSTURE,
    HERMES_HOME_VOLUME,
    HERMES_HOME_VOLUME_LITERAL,
    HERMES_WRITE_SAFE_ROOT_ROLE,
    LINUX_CAPABILITY_HARDENING,
    LITERAL_APPROVED_BIND_SOURCES,
    PYTEST_PIN,
    R5_F06_STATUS,
    REPO_A_CONTAINER,
    REPO_A_REPO_B_SAME_TRUST_DOMAIN,
    REPO_B_CONTAINER,
    TYPESCRIPT_PIN,
    assert_trusted_host_launcher,
    bind_sources_match_literal_allowlist,
    canonicalize_bind_source,
    classify_inspect_mounts,
    docker_run_argv,
    is_approved_bind_source,
    is_forbidden_host_source,
    is_under_dedicated_clone_root,
    literal_approved_bind_source_set,
    sanitize_container_inspect,
)
from r5_developer_hermes.container.launch import reset_home
from r5_developer_hermes.harness import REPO_ROOT


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"
LAUNCHER = CONTAINER_DIR / "launch-developer-hermes.ps1"

# Independent of BIND_MOUNTS / HOST_WORKSPACE_ROOT. Do not derive these
# expected values from the contract object under test.
EXPECTED_BIND_A = r"W:\hermes-dev\workspace\hermes-agent"
EXPECTED_BIND_B = r"W:\hermes-dev\workspace\EU-PP-Database"


def test_developer_runtime_is_pinned_pure_upstream_not_operator_cap() -> None:
    assert DEVELOPER_HERMES_CONTROLLER == "PINNED_PURE_UPSTREAM"
    assert DEVELOPER_RUNTIME_SOURCE == "/opt/hermes"
    assert GENERIC_FINAL_TOOLSET_CAP_ACTIVE == "NO"
    assert HERMES_WRITE_SAFE_ROOT_ROLE == "DEFENSE_IN_DEPTH"
    assert REPO_A_REPO_B_SAME_TRUST_DOMAIN == "YES"
    # F06 was the open outbound-network policy decision. It is now resolved and
    # enforced by the egress broker, so the contract must no longer describe it
    # as pending.
    assert R5_F06_STATUS == "ENFORCED_EGRESS_POLICY"
    assert DESKTOP_CONTAINER_COMPATIBILITY == "NEEDS_REMEDIATION"
    assert BOT_MODE_CONTAINER_COMPATIBILITY == "NEEDS_REMEDIATION"
    assert GIT_HOOKS_POSTURE == "CONTAINED_CODE_EXECUTION"
    assert LINUX_CAPABILITY_HARDENING == "DEFERRED_WITH_RATIONALE"
    doc = (REPO_ROOT / "docs" / "architecture" / "hermes_r5_developer_hermes_v1.md").read_text(
        encoding="utf-8"
    )
    assert "DEVELOPER_HERMES_CONTROLLER" in doc and "PINNED_PURE_UPSTREAM" in doc
    assert "GENERIC_FINAL_TOOLSET_CAP_ACTIVE" in doc
    assert "REPO_A_REPO_B_SAME_TRUST_DOMAIN" in doc
    assert "R5_F06_STATUS" in doc and "ENFORCED_EGRESS_POLICY" in doc


def test_bind_mounts_equal_literal_independent_allowlist() -> None:
    assert LITERAL_APPROVED_BIND_SOURCES == (EXPECTED_BIND_A, EXPECTED_BIND_B)
    assert tuple(source for source, _dst in BIND_MOUNTS) == (EXPECTED_BIND_A, EXPECTED_BIND_B)
    assert [dst for _src, dst in BIND_MOUNTS] == [REPO_A_CONTAINER, REPO_B_CONTAINER]
    argv = docker_run_argv()
    assert f"type=bind,src={EXPECTED_BIND_A},dst={REPO_A_CONTAINER}" in argv
    assert f"type=bind,src={EXPECTED_BIND_B},dst={REPO_B_CONTAINER}" in argv


def test_docker_desktop_bind_sources_normalize_to_literal_allowlist() -> None:
    approved = literal_approved_bind_source_set()
    equivalents_a = (
        EXPECTED_BIND_A,
        r"W:/hermes-dev/workspace/hermes-agent",
        "/run/desktop/mnt/host/w/hermes-dev/workspace/hermes-agent",
        "/host_mnt/w/hermes-dev/workspace/hermes-agent",
        "/mnt/host/w/hermes-dev/workspace/hermes-agent",
        "/mnt/w/hermes-dev/workspace/hermes-agent",
    )
    equivalents_b = (
        EXPECTED_BIND_B,
        "/run/desktop/mnt/host/w/hermes-dev/workspace/EU-PP-Database",
        "/host_mnt/w/hermes-dev/workspace/EU-PP-Database",
        "/mnt/host/w/hermes-dev/workspace/EU-PP-Database",
    )
    for source in equivalents_a:
        assert canonicalize_bind_source(source) == "w:/hermes-dev/workspace/hermes-agent"
        assert is_approved_bind_source(source) is True
        assert is_forbidden_host_source(source) is False
    for source in equivalents_b:
        assert canonicalize_bind_source(source) == "w:/hermes-dev/workspace/eu-pp-database"
        assert is_approved_bind_source(source) is True
    assert approved == {
        "w:/hermes-dev/workspace/hermes-agent",
        "w:/hermes-dev/workspace/eu-pp-database",
    }


def test_live_docker_desktop_inspect_sources_match_literal_allowlist() -> None:
    """Exact bind Source strings observed on this host via docker inspect Mounts."""
    live = classify_inspect_mounts(
        [
            {
                "type": "volume",
                "name": "r5-developer-hermes-home",
                "source": "/var/lib/docker/volumes/r5-developer-hermes-home/_data",
                "destination": "/opt/data",
                "rw": True,
            },
            {
                "type": "bind",
                "source": "/run/desktop/mnt/host/w/hermes-dev/workspace/hermes-agent",
                "destination": REPO_A_CONTAINER,
                "rw": True,
            },
            {
                "type": "bind",
                "source": "/run/desktop/mnt/host/w/hermes-dev/workspace/EU-PP-Database",
                "destination": REPO_B_CONTAINER,
                "rw": True,
            },
        ]
    )
    assert live["exact_allowlist_match"] is True
    assert live["exact_two_approved_rw"] is True
    assert live["forbidden_sources"] == []
    assert live["HOST_C_MOUNTED"] == "NO"
    assert live["HOST_D_MOUNTED"] == "NO"
    assert live["HOST_W_MOUNTED"] == "NO"
    assert live["HOST_W_WHOLE_MOUNTED"] == "NO"
    assert live["HERMES_HOME_VOLUME_PRESENT"] == "YES"


def test_positive_allowlist_rejects_parent_sibling_and_credentials() -> None:
    rejected = (
        r"W:\hermes-dev",
        r"W:\hermes-dev\credentials",
        r"W:\hermes-dev\credentials\developer-hermes-model.env",
        r"C:\ProgramData",
        r"C:\Users",
        r"C:\Users\User",
        "W:\\",
        "D:\\",
        "C:\\",
        r"W:\Workbench",
        r"W:\hermes-dev\workspace\hermes-agent\scripts",
        "/run/desktop/mnt/host/w",
        "/run/desktop/mnt/host/w/hermes-dev",
        "/run/desktop/mnt/host/w/hermes-dev/credentials",
        "/run/desktop/mnt/host/c/Users/User",
        "/host_mnt/c/Users/User/.powerunits/secrets",
        "/mnt/host/w/Workbench",
        "/var/run/docker.sock",
    )
    for source in rejected:
        assert is_approved_bind_source(source) is False, source
        assert is_forbidden_host_source(source) is True, source


def test_redteam_w3_host_workspace_root_mutation_fails() -> None:
    """Mutating the workspace root to W:\\hermes-dev must not stay green."""
    mutated_from_root = (
        r"W:\hermes-dev\hermes-agent",
        r"W:\hermes-dev\EU-PP-Database",
    )
    parent_and_credentials = (
        r"W:\hermes-dev",
        r"W:\hermes-dev\credentials",
    )
    docker_desktop_parent = (
        "/run/desktop/mnt/host/w/hermes-dev",
        "/run/desktop/mnt/host/w/hermes-dev/credentials",
    )
    assert bind_sources_match_literal_allowlist(mutated_from_root) is False
    assert bind_sources_match_literal_allowlist(parent_and_credentials) is False
    assert bind_sources_match_literal_allowlist(docker_desktop_parent) is False
    poisoned = classify_inspect_mounts(
        [
            {
                "type": "bind",
                "source": r"W:\hermes-dev",
                "destination": REPO_A_CONTAINER,
                "rw": True,
            },
            {
                "type": "bind",
                "source": r"W:\hermes-dev\workspace\EU-PP-Database",
                "destination": REPO_B_CONTAINER,
                "rw": True,
            },
            {
                "type": "volume",
                "source": "/var/lib/docker/volumes/r5-developer-hermes-home/_data",
                "destination": "/opt/data",
                "name": "r5-developer-hermes-home",
                "rw": True,
            },
        ]
    )
    assert poisoned["exact_allowlist_match"] is False
    assert poisoned["exact_two_approved_rw"] is False
    assert poisoned["HOST_W_MOUNTED"] == "YES"
    assert poisoned["forbidden_sources"]


def test_classifier_rejects_docker_desktop_user_profile_substitution() -> None:
    result = classify_inspect_mounts(
        [
            {
                "type": "bind",
                "source": "/run/desktop/mnt/host/c/Users/User",
                "destination": REPO_A_CONTAINER,
                "rw": True,
            },
            {
                "type": "bind",
                "source": "/host_mnt/c",
                "destination": REPO_B_CONTAINER,
                "rw": True,
            },
            {
                "type": "volume",
                "name": "r5-developer-hermes-home",
                "destination": "/opt/data",
                "rw": True,
            },
        ]
    )
    assert result["exact_allowlist_match"] is False
    assert result["HOST_C_MOUNTED"] == "YES"
    assert result["forbidden_sources"]


def test_host_launcher_from_dedicated_clone_is_denied() -> None:
    clone_script = r"W:\hermes-dev\workspace\hermes-agent\scripts\r5_developer_hermes\container\launch.py"
    clone_root = r"W:\hermes-dev\workspace\hermes-agent"
    relative_escape = r"W:\Workbench\hermes-agent\..\..\hermes-dev\workspace\hermes-agent\scripts\r5_developer_hermes\container\launch.py"
    # Linux pathlib does not collapse Windows-backslash "..". Express the
    # intended host path with deterministic Windows canonicalization so the
    # same denial holds on Linux CI and native Windows.
    windows_canonical_escape = str(PureWindowsPath(ntpath.normpath(relative_escape)))
    assert windows_canonical_escape.replace("/", "\\").casefold() == clone_script.casefold()
    assert is_under_dedicated_clone_root(clone_script) is True
    assert is_under_dedicated_clone_root(clone_root) is True
    assert is_under_dedicated_clone_root(windows_canonical_escape) is True
    if os.name == "nt":
        assert is_under_dedicated_clone_root(relative_escape) is True
    assert is_under_dedicated_clone_root(r"W:\Workbench\hermes-agent") is False
    with pytest.raises(RuntimeError, match="HOST_LAUNCHER_FROM_CONTAINER_CLONE"):
        assert_trusted_host_launcher(clone_script, clone_root)
    assert_trusted_host_launcher(
        CONTAINER_DIR / "launch.py",
        REPO_ROOT,
    )
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "Get-R5CanonicalPath" in text
    assert "Test-R5PathIsDedicatedClone" in text
    assert "W:\\hermes-dev" in text
    assert "HOST_LAUNCHER_FROM_CONTAINER_CLONE" in text


def test_hermes_home_reset_is_fixed_volume_only() -> None:
    assert HERMES_HOME_VOLUME == "r5-developer-hermes-home"
    assert HERMES_HOME_VOLUME_LITERAL == "r5-developer-hermes-home"
    signature = inspect.signature(reset_home)
    assert "volume" not in signature.parameters
    launch_py = (CONTAINER_DIR / "launch.py").read_text(encoding="utf-8")
    assert '"reset"' in launch_py or "'reset'" in launch_py
    assert '["volume", "rm", HERMES_HOME_VOLUME_LITERAL]' in launch_py
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "SupportsShouldProcess" in launcher
    assert "RESET_DEVELOPER_HERMES_HOME" in launcher
    assert "r5-developer-hermes-home" in launcher
    assert "-Volume" not in launcher


def test_inspect_omits_synthetic_secret_values() -> None:
    canary = "R5_SYNTHETIC_CANARY_SECRET_9f3a7c1e_do_not_leak"
    payload = {
        "Id": "abc123",
        "Image": "sha256:deadbeef",
        "Config": {
            "Image": "r5-developer-hermes:dx-v1",
            "User": "0:0",
            "Env": [
                f"OPENAI_API_KEY={canary}",
                "HERMES_HOME=/opt/data",
                f"ANTHROPIC_API_KEY={canary}-two",
            ],
            "WorkingDir": "/workspace",
        },
        "HostConfig": {
            "Privileged": False,
            "PidMode": "",
            "NetworkMode": "bridge",
            "Runtime": "",
        },
        "Mounts": [
            {
                "Source": EXPECTED_BIND_A,
                "Destination": REPO_A_CONTAINER,
                "RW": True,
                "Type": "bind",
            }
        ],
    }
    sanitized = sanitize_container_inspect(payload)
    dumped = json.dumps(sanitized)
    assert canary not in dumped
    assert f"{canary}-two" not in dumped
    assert "env" not in sanitized
    assert sanitized["env_names"] == [
        "ANTHROPIC_API_KEY",
        "HERMES_HOME",
        "OPENAI_API_KEY",
    ]
    launch_py = (CONTAINER_DIR / "launch.py").read_text(encoding="utf-8")
    assert "sanitize_container_inspect" in launch_py
    assert 'config.get("Env")' not in launch_py


def test_typescript_and_pytest_are_pinned_at_image_build() -> None:
    assert TYPESCRIPT_PIN == "7.0.2"
    assert PYTEST_PIN == "9.1.1"
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert f"typescript@{TYPESCRIPT_PIN}" in dockerfile
    assert f"pytest=={PYTEST_PIN}" in dockerfile
    assert "uvx --from pytest" not in dockerfile
    assert "npm install -g typescript \\" not in dockerfile
    probe = (CONTAINER_DIR / "isolation_probe.py").read_text(encoding="utf-8")
    assert "uvx --from pytest" not in probe


def test_canonical_launch_path_is_docker_run_argv() -> None:
    assert CANONICAL_LAUNCH_CONTRACT == "docker_run_argv"
    assert COMPOSE_FILE_ROLE == "NON_AUTHORITATIVE_EXAMPLE"
    assert DUPLICATE_MODEL_KEY_POLICY == "REJECT"
    compose = (CONTAINER_DIR / "compose.yaml").read_text(encoding="utf-8")
    assert "NON-AUTHORITATIVE EXAMPLE ONLY" in compose
    argv = docker_run_argv()
    assert argv[0:3] == ["docker", "run", "--detach"]


def test_trust_domain_and_git_hooks_are_documented() -> None:
    readme = (CONTAINER_DIR / "README.md").read_text(encoding="utf-8")
    assert "DEDICATED_CONTAINER_CLONES" in readme and "DO_NOT_EXECUTE_ON_HOST" in readme
    assert "GIT_HOOKS" in readme and "CONTAINED_CODE_EXECUTION" in readme
    assert "RESET_DEVELOPER_HERMES_HOME" in readme
    assert "REPO_A_REPO_B_SAME_TRUST_DOMAIN" in readme
