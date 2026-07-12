"""Tests for operator country scope v1."""

from __future__ import annotations

from powerunits_operator_country_scope_v1 import (
    ERA5_TIER1_CSV_V1,
    NATIONAL_TIER1_ISO2_V1,
    default_triptychon_country_codes,
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
