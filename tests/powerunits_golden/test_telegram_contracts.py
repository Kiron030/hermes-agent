"""Task F — Telegram operator behaviour without brittle prose snapshots."""

from __future__ import annotations

import json

import pytest

from powerunits_telegram_overlays import energy_web_research_telegram_overlay_instructions
from tests.powerunits_golden.env import (
    SYNTHETIC_EXECUTE_BASE_URL,
    SYNTHETIC_EXECUTE_HOST,
    SYNTHETIC_EXECUTE_SECRET,
    SYNTHETIC_TAVILY_KEY,
)
from tests.powerunits_golden.http import RecordingPoster
from tools import powerunits_bounded_coverage_snapshot_tool as snap
from tools import powerunits_energy_web_research_tool as research
from tools import powerunits_option_d_execute_tool as exec_mod
import tools.approval as approval


def test_chat_summary_shape_on_powerunits_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    poster = RecordingPoster(
        {
            "success": True,
            "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "snapshot_api_version": "bounded_coverage_snapshot_v1",
            "baseline_ready": True,
            "baseline_readiness_reason": "all gates pass",
            "time_window": {
                "start_utc": "2024-01-01T00:00:00+00:00",
                "end_utc_exclusive": "2024-01-02T00:00:00+00:00",
                "expected_hours": 24,
            },
            "baseline_readiness_detail": {"DE": {"baseline_ready": True}},
            "latest_pipeline_runs": [
                {
                    "job_name": "entsoe_market_sync",
                    "found": True,
                    "status": "success",
                    "finished_at": "2024-01-01T12:00:00+00:00",
                }
            ],
        }
    )
    out = json.loads(
        snap.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-02T00:00:00Z",
            country_codes=["DE"],
            _http_post=poster,
        )
    )
    assert out["success"] is True
    summary = out["chat_summary"]
    assert isinstance(summary, str)
    assert "Baseline ready" in summary
    assert "entsoe_market_sync" in summary
    assert "correlation_id" in summary
    assert out["correlation_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert out["read_attempted"] is True
    assert out["http_status_from_repo_b"] == 200


def test_model_readable_tool_error_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    out = json.loads(
        snap.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-02T00:00:00Z",
            country_codes=["DE"],
        )
    )
    assert out["success"] is False
    assert out["error_code"] == "feature_disabled"
    assert out.get("message")
    assert out.get("read_attempted") is False

    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": False, "message": "denied by operator"},
    )
    denied = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=RecordingPoster({"success": True}),
        )
    )
    assert denied["success"] is False
    assert denied["error_code"] == "approval_denied"
    assert denied["execution_attempted"] is False
    assert "denied" in (denied.get("message") or "").lower()


def test_energy_web_research_source_and_disclaimer_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED", "1")
    monkeypatch.setenv("TAVILY_API_KEY", SYNTHETIC_TAVILY_KEY)

    def _search(query: str, max_results: int):
        return {
            "results": [
                {"title": "A", "url": "https://a.example.com", "content": "snippet a"},
                {"title": "B", "url": "https://b.example.com", "content": "snippet b"},
            ]
        }

    out = json.loads(
        research.research_powerunits_energy_web_v1(
            query="German day-ahead prices",
            topic_type="market_news",
            _search_fn=_search,
        )
    )
    assert out["success"] is True
    assert out["external_web_context"] is True
    assert isinstance(out["sources"], list) and len(out["sources"]) == 2
    assert all("url" in row for row in out["sources"])
    assert "- [A](https://a.example.com)" in out["sources_markdown"]
    assert out["disclaimer_de"]
    assert "tavily" in out["disclaimer_de"].lower()
    assert "gem_units" in out["disclaimer_de"].lower()
    assert "gem_units" in out["operator_notice"].lower()
    assert any("not authoritative" in w.lower() for w in out["warnings"])
    overlay = energy_web_research_telegram_overlay_instructions()
    assert "disclaimer_de" in overlay
    assert "sources_markdown" in overlay
    assert "GEM" in overlay or "gem" in overlay.lower()
