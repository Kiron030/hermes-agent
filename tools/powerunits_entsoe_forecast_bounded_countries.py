"""
Bounded ENTSO-E forecast ISO2 Tier v1 (mirror Repo B bounded allowlist).

Keep in sync with ``services.internal.hermes_bounded_entsoe_forecast_countries`` in EU-PP-Database.
"""

from __future__ import annotations

ALLOWED_BOUNDED_ENTSOE_FORECAST_COUNTRY_CODES_V1: frozenset[str] = frozenset(
    {"DE", "NL", "BE", "FR", "AT", "CZ", "PL"}
)

BOUNDED_ENTSOE_FORECAST_USER_FACING_ISO2_DOCUMENTATION_V1 = (
    "Repo B Tier v1 bounded ENTSO-E forecast: **`DE`**, **`NL`**, **`BE`**, **`FR`**, **`AT`**, **`CZ`**, **`PL`** "
    "(expandable bounded set; aligns with Repo B market Tier-v1)."
)
