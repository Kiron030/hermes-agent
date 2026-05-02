"""Tests for bounded coverage inventory Hermes tool (Repo B aggregator)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


def test_inventory_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_inventory_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED", raising=False)
    out = json.loads(
        mod.inventory_powerunits_bounded_coverage_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes=["DE"],
        )
    )
    assert out["error_code"] == "feature_disabled"


def test_inventory_http_200_with_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_inventory_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    ok_body = {
        "success": True,
        "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "rows": [
            {
                "country_code": "DE",
                "family": "bounded_era5_weather_normalized_v1",
                "version": "v1",
                "overall_window_start_utc": "2024-01-01T00:00:00Z",
                "overall_window_end_utc_exclusive": "2024-01-02T00:00:00Z",
                "window_start_utc": "2024-01-01T00:00:00Z",
                "window_end_utc_exclusive": "2024-01-02T00:00:00Z",
                "subwindow_index": 0,
                "status": "ok",
                "summary_code": "validation_passed",
                "warnings": [],
                "coverage_metrics": {"checks": {}},
                "suggested_next_action": "fine",
                "tool_hint_hermes": None,
                "scanner_id": "era5_weather_normalized_bounded_v1",
                "rollup_scan_outcome": "ok",
            },
        ],
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps(ok_body)
    resp.headers = MagicMock()
    resp.headers.get.return_value = "application/json"
    resp.json = lambda body=ok_body: body

    def fake_post(*_a: object, **_k: object) -> MagicMock:
        return resp

    out_raw = mod.inventory_powerunits_bounded_coverage_v1(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-02T00:00:00Z",
        country_codes="DE",
        export_format="csv",
        _http_post=fake_post,
    )
    out = json.loads(out_raw)
    assert out["success"] is True
    assert "DE" in out["chat_summary"]
    assert isinstance(out["csv_export"], str)
    hdr = out["csv_export"].splitlines()[0]
    assert hdr.startswith("country_code,")
    assert "warnings_json" in hdr
