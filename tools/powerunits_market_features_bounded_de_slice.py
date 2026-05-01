"""
Local slice validation for Hermes **DE** bounded `market_features_hourly` tools.

Matches Repo B `validate_bounded_slice` for `country_code=DE`: `version=v1`, window
`> 0` and `<= 24` hours UTC, exclusive end.

No `registry.register` — imported by DE-only Hermes tools only. **PL** Option D
uses `tools.powerunits_option_d_bounded_market_features._validate_slice` instead.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_DE = "DE"


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


def validate_de_market_features_bounded_window(
    start_s: str, end_s: str, version: str
) -> tuple[str, str, str, datetime, datetime]:
    """
    Return ``(country_code, version, start_trimmed, end_trimmed, start_dt, end_dt)``.
    """
    ver = (version or "").strip()
    if ver != "v1":
        raise ValueError("version must be v1 for bounded market_features_hourly DE release")
    st = (start_s or "").strip()
    en = (end_s or "").strip()
    start = _parse_utc_iso(st)
    end = _parse_utc_iso(en)
    if end <= start:
        raise ValueError("window_end_utc must be strictly after window_start_utc (exclusive end)")
    delta = end - start
    if delta <= timedelta(0):
        raise ValueError("window must be > 0")
    if delta > timedelta(hours=24):
        raise ValueError("window must be <= 24 hours for bounded market_features_hourly")
    return _DE, ver, st, en, start, end
