#!/usr/bin/env python3
"""
Bounded **DB health observe** — thin read-only POSTs to Repo B.

Seven named routes under ``/internal/hermes/bounded/v1/db-health/…``.
Hermes performs no SQL and holds no DB credential for this path.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Final

import httpx

from tools.powerunits_bounded_family_gates import (
    DB_HEALTH_READ_PRIMARY_ENV,
    db_health_read_enabled,
    db_health_read_requirement_text,
)
from tools.powerunits_execute_base_url_v1 import (
    apply_powerunits_execute_base_url_refusal,
    powerunits_execute_base_url_is_configured,
    resolve_powerunits_execute_base_url,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_db_health_observe_v1"
_DEFAULT_TIMEOUT_S = 60
_DEFAULT_VERSION = "v1"
_MAX_SUMMARY_CHARS = 12000
_DEFAULT_LIMIT = 10
_DEFAULT_STORAGE_LIMIT = 20
_HARD_MAX_LIMIT = 25
_HARD_MAX_STORAGE_LIMIT = 50

ObserveSurface = str

SURFACES_V1: Final[tuple[str, ...]] = (
    "storage",
    "planner",
    "indexes",
    "vacuum",
    "sessions",
    "statements",
    "timescale",
)
SURFACE_PATHS_V1: Final[dict[str, str]] = {
    "storage": "/internal/hermes/bounded/v1/db-health/storage",
    "planner": "/internal/hermes/bounded/v1/db-health/planner",
    "indexes": "/internal/hermes/bounded/v1/db-health/indexes",
    "vacuum": "/internal/hermes/bounded/v1/db-health/vacuum",
    "sessions": "/internal/hermes/bounded/v1/db-health/sessions",
    "statements": "/internal/hermes/bounded/v1/db-health/statements",
    "timescale": "/internal/hermes/bounded/v1/db-health/timescale",
}
TOOL_BY_SURFACE_V1: Final[dict[str, str]] = {
    "storage": "read_powerunits_db_health_storage_v1",
    "planner": "read_powerunits_db_health_planner_v1",
    "indexes": "read_powerunits_db_health_indexes_v1",
    "vacuum": "read_powerunits_db_health_vacuum_v1",
    "sessions": "read_powerunits_db_health_sessions_v1",
    "statements": "read_powerunits_db_health_statements_v1",
    "timescale": "read_powerunits_timescale_observe_v1",
}
RELATION_CATALOG_V1: Final[tuple[str, ...]] = (
    "market_demand_hourly",
    "market_prices_day_ahead",
    "market_generation_by_type_hourly",
    "weather_country_hourly",
    "market_border_flow_hourly",
    "outage_country_hourly",
    "market_features_hourly",
    "market_driver_features_hourly",
    "market_prices_day_ahead_bzn_v1",
    "market_price_model_dataset_v",
    "data_pipeline_runs",
)

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)

_HERMES_NOTE_V1 = (
    "Hermes: read-only bounded POST to Repo B db-health observe. "
    "No jobs, no SQL from Hermes, no DB credential, no writes, no advisor. "
    "Repo B JSON is canonical. UNAVAILABLE / NOT_CONFIGURED are successful reads."
)


def check_powerunits_db_health_read_requirements() -> bool:
    if not db_health_read_enabled():
        return False
    if not powerunits_execute_base_url_is_configured():
        return False
    if not (os.getenv(_SECRET_ENV) or "").strip():
        return False
    return True


def _redact_secrets(text: str) -> str:
    if not text:
        return ""
    redacted = _SECRET_URL_RE.sub("[REDACTED_URL]", text)
    if len(redacted) > _MAX_SUMMARY_CHARS:
        return redacted[:_MAX_SUMMARY_CHARS] + "\n...[truncated]"
    return redacted


def _observe_url(surface: str) -> str:
    resolved = resolve_powerunits_execute_base_url()
    if resolved.refused or not resolved.base_url:
        return ""
    return f"{resolved.base_url}{SURFACE_PATHS_V1[surface]}"


def _read_timeout_s() -> float:
    raw = (os.getenv(_TIMEOUT_ENV) or "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT_S)
    try:
        return max(15.0, float(raw))
    except ValueError:
        return float(_DEFAULT_TIMEOUT_S)


def _default_http_post(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout_s: float,
) -> httpx.Response:
    timeout = httpx.Timeout(connect=15.0, read=timeout_s, write=60.0, pool=15.0)
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, headers=headers, json=json_body)


def _hard_max(surface: str) -> int:
    return _HARD_MAX_STORAGE_LIMIT if surface == "storage" else _HARD_MAX_LIMIT


def _default_limit(surface: str) -> int:
    return _DEFAULT_STORAGE_LIMIT if surface == "storage" else _DEFAULT_LIMIT


def _validate_args(
    surface: str,
    relation: Any,
    limit: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if surface not in SURFACE_PATHS_V1:
        return None, {"error_code": "invalid_surface", "message": f"unknown surface {surface!r}"}
    relation_id = str(relation or "").strip() or None
    if relation_id is not None and relation_id not in RELATION_CATALOG_V1:
        return None, {
            "error_code": "unknown_relation",
            "message": f"relation must be one of: {', '.join(RELATION_CATALOG_V1)}",
        }
    body: dict[str, Any] = {"version": _DEFAULT_VERSION}
    if relation_id is not None:
        body["relation"] = relation_id
    if limit is None or limit == "":
        return body, None
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return None, {"error_code": "invalid_limit", "message": "limit must be an integer"}
    if parsed < 1 or parsed > _hard_max(surface):
        return None, {
            "error_code": "invalid_limit",
            "message": f"limit must be between 1 and {_hard_max(surface)}",
        }
    body["limit"] = parsed
    return body, None


def _chat_summary(surface: str, payload: dict[str, Any]) -> str:
    lines = [f"**DB health observe** `{surface}`"]
    if surface == "storage":
        lines.append(f"database_bytes=`{payload.get('database_bytes')}` relations={payload.get('result_count')}")
    elif surface in {"planner", "vacuum"}:
        lines.append(f"tables={payload.get('result_count')}")
    elif surface == "indexes":
        lines.append(f"indexes={payload.get('result_count')}")
    elif surface == "sessions":
        lines.append(
            f"long_xact={payload.get('long_running_xact_count')} "
            f"blocked={payload.get('blocked_session_count')}"
        )
    elif surface == "statements":
        lines.append(f"pg_stat_statements=`{payload.get('pg_stat_statements_status')}`")
    elif surface == "timescale":
        lines.append(f"timescale=`{payload.get('timescale_status')}` cagg=`{payload.get('continuous_aggregates')}`")
    lines.append("Read-only Repo B observe — no advisor, no maintenance, no SQL from Hermes.")
    lines.append(f"_correlation_id: `{payload.get('correlation_id') or 'n/a'}`")
    return "\n".join(lines)


def _fail(payload: dict[str, Any]) -> str:
    base = {
        "surface": _SURFACE,
        "read_attempted": False,
        "http_status_from_repo_b": None,
        "success": False,
        "hermes_operator_note_v1": _HERMES_NOTE_V1,
        "effect_class": "READ",
    }
    base.update(payload)
    return json.dumps(base, ensure_ascii=False)


def read_powerunits_db_health_observe_v1(
    *,
    surface: str,
    relation: str = "",
    limit: Any = None,
    version: str = _DEFAULT_VERSION,
    _http_post: Any = None,
) -> str:
    """Return JSON: Repo B db-health observe payload plus chat_summary."""
    poster = _http_post or _default_http_post

    if not check_powerunits_db_health_read_requirements():
        return _fail(
            {
                "error_code": "feature_disabled",
                "message": (
                    f"{db_health_read_requirement_text()}; "
                    f"also requires {_BASE_ENV} and {_SECRET_ENV}."
                ),
            }
        )

    body, err = _validate_args(surface, relation, limit)
    if err or not body:
        return _fail(err or {"error_code": "invalid_arguments", "message": "invalid arguments"})

    url = _observe_url(surface)
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            apply_powerunits_execute_base_url_refusal(
                {
                    "error_code": "read_config_incomplete",
                    "surface": _SURFACE,
                    "read_attempted": False,
                    "http_status_from_repo_b": None,
                    "success": False,
                    "hermes_operator_note_v1": _HERMES_NOTE_V1,
                    "effect_class": "READ",
                }
            ),
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    body["version"] = (version or "").strip() or _DEFAULT_VERSION

    try:
        resp = poster(url, headers, body, _read_timeout_s())
    except httpx.TimeoutException:
        logger.warning("db health observe: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "observe_surface": surface,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "timeout",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
                "effect_class": "READ",
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("db health observe: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "observe_surface": surface,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
                "effect_class": "READ",
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    raw_text = _redact_secrets(resp.text or "")
    try:
        parsed = resp.json() if resp.content else {}
        if not isinstance(parsed, dict):
            parsed = {"repo_b_non_object_json": parsed}
    except (ValueError, TypeError):
        parsed = {"parse_error": True, "response_body_summary": raw_text[:8000]}

    merged: dict[str, Any] = dict(parsed)
    merged["http_status_from_repo_b"] = status
    merged["read_attempted"] = True
    merged.setdefault("correlation_id", correlation_id)
    merged["hermes_operator_note_v1"] = _HERMES_NOTE_V1
    merged["surface"] = _SURFACE
    merged["observe_surface"] = surface
    merged["effect_class"] = "READ"
    if status == 200 and merged.get("success") is not False:
        merged["chat_summary"] = _chat_summary(surface, merged)
    else:
        merged.setdefault("response_body_summary", raw_text)
    return json.dumps(merged, ensure_ascii=False)


def read_powerunits_db_health_storage_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="storage", relation=relation, limit=limit, **kwargs)


def read_powerunits_db_health_planner_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="planner", relation=relation, limit=limit, **kwargs)


def read_powerunits_db_health_indexes_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="indexes", relation=relation, limit=limit, **kwargs)


def read_powerunits_db_health_vacuum_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="vacuum", relation=relation, limit=limit, **kwargs)


def read_powerunits_db_health_sessions_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="sessions", relation=relation, limit=limit, **kwargs)


def read_powerunits_db_health_statements_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="statements", relation=relation, limit=limit, **kwargs)


def read_powerunits_timescale_observe_v1(*, relation: str = "", limit: Any = None, **kwargs: Any) -> str:
    return read_powerunits_db_health_observe_v1(surface="timescale", relation=relation, limit=limit, **kwargs)


def _schema(name: str, surface: str, extra: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": (
            f"**DB health observe / {surface} (read-only)** — one bounded Repo B POST "
            f"`{SURFACE_PATHS_V1[surface]}`. {extra} "
            "Optional **relation** is a catalog id (not a SQL identifier). "
            f"Allowed: {', '.join(RELATION_CATALOG_V1)}. "
            f"Optional **limit** is top-N (default {_default_limit(surface)}, hard max {_hard_max(surface)}). "
            "Does not accept SQL, URLs, or arbitrary table names. "
            "Hermes does not run SQL or hold a DB credential. Observe only — no advisor, VACUUM, ANALYZE, "
            "or CREATE EXTENSION. "
            f"Gate `{DB_HEALTH_READ_PRIMARY_ENV}` plus "
            f"`{_BASE_ENV}` and `{_SECRET_ENV}`."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relation": {
                    "type": "string",
                    "description": "Optional catalog id. Omit for all allowlisted relations.",
                },
                "limit": {
                    "type": "integer",
                    "description": f"Optional top-N. Default {_default_limit(surface)}; hard max {_hard_max(surface)}.",
                },
            },
        },
    }


DB_HEALTH_STORAGE_SCHEMA_V1 = _schema(
    "read_powerunits_db_health_storage_v1",
    "storage",
    "Database size and allowlisted parent relation sizes. Chunk heap sizing is skipped.",
)
DB_HEALTH_PLANNER_SCHEMA_V1 = _schema(
    "read_powerunits_db_health_planner_v1",
    "planner",
    "seq/idx scan counters, live/dead tuples, last analyze/vacuum. No judgement labels.",
)
DB_HEALTH_INDEXES_SCHEMA_V1 = _schema(
    "read_powerunits_db_health_indexes_v1",
    "indexes",
    "Index size, idx_scan, valid/ready. No CREATE/DROP INDEX.",
)
DB_HEALTH_VACUUM_SCHEMA_V1 = _schema(
    "read_powerunits_db_health_vacuum_v1",
    "vacuum",
    "Dead-tuple ratio and last vacuum/analyze timestamps. No maintenance action.",
)
DB_HEALTH_SESSIONS_SCHEMA_V1 = _schema(
    "read_powerunits_db_health_sessions_v1",
    "sessions",
    "Connection/lock aggregates and a redacted session sample. Query text is omitted.",
)
DB_HEALTH_STATEMENTS_SCHEMA_V1 = _schema(
    "read_powerunits_db_health_statements_v1",
    "statements",
    "Bounded pg_stat_statements top-N when present; otherwise UNAVAILABLE.",
)
TIMESCALE_OBSERVE_SCHEMA_V1 = _schema(
    "read_powerunits_timescale_observe_v1",
    "timescale",
    "Allowlisted hypertables, chunk counts, CAGG/job presence. Absence is NOT_CONFIGURED.",
)


from tools.registry import registry

_COMMON_ENV = [DB_HEALTH_READ_PRIMARY_ENV, _BASE_ENV, _SECRET_ENV]


def _handler(surface: str):
    return lambda args, **kw: read_powerunits_db_health_observe_v1(
        surface=surface,
        relation=str((args or {}).get("relation", "") or ""),
        limit=(args or {}).get("limit"),
        version=str((args or {}).get("version", "") or _DEFAULT_VERSION),
    )


registry.register(
    name="read_powerunits_db_health_storage_v1",
    toolset="powerunits_db_observe",
    schema=DB_HEALTH_STORAGE_SCHEMA_V1,
    handler=_handler("storage"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
registry.register(
    name="read_powerunits_db_health_planner_v1",
    toolset="powerunits_db_observe",
    schema=DB_HEALTH_PLANNER_SCHEMA_V1,
    handler=_handler("planner"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
registry.register(
    name="read_powerunits_db_health_indexes_v1",
    toolset="powerunits_db_observe",
    schema=DB_HEALTH_INDEXES_SCHEMA_V1,
    handler=_handler("indexes"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
registry.register(
    name="read_powerunits_db_health_vacuum_v1",
    toolset="powerunits_db_observe",
    schema=DB_HEALTH_VACUUM_SCHEMA_V1,
    handler=_handler("vacuum"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
registry.register(
    name="read_powerunits_db_health_sessions_v1",
    toolset="powerunits_db_observe",
    schema=DB_HEALTH_SESSIONS_SCHEMA_V1,
    handler=_handler("sessions"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
registry.register(
    name="read_powerunits_db_health_statements_v1",
    toolset="powerunits_db_observe",
    schema=DB_HEALTH_STATEMENTS_SCHEMA_V1,
    handler=_handler("statements"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
registry.register(
    name="read_powerunits_timescale_observe_v1",
    toolset="powerunits_db_observe",
    schema=TIMESCALE_OBSERVE_SCHEMA_V1,
    handler=_handler("timescale"),
    check_fn=check_powerunits_db_health_read_requirements,
    requires_env=_COMMON_ENV,
    emoji="🩺",
)
