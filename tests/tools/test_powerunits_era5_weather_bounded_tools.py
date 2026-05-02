"""Tests for bounded ERA5 weather sync Hermes tools (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_era5_weather_bounded_campaign_tool as camp_mod
from tools import powerunits_era5_weather_bounded_execute_tool as exec_mod
from tools import powerunits_era5_weather_bounded_preflight_tool as pre_mod
from tools import powerunits_era5_weather_bounded_validate_tool as val_mod
from tools.powerunits_bounded_family_gates import (
    ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ERA5_WEATHER_BOUNDED_LEGACY_ENV,
    ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
)
from tools.powerunits_era5_weather_bounded_slice import (
    validate_era5_bounded_campaign,
    validate_era5_bounded_slice,
)


def _clear_era5_bounded_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, raising=False)
    for env_name in ERA5_WEATHER_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_execute_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_feature_disabled_primary_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_http_200_via_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
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
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job", "market_driver_feature_job"],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/recompute" in url
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True


def test_execute_primary_implicit_de_blocks_fr(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("no http")

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="FR",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out.get("error_code") == "country_not_permitted"
    assert out.get("execution_attempted") is False


def test_execute_primary_allows_fr_when_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,FR")
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
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job", "market_driver_feature_job"],
            }
        )

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    def fake_post(
        url: str, headers: dict[str, Any], json_body: dict[str, Any], timeout_s: float
    ) -> Any:
        assert json_body["country_code"] == "FR"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="FR",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True


def test_legacy_execute_allows_fr_without_primary_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy path ignores Hermes allowlist narrowing; Repo B still validates HTTP."""
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_LEGACY_ENV["execute"], "1")
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
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job", "market_driver_feature_job"],
            }
        )

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    def fake_post(
        url: str, headers: dict[str, Any], json_body: dict[str, Any], timeout_s: float
    ) -> Any:
        assert json_body["country_code"] == "FR"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="FR",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True


def test_preflight_primary_allows_pt_when_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "PT")
    out = json.loads(
        pre_mod.preflight_powerunits_era5_weather_bounded_slice(
            country="PT",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("syntactically_valid") is True
    assert out.get("slice", {}).get("country") == "PT"


def test_execute_primary_allows_hu_when_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "HU")
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
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job", "market_driver_feature_job"],
            }
        )

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    def fake_post(
        url: str, headers: dict[str, Any], json_body: dict[str, Any], timeout_s: float
    ) -> Any:
        assert json_body["country_code"] == "HU"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="HU",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True


def test_preflight_primary_implicit_de_blocks_fr(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    out = json.loads(
        pre_mod.preflight_powerunits_era5_weather_bounded_slice(
            country="FR",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "country_not_permitted"
    assert out["syntactically_valid"] is False


def test_validate_primary_implicit_blocks_fr(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("no http")

    out = json.loads(
        val_mod.validate_powerunits_era5_weather_bounded_window(
            country="FR",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out.get("error_code") == "country_not_permitted"


def test_summary_primary_implicit_blocks_fr(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_era5_weather_bounded_summary_tool as sum_mod

    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("no http")

    out = json.loads(
        sum_mod.summarize_powerunits_era5_weather_bounded_window(
            country="FR",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out.get("error_code") == "country_not_permitted"


def test_campaign_primary_implicit_blocks_fr(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    out = json.loads(
        camp_mod.campaign_powerunits_era5_weather_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-08T00:00:00Z",
            country="FR",
        )
    )
    assert out.get("stopped_reason") == "country_not_permitted"
    assert out["windows_planned"] == 0


def test_legacy_execute_only_does_not_open_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert val_mod.check_powerunits_era5_weather_bounded_validate_requirements() is False


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
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job", "market_driver_feature_job"],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/recompute" in url
        assert json_body["country_code"] == "DE"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert out["execution_attempted"] is True
    assert "operator_statement" in out
    assert "market_feature_job was NOT auto-run" in out["operator_statement"]
    assert "market_driver_feature_job was NOT auto-run" in out["operator_statement"]


def test_validate_wrong_country(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("no http")

    out = json.loads(
        val_mod.validate_powerunits_era5_weather_bounded_window(
            country="XX",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out["validation_attempted"] is False


def test_validate_http_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "outcome": "passed",
                "summary_code": "validation_passed",
                "correlation_id": "c",
                "warnings": [],
                "checks": {"expected_hour_slots": 12},
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/validate-window" in url
        return R()

    out = json.loads(
        val_mod.validate_powerunits_era5_weather_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["validation_passed"] is True
    assert "operator_statement" in out
    assert "market_feature_job was NOT auto-run" in out["operator_statement"]


def test_summary_http_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_era5_weather_bounded_summary_tool as sum_mod

    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "outcome_class": "ok",
                "correlation_id": "c",
                "flags": {},
                "validation": {},
                "execution": {},
                "operator_next": "ok",
                "caveats": [],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/summary-window" in url
        return R()

    out = json.loads(
        sum_mod.summarize_powerunits_era5_weather_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert "operator_statement" in out
    assert "market_feature_job was NOT auto-run" in out["operator_statement"]


def test_validate_schema_mentions_weather_and_no_auto() -> None:
    desc = val_mod.VALIDATE_ERA5_SCHEMA["description"]
    assert "weather_country_hourly" in desc
    assert "market_feature_job" in desc.lower()


def test_summary_schema_mentions_no_auto() -> None:
    from tools import powerunits_era5_weather_bounded_summary_tool as sum_mod

    desc = sum_mod.SUMMARY_ERA5_SCHEMA["description"]
    assert "market_feature_job" in desc.lower()
    assert "7d" in desc or "≤7" in desc or "7 d" in desc.lower()


def test_era5_bounded_slice_accepts_7d() -> None:
    cc, start, end = validate_era5_bounded_slice(
        "DE",
        "2024-01-01T00:00:00Z",
        "2024-01-08T00:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert (end - start).total_seconds() == 7 * 24 * 3600


def test_era5_bounded_slice_rejects_over_7d() -> None:
    with pytest.raises(ValueError, match="7 days"):
        validate_era5_bounded_slice(
            "DE",
            "2024-01-01T00:00:00Z",
            "2024-01-09T00:00:00Z",
            "v1",
        )


def test_preflight_valid_de(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED", "1")
    out = json.loads(
        pre_mod.preflight_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert "execute_powerunits_era5_weather_bounded_slice" in out["bounded_http_operator_hint"]


def test_preflight_valid_de_via_primary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    out = json.loads(
        pre_mod.preflight_powerunits_era5_weather_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert "execute_powerunits_era5_weather_bounded_slice" in out["bounded_http_operator_hint"]


def test_era5_bounded_campaign_plan_contiguous_three_windows() -> None:
    cc, ver, wins = validate_era5_bounded_campaign(
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


def test_era5_bounded_campaign_rejects_over_31d() -> None:
    with pytest.raises(ValueError, match="31"):
        validate_era5_bounded_campaign(
            "DE",
            "2024-01-01T00:00:00Z",
            "2024-02-02T00:00:00Z",
            "v1",
        )


def test_era5_campaign_via_primary_family_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_era5_bounded_core(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    assert camp_mod.check_powerunits_era5_weather_bounded_campaign_requirements() is True


def test_era5_campaign_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    monkeypatch.delenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED", raising=False)
    out = json.loads(
        camp_mod.campaign_powerunits_era5_weather_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-08T00:00:00Z",
        )
    )
    assert out.get("stopped_reason") == "feature_disabled"


def test_era5_campaign_fail_fast_on_second_execute_when_three_windows_planned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """21-day campaign → three 7d windows; window 2 execute fails; window 3 not attempted."""
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class RExeOk:
        status_code = 200
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "11111111-1111-1111-1111-111111111111",
                "correlation_id": "cid",
                "rows_written": 24,
            }
        )
        content = b"{}"

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    class RExeFail:
        status_code = 502
        text = json.dumps({"success": False, "message": "cds failed"})
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
                "caveats": [],
            }
        )
        content = b"{}"

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    exec_calls = {"n": 0}

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> Any:
        if "era5-weather/recompute" in url:
            exec_calls["n"] += 1
            if exec_calls["n"] <= 1:
                return RExeOk()
            return RExeFail()
        if "era5-weather/summary-window" in url:
            return RSumOk()
        raise AssertionError(f"unexpected url {url!r}")

    out = json.loads(
        camp_mod.campaign_powerunits_era5_weather_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-22T00:00:00Z",
            _http_post=fake_post,
        )
    )
    assert out["windows_planned"] == 3
    assert exec_calls["n"] == 2
    assert out["windows_attempted"] == 2
    assert out["windows_succeeded"] == 1
    assert out["stopped_reason"] == "execute_failed"
    assert len(out["windows"]) == 2
    assert out["windows"][0]["execute_success"] is True
    assert out["windows"][0]["summary_success"] is True
    assert out["windows"][1]["execute_success"] is False
