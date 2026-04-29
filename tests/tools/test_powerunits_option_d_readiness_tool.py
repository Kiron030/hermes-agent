"""Tests for Option D Hermes bounded readiness-window tool (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_option_d_readiness_tool as mod


def _call(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    pipeline_run_id: str | None = None,
    _http_post=None,
) -> dict:
    return json.loads(
        mod.readiness_powerunits_option_d_bounded_window(
            country=country,
            start=start,
            end=end,
            version=version,
            pipeline_run_id=pipeline_run_id,
            _http_post=_http_post,
        )
    )


def _with_readiness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-bearer-secret")


def test_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED", raising=False)
    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out.get("error_code") == "feature_disabled"
    assert out["readiness_attempted"] is False


def test_check_fn_requires_base_and_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert mod.check_powerunits_option_d_readiness_requirements() is True
    monkeypatch.delenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", raising=False)
    assert mod.check_powerunits_option_d_readiness_requirements() is False


def test_client_validation_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_readiness_env(monkeypatch)

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("HTTP must not be called")

    out = _call(
        country="DE",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=boom,
    )
    assert out["readiness_attempted"] is False
    assert out["slice"] is None


def test_http_200_go(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_readiness_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "readiness": "go",
                "dominant_blocker": None,
                "reason_codes": [],
                "warnings": [],
                "checks": {"expected_hour_slots": 12},
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "readiness-window" in url
        assert json_body["country_code"] == "PL"
        return R()

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=fake_post,
    )
    assert out["readiness_attempted"] is True
    assert out["http_ok"] is True
    assert out["success"] is True
    assert out["readiness"] == "go"
    assert out["readiness_go"] is True
    assert "readiness-window" in out["hermes_statement"].lower()


def test_http_200_no_go(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_readiness_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "readiness": "no_go",
                "dominant_blocker": "demand_missing",
                "reason_codes": ["demand_missing"],
                "warnings": [],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        return R()

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=fake_post,
    )
    assert out["readiness_go"] is False
    assert out["success"] is False
    assert out["dominant_blocker"] == "demand_missing"
