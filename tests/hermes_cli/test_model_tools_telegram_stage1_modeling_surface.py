"""model_tools × Telegram first_safe_v1 surface for market features/driver + outage."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _invalidate_registry_cache() -> None:
    from tools.registry import invalidate_check_fn_cache

    invalidate_check_fn_cache()


def _telegram_tool_names(monkeypatch: pytest.MonkeyPatch, **env: str) -> set[str]:
    for key, val in env.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    return {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }


def test_market_driver_validate_visible_when_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    names = _telegram_tool_names(
        monkeypatch,
        HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED="1",
    )
    assert "validate_powerunits_market_driver_features_bounded_de_window" in names


def test_outage_repair_execute_visible_when_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    names = _telegram_tool_names(
        monkeypatch,
        HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED="1",
    )
    assert "execute_powerunits_outage_repair_bounded_slice" in names


def test_market_features_execute_visible_when_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    names = _telegram_tool_names(
        monkeypatch,
        HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED="1",
    )
    assert "execute_powerunits_market_features_bounded_de_slice" in names
