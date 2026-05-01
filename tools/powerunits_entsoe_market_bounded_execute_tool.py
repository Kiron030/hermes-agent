#!/usr/bin/env python3
"""
Hermes bounded ENTSO-E market sync **execute** — one HTTP POST to Repo B.

``POST /internal/hermes/bounded/v1/entsoe-market-sync/recompute``. Core gate:
``HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`` (or legacy execute flag).
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
    ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ENTSOE_MARKET_BOUNDED_LEGACY_ENV,
    ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
    entsoe_market_bounded_core_step_enabled,
    entsoe_market_bounded_gate_requirement_text,
)
from tools.powerunits_entsoe_market_bounded_slice import validate_entsoe_bounded_slice

logger = logging.getLogger(__name__)

_STEP = "execute"
_LEGACY_ENV = ENTSOE_MARKET_BOUNDED_LEGACY_ENV[_STEP]
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_entsoe_market_bounded_execute"
_EXECUTE_PATH = "/internal/hermes/bounded/v1/entsoe-market-sync/recompute"
_DEFAULT_TIMEOUT_S = 3600
_MAX_SUMMARY_CHARS = 8000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_entsoe_market_bounded_execute_requirements() -> bool:
    if not entsoe_market_bounded_core_step_enabled(_STEP):
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


def _internal_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_EXECUTE_PATH}"


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


def execute_powerunits_entsoe_market_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    if not check_powerunits_entsoe_market_bounded_execute_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{entsoe_market_bounded_gate_requirement_text(_STEP)}; "
                    f"and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "slice": None,
                "execution_attempted": False,
                "success": False,
                "http_status": None,
            },
            ensure_ascii=False,
        )

    base_statement = (
        "Hermes performed no direct SQL. Execution used exactly one HTTP POST to the "
        f"Powerunits bounded internal entsoe-market-sync recompute API (`POST {_EXECUTE_PATH}`)."
    )

    country_s = (country or "").strip()
    start_s = (start or "").strip()
    end_s = (end or "").strip()
    version_s = (version or "").strip()

    try:
        cc, start_dt, end_dt = validate_entsoe_bounded_slice(country_s, start_s, end_s, version_s)
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": None,
                "validation_messages": [str(e)],
                "execution_attempted": False,
                "success": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    slice_obj = {
        "country": cc,
        "version": version_s,
        "start_utc": start_dt.isoformat().replace("+00:00", "Z"),
        "end_utc_exclusive": end_dt.isoformat().replace("+00:00", "Z"),
    }

    url = _internal_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "execute_config_incomplete",
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": False,
                "success": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    body = {
        "country_code": cc,
        "version": version_s,
        "window_start_utc": start_s,
        "window_end_utc": end_s,
    }
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    timeout_s = _read_timeout_s()

    try:
        resp = poster(url, headers, body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("entsoe bounded execute: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": True,
                "success": False,
                "http_status": None,
                "error_class": "timeout",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("entsoe bounded execute: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": True,
                "success": False,
                "http_status": None,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    summary = _redact_secrets(resp.text or "")
    parsed: dict[str, Any] = {}
    try:
        if resp.content:
            pj = resp.json()
            parsed = pj if isinstance(pj, dict) else {}
    except (ValueError, json.JSONDecodeError, TypeError):
        parsed = {}

    ok = status == 200 and bool(parsed.get("success"))
    out: dict[str, Any] = {
        "surface": _SURFACE,
        "slice": slice_obj,
        "execution_attempted": True,
        "success": ok,
        "http_status": status,
        "pipeline_run_id": parsed.get("pipeline_run_id"),
        "correlation_id": parsed.get("correlation_id") or correlation_id,
        "status": parsed.get("status"),
        "rows_written": parsed.get("rows_written"),
        "response_body_summary": summary,
        "hermes_statement": base_statement,
    }
    if status == 400:
        out["error_class"] = "server_validation"
        out["server_message"] = parsed.get("message")
    elif status == 502:
        out["error_class"] = "job_failed"
    elif status != 200:
        out["error_class"] = "http_error"
    return json.dumps(out, ensure_ascii=False)


EXECUTE_ENTSOE_SCHEMA = {
    "name": "execute_powerunits_entsoe_market_bounded_slice",
    "description": (
        "**Bounded ENTSO-E market sync execute** — one HTTP POST to Powerunits "
        f"`{_EXECUTE_PATH}` (DE / v1 / ≤7d UTC). "
        f"Gate `{ENTSOE_MARKET_BOUNDED_PRIMARY_ENV}` or legacy `{_LEGACY_ENV}`; "
        f"optional `{ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV}`; {_BASE_ENV}, {_SECRET_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Must be DE (v1)."},
            "start": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "end": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
            "version": {"type": "string", "description": "Must be v1."},
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="execute_powerunits_entsoe_market_bounded_slice",
    toolset="powerunits_entsoe_market_bounded_execute",
    schema=EXECUTE_ENTSOE_SCHEMA,
    handler=lambda args, **kw: execute_powerunits_entsoe_market_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_entsoe_market_bounded_execute_requirements,
    requires_env=[
        ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
        ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="⚡",
)
