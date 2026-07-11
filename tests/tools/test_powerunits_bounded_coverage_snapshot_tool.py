"""Tests for bounded coverage snapshot Hermes tool (Repo B read-only)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


def test_snapshot_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    out = json.loads(
        mod.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes=["DE"],
        )
    )
    assert out["error_code"] == "feature_disabled"


def test_snapshot_http_200_chat_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    ok_body = {
        "success": True,
        "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "snapshot_api_version": "bounded_coverage_snapshot_v1",
        "baseline_ready": True,
        "baseline_readiness_reason": "all gates pass",
        "time_window": {
            "start_utc": "2024-01-01T00:00:00+00:00",
            "end_utc_exclusive": "2024-01-08T00:00:00+00:00",
            "expected_hours": 168,
        },
        "baseline_readiness_detail": {"DE": {"baseline_ready": True}},
        "latest_pipeline_runs": [
            {
                "job_name": "entsoe_market_sync",
                "found": True,
                "status": "success",
                "finished_at": "2024-01-07T12:00:00+00:00",
            },
        ],
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps(ok_body)
    resp.content = resp.text.encode()
    resp.json = lambda body=ok_body: body

    def fake_post(*_a: object, **_k: object) -> MagicMock:
        return resp

    out = json.loads(
        mod.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes="DE",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert "Baseline ready" in out["chat_summary"]
    assert "entsoe_market_sync" in out["chat_summary"]


def test_snapshot_missing_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    out = json.loads(
        mod.read_powerunits_coverage_snapshot_v1(
            window_start_utc="",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes=["DE"],
        )
    )
    assert out["error_code"] == "invalid_window"
