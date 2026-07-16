"""Tests for operator country scope v1."""

from __future__ import annotations

import pytest

from powerunits_operator_country_scope_v1 import (
    ERA5_TIER1_CSV_V1,
    NATIONAL_TIER1_ISO2_V1,
    default_triptychon_country_codes,
    era5_entsoe_scope_asymmetry_caution_flags_v1,
    normalize_country_codes,
    operator_country_scope_summary_v1,
)


def test_national_tier1_has_eleven_countries() -> None:
    assert len(NATIONAL_TIER1_ISO2_V1) == 11
    assert "DE" in NATIONAL_TIER1_ISO2_V1
    assert "FI" in NATIONAL_TIER1_ISO2_V1


def test_default_triptychon_matches_national_tier1() -> None:
    assert default_triptychon_country_codes() == list(NATIONAL_TIER1_ISO2_V1)


def test_normalize_country_codes_defaults_to_national() -> None:
    codes, err = normalize_country_codes(None)
    assert err is None
    assert codes == list(NATIONAL_TIER1_ISO2_V1)


def test_normalize_country_codes_csv_string() -> None:
    codes, err = normalize_country_codes("de, pl")
    assert err is None
    assert codes == ["DE", "PL"]


def test_era5_csv_has_nineteen_keys() -> None:
    assert len(ERA5_TIER1_CSV_V1.split(",")) == 19


def test_operator_country_scope_summary_structure() -> None:
    summary = operator_country_scope_summary_v1()
    assert len(summary["national_tier1_entsoe_market_forecast_worker"]) == 11
    assert summary["market_features_bounded_execute"] == ["DE", "PL"]
    assert summary["market_driver_bounded_execute"] == ["DE"]


def _clear_scope_asymmetry_envs(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED",
        "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES",
        "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED",
        "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES",
        "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED",
        "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_scope_asymmetry_no_flags_when_era5_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_scope_asymmetry_envs(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    assert era5_entsoe_scope_asymmetry_caution_flags_v1() == []


def test_scope_asymmetry_no_flags_when_entsoe_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_scope_asymmetry_envs(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED", "1")
    assert era5_entsoe_scope_asymmetry_caution_flags_v1() == []


def test_scope_asymmetry_no_flags_when_era5_allowlist_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_scope_asymmetry_envs(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES", "DE,FR")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    assert era5_entsoe_scope_asymmetry_caution_flags_v1() == []


def test_scope_asymmetry_no_flags_when_entsoe_allowlist_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_scope_asymmetry_envs(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES", "DE")
    assert era5_entsoe_scope_asymmetry_caution_flags_v1() == []


def test_scope_asymmetry_flags_entsoe_market_open_era5_de_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_scope_asymmetry_envs(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    flags = era5_entsoe_scope_asymmetry_caution_flags_v1()
    assert len(flags) == 1
    assert flags[0].startswith("era5_entsoe_scope_asymmetry:entsoe_market_bounded_open")
    assert "11_iso2" in flags[0]


def test_scope_asymmetry_flags_both_entsoe_families(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_scope_asymmetry_envs(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED", "1")
    flags = era5_entsoe_scope_asymmetry_caution_flags_v1()
    assert len(flags) == 2
    assert any("entsoe_market_bounded_open" in f for f in flags)
    assert any("entsoe_forecast_bounded_open" in f for f in flags)
