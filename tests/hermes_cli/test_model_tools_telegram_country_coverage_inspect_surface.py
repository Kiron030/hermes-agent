"""model_tools × Telegram first_safe_v1 surface for country coverage inspect."""

from __future__ import annotations

import pytest


def test_model_tools_includes_country_coverage_inspect_when_gate_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    assert "powerunits_country_coverage_inspect" in enabled

    names = {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }
    assert "inspect_powerunits_country_coverage_v1" in names


def test_model_tools_country_coverage_inspect_absent_when_gate_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED", "0")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")

    from tools.registry import invalidate_check_fn_cache

    invalidate_check_fn_cache()

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    assert "powerunits_country_coverage_inspect" in enabled

    names = {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }
    assert "inspect_powerunits_country_coverage_v1" not in names
