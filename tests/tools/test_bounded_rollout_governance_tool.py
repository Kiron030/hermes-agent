"""HTTP wiring tests for rollout governance bounded tool."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_bounded_rollout_governance_tool as gov


def test_governance_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED", raising=False)
    out = json.loads(gov.governance_powerunits_bounded_rollout_read_v1(country_codes_csv=None))
    assert out.get("error_code") == "feature_disabled"


def test_governance_posts_expected_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES", "DE,NL,BE,FR")

    sample = json.dumps(
        {
            "success": True,
            "governance_api_version": "bounded_rollout_governance_v1",
            "rows": [],
            "meta": {},
            "rollup": {},
        }
    )

    class R:
        status_code = 200
        text = sample
        content = sample.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    seen: dict[str, str] = {}

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        seen["url"] = url
        assert json_body.get("country_codes") is None or json_body.get("country_codes") == ["NL"]
        return R()

    out = json.loads(
        gov.governance_powerunits_bounded_rollout_read_v1(
            country_codes_csv="NL",
            apply_hermes_overlay=False,
            _http_post=fake_post,
        )
    )
    assert "rollout-governance" in seen["url"]
    assert out.get("success") is True


def test_governance_echoes_repo_b_meta_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")

    sample = json.dumps(
        {
            "success": True,
            "rows": [],
            "meta": {
                "generated_at_utc": "2026-04-30T12:00:00Z",
                "canonical_bounded_entso_market_v1_iso2": ["BE", "DE", "FR", "NL"],
                "canonical_bounded_entso_forecast_v1_iso2": ["BE", "DE", "FR", "NL"],
            },
            "rollup": {},
        }
    )

    class R:
        status_code = 200
        text = sample
        content = sample.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    out = json.loads(
        gov.governance_powerunits_bounded_rollout_read_v1(
            apply_hermes_overlay=False,
            _http_post=lambda *a, **k: R(),
        )
    )
    assert out.get("repo_b_rollout_governance_generated_at_utc") == "2026-04-30T12:00:00Z"
    assert out.get("repo_b_canonical_bounded_entso_forecast_v1_iso2") == ["BE", "DE", "FR", "NL"]
    assert "hint_governance_truth_vs_overlay_v1" in out


def test_governance_csv_export_contains_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")
    row = {
        "family": "bounded_entsoe_market_normalized_v1",
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
        "suggested_next_action": "ok",
    }
    sample = json.dumps({"success": True, "rows": [row], "meta": {}, "rollup": {}})

    class R:
        status_code = 200
        text = sample
        content = sample.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    out = json.loads(
        gov.governance_powerunits_bounded_rollout_read_v1(
            export_format="csv",
            apply_hermes_overlay=False,
            _http_post=lambda *a, **k: R(),
        )
    )
    ce = out.get("csv_export") or ""
    assert ce.startswith("family,country_code,repo_b_allowed,hermes_allowed_now")
    assert "effective_status_cross_layer" in ce
    assert "BE" in ce
    assert list(gov.GOVERNANCE_CSV_EXPORT_COLUMNS_V1)[0] == "family"
