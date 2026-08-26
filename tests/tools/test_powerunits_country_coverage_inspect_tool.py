"""Tests for bounded country coverage inspect Hermes tool (Repo B read-only)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_a_tool_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED", raising=False)
    out = json.loads(mod.inspect_powerunits_country_coverage_v1(country="AT"))
    assert out["error_code"] == "feature_disabled"
    assert out["read_attempted"] is False
    assert out["effect_class"] == "READ"


def test_b_invalid_country_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    _enable(monkeypatch)
    out = json.loads(mod.inspect_powerunits_country_coverage_v1(country="US"))
    assert out["error_code"] == "unsupported_country"
    assert out["read_attempted"] is False


def test_d_invalid_dataset_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    _enable(monkeypatch)
    out = json.loads(
        mod.inspect_powerunits_country_coverage_v1(
            country="DE",
            dataset="public.market_demand_hourly; DROP TABLE x",
        )
    )
    assert out["error_code"] == "invalid_dataset"
    assert out["read_attempted"] is False


def test_f_end_before_start_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    _enable(monkeypatch)
    out = json.loads(
        mod.inspect_powerunits_country_coverage_v1(
            country="DE",
            dataset="demand",
            start="2026-08-08T00:00:00Z",
            end="2026-08-01T00:00:00Z",
        )
    )
    assert out["error_code"] == "invalid_window"
    assert out["read_attempted"] is False


def test_c_e_typed_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    _enable(monkeypatch)
    captured: dict[str, Any] = {}

    ok_body = {
        "success": True,
        "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "inspect_api_version": "bounded_country_coverage_inspect_v1",
        "country": "AT",
        "mode": "dataset",
        "requested_start": "2026-08-01T00:00:00+00:00",
        "requested_end": "2026-08-02T00:00:00+00:00",
        "used_default_range": False,
        "no_data": False,
        "items": [
            {
                "dataset": "demand",
                "status": "OK",
                "coverage_ratio": 1.0,
                "observed_points": 24,
                "expected_points": 24,
                "latest_timestamp": "2026-08-01T23:00:00+00:00",
                "age_hours": 12.0,
            }
        ],
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps(ok_body)
    resp.content = resp.text.encode()
    resp.json = lambda body=ok_body: body

    def fake_post(url: str, headers: dict, json_body: dict, _timeout: float) -> MagicMock:
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json_body
        return resp

    out = json.loads(
        mod.inspect_powerunits_country_coverage_v1(
            country="at",
            dataset="demand",
            start="2026-08-01T00:00:00Z",
            end="2026-08-02T00:00:00Z",
            _http_post=fake_post,
        )
    )
    assert captured["url"] == "https://api.test/internal/hermes/bounded/v1/country-coverage/inspect"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["body"]["country"] == "AT"
    assert captured["body"]["dataset"] == "demand"
    assert "sql" not in captured["body"]
    assert out["success"] is True
    assert out["inspect_api_version"] == "bounded_country_coverage_inspect_v1"
    assert "demand" in out["chat_summary"]
    assert out["effect_class"] == "READ"


def test_g_summary_omits_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    _enable(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_post(_url: str, _headers: dict, json_body: dict, _timeout: float) -> MagicMock:
        captured["body"] = json_body
        resp = MagicMock()
        resp.status_code = 200
        body = {
            "success": True,
            "country": "DE",
            "mode": "summary",
            "no_data": True,
            "items": [{"dataset": "demand", "status": "NO_DATA", "coverage_ratio": 0, "observed_points": 0, "expected_points": 168}],
        }
        resp.text = json.dumps(body)
        resp.content = resp.text.encode()
        resp.json = lambda payload=body: payload
        return resp

    out = json.loads(mod.inspect_powerunits_country_coverage_v1(country="DE", _http_post=fake_post))
    assert "dataset" not in captured["body"]
    assert "NO_DATA" in out["chat_summary"]


def test_f_no_db_credential_and_no_arbitrary_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_country_coverage_inspect_tool as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "DATABASE_URL" not in source
    assert "DATABASE_URL_TIMESCALE" not in source
    assert "/internal/hermes/bounded/v1/country-coverage/inspect" in source
    props = set((mod.COUNTRY_COVERAGE_INSPECT_SCHEMA_V1.get("parameters") or {}).get("properties") or {})
    assert {"url", "host", "path", "sql", "table"}.isdisjoint(props)


def test_j_developer_pin_does_not_receive_operator_tool() -> None:
    from pathlib import Path
    import json as json_mod

    pin = json_mod.loads(
        (Path(__file__).resolve().parents[2] / "scripts" / "r5_developer_hermes" / "pin.json").read_text(
            encoding="utf-8"
        )
    )
    assert "powerunits_country_coverage_inspect" not in pin["developer_enabled_toolsets"]
    assert "powerunits" not in " ".join(pin["developer_enabled_toolsets"])
