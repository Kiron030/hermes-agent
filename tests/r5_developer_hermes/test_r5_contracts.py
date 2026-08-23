"""R5 contracts: isolation, authority absence, developer policy."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from r5_developer_hermes.authority_failclosed import _resolve_real_cli
from r5_developer_hermes.harness import (
    DEPLOY_CLI_STUB_SECURITY_CONTROL,
    PIN_PATH,
    REPO_ROOT,
    SAFE_ENV_PASSTHROUGH,
    WEB_KEY_ENV,
    assert_authority_absent,
    blocked_names,
    isolated_env,
    isolation_boundary_status,
    load_pin,
    os_principal_status,
    production_authority_names,
    proof_root,
    write_developer_home,
)

PRINCIPAL_SCRIPTS = REPO_ROOT / "scripts" / "r5_developer_hermes" / "principal"


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
    assert pin["isolation_boundary"] == "DEDICATED_OS_PRINCIPAL"
    assert pin["isolation_boundary_rejected"] == "PROCESS_CONSTRUCTED_ENV"
    assert pin["path_stub_security_role"] == "NONE"


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


def test_isolation_boundary_fails_closed_without_principal_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_R5_PROOF_ROOT", str(tmp_path / "proof"))
    status = isolation_boundary_status()
    assert status["ISOLATION_BOUNDARY"] == "PROCESS_CONSTRUCTED_ENV"
    assert status["BOUNDARY_SUFFICIENT"] == "NO"
    assert status["principal_evidence_present"] is False
    assert status["container_used"] is False


def test_isolation_boundary_claims_principal_only_on_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proof"
    monkeypatch.setenv("HERMES_R5_PROOF_ROOT", str(root))
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    evidence = artifacts / "principal_isolation.json"

    evidence.write_text(
        json.dumps({"CHILD_OS_PRINCIPAL": "SEPARATE_PRINCIPAL", "ISOLATION_ACCEPTANCE": "FAIL"}),
        encoding="utf-8",
    )
    assert isolation_boundary_status()["BOUNDARY_SUFFICIENT"] == "NO"

    evidence.write_text(
        json.dumps({"CHILD_OS_PRINCIPAL": "SEPARATE_PRINCIPAL", "ISOLATION_ACCEPTANCE": "PASS"}),
        encoding="utf-8",
    )
    status = isolation_boundary_status()
    assert status["ISOLATION_BOUNDARY"] == "DEDICATED_OS_PRINCIPAL"
    assert status["BOUNDARY_SUFFICIENT"] == "YES"


def test_path_stubs_are_declared_non_security() -> None:
    assert DEPLOY_CLI_STUB_SECURITY_CONTROL is False
    assert isolation_boundary_status()["PATH_STUB_SECURITY_ROLE"] == "NONE"


def test_deploy_cli_resolution_skips_the_stub_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old proof measured its own stub; resolution must now look past it."""
    home = tmp_path / "process-home"
    stub_dir = home / "bin"
    stub_dir.mkdir(parents=True)
    (stub_dir / "railway.cmd").write_text("@echo off\r\nexit /b 1\r\n", encoding="utf-8")

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real_cli = real_dir / "railway.cmd"
    real_cli.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATHEXT", ".CMD")
    monkeypatch.setenv("PATH", os.pathsep.join([str(stub_dir), str(real_dir)]))

    resolved = _resolve_real_cli("railway")
    assert str(real_cli) in resolved
    assert not any(str(stub_dir) in candidate for candidate in resolved)


def test_os_principal_status_reports_an_identity() -> None:
    status = os_principal_status()
    assert status["principal_id"]
    assert "is_administrator" in status


def test_principal_provisioning_scripts_are_present() -> None:
    expected = (
        "preflight-principal.ps1",
        "provision-principal.ps1",
        "launch-developer-hermes.ps1",
        "verify-principal-isolation.ps1",
    )
    for name in expected:
        assert (PRINCIPAL_SCRIPTS / name).is_file(), name


def _powershell_code(path: Path) -> str:
    """Strip block and line comments so prohibitions are tested against code."""
    text = re.sub(r"<#.*?#>", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def test_provisioning_never_persists_credentials_or_touches_the_host_profile() -> None:
    provision = _powershell_code(PRINCIPAL_SCRIPTS / "provision-principal.ps1")
    launch = _powershell_code(PRINCIPAL_SCRIPTS / "launch-developer-hermes.ps1")

    # No cached credentials anywhere in the workflow.
    assert "/savecred" not in provision.lower()
    assert "/savecred" not in launch.lower()
    # Elevation is demanded, not assumed.
    assert "IsInRole" in provision
    # Additive ACL edits only: no protection flips, no removals, no purges.
    assert "AddAccessRule" in provision
    assert "SetAccessRuleProtection" not in provision
    assert "RemoveAccessRule" not in provision
    assert "PurgeAccessRules" not in provision
    # The host profile stays out of scope.
    assert "Refusing to operate on" in provision


def test_r1_decision_docs_remain_tracked() -> None:
    report = REPO_ROOT / "docs" / "architecture" / "hermes_r1_proof_report_v1.md"
    assert report.is_file()
    assert "GATE_1_STATUS = CLOSED" in report.read_text(encoding="utf-8")
