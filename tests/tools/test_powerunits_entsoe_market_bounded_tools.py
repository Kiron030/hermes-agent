"""Tests for bounded ENTSO-E market sync Hermes tools (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_entsoe_market_bounded_execute_tool as exec_mod
from tools import powerunits_entsoe_market_bounded_preflight_tool as pre_mod
from tools import powerunits_entsoe_market_bounded_validate_tool as val_mod


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_execute_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED", raising=False)
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_market_bounded_slice(
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
                "rows_written": 10,
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-market-sync/recompute" in url
        assert json_body["country_code"] == "DE"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_market_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert out["execution_attempted"] is True


def test_validate_wrong_country(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("no http")

    out = json.loads(
        val_mod.validate_powerunits_entsoe_market_bounded_window(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out["validation_attempted"] is False


def test_preflight_valid_de(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED", "1")
    out = json.loads(
        pre_mod.preflight_powerunits_entsoe_market_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert "execute_powerunits_entsoe_market_bounded_slice" in out["bounded_http_operator_hint"]
