"""
Operator country scope v1 — Hermes mirror of Repo B bounded Tier-1 sets.

Use for multi-country triptychon, analyst synthesis, and posture readouts.
Repo B remains authoritative; Hermes ``*_ALLOWED_COUNTRIES`` may narrow only.
"""

from __future__ import annotations

from typing import Any, Final

from tools.powerunits_entsoe_forecast_bounded_countries import (
    ALLOWED_BOUNDED_ENTSOE_FORECAST_COUNTRY_CODES_V1,
)
from tools.powerunits_entsoe_market_bounded_countries import (
    ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1,
)
from tools.powerunits_era5_tier1_countries import TIER_1_BOUNDED_ISO2_SORTED_V1

# National worker + ENTSO-E market/forecast Tier-1 (11 ISO2).
NATIONAL_TIER1_ISO2_V1: Final[tuple[str, ...]] = tuple(
    sorted(ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1)
)

ERA5_TIER1_ISO2_V1: Final[tuple[str, ...]] = TIER_1_BOUNDED_ISO2_SORTED_V1

ERA5_TIER1_CSV_V1: Final[str] = ",".join(ERA5_TIER1_ISO2_V1)

# Repo B market_features_hourly bounded execute (not full national tier).
MARKET_FEATURES_ISO2_V1: Final[tuple[str, ...]] = ("DE", "PL")

# Repo B market_driver_features_hourly bounded execute.
MARKET_DRIVER_ISO2_V1: Final[tuple[str, ...]] = ("DE",)

# Outage awareness + repair v1.
OUTAGE_ISO2_V1: Final[tuple[str, ...]] = ("DE",)

# BZN advisory reads (separate from national tier).
BZN_ADVISORY_ISO2_V1: Final[tuple[str, ...]] = ("DK", "NO", "SE", "IT", "IE")

# ADR 045 empirical ENTSO-E candidate validate (read-only; not Tier-1 bounded execute).
EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1: Final[tuple[str, ...]] = ("DK", "NO", "IE")

# Separate price-policy rollout track — not empirical HTTP, not Tier-1 mirror.
POLICY_HOLD_COMPLEX_PRICE_ISO2_V1: Final[tuple[str, ...]] = ("ES", "IT", "SE")

DEFAULT_TRIPTYCHON_NATIONAL_ISO2_V1: Final[tuple[str, ...]] = NATIONAL_TIER1_ISO2_V1


def default_triptychon_country_codes() -> list[str]:
    return list(DEFAULT_TRIPTYCHON_NATIONAL_ISO2_V1)


def normalize_country_codes(raw: Any) -> tuple[list[str] | None, str | None]:
    if raw is None:
        return list(NATIONAL_TIER1_ISO2_V1), None
    if isinstance(raw, str):
        parts = [p.strip().upper() for p in raw.replace(";", ",").split(",") if p.strip()]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip().upper() for p in raw if str(p).strip()]
    else:
        return None, "country_codes must be comma string or list of ISO2 codes"
    if not parts:
        return None, "country_codes must not be empty"
    return parts, None


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def era5_entsoe_scope_asymmetry_caution_flags_v1() -> list[str]:
    """
    Read-only comparison of effective **bounded ENTSO-E** national mirror scope vs
    effective **bounded ERA5** weather scope.

    Surfaces a caution when an operator has opened ENTSO-E market and/or forecast
    bounded reads with an **unset** allowlist (Repo B Tier-1 mirror — up to
    ``len(NATIONAL_TIER1_ISO2_V1)`` ISO2) while ERA5 weather bounded stays on its
    **unset-allowlist implicit DE-only** default (see
    ``tools/powerunits_bounded_family_gates.py`` — ERA5 primary narrows to DE when
    its allowlist env is absent; ENTSO-E primary does not narrow when its allowlist
    env is absent). Purely informational: does not change any gate, and Repo B
    remains authoritative on country/version/window validation.
    """
    import os

    from tools.powerunits_bounded_family_gates import (
        ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV,
        ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV,
        ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
        ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
        ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
        ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
    )

    if not _truthy(os.getenv(ERA5_WEATHER_BOUNDED_PRIMARY_ENV)):
        return []
    if os.getenv(ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV) is not None:
        # Operator made an explicit ERA5 scope choice — not a silent default asymmetry.
        return []

    entsoe_families = (
        (ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV, "market"),
        (ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "forecast"),
    )
    flags: list[str] = []
    for primary_env, allowed_env, label in entsoe_families:
        if not _truthy(os.getenv(primary_env)):
            continue
        if os.getenv(allowed_env) is not None:
            # Explicit ENTSO-E allowlist — operator already narrowed intentionally.
            continue
        flags.append(
            f"era5_entsoe_scope_asymmetry:entsoe_{label}_bounded_open_across_national_tier1_"
            f"{len(NATIONAL_TIER1_ISO2_V1)}_iso2_via_unset_{allowed_env}_but_era5_bounded_"
            f"unset_{ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV}_stays_de_only_weather_"
            "features_will_be_thin_outside_de"
        )
    return flags


def operator_country_scope_summary_v1() -> dict[str, Any]:
    """Read-only matrix for posture / operator docs."""
    return {
        "national_tier1_entsoe_market_forecast_worker": list(NATIONAL_TIER1_ISO2_V1),
        "era5_tier1_weather_bbox_keys": list(ERA5_TIER1_ISO2_V1),
        "market_features_bounded_execute": list(MARKET_FEATURES_ISO2_V1),
        "market_driver_bounded_execute": list(MARKET_DRIVER_ISO2_V1),
        "outage_awareness_repair_v1": list(OUTAGE_ISO2_V1),
        "bzn_advisory_reads": list(BZN_ADVISORY_ISO2_V1),
        "empirical_entsoe_candidate_read_only": list(EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1),
        "policy_hold_complex_price_rollout": list(POLICY_HOLD_COMPLEX_PRICE_ISO2_V1),
        "default_triptychon_national": list(DEFAULT_TRIPTYCHON_NATIONAL_ISO2_V1),
        "tier2_not_in_default_triptychon_reason": (
            "Empirical/policy-hold ISO2 use separate Repo B surfaces; "
            "orchestrator defaults to national Tier-1 only."
        ),
        "entsoe_forecast_mirror_equals_market": sorted(
            ALLOWED_BOUNDED_ENTSOE_FORECAST_COUNTRY_CODES_V1
        )
        == sorted(ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1),
        "hermes_era5_allowlist_unset_means": "DE-only (set profile or ERA5_*_ALLOWED_COUNTRIES for Tier-1)",
        "hermes_entsoe_allowlist_unset_means": "full national Tier-1 mirror (11 ISO2)",
    }
