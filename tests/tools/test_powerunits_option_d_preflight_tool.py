"""Tests for Option D Hermes preflight tool (no wrapper / no DB)."""

from __future__ import annotations

import json

import pytest


def _call(**kwargs: str) -> dict:
    from tools import powerunits_option_d_preflight_tool as mod

    raw = mod.preflight_powerunits_option_d_bounded_slice(**kwargs)
    return json.loads(raw)


def test_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", raising=False)
    out = _call(country="PL", start="2024-01-01T00:00:00Z", end="2024-01-01T12:00:00Z", version="v1")
    assert out.get("error_code") == "feature_disabled"


def test_valid_pl_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", "1")
    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out["syntactically_valid"] is True
    assert out["normalization_errors"] == []
    assert out["hermes_executed_write"] is False
    assert out["hermes_ran_bounded_wrapper"] is False
    assert "Hermes did not execute" in out.get("hermes_statement", "")
    assert out["slice"]["country"] == "PL"
    assert out["slice"]["version"] == "v1"
    assert out["slice"]["start_utc"] == "2024-01-01T00:00:00Z"
    assert "python -m tools.powerunits_option_d_bounded_market_features" in out["operator_wrapper_command"]
    assert "--country PL" in out["operator_wrapper_command"]
    assert "DELETE FROM public.market_features_hourly" in out["rollback_sql_template"]
    assert "DATABASE_URL" in out["required_environment_variables"]


def test_invalid_country(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", "1")
    out = _call(
        country="DE",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out["syntactically_valid"] is False
    assert out["slice"] is None
    assert out["operator_wrapper_command"] is None


def test_invalid_window_over_24h(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", "1")
    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:01Z",
        version="v1",
    )
    assert out["syntactically_valid"] is False


def test_invalid_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", "1")
    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v2",
    )
    assert out["syntactically_valid"] is False


def test_end_not_after_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", "1")
    out = _call(
        country="PL",
        start="2024-01-01T12:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out["syntactically_valid"] is False


def test_first_safe_surface_includes_preflight_when_gated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED", "1")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_option_d_preflight", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "preflight_powerunits_option_d_bounded_slice" in names
    assert "web_search" not in names
