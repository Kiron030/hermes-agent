"""Tests for bounded ERA5 weather coverage-scan Hermes tool (HTTP to Repo B)."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_era5_weather_bounded_coverage_scan_tool as scan_mod
from tools.powerunits_bounded_family_gates import (
    ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
)
from tools.powerunits_era5_tier1_countries import (
    BOUNDED_ERA5_USER_FACING_ISO2_DOCUMENTATION_V1 as TIER1_ERA5_ISO2_DOC,
)


def _with_coverage_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_era5_coverage_scan_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED", raising=False)
    out = json.loads(
        scan_mod.scan_powerunits_era5_weather_bounded_coverage_de(
            scan_start_utc="2024-01-01T00:00:00Z",
            scan_end_utc="2024-01-08T00:00:00Z",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_era5_coverage_scan_primary_implicit_de_blocks_fr(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_coverage_env(monkeypatch)
    monkeypatch.delenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("no http")

    out = json.loads(
        scan_mod.scan_powerunits_era5_weather_bounded_coverage_de(
            scan_start_utc="2024-01-01T00:00:00Z",
            scan_end_utc="2024-01-08T00:00:00Z",
            country="FR",
            _http_post=boom,
        )
    )
    assert out.get("error_code") == "country_not_permitted"
    assert out["scan_attempted"] is False


@pytest.mark.parametrize("country", ("ES", "IE", "NO", "PL"))
def test_era5_coverage_scan_primary_allows_country_when_allowlisted(
    monkeypatch: pytest.MonkeyPatch, country: str
) -> None:
    _with_coverage_env(monkeypatch)
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, country)

    payload = {
        "correlation_id": "srv-cid",
        "hermes_statement": "read_only_scan_no_writes",
        "rollup": {"scan_outcome": "ok", "suggested_next_bounded_action": []},
        "scanner": "era5_weather_normalized_es_v1",
        "slice": {},
        "subwindows": [],
        "partition": {},
    }

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(payload)

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert json_body["country_code"] == country
        return R()

    out = json.loads(
        scan_mod.scan_powerunits_era5_weather_bounded_coverage_de(
            scan_start_utc="2024-01-01T00:00:00Z",
            scan_end_utc="2024-01-08T00:00:00Z",
            country=country,
            _http_post=fake_post,
        )
    )
    assert out["scan_attempted"] is True


def test_era5_coverage_scan_local_validation_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_coverage_env(monkeypatch)

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("no http")

    out = json.loads(
        scan_mod.scan_powerunits_era5_weather_bounded_coverage_de(
            scan_start_utc="2024-01-01T00:00:00Z",
            scan_end_utc="2024-02-02T00:00:00Z",
            _http_post=boom,
        )
    )
    assert out["scan_attempted"] is False
    assert "31" in " ".join(out.get("scan_messages", []))
    hs = out.get("hermes_statement", "")
    assert "Repo B only" in hs
    assert "market_driver_feature_job" in hs


def test_era5_coverage_scan_http_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_coverage_env(monkeypatch)

    payload = {
        "correlation_id": "srv-cid",
        "hermes_statement": "read_only_scan_no_writes",
        "rollup": {
            "scan_outcome": "warnings",
            "suggested_next_bounded_action": [{"action": "bounded_era5_weather_campaign_or_execute"}],
        },
        "scanner": "era5_weather_normalized_de_v1",
        "slice": {},
        "subwindows": [],
        "partition": {},
    }

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(payload)

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "era5-weather/coverage-scan" in url
        assert json_body["country_code"] == "DE"
        assert json_body["scan_start_utc"] == "2024-01-01T00:00:00Z"
        assert json_body["scan_end_utc"] == "2024-01-10T00:00:00Z"
        return R()

    out = json.loads(
        scan_mod.scan_powerunits_era5_weather_bounded_coverage_de(
            scan_start_utc="2024-01-01T00:00:00Z",
            scan_end_utc="2024-01-10T00:00:00Z",
            _http_post=fake_post,
        )
    )
    assert out["http_ok"] is True
    assert out["scan_attempted"] is True
    assert out["rollup"]["scan_outcome"] == "warnings"
    stmt = out["hermes_statement"].lower()
    assert "read_only" in stmt or "read only" in stmt


def test_era5_coverage_scan_schema_read_only_and_no_jobs() -> None:
    desc = scan_mod.SCAN_ERA5_SCHEMA["description"]
    assert "read-only" in desc.lower() or "read only" in desc.lower()
    assert "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED" in desc
    assert "era5_weather_job" in desc.lower()
    assert "Repo B" in desc
    country_desc = scan_mod.SCAN_ERA5_SCHEMA["parameters"]["properties"]["country"]["description"]
    assert country_desc == TIER1_ERA5_ISO2_DOC
