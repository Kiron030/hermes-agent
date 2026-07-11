#!/usr/bin/env python3
"""
Read-only **worker country coverage freshness** rollup — thin POST to Repo B.

``POST /internal/hermes/bounded/v1/worker-country-coverage/freshness/read``
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from tools.powerunits_bounded_family_gates import (
    WORKER_COUNTRY_COVERAGE_FRESHNESS_PRIMARY_ENV,
    worker_country_coverage_freshness_enabled,
    worker_country_coverage_freshness_requirement_text,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_worker_country_coverage_freshness_v1"
_READ_PATH = "/internal/hermes/bounded/v1/worker-country-coverage/freshness/read"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 12000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)

_HERMES_NOTE_V1 = (
    "Hermes: read-only bounded POST to Repo B worker-country-coverage freshness. "
    "No jobs, ingestion, writes, or Tier-1 promotion."
)


def check_powerunits_worker_country_coverage_freshness_requirements() -> bool:
    if not worker_country_coverage_freshness_enabled():
        return False
    if not (os.getenv(_BASE_ENV) or "").strip():
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


def _read_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_READ_PATH}"


def _read_timeout_s() -> float:
    raw = (os.getenv(_TIMEOUT_ENV) or "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT_S)
    try:
        return max(30.0, float(raw))
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


def _optional_str_list(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
        return parts if parts else []
    if isinstance(raw, list):
        parts = [(str(x) or "").strip().upper() for x in raw if str(x or "").strip()]
        return parts
    return None


def _chat_summary(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        f"**Outcomes:** passed={summary.get('passed', 0)}, "
        f"warning={summary.get('warning', 0)}, failed={summary.get('failed', 0)}"
    ]
    rows = payload.get("rows") or []
    order = {"failed": 3, "warning": 2, "passed": 1}
    worst = sorted(
        rows,
        key=lambda r: order.get(str(r.get("outcome") or ""), 0),
        reverse=True,
    )[:12]
    if worst:
        lines.append("**Notable surfaces:**")
        for row in worst:
            if str(row.get("outcome") or "passed") == "passed":
                continue
            lines.append(
                f"• **{row.get('country_code')}/{row.get('surface')}** — "
                f"**{row.get('outcome')}** latest=`{row.get('latest_utc')}` "
                f"rows_window={row.get('rows_last_window')}"
            )
    cid = payload.get("correlation_id") or "n/a"
    lines.append("")
    lines.append("Read-only post-deploy freshness rollup — rerun after repairs.")
    lines.append(f"_correlation_id: `{cid}`")
    return "\n".join(lines)


def read_powerunits_worker_country_coverage_freshness_v1(
    *,
    national_country_codes: Any = None,
    bzn_country_codes: Any = None,
    rows_window_days: Any = None,
    stale_after_hours: Any = None,
    forecast_stale_after_hours: Any = None,
    era5_stale_after_hours: Any = None,
    include_empty: Any = None,
    _http_post: Any = None,
) -> str:
    """Return JSON: Repo B freshness rollup plus ``chat_summary``."""
    poster = _http_post or _default_http_post

    if not check_powerunits_worker_country_coverage_freshness_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "message": (
                    f"{worker_country_coverage_freshness_requirement_text()}; "
                    f"also requires {_BASE_ENV} and {_SECRET_ENV}."
                ),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    url = _read_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "read_config_incomplete",
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    body: dict[str, Any] = {}
    nat = _optional_str_list(national_country_codes)
    if nat is not None:
        body["national_country_codes"] = nat
    bzn = _optional_str_list(bzn_country_codes)
    if bzn is not None:
        body["bzn_country_codes"] = bzn
    for key, raw in (
        ("rows_window_days", rows_window_days),
        ("stale_after_hours", stale_after_hours),
        ("forecast_stale_after_hours", forecast_stale_after_hours),
        ("era5_stale_after_hours", era5_stale_after_hours),
    ):
        if raw is not None and str(raw).strip() != "":
            try:
                body[key] = int(raw)
            except (TypeError, ValueError):
                return json.dumps(
                    {
                        "surface": _SURFACE,
                        "read_attempted": False,
                        "success": False,
                        "error_code": "invalid_integer_param",
                        "message": f"{key} must be an integer when provided",
                        "hermes_operator_note_v1": _HERMES_NOTE_V1,
                    },
                    ensure_ascii=False,
                )
    if include_empty is not None:
        body["include_empty"] = bool(include_empty)

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }

    try:
        resp = poster(url, headers, body, _read_timeout_s())
    except httpx.TimeoutException:
        logger.warning("worker country coverage freshness: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "timeout",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("worker country coverage freshness: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
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
    if status == 200 and merged.get("success") is not False:
        merged["chat_summary"] = _chat_summary(merged)
    else:
        merged.setdefault("response_body_summary", raw_text)

    return json.dumps(merged, ensure_ascii=False)


WORKER_FRESHNESS_SCHEMA_V1 = {
    "name": "read_powerunits_worker_country_coverage_freshness_v1",
    "description": (
        "**Post-deploy freshness rollup (read-only)** — Repo B "
        "**`POST /internal/hermes/bounded/v1/worker-country-coverage/freshness/read`**. "
        "Per country/surface: latest timestamp, rows in window, outcome (passed/warning/failed). "
        "Defaults: Tier-1 nationals + DK/NO/SE BZN; rows_window_days=7; stale 48h (ERA5 168h). "
        "**No** jobs or Tier-1 promotion. Gate "
        "**`HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED`**."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "national_country_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional ISO2 list; omit for Tier-1 defaults.",
            },
            "bzn_country_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional BZN advisory ISO2 list; omit for DK/NO/SE.",
            },
            "rows_window_days": {"type": "integer", "description": "Default 7, max 90."},
            "stale_after_hours": {"type": "integer", "description": "Default 48."},
            "forecast_stale_after_hours": {"type": "integer", "description": "Default 48."},
            "era5_stale_after_hours": {"type": "integer", "description": "Default 168."},
            "include_empty": {
                "type": "boolean",
                "description": "When false, omit zero-row surfaces.",
            },
        },
        "required": [],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_worker_country_coverage_freshness_v1",
    toolset="powerunits_worker_country_coverage_freshness",
    schema=WORKER_FRESHNESS_SCHEMA_V1,
    handler=lambda args, **kw: read_powerunits_worker_country_coverage_freshness_v1(
        national_country_codes=(args or {}).get("national_country_codes"),
        bzn_country_codes=(args or {}).get("bzn_country_codes"),
        rows_window_days=(args or {}).get("rows_window_days"),
        stale_after_hours=(args or {}).get("stale_after_hours"),
        forecast_stale_after_hours=(args or {}).get("forecast_stale_after_hours"),
        era5_stale_after_hours=(args or {}).get("era5_stale_after_hours"),
        include_empty=(args or {}).get("include_empty"),
    ),
    check_fn=check_powerunits_worker_country_coverage_freshness_requirements,
    requires_env=[
        WORKER_COUNTRY_COVERAGE_FRESHNESS_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🕒",
)
