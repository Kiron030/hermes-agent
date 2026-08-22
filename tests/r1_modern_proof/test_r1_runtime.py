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
    probe_model_smoke_auth_path,
    probe_model_smoke_reasoning_kwargs,
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
    assert result["CLAMP_EQUIVALENCE"] == "PATCH_REQUIRED"
    assert result["CONFIG_ONLY"] == "INSUFFICIENT"
    assert result["CORE_PATCH_NEEDED"] == "YES"
    assert result["CLAMP_IMPLEMENTATION_CLASS"] == "THIN_CORE_PATCH"
    assert result["FUTURE_CORE_PATCH_IMPLEMENTED"] == "NO"
    names = {case["name"]: case for case in result["cases"]}
    assert "terminal" not in names["normal_allowed_set"]["forbidden_present"]
    assert "terminal" not in names["disabled_family_terminal"]["forbidden_present"]
    assert "terminal" not in names["unknown_toolset_does_not_widen"]["forbidden_present"]
    explicit = names["explicit_caller_requests_terminal"]
    assert result["PATCH_SEAM_IF_REQUIRED"]
    assert result["CALLER_BYPASS"] == "VERIFIED"
    assert result["caller_can_restore_forbidden_tool"] is True
    assert "terminal" in explicit["forbidden_present"] or "process" in explicit["forbidden_present"]


def test_toolsets_all_bypasses_operator_allowlist() -> None:
    result = clamp_operator()
    bypass = result["TOOLSETS_ALL_BYPASS"]
    assert bypass["resolved_enabled"] is None
    assert bypass["pass"] is True
    restored = set(bypass["restored_high_authority"])
    assert {"write_file", "delegate_task", "session_search"} <= restored


def test_plugin_allowlist_self_expansion() -> None:
    result = clamp_operator()
    expansion = result["PLUGIN_SELF_EXPANSION"]
    assert "r1_undeclared_plugin" not in expansion["declared"]
    assert expansion["undeclared_plugin_present"] is True


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


def test_benign_capability_probes_use_hermes_dispatch() -> None:
    result = capability_probes()
    assert result["dispatch_path"] == "model_tools.handle_function_call"
    assert result["CAPABILITY_PROBE_1_WORKSPACE"] == "PASS"
    assert result["CAPABILITY_PROBE_2_TERMINAL_TEST_LOOP"] == "PASS"
    assert result["CAPABILITY_PROBE_3_MODERN_PRIMITIVE"] == "PASS"
    assert result["filesystem"]["pass"] is True
    assert result["terminal"]["pass"] is True
    assert result["skills"]["pass"] is True
    assert result["CAPABILITY_TOOL_DISPATCH"]["FILESYSTEM"] == "PASS"
    assert result["CAPABILITY_TOOL_DISPATCH"]["TERMINAL"] == "PASS"
    assert result["CAPABILITY_TOOL_DISPATCH"]["SKILLS"] == "PASS"


def test_model_smoke_sentinel_reaches_openai_api_request_path() -> None:
    result = probe_model_smoke_auth_path("r1-sentinel-not-a-real-secret")
    assert result["provider"] == "openai-api"
    assert result["base_url_scheme"] == "https"
    assert result["base_url_host"] == "api.openai.com"
    assert result["path_class"] == "/v1/chat/completions"
    assert result["child_key_present"] is True
    assert result["runtime_key_present"] is True
    assert result["runtime_key_matches_sentinel"] is True
    assert result["auth_header_scheme"] == "Bearer"
    assert result["wrong_host_openrouter"] is False
    assert result["returncode"] == 0


def test_gpt_41_mini_openai_api_omits_reasoning_effort() -> None:
    result = probe_model_smoke_reasoning_kwargs()
    assert result["provider"] == "openai-api"
    assert result["model"] == "gpt-4.1-mini"
    assert result["resolved_omits_reasoning_effort"] is True
    assert result["upstream_default_effort"] == "medium"
    assert result["upstream_default_emits_reasoning_effort"] is True
    assert result["returncode"] == 0


def test_operator_and_developer_homes_differ() -> None:
    homes = write_proof_homes()
    op = Path(homes["operator"]) / "config.yaml"
    dev = Path(homes["developer"]) / "config.yaml"
    assert op.read_text(encoding="utf-8") != dev.read_text(encoding="utf-8")
    assert "disabled_toolsets:" in op.read_text(encoding="utf-8")
    env = isolated_env(operator_home(), extra={"HERMES_R1_CONTEXT": "operator"})
    pin = load_pin()
    assert all(not env.get(name) for name in pin["production_authority_names"])
