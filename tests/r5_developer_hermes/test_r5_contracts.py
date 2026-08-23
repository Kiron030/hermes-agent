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
        "bootstrap-host-secrets.ps1",
        "run-with-host-secrets.ps1",
        "scope-workspace-authority.ps1",
        "rollback-workspace-authority.ps1",
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


def test_host_secret_root_is_derived_not_hardcoded() -> None:
    """A hardcoded username would break on any other host and leak this one."""
    for name in ("bootstrap-host-secrets.ps1", "run-with-host-secrets.ps1"):
        code = _powershell_code(PRINCIPAL_SCRIPTS / name)
        assert "$env:USERPROFILE" in code, name
        assert ".powerunits\\secrets" in code, name
        assert "C:\\Users\\" not in code, name


def test_secret_relocation_never_links_back_into_the_workspace() -> None:
    """A link at the old path restores the reachability relocation removes."""
    forbidden = ("SymbolicLink", "HardLink", "Junction", "mklink", "New-Symlink")
    for script in PRINCIPAL_SCRIPTS.glob("*.ps1"):
        code = _powershell_code(script)
        for marker in forbidden:
            assert f"New-Item -ItemType {marker}" not in code, (script.name, marker)
            assert f"mklink /{marker[0]}" not in code, (script.name, marker)
        assert "mklink" not in code.lower(), script.name


def test_relocation_moves_and_never_copies_secrets() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "bootstrap-host-secrets.ps1")
    assert "Move-Item" in code
    assert "Copy-Item" not in code
    # A git-tracked secret needs rotation, so relocation must refuse to move it.
    assert "ORIGIN_IS_GIT_TRACKED" in code
    # And it must refuse a root that the dedicated principal can reach.
    assert "Refusing to place the secret root inside workspace root" in code


def test_host_launcher_injects_without_persisting_or_printing_values() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "run-with-host-secrets.ps1")
    # Injection into this process only.
    assert 'Set-Item -LiteralPath "Env:$key"' in code
    # Nothing is written back to disk: no file-writing cmdlet at all.
    for writer in ("Out-File", "Set-Content", "Add-Content", "Copy-Item", "Export-Csv"):
        assert writer not in code, writer
    # The dedicated principal does not gain this authority by reading the source.
    assert "Refusing to run as" in code


def test_provisioning_refuses_to_grant_the_host_secret_root() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "provision-principal.ps1")
    assert "HostSecretRoot" in code
    assert "host_secret_root_granted = $false" in code
    assert "toolchain_acls_changed = $false" in code
    # Toolchain rights are verified, never widened.
    assert "does not widen toolchain ACLs" in code


def test_secret_relocation_plan_is_documented() -> None:
    doc = REPO_ROOT / "docs" / "architecture" / "hermes_r5_secret_relocation_v1.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    for marker in (
        "HOST_ONLY_SECRET_ROOT = %USERPROFILE%\\.powerunits\\secrets\\",
        "LEGACY_DB_GITHUB_SECRET_NAMES = none",
        "LEGACY_DB_RAILWAY_SERVICE = HUMAN_CONFIRMATION_REQUIRED",
        "Runbook (human execution)",
    ):
        assert marker in text, marker


def test_secret_relocation_doc_carries_no_secret_values() -> None:
    doc = REPO_ROOT / "docs" / "architecture" / "hermes_r5_secret_relocation_v1.md"
    text = doc.read_text(encoding="utf-8").lower()
    for needle in ("postgres://", "postgresql://", "sk-", "sk.ey", "ghp_", "pk.ey"):
        assert needle not in text, needle


def test_authority_scoping_never_removes_an_existing_ace() -> None:
    """The broad Authenticated Users grant is the host user's only write path."""
    code = _powershell_code(PRINCIPAL_SCRIPTS / "scope-workspace-authority.ps1")
    assert "RemoveAccessRule" not in code
    assert "PurgeAccessRules" not in code
    assert "existing_ace_removed  = $false" in code
    assert "broad_ace_modified    = $false" in code


def test_authority_scoping_backs_up_every_dacl_before_mutating() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "scope-workspace-authority.ps1")
    backup_at = code.index("r5.acl_backup.v1")
    first_mutation = min(code.index("Set-Acl"), code.index("New-Item -ItemType Directory -Force -Path $ScopedWorkspaceRoot"))
    assert backup_at < first_mutation, "the ACL backup must be captured before any mutation"
    assert "IsInRole" in code, "ACL mutation demands an elevated session"


def test_authority_scoping_denies_write_but_never_read() -> None:
    """Denying read would break machine-wide tools and traversal."""
    code = _powershell_code(PRINCIPAL_SCRIPTS / "scope-workspace-authority.ps1")
    assert "read_access_denied    = $false" in code
    deny_block = code[code.index("$WRITE_DENY_RIGHTS ="):code.index("function Test-HasWriteDeny")]
    for right in ("Write", "Delete", "ChangePermissions", "TakeOwnership"):
        assert right in deny_block, right
    for right in ("FullControl", "ReadData", "ReadAndExecute"):
        assert right not in deny_block, right


def test_authority_scoping_refuses_to_protect_a_pre_existing_directory() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "scope-workspace-authority.ps1")
    assert "AreAccessRulesProtected" in code
    assert "it already exists with an inheriting DACL" in code
    # The scoped grant only survives the volume deny if inheritance is dropped.
    assert "SetAccessRuleProtection($true, $false)" in code


def test_rollback_restores_only_the_dacl_and_deletes_nothing() -> None:
    path = PRINCIPAL_SCRIPTS / "rollback-workspace-authority.ps1"
    assert path.is_file()
    code = _powershell_code(path)
    assert "SetSecurityDescriptorSddlForm($entry.sddl, 'Access')" in code
    assert "Mandatory = $true" in code, "a rollback without a backup would be a guess"
    assert "refusing to guess a prior ACL" in code
    for line in code.splitlines():
        if "Remove-Item" in line:
            assert line.strip().startswith("Write-Host"), line


def test_broad_volume_write_authority_is_a_preflight_blocker() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "preflight-principal.ps1")
    assert "OTHER_WRITE_AUTHORITY_NOT_PROVEN" in code
    assert "OTHER_WRITE_AUTHORITY_PRESENT" in code
    # Explicit workspace ACLs must not be mistaken for a boundary.
    assert "WORKSPACE_GRANT_DEFEATED_BY_INHERITED_DENY" in code


def test_every_required_preflight_gate_is_load_bearing() -> None:
    """A gate that is reported but not asserted would let READY lie."""
    code = _powershell_code(PRINCIPAL_SCRIPTS / "preflight-principal.ps1")
    start = code.index("$gatesPassed = (")
    gate_expression = code[start:code.index("$report = [ordered]", start)]
    for gate in (
        "ACTIVE_WORKSPACE_SECRET_FILES",
        "UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY",
        "HOST_ONLY_SECRET_ROOT_REACHABLE_BY_HERMES_DEV",
        "OTHER_WRITE_AUTHORITY",
        "REPO_A_RW_DESIGN",
        "REPO_B_RW_DESIGN",
        "HOST_PROFILE_READ_DESIGN",
        "R5_MINIMUM_TOOLCHAIN",
    ):
        assert gate in gate_expression, gate
    assert "$blockers.Count -eq 0 -and $gatesPassed" in code


def test_preflight_classifies_history_secrets_instead_of_blanket_blocking() -> None:
    code = _powershell_code(PRINCIPAL_SCRIPTS / "preflight-principal.ps1")
    assert "retired_authority.py" in code
    # The old blanket blockers are gone, replaced by classified verdicts.
    assert "SECRETS_IN_GIT_HISTORY" not in code
    assert "SECRETS_INSIDE_APPROVED_WORKSPACE" not in code
    # A classification covering fewer findings than were scanned must not read
    # as clean, and an unavailable classifier must not either.
    assert "SECRET_CLASSIFICATION_INCOMPLETE" in code
    assert "UNAVAILABLE_FAILED_CLOSED" in code


def test_no_script_offers_a_wholesale_history_secret_exemption() -> None:
    for script in PRINCIPAL_SCRIPTS.glob("*.ps1"):
        lowered = _powershell_code(script).lower()
        for escape in ("ignore_git_history", "skip_history_secrets", "allow_history_secrets"):
            assert escape not in lowered, (script.name, escape)


def test_developer_capability_is_accounted_for_not_silently_dropped() -> None:
    preflight = _powershell_code(PRINCIPAL_SCRIPTS / "preflight-principal.ps1")
    verify = _powershell_code(PRINCIPAL_SCRIPTS / "verify-principal-isolation.ps1")

    # uv is required (prepare-runtime runs `uv sync --frozen`), node/npm are not.
    assert "R5_MINIMUM_TOOLCHAIN_NOT_SYSTEM_WIDE" in preflight
    assert "POST_R5_DX_TOOL_NOT_SYSTEM_WIDE" in preflight
    # Reaching the host copy by opening the profile is explicitly not the fix.
    assert "do NOT open the host profile" in preflight
    assert "R5_MINIMUM_TOOLCHAIN_MISSING" in verify


def test_phase_c_proves_write_isolation_by_attempting_a_write() -> None:
    """An ACL read states intent; only a failed write proves the boundary."""
    code = _powershell_code(PRINCIPAL_SCRIPTS / "verify-principal-isolation.ps1")
    assert "function Test-CanWrite" in code
    assert "OTHER_WRITE_AUTHORITY_PRESENT" in code
    assert "$otherWriteAuthority -eq 'NO' -and" in code, "the probe must gate acceptance"


def test_workspace_authority_design_is_documented() -> None:
    doc = REPO_ROOT / "docs" / "architecture" / "hermes_r5_workspace_authority_v1.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    for marker in (
        "RECOMMENDED_WORKSPACE_AUTHORITY_DESIGN = DEDICATED_SCOPED_WORKSPACE",
        "W_VOLUME_ROOT_BROAD_MODIFY = YES",
        "HUMAN_RUNBOOK",
        "ROLLBACK_RUNBOOK",
        "CURRENT_PGURL_CLASSIFICATION",
        "HISTORICAL_PGURL_CLASSIFICATION",
    ):
        assert marker in text, marker


def test_workspace_authority_doc_carries_no_secret_values() -> None:
    doc = REPO_ROOT / "docs" / "architecture" / "hermes_r5_workspace_authority_v1.md"
    text = doc.read_text(encoding="utf-8").lower()
    for needle in ("postgres://", "postgresql://", "sk-", "ghp_", "password ="):
        assert needle not in text, needle


def test_r1_decision_docs_remain_tracked() -> None:
    report = REPO_ROOT / "docs" / "architecture" / "hermes_r1_proof_report_v1.md"
    assert report.is_file()
    assert "GATE_1_STATUS = CLOSED" in report.read_text(encoding="utf-8")
