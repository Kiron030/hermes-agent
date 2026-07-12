"""Tests for multi-country data-health orchestrator tool."""

from __future__ import annotations

import json

import pytest


def test_multi_country_health_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_multi_country_data_health_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    out = json.loads(mod.read_powerunits_multi_country_data_health_v1())
    assert out["error_code"] == "feature_disabled"
    assert "country_scope_v1" in out


def test_multi_country_health_orchestrates_three_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_multi_country_data_health_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    snap_body = {
        "success": True,
        "http_status_from_repo_b": 200,
        "baseline_ready": False,
        "baseline_readiness_detail": {
            "DE": {"baseline_ready": True},
            "PL": {"baseline_ready": False},
        },
        "correlation_id": "snap-cid",
    }
    inv_body = {
        "success": True,
        "http_status_from_repo_b": 200,
        "rows": [
            {
                "country_code": "PL",
                "family": "bounded_entsoe_market_v1",
                "status": "warnings",
                "suggested_next_action": "validate",
            },
            {"country_code": "DE", "family": "bounded_era5_weather_v1", "status": "ok"},
        ],
        "correlation_id": "inv-cid",
    }
    fresh_body = {
        "success": True,
        "http_status_from_repo_b": 200,
        "summary": {"passed": 5, "warning": 1, "failed": 0},
        "rows": [
            {
                "country_code": "PL",
                "surface": "national_demand",
                "outcome": "warning",
            }
        ],
        "correlation_id": "fresh-cid",
    }

    def fake_snap(**_kw: object) -> str:
        return json.dumps(snap_body)

    def fake_inv(**_kw: object) -> str:
        return json.dumps(inv_body)

    def fake_fresh(**_kw: object) -> str:
        return json.dumps(fresh_body)

    monkeypatch.setattr(mod, "read_powerunits_coverage_snapshot_v1", fake_snap)
    monkeypatch.setattr(mod, "inventory_powerunits_bounded_coverage_v1", fake_inv)
    monkeypatch.setattr(mod, "read_powerunits_worker_country_coverage_freshness_v1", fake_fresh)

    out = json.loads(
        mod.read_powerunits_multi_country_data_health_v1(country_codes=["DE", "PL"])
    )
    assert out["success"] is True
    assert out["rollup_v1"]["green_count"] == 1
    assert "DE" in out["operator_summary_v1"]
    assert "PL" in out["operator_summary_v1"]
    assert "Grün" in out["operator_summary_v1"]
