"""Tests for bounded ERA5 weather sync Hermes tools (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_era5_weather_bounded_execute_tool as exec_mod
from tools import powerunits_era5_weather_bounded_preflight_tool as pre_mod
from tools import powerunits_era5_weather_bounded_validate_tool as val_mod
from tools.powerunits_era5_weather_bounded_slice import validate_era5_bounded_slice


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_execute_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED", raising=False)
    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_http_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "rid",
                "correlation_id": "cid",
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job", "market_driver_feature_job"],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/recompute" in url
        assert json_body["country_code"] == "DE"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert out["execution_attempted"] is True
    assert "operator_statement" in out
    assert "market_feature_job was NOT auto-run" in out["operator_statement"]
    assert "market_driver_feature_job was NOT auto-run" in out["operator_statement"]


def test_validate_wrong_country(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("no http")

    out = json.loads(
        val_mod.validate_powerunits_era5_weather_bounded_window(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out["validation_attempted"] is False


def test_validate_http_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "outcome": "passed",
                "summary_code": "validation_passed",
                "correlation_id": "c",
                "warnings": [],
                "checks": {"expected_hour_slots": 12},
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/validate-window" in url
        return R()

    out = json.loads(
        val_mod.validate_powerunits_era5_weather_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["validation_passed"] is True
    assert "operator_statement" in out
    assert "market_feature_job was NOT auto-run" in out["operator_statement"]


def test_summary_http_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_era5_weather_bounded_summary_tool as sum_mod

    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "outcome_class": "ok",
                "correlation_id": "c",
                "flags": {},
                "validation": {},
                "execution": {},
                "operator_next": "ok",
                "caveats": [],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/summary-window" in url
        return R()

    out = json.loads(
        sum_mod.summarize_powerunits_era5_weather_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert "operator_statement" in out
    assert "market_feature_job was NOT auto-run" in out["operator_statement"]


def test_validate_schema_mentions_weather_and_no_auto() -> None:
    desc = val_mod.VALIDATE_ERA5_SCHEMA["description"]
    assert "weather_country_hourly" in desc
    assert "market_feature_job" in desc.lower()


def test_summary_schema_mentions_no_auto() -> None:
    from tools import powerunits_era5_weather_bounded_summary_tool as sum_mod

    desc = sum_mod.SUMMARY_ERA5_SCHEMA["description"]
    assert "market_feature_job" in desc.lower()
    assert "7d" in desc or "≤7" in desc or "7 d" in desc.lower()


def test_era5_bounded_slice_accepts_7d() -> None:
    cc, start, end = validate_era5_bounded_slice(
        "DE",
        "2024-01-01T00:00:00Z",
        "2024-01-08T00:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert (end - start).total_seconds() == 7 * 24 * 3600


def test_era5_bounded_slice_rejects_over_7d() -> None:
    with pytest.raises(ValueError, match="7 days"):
        validate_era5_bounded_slice(
            "DE",
            "2024-01-01T00:00:00Z",
            "2024-01-09T00:00:00Z",
            "v1",
        )


def test_preflight_valid_de(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED", "1")
    out = json.loads(
        pre_mod.preflight_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert "execute_powerunits_era5_weather_bounded_slice" in out["bounded_http_operator_hint"]
    assert "market_feature_job was NOT auto-run" in out["bounded_http_operator_hint"]
