"""Tests for bounded ENTSO-E market sync Hermes tools (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_entsoe_market_bounded_execute_tool as exec_mod
from tools import powerunits_entsoe_market_bounded_preflight_tool as pre_mod
from tools import powerunits_entsoe_market_bounded_validate_tool as val_mod
from tools import powerunits_entsoe_market_bounded_campaign_tool as camp_mod
from tools.powerunits_bounded_family_gates import (
    ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ENTSOE_MARKET_BOUNDED_LEGACY_ENV,
    ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
)
from tools.powerunits_entsoe_market_bounded_slice import (
    validate_entsoe_bounded_campaign,
    validate_entsoe_bounded_slice,
)


def _clear_entso_bounded_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, raising=False)
    for env_name in ENTSOE_MARKET_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_execute_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_entso_bounded_core(monkeypatch)
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_market_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_feature_disabled_primary_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_entso_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_market_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_http_200_via_primary_family_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_entso_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

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


def test_legacy_execute_only_does_not_open_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_entso_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    assert val_mod.check_powerunits_entsoe_market_bounded_validate_requirements() is False


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


def test_validate_schema_mentions_normalized_hourly_semantics() -> None:
    desc = val_mod.VALIDATE_ENTSOE_SCHEMA["description"]
    assert "hour-bucket" in desc or "UTC hour" in desc
    assert "technology_group" in desc or "long-format" in desc
    assert "7d" in desc or "≤7" in desc or "7 d" in desc.lower()


def test_summary_schema_mentions_normalized_hourly_semantics() -> None:
    from tools import powerunits_entsoe_market_bounded_summary_tool as sum_mod

    desc = sum_mod.SUMMARY_ENTSOE_SCHEMA["description"]
    assert "hourly" in desc.lower()
    assert "7d" in desc or "≤7" in desc or "7 d" in desc.lower()


def test_entsoe_bounded_slice_accepts_7d() -> None:
    cc, start, end = validate_entsoe_bounded_slice(
        "DE",
        "2024-01-01T00:00:00Z",
        "2024-01-08T00:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert (end - start).total_seconds() == 7 * 24 * 3600


def test_entsoe_bounded_slice_rejects_over_7d() -> None:
    with pytest.raises(ValueError, match="7 days"):
        validate_entsoe_bounded_slice(
            "DE",
            "2024-01-01T00:00:00Z",
            "2024-01-09T00:00:00Z",
            "v1",
        )


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


def test_preflight_valid_de_via_primary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_entso_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
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


def test_entsoe_bounded_campaign_plan_contiguous_three_windows() -> None:
    cc, ver, wins = validate_entsoe_bounded_campaign(
        "DE",
        "2024-01-01T00:00:00Z",
        "2024-01-16T00:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert ver == "v1"
    assert len(wins) == 3
    assert wins[0][1] == wins[1][0]
    assert wins[1][1] == wins[2][0]


def test_entsoe_bounded_campaign_rejects_over_31d() -> None:
    with pytest.raises(ValueError, match="31"):
        validate_entsoe_bounded_campaign(
            "DE",
            "2024-01-01T00:00:00Z",
            "2024-02-02T00:00:00Z",
            "v1",
        )


def test_campaign_via_primary_execute_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Campaign works when ENTSO_PRIMARY replaces legacy execute+summary flags."""
    _clear_entso_bounded_core(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    assert camp_mod.check_powerunits_entsoe_market_bounded_campaign_requirements() is True


def _with_campaign_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_campaign_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    monkeypatch.delenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED", raising=False)
    out = json.loads(
        camp_mod.campaign_powerunits_entsoe_market_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-08T00:00:00Z",
        )
    )
    assert out.get("stopped_reason") == "feature_disabled"


def test_campaign_fail_fast_on_second_execute_of_three(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two full windows planned (9 days); succeed window 1; fail execute on window 2."""
    _with_campaign_env(monkeypatch)

    class RExeOk:
        status_code = 200
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "11111111-1111-1111-1111-111111111111",
                "correlation_id": "cid",
                "rows_written": 42,
            }
        )
        content = b"{}"

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    class RExeFail:
        status_code = 502
        text = json.dumps({"success": False, "message": "job failed"})
        content = b"{}"

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    class RSumOk:
        status_code = 200
        text = json.dumps(
            {
                "success": True,
                "outcome_class": "ok",
                "correlation_id": "sid",
                "operator_next": "ok",
            }
        )
        content = b"{}"

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    exec_calls = {"n": 0}

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> Any:
        if "entsoe-market-sync/recompute" in url:
            exec_calls["n"] += 1
            if exec_calls["n"] == 1:
                return RExeOk()
            return RExeFail()
        if "summary-window" in url:
            return RSumOk()
        raise AssertionError(f"unexpected url {url!r}")

    out = json.loads(
        camp_mod.campaign_powerunits_entsoe_market_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-10T00:00:00Z",
            _http_post=fake_post,
        )
    )
    assert out["windows_planned"] == 2
    assert exec_calls["n"] == 2
    assert out["windows_attempted"] == 2
    assert out["windows_succeeded"] == 1
    assert out["stopped_reason"] == "execute_failed"
    assert len(out["windows"]) == 2
    assert out["windows"][0]["execute_success"] is True
    assert out["windows"][0]["summary_success"] is True
    assert out["windows"][1]["execute_success"] is False
