"""Runtime proofs against the prepared modern developer instance."""

from __future__ import annotations

from pathlib import Path

import pytest

from r5_developer_hermes.harness import (
    authority_proof,
    boot_smoke,
    capability_inventory,
    deletion_has_zero_production_effect,
    developer_probes,
    enumerate_tools,
    isolated_env,
    sqlite_probe,
    upstream_src,
    write_developer_home,
)


def _venv_ready() -> bool:
    src = upstream_src()
    return (src / ".venv" / "Scripts" / "python.exe").exists() or (
        src / ".venv" / "bin" / "python"
    ).exists()


pytestmark = pytest.mark.skipif(
    not _venv_ready(),
    reason="run harness prepare-runtime first",
)


def test_boot_smoke_and_authority_absence() -> None:
    result = boot_smoke()
    assert result["pass"] is True
    assert result["LISTEN_ADDRESS"] == "none"
    assert result["PUBLIC_INGRESS"] == "NO"
    assert result["production_credential_assertions"]["pass"] is True


def test_developer_surface_is_powerful_not_operator_clamped() -> None:
    result = enumerate_tools()
    names = set(result["callable_tools"])
    assert {"read_file", "write_file", "terminal", "skills_list", "skill_view"} <= names
    assert "execute_powerunits_option_d_bounded_slice" not in names
    assert "inspect_powerunits_country_coverage_v1" not in names
    assert result["has_operator_execute"] is False


def test_developer_probes_use_hermes_dispatch() -> None:
    result = developer_probes()
    assert result["dispatch_path"] == "model_tools.handle_function_call"
    assert result["ordinary_workspace_approvals"] == 0
    assert result["PROBE_A_CODE_EXPLORATION"] == "PASS"
    assert result["PROBE_B_EDIT"] == "PASS"
    assert result["PROBE_C_TEST_LOOP"] == "PASS"
    assert result["PROBE_D_GIT"] == "PASS"
    assert result["PROBE_E_SKILLS"] == "PASS"
    assert result["PROBE_F_WEB"] in {"PASS", "NOT_RUN_CREDENTIAL_REQUIRED"}
    assert result["could_edit"] is True
    assert result["could_run_tests"] is True
    assert result["could_inspect_diff"] is True
    assert result["tool_call_count"] >= 8
    assert result["production_execute_dispatch"]["unreachable"] is True


def test_production_authority_is_not_claimed_without_principal_proof() -> None:
    """Environment hygiene is real; it is just not the same thing as authority.

    The independent review overturned the original assertion here, which read
    ``PRODUCTION_DEPLOY_REACHABLE is False`` off an environment scan while a
    file-backed Railway session remained reachable by absolute path. Deploy and
    secret-file reachability are now sourced from the OS-principal proof and
    default to unproven.
    """
    result = authority_proof()
    assert result["PRODUCTION_DB_CREDENTIAL_PRESENT"] is False
    assert result["POWERUNITS_EXECUTE_SECRET_PRESENT"] is False
    assert result["DEPLOYMENT_CREDENTIAL_PRESENT"] is False
    assert result["PRODUCTION_WRITE_REACHABLE"] is False
    assert result["modern_execute_unreachable"] is True
    assert result["fork_fail_closed"]["execute_check_fn"]["fail_closed"] is True
    assert result["PATH_STUB_SECURITY_ROLE"] == "NONE"

    if result["principal_evidence"] is None:
        assert result["PRODUCTION_DEPLOY_REACHABLE"] == "NOT_PROVEN"
        assert result["PRODUCTION_SECRET_FILES_REACHABLE"] == "NOT_PROVEN"
        assert result["pass"] is False
    else:
        assert result["pass"] is (
            result["PRODUCTION_DEPLOY_REACHABLE"] == "NO"
            and result["PRODUCTION_SECRET_FILES_REACHABLE"] == "NO"
        )


def test_sqlite_keeps_safe_delete_on_old_build() -> None:
    result = sqlite_probe()
    assert result["sqlite_version"]
    if tuple(int(part) for part in result["sqlite_version"].split(".")[:3]) < (3, 51, 3):
        assert result["SQLITE_RUNTIME_STATUS"] == "KNOWN_RUNTIME_DEPENDENCY_DEBT"
        assert result["SQLITE_WAL_MODE"] == "delete"
    else:
        assert result["SQLITE_RUNTIME_STATUS"] == "SAFE_WAL_AVAILABLE"


def test_inventory_does_not_treat_catalog_as_proof() -> None:
    inventory = capability_inventory()
    assert inventory["filesystem"] == "PROVEN_NOW"
    assert inventory["terminal"] == "PROVEN_NOW"
    assert inventory["git"] == "PROVEN_NOW"
    assert inventory["tests"] == "PROVEN_NOW"
    assert inventory["skills"] == "PROVEN_NOW"
    assert inventory["delegation"] == "DEFERRED"
    assert inventory["browser"] == "DEFERRED"
    assert inventory["web"] in {"PROVEN_NOW", "AVAILABLE_NOT_YET_PROVEN"}


def test_deleting_developer_instance_cannot_touch_production() -> None:
    result = deletion_has_zero_production_effect()
    assert result["pass"] is True
    assert result["contains_production_secrets_file"] is False


def test_child_env_does_not_reabsorb_os_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_R5_PROOF_ROOT", str(tmp_path / "proof"))
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://prod/should-not-leak")
    home = write_developer_home()
    env = isolated_env(home)
    assert "DATABASE_URL_TIMESCALE" not in env
    assert env["HERMES_HOME"] == str(home)
