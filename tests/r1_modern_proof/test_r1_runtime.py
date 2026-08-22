"""Runtime proofs against the prepared upstream worktree + venv."""

from __future__ import annotations

from pathlib import Path

import pytest

from r1_modern_hermes_proof.harness import (
    boot_smoke,
    capability_inventory,
    capability_probes,
    clamp_operator,
    enumerate_tools,
    inspect_lazy_install,
    isolated_env,
    load_pin,
    operator_home,
    upstream_src,
    write_proof_homes,
)


def _venv_ready() -> bool:
    src = upstream_src()
    return (src / ".venv" / "Scripts" / "python.exe").exists() or (
        src / ".venv" / "bin" / "python"
    ).exists()


pytestmark = pytest.mark.skipif(
    not _venv_ready(),
    reason="run harness prepare-source and frozen-install first",
)


def test_boot_smoke_and_authority_absence() -> None:
    result = boot_smoke()
    assert result["pass"] is True
    assert result["LISTEN_ADDRESS"] == "none"
    assert result["PUBLIC_INGRESS"] == "NO"
    assert result["production_credential_assertions"]["pass"] is True


def test_tool_surface_is_inspectable() -> None:
    result = enumerate_tools("operator")
    assert result["inspectable"] is True
    assert isinstance(result["callable_tools"], list)
    assert "memory" in result["callable_tools"] or "todo" in result["callable_tools"]
    forbidden = {"terminal", "process", "read_file", "delegate_task", "session_search"}
    assert forbidden.isdisjoint(result["callable_tools"])


def test_operator_clamp_answers_equivalence() -> None:
    result = clamp_operator()
    assert result["CLAMP_EQUIVALENCE"] in {"CONFIG_SUFFICIENT", "PATCH_REQUIRED"}
    names = {case["name"]: case for case in result["cases"]}
    assert "terminal" not in names["normal_allowed_set"]["forbidden_present"]
    assert "terminal" not in names["disabled_family_terminal"]["forbidden_present"]
    assert "terminal" not in names["unknown_toolset_does_not_widen"]["forbidden_present"]
    explicit = names["explicit_caller_requests_terminal"]
    if result["CLAMP_EQUIVALENCE"] == "CONFIG_SUFFICIENT":
        assert "terminal" not in explicit["forbidden_present"]
    else:
        assert result["PATCH_SEAM_IF_REQUIRED"]
        assert result["caller_can_restore_forbidden_tool"] or not result[
            "oneshot_passes_disabled_toolsets"
        ]


def test_lazy_install_is_absent_or_disabled_on_startup() -> None:
    result = inspect_lazy_install()
    assert result["RUNTIME_LAZY_INSTALL"] == "ABSENT_OR_DISABLED"
    assert result["startup_direct_ensure_hits"] == []


def test_capability_inventory_records_upstream_names() -> None:
    inventory = capability_inventory()
    assert inventory["filesystem_read"].startswith("file")
    assert inventory["terminal_command_execution"].startswith("terminal")
    assert inventory["skills"].startswith("skills")
    assert inventory["delegation_subagents"].startswith("delegation")


def test_benign_capability_probes_operate_on_scratch() -> None:
    result = capability_probes()
    assert result["CAPABILITY_PROBE_1_WORKSPACE"] == "PASS"
    assert result["CAPABILITY_PROBE_2_TERMINAL_TEST_LOOP"] == "PASS"
    assert result["CAPABILITY_PROBE_3_MODERN_PRIMITIVE"] == "PASS"


def test_operator_and_developer_homes_differ() -> None:
    homes = write_proof_homes()
    op = Path(homes["operator"]) / "config.yaml"
    dev = Path(homes["developer"]) / "config.yaml"
    assert op.read_text(encoding="utf-8") != dev.read_text(encoding="utf-8")
    assert "disabled_toolsets:" in op.read_text(encoding="utf-8")
    env = isolated_env(operator_home(), extra={"HERMES_R1_CONTEXT": "operator"})
    pin = load_pin()
    assert all(not env.get(name) for name in pin["production_authority_names"])
