"""
Shared local slice validation for bounded ENTSO-E **forecast** Hermes tools (DE / v1 / ≤7d).

No registry.register — imported by entsoe forecast bounded tool modules only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


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


def validate_entsoe_forecast_bounded_slice(
    country: str,
    start_s: str,
    end_s: str,
    version: str,
) -> tuple[str, datetime, datetime]:
    cc = (country or "").strip().upper()
    if cc != "DE":
        raise ValueError("country must be DE for bounded entsoe_forecast_sync v1")
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
