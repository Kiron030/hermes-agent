"""Repo B mirror: bounded ENTSO-E **market** v1 ISO2 allowlist (Hermes preflight only).

Keep in sync with EU-PP-Database
``services.internal.hermes_bounded_entsoe_market_countries``.
"""

from __future__ import annotations

ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1: frozenset[str] = frozenset({"DE", "NL"})

BOUNDED_ENTSOE_MARKET_USER_FACING_ISO2_DOCUMENTATION_V1 = (
    "Repo B bounded v1 ENTSO-E market ISO2: **`DE`** or **`NL`** only (expandable Tier; same "
    "`entsoe_market_job` path). With primary `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`, "
    "outbound requests also intersect `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`; "
    "**unset** ⇒ implicit **DE**-only narrowing; **explicit empty** allowlist ⇒ fail‑closed."
)
