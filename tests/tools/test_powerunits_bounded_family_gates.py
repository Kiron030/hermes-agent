"""Unit tests for consolidated bounded-family Hermes gates (features / driver / ENTSO‑E market & forecast / ERA5 / outage awareness)."""

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
        g.OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV,
        g.OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV,
        *g.OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV.values(),
        g.OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV,
        g.OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV,
        *g.OUTAGE_REPAIR_BOUNDED_LEGACY_ENV.values(),
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


def test_entsoe_primary_nonempty_allowlist_without_de_still_unlocks_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    """ENTSO‑E market: nonempty allowlist only fails closed when explicitly empty — not ERA5‑style implicit DE."""
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "FR,IT")
    assert g.entsoe_market_bounded_core_step_enabled("execute") is True


def test_entsoe_requested_nl_denied_when_primary_allowlists_only_de(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE")
    assert g.entsoe_market_bounded_request_country_permitted("NL") is False


def test_entsoe_requested_nl_permitted_when_allowlist_contains_nl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL")
    assert g.entsoe_market_bounded_request_country_permitted("NL") is True


def test_entsoe_requested_tier1_permitted_when_primary_allowlist_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Primary with **no** ALLOWED env ⇒ Hermes uses full Repo B Tier‑1 mirror for ENTSO‑E (mirrored frozenset; widens only when Repo B does), alongside unrelated DE‑only legacy bounded families."""
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.delenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    for cc in ("NL", "BE", "FR", "AT", "CZ", "PL", "FI", "HU", "SK", "RO"):
        assert g.entsoe_market_bounded_request_country_permitted(cc) is True
    for cc in ("ES", "IT", "SE", "DK", "NO"):
        assert g.entsoe_market_bounded_request_country_permitted(cc) is False


def test_entsoe_explicit_core_four_allowlist_blocks_at(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL,BE,FR")
    assert g.entsoe_market_bounded_request_country_permitted("AT") is False
    assert g.entsoe_market_bounded_request_country_permitted("DE") is True


def test_era5_primary_nonempty_allowlist_without_de_still_unlocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """ERA5 Tier-1 rollout: allowlist needs not contain DE — only fail-closed on explicit empty."""
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "AT,NL")
    assert g.era5_weather_bounded_core_step_enabled("summary") is True


def test_era5_requested_nl_permitted_when_primary_allowlists_nl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL")
    assert g.era5_weather_bounded_request_country_permitted("NL") is True


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


def test_entsoe_forecast_nonempty_allowlist_without_de_unlocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier rollout: gates open whenever primary is on and allowlist non-empty."""
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "NL")
    assert g.entsoe_forecast_bounded_core_step_enabled("execute") is True


def test_entsoe_forecast_nl_denied_when_primary_allowlists_only_de(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE")
    assert g.entsoe_forecast_bounded_request_country_permitted("NL") is False


def test_entsoe_forecast_nl_permitted_when_primary_allowlists_de_nl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL")
    assert g.entsoe_forecast_bounded_request_country_permitted("NL") is True


def test_entsoe_forecast_tier1_permitted_when_allowlist_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.delenv(g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    for cc in ("NL", "BE", "FR", "AT", "CZ", "PL", "FI", "HU", "SK", "RO"):
        assert g.entsoe_forecast_bounded_request_country_permitted(cc) is True
    for cc in ("ES", "IT", "SE", "DK", "NO"):
        assert g.entsoe_forecast_bounded_request_country_permitted(cc) is False


def test_entsoe_forecast_explicit_core_four_allowlist_blocks_at(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL,BE,FR")
    assert g.entsoe_forecast_bounded_request_country_permitted("AT") is False


def test_entsoe_market_and_forecast_tier1_mirrors_stay_identical() -> None:
    """Guard: Hermes mirrors must track Repo B (market and forecast share the same expanding Tier v1 set)."""
    from tools.powerunits_entsoe_forecast_bounded_countries import (
        ALLOWED_BOUNDED_ENTSOE_FORECAST_COUNTRY_CODES_V1 as fc,
    )
    from tools.powerunits_entsoe_market_bounded_countries import (
        ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1 as mc,
    )

    assert mc == fc


def test_outage_awareness_primary_unlocks_validate_and_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV, "1")
    assert g.outage_awareness_bounded_core_step_enabled("validate") is True
    assert g.outage_awareness_bounded_core_step_enabled("summary") is True


def test_outage_awareness_primary_with_empty_allowlist_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.outage_awareness_bounded_core_step_enabled("validate") is False


def test_outage_awareness_legacy_granular(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV["validate"], "1")
    assert g.outage_awareness_bounded_core_step_enabled("validate") is True
    assert g.outage_awareness_bounded_core_step_enabled("summary") is False


def test_outage_awareness_legacy_validate_only_does_not_open_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV["validate"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    import tools.powerunits_outage_awareness_bounded_summary_tool as sum_mod

    assert sum_mod.check_powerunits_outage_awareness_bounded_summary_requirements() is False


def test_outage_repair_primary_unlocks_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV, "1")
    assert g.outage_repair_bounded_core_step_enabled("execute") is True


def test_outage_repair_primary_empty_allowlist_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(g.OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    assert g.outage_repair_bounded_core_step_enabled("execute") is False


def test_outage_repair_legacy_execute_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(g.OUTAGE_REPAIR_BOUNDED_LEGACY_ENV["execute"], "1")
    assert g.outage_repair_bounded_core_step_enabled("execute") is True
