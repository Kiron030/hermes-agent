"""Consolidated Hermes gates for Repo B bounded **families**.

Design:
- One **primary** ``HERMES_*_ENABLED`` flag per family (no country suffix).
- Optional ``HERMES_*_ALLOWED_COUNTRIES`` comma list (uppercase ISO2). When the primary
  flag is set, an empty / missing allowlist defaults to **DE** for the current
  DE-only tool implementations. Empty string → no countries → fail-closed.
- **Legacy** per-step / ``_DE_`` flags remain supported so existing Railway configs keep
  working until operators migrate. Legacy path does **not** consult the allowlist
  (preserves prior behavior and avoids accidental lockout).

Repo B remains authoritative for country / version / window validation on HTTP.
"""

from __future__ import annotations

import os
from typing import Literal

MarketFeaturesStep = Literal["execute", "validate", "readiness", "summary"]
MarketDriverStep = Literal["execute", "validate", "readiness", "summary"]

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

# Current Hermes tools for both families only emit **DE**; allowlist must include DE
# when primary is used (or unset allowlist → implicit DE).
_IMPL_COUNTRY = "DE"


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
