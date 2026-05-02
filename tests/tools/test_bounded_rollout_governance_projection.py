"""Tests for rollout governance Hermes overlay (bounded_rollout_governance_projection_v1)."""

from __future__ import annotations

import pytest

from tools import bounded_rollout_governance_projection_v1 as pv1


@pytest.fixture(autouse=True)
def _forecast_primary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES", "DE,NL")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def test_overlay_adds_execute_tool_cross_layer_nl_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED", "1")
    repo_like = {
        "success": True,
        "rows": [
            {
                "family": pv1.ENTSOE_FORECAST_FAMILY,
                "country_code": "NL",
                "repo_b_allowed": True,
                "hermes_allowed_now": None,
                "inventory_ready": True,
                "execute_ready": True,
                "validate_ready": True,
                "summary_ready": True,
                "coverage_scan_ready": True,
                "campaign_ready": True,
                "planner_ready": False,
                "effective_status": "bounded_execute_lane_open_repo_b",
                "blocking_reason": None,
                "suggested_next_action": "x",
            }
        ],
    }
    merged = pv1.merge_repo_b_rollout_governance_payload_v1(repo_like)
    row = merged["rows"][0]
    assert row["hermes_allowed_now"]["execute_tool_open"] is True
    assert merged["meta"].get("hermes_overlay_version") == "bounded_rollout_governance_hermes_overlay_v1"
    assert row.get("effective_status_cross_layer")


def test_cross_layer_blocked_when_nl_not_allowed_by_hermes_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES", "DE")
    repo_like = {
        "success": True,
        "rows": [
            {
                "family": pv1.ENTSOE_FORECAST_FAMILY,
                "country_code": "NL",
                "repo_b_allowed": True,
                "hermes_allowed_now": None,
                "inventory_ready": True,
                "execute_ready": True,
                "validate_ready": True,
                "summary_ready": True,
                "coverage_scan_ready": True,
                "campaign_ready": True,
                "planner_ready": False,
                "effective_status": "bounded_execute_lane_open_repo_b",
                "blocking_reason": None,
                "suggested_next_action": "",
            },
        ],
    }
    merged = pv1.merge_repo_b_rollout_governance_payload_v1(repo_like)
    row = merged["rows"][0]
    assert row["hermes_allowed_now"]["execute_tool_open"] is False
    assert row.get("effective_status_cross_layer") == "repo_execute_ready_hermes_gated"
    blk = row.get("blocking_reason_cross_layer") or ""
    assert "narrowing_hint" in blk
    assert "FORECAST_BOUNDED_ALLOWED_COUNTRIES" in blk


def test_overlay_be_forecast_execute_open_when_allowlist_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES", raising=False)
    repo_like = {
        "success": True,
        "rows": [
            {
                "family": pv1.ENTSOE_FORECAST_FAMILY,
                "country_code": "BE",
                "repo_b_allowed": True,
                "hermes_allowed_now": None,
                "inventory_ready": True,
                "execute_ready": True,
                "validate_ready": True,
                "summary_ready": True,
                "coverage_scan_ready": True,
                "campaign_ready": True,
                "planner_ready": False,
                "effective_status": "bounded_execute_lane_open_repo_b",
                "blocking_reason": None,
                "suggested_next_action": "",
            },
        ],
    }
    merged = pv1.merge_repo_b_rollout_governance_payload_v1(repo_like)
    row = merged["rows"][0]
    assert row["hermes_allowed_now"]["execute_tool_open"] is True
