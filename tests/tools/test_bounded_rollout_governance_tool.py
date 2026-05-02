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
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES", "DE,NL")

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
