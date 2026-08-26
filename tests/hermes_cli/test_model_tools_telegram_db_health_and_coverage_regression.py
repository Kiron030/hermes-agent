"""Operator surface: DB health tools plus country-coverage regression."""

from __future__ import annotations

import pytest


def _operator_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")


def test_model_tools_includes_db_health_when_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    _operator_env(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_DB_HEALTH_READ_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED", "1")

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    assert "powerunits_db_observe" in enabled
    assert "powerunits_country_coverage_inspect" in enabled

    names = {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }
    assert "read_powerunits_db_health_storage_v1" in names
    assert "read_powerunits_db_health_planner_v1" in names
    assert "read_powerunits_db_health_indexes_v1" in names
    assert "read_powerunits_db_health_vacuum_v1" in names
    assert "read_powerunits_db_health_sessions_v1" in names
    assert "read_powerunits_db_health_statements_v1" in names
    assert "read_powerunits_timescale_observe_v1" in names
    assert "inspect_powerunits_country_coverage_v1" in names


def test_model_tools_db_health_absent_when_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _operator_env(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_DB_HEALTH_READ_ENABLED", "0")
    monkeypatch.setenv("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED", "1")

    from tools.registry import invalidate_check_fn_cache

    invalidate_check_fn_cache()

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    assert "powerunits_db_observe" in enabled
    assert "powerunits_country_coverage_inspect" in enabled

    names = {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }
    assert "read_powerunits_db_health_storage_v1" not in names
    assert "inspect_powerunits_country_coverage_v1" in names
