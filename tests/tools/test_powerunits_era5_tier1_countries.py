from __future__ import annotations

from tools import powerunits_bounded_family_gates as g
from tools.powerunits_era5_tier1_countries import (
    ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1 as TIER1_ALLOWED,
)


def test_tier1_mirror_matches_bounded_slice_gate() -> None:
    assert TIER1_ALLOWED == g.BOUNDED_SLICE_ERA5_WEATHER_ISO2_V1
    assert len(TIER1_ALLOWED) == 19
