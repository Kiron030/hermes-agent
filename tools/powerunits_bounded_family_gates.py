"""Consolidated Hermes gates for Repo B bounded **families**.

Design:
- One **primary** ``HERMES_*_ENABLED`` flag per family (no country suffix).
- Optional ``HERMES_*_ALLOWED_COUNTRIES`` comma list (uppercase ISO2). **Bounded ENTSO‑E market**, **bounded ENTSO‑E forecast**,
  and **bounded ERA5** primaries mirror each other (**unset ⇒ implicit DE per request intersection**;
  **explicit empty** ⇒ fail-closed); other families still use implicit **DE** for **opening** tools
  when unset (see implementations below).
- **Legacy** per-step flags remain supported so existing Railway configs keep working
  until operators migrate (including ENTSO‑E / ERA5 names without `_DE_` suffix).
  Legacy path does **not** consult the allowlist (preserves prior behavior).

Repo B remains authoritative for country / version / window validation on HTTP.

**Modifiers** (campaign, coverage-scan) stay on separate ``*_CAMPAIGN_ENABLED`` /
``*_COVERAGE_SCAN_ENABLED`` env vars — higher blast radius or different semantics than
single-slice bounded POSTs.
"""

from __future__ import annotations

import os
from typing import Literal

from tools.powerunits_era5_tier1_countries import (
    ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1 as BOUNDED_SLICE_ERA5_WEATHER_ISO2_V1,
)
from tools.powerunits_entsoe_market_bounded_countries import (
    ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1 as BOUNDED_ENTSOE_MARKET_ISO2_V1,
)
from tools.powerunits_entsoe_forecast_bounded_countries import (
    ALLOWED_BOUNDED_ENTSOE_FORECAST_COUNTRY_CODES_V1 as BOUNDED_ENTSOE_FORECAST_ISO2_V1,
)
MarketFeaturesStep = Literal["execute", "validate", "readiness", "summary"]
MarketDriverStep = Literal["execute", "validate", "readiness", "summary"]
EntsoeMarketBoundedStep = Literal["preflight", "execute", "validate", "summary"]
EntsoeForecastBoundedStep = Literal["preflight", "execute", "validate", "summary"]
OutageAwarenessBoundedStep = Literal["validate", "summary"]
OutageRepairBoundedStep = Literal["execute"]
Era5WeatherBoundedStep = Literal["preflight", "execute", "validate", "summary"]

MARKET_FEATURES_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED"
_MARKET_FEATURES_PRIMARY = MARKET_FEATURES_BOUNDED_PRIMARY_ENV
MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES"
)
_MARKET_FEATURES_ALLOWED = MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV
MARKET_FEATURES_BOUNDED_LEGACY_ENV: dict[MarketFeaturesStep, str] = {
    "execute": "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_EXECUTE_ENABLED",
    "validate": "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_VALIDATE_ENABLED",
    "readiness": "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_READINESS_ENABLED",
    "summary": "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_SUMMARY_ENABLED",
}
_MARKET_FEATURES_LEGACY = MARKET_FEATURES_BOUNDED_LEGACY_ENV

MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED"
_MARKET_DRIVER_PRIMARY = MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV
MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES"
)
_MARKET_DRIVER_ALLOWED = MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV
MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV: dict[MarketDriverStep, str] = {
    "execute": "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_EXECUTE_ENABLED",
    "validate": "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_VALIDATE_ENABLED",
    "readiness": "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_READINESS_ENABLED",
    "summary": "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_SUMMARY_ENABLED",
}
_MARKET_DRIVER_LEGACY = MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV

ENTSOE_MARKET_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED"
_ENTSOE_PRIMARY = ENTSOE_MARKET_BOUNDED_PRIMARY_ENV
ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES"
)
_ENTSOE_ALLOWED = ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV
ENTSOE_MARKET_BOUNDED_LEGACY_ENV: dict[EntsoeMarketBoundedStep, str] = {
    "preflight": "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED",
    "execute": "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED",
    "validate": "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED",
    "summary": "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED",
}
_ENTSOE_LEGACY = ENTSOE_MARKET_BOUNDED_LEGACY_ENV

ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED"
_ENTSOE_FORECAST_PRIMARY = ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV
ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES"
)
_ENTSOE_FORECAST_ALLOWED = ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV
ENTSOE_FORECAST_BOUNDED_LEGACY_ENV: dict[EntsoeForecastBoundedStep, str] = {
    "preflight": "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_PREFLIGHT_ENABLED",
    "execute": "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_EXECUTE_ENABLED",
    "validate": "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED",
    "summary": "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_SUMMARY_ENABLED",
}
_ENTSOE_FORECAST_LEGACY = ENTSOE_FORECAST_BOUNDED_LEGACY_ENV

OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED"
_OUTAGE_AWARENESS_PRIMARY = OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV
OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES"
)
_OUTAGE_AWARENESS_ALLOWED = OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV
OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV: dict[OutageAwarenessBoundedStep, str] = {
    "validate": "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED",
    "summary": "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED",
}
_OUTAGE_AWARENESS_LEGACY = OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV

OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED"
_OUTAGE_REPAIR_PRIMARY = OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV
OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES"
)
_OUTAGE_REPAIR_ALLOWED = OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV
OUTAGE_REPAIR_BOUNDED_LEGACY_ENV: dict[OutageRepairBoundedStep, str] = {
    "execute": "HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED",
}
_OUTAGE_REPAIR_LEGACY = OUTAGE_REPAIR_BOUNDED_LEGACY_ENV

ERA5_WEATHER_BOUNDED_PRIMARY_ENV = "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED"
_ERA5_PRIMARY = ERA5_WEATHER_BOUNDED_PRIMARY_ENV
ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV = (
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES"
)
_ERA5_ALLOWED = ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV
ERA5_WEATHER_BOUNDED_LEGACY_ENV: dict[Era5WeatherBoundedStep, str] = {
    "preflight": "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED",
    "execute": "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED",
    "validate": "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED",
    "summary": "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED",
}
_ERA5_LEGACY = ERA5_WEATHER_BOUNDED_LEGACY_ENV

# Implicit single-country fallback for primary allowlists across **DE-implicit** bounded families.
_IMPL_COUNTRY = "DE"


def era5_weather_bounded_request_country_permitted(iso2: str) -> bool:
    """
    Repo B authoritative validation still applies per HTTP POST; this intersections the
    **bounded ERA5 Hermes family's** slice vs ``HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES``
    when the primary ERA5 gate is truthy (**legacy paths keep ignoring** the env allowlist).
    """
    cc = (iso2 or "").strip().upper()
    if cc not in BOUNDED_SLICE_ERA5_WEATHER_ISO2_V1:
        return False
    if _truthy(_ERA5_PRIMARY):
        return cc in _allowed_countries_for_primary(_ERA5_ALLOWED)
    return True


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _allowed_countries_for_primary(allowed_env: str) -> frozenset[str]:
    raw = os.getenv(allowed_env)
    if raw is None:
        return frozenset({_IMPL_COUNTRY})
    if not raw.strip():
        return frozenset()
    return frozenset(p.strip().upper() for p in raw.split(",") if p.strip())


def _impl_country_allowed(allowed_env: str) -> bool:
    return _IMPL_COUNTRY in _allowed_countries_for_primary(allowed_env)


def market_features_bounded_step_enabled(step: MarketFeaturesStep) -> bool:
    if _truthy(_MARKET_FEATURES_PRIMARY):
        return _impl_country_allowed(_MARKET_FEATURES_ALLOWED)
    return _truthy(_MARKET_FEATURES_LEGACY[step])


def market_driver_features_bounded_step_enabled(step: MarketDriverStep) -> bool:
    if _truthy(_MARKET_DRIVER_PRIMARY):
        return _impl_country_allowed(_MARKET_DRIVER_ALLOWED)
    return _truthy(_MARKET_DRIVER_LEGACY[step])


def market_features_bounded_gate_requirement_text(step: MarketFeaturesStep) -> str:
    return (
        f"{_MARKET_FEATURES_PRIMARY} (recommended) or legacy {_MARKET_FEATURES_LEGACY[step]}, "
        f"and when using the primary flag optionally {_MARKET_FEATURES_ALLOWED} (default DE for current tools)"
    )


def market_driver_features_bounded_gate_requirement_text(step: MarketDriverStep) -> str:
    return (
        f"{_MARKET_DRIVER_PRIMARY} (recommended) or legacy {_MARKET_DRIVER_LEGACY[step]}, "
        f"and when using the primary flag optionally {_MARKET_DRIVER_ALLOWED} (default DE for current tools)"
    )


def entsoe_market_bounded_request_country_permitted(iso2: str) -> bool:
    """Repo B Tier v1 ∩ optional Hermes allowlist when ENTSO‑E primary is truthy; legacy ⇒ no narrowing."""
    cc = (iso2 or "").strip().upper()
    if cc not in BOUNDED_ENTSOE_MARKET_ISO2_V1:
        return False
    if _truthy(_ENTSOE_PRIMARY):
        return cc in _allowed_countries_for_primary(_ENTSOE_ALLOWED)
    return True


def entsoe_market_bounded_core_step_enabled(step: EntsoeMarketBoundedStep) -> bool:
    if _truthy(_ENTSOE_PRIMARY):
        # Explicit empty ALLOWED ⇒ fail‑closed; **unset** ⇒ tools open — per‑request narrowing via
        # `entsoe_market_bounded_request_country_permitted` (implicit DE-only when env absent).
        if _ENTSOE_ALLOWED in os.environ and not (os.getenv(_ENTSOE_ALLOWED) or "").strip():
            return False
        return True
    return _truthy(_ENTSOE_LEGACY[step])


def entsoe_market_bounded_gate_requirement_text(step: EntsoeMarketBoundedStep) -> str:
    return (
        f"{_ENTSOE_PRIMARY} (recommended) or legacy {_ENTSOE_LEGACY[step]}; "
        f"when using primary optionally {_ENTSOE_ALLOWED} (**unset ⇒ implicit DE-only per slice**; "
        "explicitly empty disallowlist ⇒ fail‑closed)"
    )


def entsoe_forecast_bounded_request_country_permitted(iso2: str) -> bool:
    """Repo B Tier v1 ∩ optional Hermes allowlist when forecast primary truthy; legacy ⇒ no narrowing."""
    cc = (iso2 or "").strip().upper()
    if cc not in BOUNDED_ENTSOE_FORECAST_ISO2_V1:
        return False
    if _truthy(_ENTSOE_FORECAST_PRIMARY):
        return cc in _allowed_countries_for_primary(_ENTSOE_FORECAST_ALLOWED)
    return True


def entsoe_forecast_bounded_core_step_enabled(step: EntsoeForecastBoundedStep) -> bool:
    if _truthy(_ENTSOE_FORECAST_PRIMARY):
        if _ENTSOE_FORECAST_ALLOWED in os.environ and not (os.getenv(_ENTSOE_FORECAST_ALLOWED) or "").strip():
            return False
        return True
    return _truthy(_ENTSOE_FORECAST_LEGACY[step])


def entsoe_forecast_bounded_gate_requirement_text(step: EntsoeForecastBoundedStep) -> str:
    return (
        f"{_ENTSOE_FORECAST_PRIMARY} (recommended) or legacy {_ENTSOE_FORECAST_LEGACY[step]}; "
        f"when using primary optionally {_ENTSOE_FORECAST_ALLOWED} (**unset ⇒ implicit DE-only per slice**; "
        "explicitly empty disallowlist ⇒ fail‑closed)"
    )


def outage_awareness_bounded_core_step_enabled(step: OutageAwarenessBoundedStep) -> bool:
    if _truthy(_OUTAGE_AWARENESS_PRIMARY):
        return _impl_country_allowed(_OUTAGE_AWARENESS_ALLOWED)
    return _truthy(_OUTAGE_AWARENESS_LEGACY[step])


def outage_awareness_bounded_gate_requirement_text(step: OutageAwarenessBoundedStep) -> str:
    return (
        f"{_OUTAGE_AWARENESS_PRIMARY} (recommended) or legacy {_OUTAGE_AWARENESS_LEGACY[step]}; "
        f"when using primary optionally {_OUTAGE_AWARENESS_ALLOWED} (implicit DE when unset)"
    )


def outage_repair_bounded_core_step_enabled(step: OutageRepairBoundedStep) -> bool:
    if _truthy(_OUTAGE_REPAIR_PRIMARY):
        return _impl_country_allowed(_OUTAGE_REPAIR_ALLOWED)
    return _truthy(_OUTAGE_REPAIR_LEGACY[step])


def outage_repair_bounded_gate_requirement_text(step: OutageRepairBoundedStep) -> str:
    return (
        f"{_OUTAGE_REPAIR_PRIMARY} (recommended) or legacy {_OUTAGE_REPAIR_LEGACY[step]}; "
        f"when using primary optionally {_OUTAGE_REPAIR_ALLOWED} (implicit DE when unset)"
    )


def era5_weather_bounded_core_step_enabled(step: Era5WeatherBoundedStep) -> bool:
    if _truthy(_ERA5_PRIMARY):
        # Primary path: fail-closed only when **`ALLOWED`** is explicitly set to blank.
        # If the env var is **absent**, `era5_weather_bounded_request_country_permitted()` still
        # defaults outbound ISO2 narrowing to `{DE}`. Any **non‑empty** list opens the ERA5 bounded
        # tool surface (narrowing enforced per-request against Tier‑1 ∩ allowlist).
        if _ERA5_ALLOWED in os.environ and not (os.getenv(_ERA5_ALLOWED) or "").strip():
            return False
        return True
    return _truthy(_ERA5_LEGACY[step])


def era5_weather_bounded_gate_requirement_text(step: Era5WeatherBoundedStep) -> str:
    return (
        f"{_ERA5_PRIMARY} (recommended) or legacy {_ERA5_LEGACY[step]}; "
        f"when using primary optionally {_ERA5_ALLOWED} (**unset ⇒ implicit DE-only narrowing per HTTP "
        "request**; explicitly empty disallowlist ⇒ fail‑closed;"
        " any **non‑empty comma list ⇒ tool surface open**, intersection against Tier‑1 at request)"
    )


def campaign_entsoe_bounded_http_primitives_enabled() -> bool:
    """Execute + summary must both be acceptable for chained campaign POSTs."""
    return entsoe_market_bounded_core_step_enabled("execute") and entsoe_market_bounded_core_step_enabled(
        "summary"
    )


def campaign_era5_bounded_http_primitives_enabled() -> bool:
    return era5_weather_bounded_core_step_enabled("execute") and era5_weather_bounded_core_step_enabled(
        "summary"
    )


# Cross-cutting read-only **coverage inventory** (multi-family POST to Repo B v1 inventory route).
BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV = "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED"


def bounded_coverage_inventory_enabled() -> bool:
    return _truthy(BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV)


def bounded_coverage_inventory_requirement_text() -> str:
    return (
        f"{BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV} must be truthy (read-only Repo B aggregation; "
        "Hermes carries no authoritative inventory matrix)"
    )