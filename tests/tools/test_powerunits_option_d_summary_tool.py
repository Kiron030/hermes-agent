"""Tests for Option D Hermes bounded summary-window tool (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_option_d_summary_tool as mod


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
        mod.summarize_powerunits_option_d_bounded_window(
            country=country,
            start=start,
            end=end,
            version=version,
            pipeline_run_id=pipeline_run_id,
            _http_post=_http_post,
        )
    )


def _with_summary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-bearer-secret")


def test_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED", raising=False)
    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out.get("error_code") == "feature_disabled"
    assert out["summary_attempted"] is False


def test_http_200_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_summary_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "outcome_class": "ok",
                "flags": {"slice_ready": True},
                "readiness": {"readiness": "go"},
                "validation": {"outcome": "passed"},
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "summary-window" in url
        assert json_body["country_code"] == "PL"
        return R()

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=fake_post,
    )
    assert out["summary_attempted"] is True
    assert out["http_ok"] is True
    assert out["success"] is True
    assert out["outcome_class"] == "ok"
    assert "summary-window" in out["hermes_statement"].lower()


def test_http_200_validate_failed_still_http_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_summary_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps({"outcome_class": "validate_failed"})

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
    assert out["http_ok"] is True
    assert out["success"] is False
