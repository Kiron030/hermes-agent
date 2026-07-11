"""Tests for worker country coverage freshness Hermes tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


def test_worker_freshness_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_worker_country_coverage_freshness_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED", raising=False)
    out = json.loads(mod.read_powerunits_worker_country_coverage_freshness_v1())
    assert out["error_code"] == "feature_disabled"


def test_worker_freshness_http_200(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_worker_country_coverage_freshness_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    ok_body = {
        "success": True,
        "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "summary": {"passed": 10, "warning": 1, "failed": 0},
        "rows": [
            {
                "surface": "national_demand",
                "country_code": "DE",
                "latest_utc": "2026-07-11T18:00:00Z",
                "rows_last_window": 168,
                "outcome": "warning",
            }
        ],
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps(ok_body)
    resp.content = resp.text.encode()
    resp.json = lambda body=ok_body: body

    out = json.loads(
        mod.read_powerunits_worker_country_coverage_freshness_v1(
            national_country_codes=["DE"],
            _http_post=lambda *_a, **_k: resp,
        )
    )
    assert out["success"] is True
    assert "Outcomes" in out["chat_summary"]
    assert "DE/national_demand" in out["chat_summary"]
