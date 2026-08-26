"""Tests for bounded DB health observe Hermes tools (Repo B read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_DB_HEALTH_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_db_health_read_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_DB_HEALTH_READ_ENABLED", raising=False)
    out = json.loads(mod.read_powerunits_db_health_storage_v1())
    assert out["error_code"] == "feature_disabled"
    assert out["read_attempted"] is False
    assert out["effect_class"] == "READ"


def test_unknown_relation_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_db_health_read_tool as mod

    _enable(monkeypatch)
    out = json.loads(
        mod.read_powerunits_db_health_storage_v1(relation="pg_shadow; DROP TABLE x")
    )
    assert out["error_code"] == "unknown_relation"
    assert out["read_attempted"] is False


def test_limit_hard_max_fails_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_db_health_read_tool as mod

    _enable(monkeypatch)
    out = json.loads(mod.read_powerunits_db_health_statements_v1(limit=99))
    assert out["error_code"] == "invalid_limit"
    assert out["read_attempted"] is False


def test_typed_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_db_health_read_tool as mod

    _enable(monkeypatch)
    captured: dict[str, Any] = {}
    ok_body = {
        "success": True,
        "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "observe_api_version": "bounded_db_health_observe_v1",
        "surface": "storage",
        "database_bytes": 1024,
        "result_count": 1,
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
        mod.read_powerunits_db_health_storage_v1(
            relation="market_demand_hourly",
            limit=5,
            _http_post=fake_post,
        )
    )
    assert captured["url"] == "https://api.test/internal/hermes/bounded/v1/db-health/storage"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["body"]["relation"] == "market_demand_hourly"
    assert captured["body"]["limit"] == 5
    assert "sql" not in captured["body"]
    assert out["success"] is True
    assert out["effect_class"] == "READ"
    assert "storage" in out["chat_summary"]


def test_no_db_credential_and_no_arbitrary_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_db_health_read_tool as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "DATABASE_URL" not in source
    assert "DATABASE_URL_TIMESCALE" not in source
    assert "/internal/hermes/bounded/v1/db-health/storage" in source
    for schema in (
        mod.DB_HEALTH_STORAGE_SCHEMA_V1,
        mod.DB_HEALTH_PLANNER_SCHEMA_V1,
        mod.DB_HEALTH_INDEXES_SCHEMA_V1,
        mod.DB_HEALTH_VACUUM_SCHEMA_V1,
        mod.DB_HEALTH_SESSIONS_SCHEMA_V1,
        mod.DB_HEALTH_STATEMENTS_SCHEMA_V1,
        mod.TIMESCALE_OBSERVE_SCHEMA_V1,
    ):
        props = set((schema.get("parameters") or {}).get("properties") or {})
        assert {"url", "host", "path", "sql", "table"}.isdisjoint(props)


def test_developer_pin_does_not_receive_operator_tools() -> None:
    pin = json.loads(
        (Path(__file__).resolve().parents[2] / "scripts" / "r5_developer_hermes" / "pin.json").read_text(
            encoding="utf-8"
        )
    )
    assert "powerunits_db_observe" not in pin["developer_enabled_toolsets"]
    assert "powerunits_country_coverage_inspect" not in pin["developer_enabled_toolsets"]
    assert "powerunits" not in " ".join(pin["developer_enabled_toolsets"])
