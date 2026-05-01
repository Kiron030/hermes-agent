"""
Local slice validation for bounded baseline layer-coverage-preview Hermes tools (DE / v1 / ≤31d).

Mirrors Repo B ``validate_baseline_layer_preview_slice`` semantics (single contiguous window).
No registry.register.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_PREVIEW_MAX_SPAN_DAYS = 31
_PREVIEW_VERSION = "v1"
_PREVIEW_COUNTRY = "DE"


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


def validate_baseline_preview_slice(
    country: str,
    preview_start_s: str,
    preview_end_s: str,
    version: str,
) -> tuple[str, str, str, str]:
    """Return (country_code, version, start_s_trimmed, end_s_trimmed) after validation."""
    cc = (country or "").strip().upper()
    if cc != _PREVIEW_COUNTRY:
        raise ValueError(
            f"country must be {_PREVIEW_COUNTRY} for bounded baseline layer-coverage-preview v1"
        )
    ver = (version or "").strip()
    if ver != _PREVIEW_VERSION:
        raise ValueError("version must be v1 for this release")
    start = _parse_utc_iso(preview_start_s)
    end = _parse_utc_iso(preview_end_s)
    start_s_t = (preview_start_s or "").strip()
    end_s_t = (preview_end_s or "").strip()
    if end <= start:
        raise ValueError(
            "preview_end_utc must be strictly after preview_start_utc (exclusive end semantics)"
        )
    delta = end - start
    if delta > timedelta(days=_PREVIEW_MAX_SPAN_DAYS):
        raise ValueError(f"preview span must be <= {_PREVIEW_MAX_SPAN_DAYS} days")
    return cc, ver, start_s_t, end_s_t
