"""Unit tests for consolidated bounded-family Hermes gates (features / driver / ENTSO‑E market & forecast / ERA5)."""

from __future__ import annotations

import pytest

from tools import powerunits_bounded_family_gates as g


@pytest.fixture(autouse=True)
def _clear_bounded_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        g.MARKET_FEATURES_BOUNDED_PRIMARY_ENV,
        g.MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV,
        g.MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV,
        g.MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV,
        *g.MARKET_FEATURES_BOUNDED_LEGACY_ENV.values(),
        *g.MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV.values(),
        g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
        g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
        *g.ENTSOE_MARKET_BOUNDED_LEGACY_ENV.values(),
        g.ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
        g.ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
        *g.ERA5_WEATHER_BOUNDED_LEGACY_ENV.values(),
        g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV,
        g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV,
        *g.ENTSOE_FORECAST_BOUNDED_LEGACY_ENV.values(),
    ):
        monkeypatch.delenv(name, raising=False)


def test_market_features_primary_unlocks_all_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_PRIMARY_ENV, "1")
    for step in ("execute", "validate", "readiness", "summary"):
        assert g.market_features_bounded_step_enabled(step) is True


def test_market_features_primary_with_empty_allowlist_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.market_features_bounded_step_enabled("execute") is False


def test_market_features_primary_exclude_de_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV, "FR,IT")
    assert g.market_features_bounded_step_enabled("validate") is False


def test_market_features_legacy_granular(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_LEGACY_ENV["execute"], "1")
    assert g.market_features_bounded_step_enabled("execute") is True
    assert g.market_features_bounded_step_enabled("validate") is False


def test_market_features_legacy_ignores_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv(g.MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.market_features_bounded_step_enabled("execute") is True


def test_market_driver_primary_unlocks_all_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV, "1")
    for step in ("execute", "validate", "readiness", "summary"):
        assert g.market_driver_features_bounded_step_enabled(step) is True


def test_entsoe_primary_unlocks_preflight_through_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    for step in ("preflight", "execute", "validate", "summary"):
        assert g.entsoe_market_bounded_core_step_enabled(step) is True


def test_entsoe_primary_with_empty_allowlist_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.entsoe_market_bounded_core_step_enabled("execute") is False


def test_entsoe_legacy_granular(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_LEGACY_ENV["execute"], "1")
    assert g.entsoe_market_bounded_core_step_enabled("execute") is True
    assert g.entsoe_market_bounded_core_step_enabled("validate") is False


def test_entsoe_legacy_ignores_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.entsoe_market_bounded_core_step_enabled("execute") is True


def test_era5_primary_unlocks_preflight_through_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    for step in ("preflight", "execute", "validate", "summary"):
        assert g.era5_weather_bounded_core_step_enabled(step) is True


def test_era5_primary_with_empty_allowlist_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.era5_weather_bounded_core_step_enabled("validate") is False


def test_era5_legacy_granular(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_LEGACY_ENV["summary"], "1")
    assert g.era5_weather_bounded_core_step_enabled("summary") is True
    assert g.era5_weather_bounded_core_step_enabled("execute") is False


def test_era5_legacy_ignores_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_LEGACY_ENV["preflight"], "1")
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.era5_weather_bounded_core_step_enabled("preflight") is True


def test_entsoe_primary_exclude_de_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "FR,IT")
    assert g.entsoe_market_bounded_core_step_enabled("execute") is False


def test_era5_primary_exclude_de_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "AT,NL")
    assert g.era5_weather_bounded_core_step_enabled("summary") is False


def test_entsoe_forecast_primary_unlocks_preflight_through_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    for step in ("preflight", "execute", "validate", "summary"):
        assert g.entsoe_forecast_bounded_core_step_enabled(step) is True


def test_entsoe_forecast_primary_with_empty_allowlist_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.entsoe_forecast_bounded_core_step_enabled("preflight") is False


def test_entsoe_forecast_legacy_granular(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_LEGACY_ENV["preflight"], "1")
    assert g.entsoe_forecast_bounded_core_step_enabled("preflight") is True
    assert g.entsoe_forecast_bounded_core_step_enabled("summary") is False
