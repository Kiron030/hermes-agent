"""
Shared local slice validation for bounded ERA5 weather sync Hermes tools (allowlisted ISO2 / v1 / ≤7d).

Keep allowlist in sync with Repo B Tier‑1 (see ``powerunits_era5_tier1_countries``).
No registry.register.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.powerunits_era5_tier1_countries import (
    ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1,
)

_MAX_SUBWINDOW_DAYS = 7
_MAX_CAMPAIGN_SPAN_DAYS = 31
_MAX_CAMPAIGN_WINDOWS = 5


def _parse_utc_iso(s: str) -> datetime:
    raw = (s or "").strip()
    if not raw:
        raise ValueError("timestamp must be non-empty")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware (use Z suffix)")
    return dt.astimezone(timezone.utc)


def validate_era5_bounded_slice(
    country: str,
    start_s: str,
    end_s: str,
    version: str,
) -> tuple[str, datetime, datetime]:
    cc = (country or "").strip().upper()
    if cc not in ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1:
        opts = ", ".join(sorted(ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1))
        raise ValueError(f"country must be one of [{opts}] for bounded era5_weather_sync v1")
    if (version or "").strip() != "v1":
        raise ValueError("version must be v1 for this release")
    start = _parse_utc_iso(start_s)
    end = _parse_utc_iso(end_s)
    if end <= start:
        raise ValueError("end must be strictly after start (exclusive end semantics)")
    delta = end - start
    if delta <= timedelta(0):
        raise ValueError("window must be > 0")
    if delta > timedelta(days=7):
        raise ValueError("window must be <= 7 days")
    return cc, start, end


def plan_era5_bounded_campaign_windows(
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    """
    Partition [start, end) into contiguous sub-windows each with duration ≤ 7 days.

    Assumes ``end > start``. Caller validates campaign span separately.
    """
    max_chunk = timedelta(days=_MAX_SUBWINDOW_DAYS)
    windows: list[tuple[datetime, datetime]] = []
    cur = start
    while cur < end:
        nxt = min(cur + max_chunk, end)
        if nxt <= cur:
            break
        windows.append((cur, nxt))
        cur = nxt
    return windows


def validate_era5_bounded_campaign(
    country: str,
    campaign_start_s: str,
    campaign_end_s: str,
    version_s: str,
) -> tuple[str, str, list[tuple[datetime, datetime]]]:
    """
    Allowlisted ISO2 / v1 only. Campaign [start,end) exclusive; total span ≤ 31 days;
    contiguous ≤7d slices; resulting slice count ≤ 5.
    """
    cc = (country or "").strip().upper()
    if cc not in ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1:
        opts = ", ".join(sorted(ALLOWED_BOUNDED_ERA5_WEATHER_COUNTRY_CODES_V1))
        raise ValueError(f"country must be one of [{opts}] for bounded era5_weather_sync v1 campaign")
    ver = (version_s or "").strip()
    if ver != "v1":
        raise ValueError("version must be v1 for this release")
    start = _parse_utc_iso(campaign_start_s)
    end = _parse_utc_iso(campaign_end_s)
    if end <= start:
        raise ValueError(
            "campaign_end_utc must be strictly after campaign_start_utc (exclusive end semantics)"
        )
    delta = end - start
    if delta > timedelta(days=_MAX_CAMPAIGN_SPAN_DAYS):
        raise ValueError(f"campaign span must be <= {_MAX_CAMPAIGN_SPAN_DAYS} days")
    windows = plan_era5_bounded_campaign_windows(start, end)
    if len(windows) > _MAX_CAMPAIGN_WINDOWS:
        raise ValueError(
            f"campaign splits into more than {_MAX_CAMPAIGN_WINDOWS} windows; reduce span"
        )
    return cc, ver, windows
