"""Repo B mirror: empirical ENTSO-E candidate validate ISO2 (ADR 045).

Keep in sync with EU-PP-Database
``services.internal.hermes_bounded_entsoe_empirical_candidate.ALLOWED_EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1``.
"""

from __future__ import annotations

ALLOWED_EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1: frozenset[str] = frozenset({"DK", "NO", "IE"})

EMPIRICAL_CANDIDATE_EXCLUDED_POLICY_ISO2_V1: frozenset[str] = frozenset({"ES", "IT", "SE"})

EMPIRICAL_ENTSOE_CANDIDATE_USER_FACING_ISO2_DOCUMENTATION_V1 = (
    "Empirical ENTSO-E candidate ISO2 only: **`DK`**, **`NO`**, **`IE`** — read-only validate-window "
    "(**not** Tier-1 bounded execute). Tier-1 live ISO2 use `validate_powerunits_entsoe_market_bounded_window` "
    "and forecast bounded validate. **`ES`/`IT`/`SE`** use separate policy track."
)
