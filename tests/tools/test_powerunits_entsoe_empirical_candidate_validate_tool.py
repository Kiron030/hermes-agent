"""Tests for empirical ENTSO-E candidate validate Hermes tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


def test_empirical_candidate_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_entsoe_empirical_candidate_validate_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_ENABLED", raising=False)
    out = json.loads(
        mod.validate_powerunits_entsoe_empirical_candidate_window_v1(
            country_code="DK",
            window_start_utc="2026-07-01T00:00:00Z",
            window_end_utc="2026-07-02T00:00:00Z",
        )
    )
    assert out["error_code"] == "feature_disabled"


def test_empirical_candidate_rejects_tier1_de(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_entsoe_empirical_candidate_validate_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    out = json.loads(
        mod.validate_powerunits_entsoe_empirical_candidate_window_v1(
            country_code="DE",
            window_start_utc="2026-07-01T00:00:00Z",
            window_end_utc="2026-07-02T00:00:00Z",
        )
    )
    assert out["error_code"] == "invalid_country_code"
    assert "Tier-1" in out["message"]


def test_empirical_candidate_http_200(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_entsoe_empirical_candidate_validate_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    ok_body = {
        "correlation_id": "cid-1",
        "country_code": "DK",
        "hermes_statement": "empirical_candidate_read_only_not_tier1_bounded",
        "promotes_tier1": False,
        "candidate_smoke_evidence_v1": {
            "by_family_v1": {
                "market": {
                    "candidate_smoke_signal_v1": "pre_backfill_gap",
                    "outcome": "failed",
                },
                "forecast": {
                    "candidate_smoke_signal_v1": "post_execute_validation_passed",
                    "outcome": "passed",
                },
            }
        },
    }

    resp = MagicMock()
    resp.status_code = 200
    resp.text = json.dumps(ok_body)
    resp.content = resp.text.encode()
    resp.json = lambda body=ok_body: body

    out = json.loads(
        mod.validate_powerunits_entsoe_empirical_candidate_window_v1(
            country_code="DK",
            window_start_utc="2026-07-01T00:00:00Z",
            window_end_utc="2026-07-02T00:00:00Z",
            _http_post=lambda *_a, **_k: resp,
        )
    )
    assert out["success"] is True
    assert "Empirical candidate DK" in out["chat_summary"]
    assert "pre_backfill_gap" in out["chat_summary"]
