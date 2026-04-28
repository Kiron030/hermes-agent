#!/usr/bin/env python3
"""
Staged, bounded read-only access to Powerunits Timescale (operator/research).

Single source: public.market_price_model_dataset_v only.
No free-form SQL, no arbitrary tables, no schema browsing.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

logger = logging.getLogger(__name__)

SOURCE_VIEW = "public.market_price_model_dataset_v"

ALLOWED_COUNTRY_CODES: frozenset[str] = frozenset({"DE", "FR", "NL", "BE", "ES"})
ALLOWED_VERSIONS: frozenset[str] = frozenset({"v1"})
ALLOWED_PATTERN_IDS: frozenset[str] = frozenset(
    {
        "recent_rows_by_country",
        "recent_window_summary_by_country",
    }
)
# Public Hermes window_id tokens (mapped to hour spans; end is floor-to-hour UTC "now").
WINDOW_ID_HOURS: dict[str, int] = {
    "last_24h": 24,
    "last_72h": 72,
    "last_7d": 7 * 24,
}

DEFAULT_ROW_LIMIT = 72
MAX_ROW_LIMIT = 240

_ALLOWED_ARG_KEYS = frozenset(
    {"pattern_id", "country_code", "version", "window_id", "row_limit"}
)

_FEATURE_ENV = "HERMES_POWERUNITS_TIMESCALE_READ_ENABLED"
_TIMESCALE_URL_ENV = "DATABASE_URL_TIMESCALE"


class TimescaleReadToolError(ValueError):
    """Invalid tool inputs (fail closed)."""


def _env_flag_enabled() -> bool:
    raw = (os.getenv(_FEATURE_ENV) or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _timescale_db_url() -> str | None:
    url = (os.getenv(_TIMESCALE_URL_ENV) or "").strip()
    return url or None


def check_powerunits_timescale_read_requirements() -> bool:
    if not _env_flag_enabled():
        return False
    if not _timescale_db_url():
        return False
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False
    return True


def _floor_to_hour_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(minute=0, second=0, microsecond=0)


def _window_bounds(window_id: str, *, end_utc: datetime | None = None) -> tuple[datetime, datetime]:
    if window_id not in WINDOW_ID_HOURS:
        raise TimescaleReadToolError(
            f"window_id must be one of: {sorted(WINDOW_ID_HOURS.keys())}"
        )
    end = _floor_to_hour_utc(end_utc or datetime.now(timezone.utc))
    hours = WINDOW_ID_HOURS[window_id]
    start = end - timedelta(hours=hours)
    return start, end


def _validate_country(country_code: str) -> str:
    c = (country_code or "").strip().upper()
    if c not in ALLOWED_COUNTRY_CODES:
        raise TimescaleReadToolError(
            f"country_code must be one of: {sorted(ALLOWED_COUNTRY_CODES)}"
        )
    return c


def _validate_version(version: str) -> str:
    v = (version or "").strip()
    if v not in ALLOWED_VERSIONS:
        raise TimescaleReadToolError(f"version must be one of: {sorted(ALLOWED_VERSIONS)}")
    return v


def _validate_row_limit(raw: Any, *, pattern_id: str) -> int | None:
    if pattern_id == "recent_window_summary_by_country":
        if raw is not None:
            raise TimescaleReadToolError("row_limit is not allowed for this pattern_id")
        return None
    if raw is None:
        return DEFAULT_ROW_LIMIT
    if isinstance(raw, bool):
        raise TimescaleReadToolError("row_limit must be an integer")
    if isinstance(raw, int):
        lim = raw
    elif isinstance(raw, float) and raw.is_integer():
        lim = int(raw)
    else:
        try:
            lim = int(raw)
        except (TypeError, ValueError):
            raise TimescaleReadToolError("row_limit must be an integer")
    if lim < 1 or lim > MAX_ROW_LIMIT:
        raise TimescaleReadToolError(f"row_limit must be between 1 and {MAX_ROW_LIMIT}")
    return lim


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ts_to_utc_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _log_outcome(
    *,
    pattern_id: str,
    country_code: str,
    version: str,
    window_id: str,
    row_limit_requested: int | None,
    rows_returned: int | None,
    outcome: str,
) -> None:
    logger.info(
        "timescale_read target=timescale pattern_id=%s country_code=%s version=%s "
        "window_id=%s row_limit_requested=%s rows_returned=%s outcome=%s",
        pattern_id,
        country_code,
        version,
        window_id,
        row_limit_requested,
        rows_returned,
        outcome,
    )


_SQL_RECENT_ROWS = f"""
    SELECT
        timestamp_utc,
        price_eur_mwh,
        demand_mw,
        renewable_share,
        residual_load_mw,
        thermal_share
    FROM {SOURCE_VIEW}
    WHERE country_code = %s
      AND version = %s
      AND timestamp_utc >= %s
      AND timestamp_utc < %s
    ORDER BY timestamp_utc DESC
    LIMIT %s;
"""

_SQL_WINDOW_SUMMARY = f"""
    SELECT
        COUNT(*)::bigint AS row_count,
        AVG(price_eur_mwh)::double precision AS avg_price_eur_mwh,
        AVG(demand_mw)::double precision AS avg_demand_mw,
        AVG(renewable_share)::double precision AS avg_renewable_share,
        AVG(residual_load_mw)::double precision AS avg_residual_load_mw,
        AVG(thermal_share)::double precision AS avg_thermal_share
    FROM {SOURCE_VIEW}
    WHERE country_code = %s
      AND version = %s
      AND timestamp_utc >= %s
      AND timestamp_utc < %s;
"""


def _run_db(
    db_url: str,
    sql: str,
    params: list[Any],
    *,
    mode: str,
) -> list[dict[str, Any]] | dict[str, Any]:
    import psycopg
    import psycopg.rows

    with psycopg.connect(db_url) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params)
            if mode == "all":
                return list(cur.fetchall() or [])
            row = cur.fetchone()
            return dict(row or {})


def read_powerunits_timescale_dataset(
    args: Mapping[str, Any],
    *,
    _db_runner: Callable[..., list[dict[str, Any]] | dict[str, Any]] | None = None,
    **_: Any,
) -> str:
    """Bounded read against market_price_model_dataset_v (Timescale URL only)."""
    from tools.registry import tool_error

    if not _env_flag_enabled():
        _log_outcome(
            pattern_id=str(args.get("pattern_id") or ""),
            country_code=str(args.get("country_code") or ""),
            version=str(args.get("version") or ""),
            window_id=str(args.get("window_id") or ""),
            row_limit_requested=None,
            rows_returned=None,
            outcome="disabled_feature_flag",
        )
        return tool_error(
            f"{_FEATURE_ENV} must be set to a truthy value (e.g. 1) to use this tool."
        )

    db_url = _timescale_db_url()
    if not db_url:
        _log_outcome(
            pattern_id=str(args.get("pattern_id") or ""),
            country_code=str(args.get("country_code") or ""),
            version=str(args.get("version") or ""),
            window_id=str(args.get("window_id") or ""),
            row_limit_requested=None,
            rows_returned=None,
            outcome="disabled_missing_database_url_timescale",
        )
        return tool_error(
            f"{_TIMESCALE_URL_ENV} is not set; Timescale read is unavailable."
        )

    extra = set(args.keys()) - _ALLOWED_ARG_KEYS
    if extra:
        _log_outcome(
            pattern_id=str(args.get("pattern_id") or ""),
            country_code=str(args.get("country_code") or ""),
            version=str(args.get("version") or ""),
            window_id=str(args.get("window_id") or ""),
            row_limit_requested=None,
            rows_returned=None,
            outcome="rejected_unknown_arguments",
        )
        return tool_error(f"Unknown arguments: {sorted(extra)}")

    pattern_id = (args.get("pattern_id") or "").strip()
    country_code = args.get("country_code")
    version = args.get("version")
    window_id = (args.get("window_id") or "").strip()
    row_limit_raw = args.get("row_limit")

    try:
        if pattern_id not in ALLOWED_PATTERN_IDS:
            raise TimescaleReadToolError(
                f"pattern_id must be one of: {sorted(ALLOWED_PATTERN_IDS)}"
            )
        cc = _validate_country(str(country_code or ""))
        ver = _validate_version(str(version or ""))
        row_limit = _validate_row_limit(row_limit_raw, pattern_id=pattern_id)
        start_utc, end_utc = _window_bounds(window_id)
    except TimescaleReadToolError as e:
        _log_outcome(
            pattern_id=pattern_id or "(empty)",
            country_code=str(country_code or ""),
            version=str(version or ""),
            window_id=window_id or "(empty)",
            row_limit_requested=None,
            rows_returned=None,
            outcome="rejected_input",
        )
        return tool_error(str(e))

    runner = _db_runner or _run_db

    try:
        if pattern_id == "recent_rows_by_country":
            assert row_limit is not None
            rows = runner(
                db_url,
                _SQL_RECENT_ROWS,
                [cc, ver, start_utc, end_utc, row_limit],
                mode="all",
            )
            assert isinstance(rows, list)
            payload = {
                "pattern_id": pattern_id,
                "source_view": SOURCE_VIEW,
                "data_plane": "timescale",
                "market": {"country_code": cc},
                "window_utc": {
                    "window_id": window_id,
                    "start": _iso_utc(start_utc),
                    "end": _iso_utc(end_utc),
                },
                "version": ver,
                "row_limit": row_limit,
                "row_count_returned": len(rows),
                "rows": [
                    {
                        "timestamp_utc": _ts_to_utc_string(r.get("timestamp_utc")),
                        "price_eur_mwh": _float_or_none(r.get("price_eur_mwh")),
                        "demand_mw": _float_or_none(r.get("demand_mw")),
                        "renewable_share": _float_or_none(r.get("renewable_share")),
                        "residual_load_mw": _float_or_none(r.get("residual_load_mw")),
                        "thermal_share": _float_or_none(r.get("thermal_share")),
                    }
                    for r in rows
                ],
            }
            _log_outcome(
                pattern_id=pattern_id,
                country_code=cc,
                version=ver,
                window_id=window_id,
                row_limit_requested=row_limit,
                rows_returned=len(rows),
                outcome="success",
            )
            return json.dumps(payload, ensure_ascii=False)

        row = runner(
            db_url,
            _SQL_WINDOW_SUMMARY,
            [cc, ver, start_utc, end_utc],
            mode="one",
        )
        assert isinstance(row, dict)
        row_count = int(row.get("row_count", 0) or 0)
        payload = {
            "pattern_id": pattern_id,
            "source_view": SOURCE_VIEW,
            "data_plane": "timescale",
            "market": {"country_code": cc},
            "window_utc": {
                "window_id": window_id,
                "start": _iso_utc(start_utc),
                "end": _iso_utc(end_utc),
            },
            "version": ver,
            "summary": {
                "row_count": row_count,
                "avg_price_eur_mwh": _float_or_none(row.get("avg_price_eur_mwh")),
                "avg_demand_mw": _float_or_none(row.get("avg_demand_mw")),
                "avg_renewable_share": _float_or_none(row.get("avg_renewable_share")),
                "avg_residual_load_mw": _float_or_none(row.get("avg_residual_load_mw")),
                "avg_thermal_share": _float_or_none(row.get("avg_thermal_share")),
            },
        }
        _log_outcome(
            pattern_id=pattern_id,
            country_code=cc,
            version=ver,
            window_id=window_id,
            row_limit_requested=None,
            rows_returned=row_count,
            outcome="success",
        )
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.warning("timescale_read target=timescale outcome=db_error: %s", type(exc).__name__)
        _log_outcome(
            pattern_id=pattern_id,
            country_code=cc,
            version=ver,
            window_id=window_id,
            row_limit_requested=row_limit,
            rows_returned=None,
            outcome="db_error",
        )
        return tool_error("Timescale query failed (see server logs for error type).")


READ_POWERUNITS_TIMESCALE_DATASET_SCHEMA = {
    "name": "read_powerunits_timescale_dataset",
    "description": (
        "Staged operator-only read of Powerunits market price model dataset rows "
        f"from {SOURCE_VIEW} via DATABASE_URL_TIMESCALE. "
        "Fixed pattern_id and window_id only; no ad-hoc SQL."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern_id": {
                "type": "string",
                "description": (
                    "One of: recent_rows_by_country | recent_window_summary_by_country"
                ),
            },
            "country_code": {"type": "string", "description": "ISO-like country code (allowlisted)."},
            "version": {"type": "string", "description": "Dataset version (allowlisted)."},
            "window_id": {
                "type": "string",
                "description": "One of: last_24h | last_72h | last_7d (UTC hour-aligned end).",
            },
            "row_limit": {
                "type": "integer",
                "description": (
                    f"Max rows for recent_rows_by_country only (default {DEFAULT_ROW_LIMIT}, "
                    f"max {MAX_ROW_LIMIT}). Must not be sent for recent_window_summary_by_country."
                ),
            },
        },
        "required": ["pattern_id", "country_code", "version", "window_id"],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_timescale_dataset",
    toolset="powerunits_timescale_read",
    schema=READ_POWERUNITS_TIMESCALE_DATASET_SCHEMA,
    handler=lambda args, **kw: read_powerunits_timescale_dataset(args, **kw),
    check_fn=check_powerunits_timescale_read_requirements,
    requires_env=[_TIMESCALE_URL_ENV, _FEATURE_ENV],
    emoji="📉",
)
