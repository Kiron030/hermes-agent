"""Tier‑1 bounded ERA5 weather ISO2 codes (Hermes mirror of Repo B).

Keep in parity with Repo B ``services.internal.hermes_bounded_era5_countries`` /
``ERA5_COUNTRY_BBOXES`` keys.

When adding a bbox key there, bump this tuple in **the same change** across both repos.

Use ``GB`` for the United Kingdom; ``UK`` is not a bbox key but is normalized in ingest.
"""

from __future__ import annotations

# Sorted stable list; mirrors Era5 ERA5_COUNTRY_BBOXES keys at bounded Tier‑1 enablement time.
TIER_1_BOUNDED_ISO2_SORTED_V1: tuple[str, ...] = (
    "AT",
    "BE",
    "CZ",
    "DE",
    "DK",
    "ES",
    "FI",
    "FR",
    "GB",
    "HU",
    "IE",
    "IT",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SE",
    "SK",
)

ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1: frozenset[str] = frozenset(
    TIER_1_BOUNDED_ISO2_SORTED_V1
)
