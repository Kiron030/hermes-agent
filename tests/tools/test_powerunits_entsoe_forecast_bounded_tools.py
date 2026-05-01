"""Tests for bounded ENTSO-E forecast Hermes tools (HTTP to Repo B)."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_entsoe_forecast_bounded_execute_tool as exec_mod
from tools import powerunits_entsoe_forecast_bounded_preflight_tool as pre_mod
from tools import powerunits_entsoe_forecast_bounded_validate_tool as val_mod
from tools.powerunits_bounded_family_gates import (
    ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ENTSOE_FORECAST_BOUNDED_LEGACY_ENV,
    ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV,
)
from tools.powerunits_entsoe_forecast_bounded_slice import validate_entsoe_forecast_bounded_slice


def _clear_fcst_bounded_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, raising=False)
    for env_name in ENTSOE_FORECAST_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_execute_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_feature_disabled_primary_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_http_200_via_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "rid",
                "correlation_id": "cid",
                "rows_written": 12,
                "downstream_not_auto_triggered": ["market_feature_job"],
                "operator_statement": "forecast only",
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/recompute" in url
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert out["downstream_not_auto_triggered"] == ["market_feature_job"]
    assert out["operator_statement"] == "forecast only"


def test_legacy_execute_only_does_not_open_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert val_mod.check_powerunits_entsoe_forecast_bounded_validate_requirements() is False


def test_preflight_valid_de_via_primary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    out = json.loads(
        pre_mod.preflight_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert "execute_powerunits_entsoe_forecast_bounded_slice" in out["bounded_http_operator_hint"]


def test_forecast_slice_accepts_7d() -> None:
    cc, start, end = validate_entsoe_forecast_bounded_slice(
        "DE",
        "2024-01-01T00:00:00Z",
        "2024-01-08T00:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert (end - start).total_seconds() == 7 * 24 * 3600
