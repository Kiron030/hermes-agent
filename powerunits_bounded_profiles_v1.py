"""
Bounded env **profiles** for Powerunits Hermes (v1).

Operators set one profile on Railway instead of dozens of individual gates::

    HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health

At container start ``docker/apply_powerunits_runtime_policy.py`` calls
:func:`apply_bounded_profile_to_process_env` **before** gateway tools load.
Explicit Railway env vars are **never overwritten** (override wins).
"""

from __future__ import annotations

import os
from typing import Any, Final

PROFILE_ENV: Final[str] = "HERMES_POWERUNITS_BOUNDED_PROFILE"

# Read-only data health + bounded reads (no primary execute families).
STAGE1_READ_HEALTH: Final[dict[str, str]] = {
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED": "1",
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED": "1",
    "HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED": "1",
    "HERMES_POWERUNITS_REPO_B_READ_ENABLED": "1",
    "HERMES_POWERUNITS_TIMESCALE_READ_ENABLED": "1",
    "HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED": "1",
    "HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED": "1",
    "HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED": "1",
    # Validate/summary/readiness via legacy per-step keys (no primary ⇒ no execute).
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_READINESS_ENABLED": "1",
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED": "1",
}

# Full Stage-1 operator: read_health + bounded execute families (DE/PL market features, ENTSO-E, ERA5, outage repair).
STAGE1_OPERATOR_EXECUTE: Final[dict[str, str]] = {
    **STAGE1_READ_HEALTH,
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED": "1",
}

PROFILE_ENV_EXPANSIONS_V1: Final[dict[str, dict[str, str]]] = {
    "stage1_read_health": STAGE1_READ_HEALTH,
    "stage1_operator_execute": STAGE1_OPERATOR_EXECUTE,
}

PROFILE_DESCRIPTIONS_V1: Final[dict[str, str]] = {
    "stage1_read_health": (
        "Data-health triptychon + bounded reads/validates; no primary execute families."
    ),
    "stage1_operator_execute": (
        "read_health plus bounded execute (market features, ENTSO-E, ERA5, outage repair)."
    ),
}


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def active_bounded_profile_id() -> str | None:
    raw = (os.getenv(PROFILE_ENV) or "").strip().lower()
    return raw or None


def apply_bounded_profile_to_process_env() -> dict[str, Any]:
    """Fill missing profile env keys; never override explicit Railway values."""
    profile = active_bounded_profile_id()
    if not profile:
        return {"profile": None, "applied": [], "skipped_explicit": [], "unknown": False}

    expansion = PROFILE_ENV_EXPANSIONS_V1.get(profile)
    if expansion is None:
        return {
            "profile": profile,
            "unknown": True,
            "applied": [],
            "skipped_explicit": [],
            "known_profiles": sorted(PROFILE_ENV_EXPANSIONS_V1.keys()),
        }

    applied: list[str] = []
    skipped_explicit: list[str] = []
    for key, value in expansion.items():
        if (os.getenv(key) or "").strip():
            skipped_explicit.append(key)
        else:
            os.environ[key] = value
            applied.append(key)

    return {
        "profile": profile,
        "unknown": False,
        "description": PROFILE_DESCRIPTIONS_V1.get(profile),
        "applied": applied,
        "skipped_explicit": skipped_explicit,
        "total_keys_in_profile": len(expansion),
    }


def evaluate_bounded_profile_alignment() -> dict[str, Any]:
    """Compare active profile (if any) against current process env."""
    profile = active_bounded_profile_id()
    if not profile:
        return {"profile": None, "aligned": None, "missing_truthy": [], "unknown_profile": False}

    expansion = PROFILE_ENV_EXPANSIONS_V1.get(profile)
    if expansion is None:
        return {
            "profile": profile,
            "aligned": False,
            "unknown_profile": True,
            "missing_truthy": [],
            "known_profiles": sorted(PROFILE_ENV_EXPANSIONS_V1.keys()),
        }

    missing: list[str] = []
    for key in expansion:
        if not _truthy(os.getenv(key)):
            missing.append(key)

    return {
        "profile": profile,
        "description": PROFILE_DESCRIPTIONS_V1.get(profile),
        "unknown_profile": False,
        "aligned": len(missing) == 0,
        "missing_truthy": missing,
        "missing_count": len(missing),
        "total_keys_in_profile": len(expansion),
    }
