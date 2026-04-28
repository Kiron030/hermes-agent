#!/usr/bin/env python3
"""
Hermes-facing **bounded Option D execute** — exactly one HTTP POST to Repo B internal API.

Calls ``POST /internal/hermes/bounded/v1/market-features-hourly/recompute`` on the Powerunits
backend (Railway). No subprocess, no local product root, no direct SQL. Gated by
``HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED`` plus base URL and bearer secret env vars.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from tools.powerunits_option_d_bounded_market_features import _validate_slice

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED"
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_option_d_execute"
_EXECUTE_PATH = "/internal/hermes/bounded/v1/market-features-hourly/recompute"
_DEFAULT_TIMEOUT_S = 3600
_MAX_SUMMARY_CHARS = 8000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_option_d_execute_requirements() -> bool:
    if not _truthy_env(_FEATURE_ENV):
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


def _error_class_for_status(status_code: int) -> str:
    if status_code == 200:
        return "success"
    if status_code == 400:
        return "server_validation"
    if status_code == 401:
        return "auth_failed"
    if status_code == 404:
        return "not_found_or_disabled"
    if status_code == 502:
        return "job_failed"
    if status_code >= 500:
        return "upstream_error"
    return "http_error"


def _default_http_post(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout_s: float,
) -> httpx.Response:
    timeout = httpx.Timeout(connect=15.0, read=timeout_s, write=60.0, pool=15.0)
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, headers=headers, json=json_body)


def execute_powerunits_option_d_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    if not check_powerunits_option_d_execute_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{_FEATURE_ENV} must be truthy and {_BASE_ENV} / {_SECRET_ENV} must be set "
                    "for this tool."
                ),
                "slice": None,
                "execution_attempted": False,
                "success": False,
                "http_status": None,
                "error_class": "feature_disabled",
            },
            ensure_ascii=False,
        )

    base_statement = (
        "Hermes performed no direct SQL. Execution used exactly one HTTP POST to the "
        "Powerunits bounded internal API "
        f"(`POST {_EXECUTE_PATH}` on the configured base URL). No subprocess and no local "
        "product-repo wrapper were used for this path."
    )

    country_s = (country or "").strip()
    start_s = (start or "").strip()
    end_s = (end or "").strip()
    version_s = (version or "").strip()

    try:
        cc, start_dt, end_dt = _validate_slice(country_s, start_s, end_s, version_s)
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": None,
                "validation_messages": [str(e)],
                "execution_attempted": False,
                "success": False,
                "http_status": None,
                "error_class": "client_validation",
                "pipeline_run_id": None,
                "correlation_id": None,
                "response_body_summary": "",
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
                "message": f"Missing {_BASE_ENV} or {_SECRET_ENV}.",
                "slice": slice_obj,
                "execution_attempted": False,
                "success": False,
                "http_status": None,
                "error_class": "config_incomplete",
                "pipeline_run_id": None,
                "correlation_id": None,
                "response_body_summary": "",
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
        logger.warning("option_d execute: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": True,
                "success": False,
                "http_status": None,
                "error_class": "timeout",
                "pipeline_run_id": None,
                "correlation_id": correlation_id,
                "response_body_summary": "",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("option_d execute: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": True,
                "success": False,
                "http_status": None,
                "error_class": "http_client_error",
                "pipeline_run_id": None,
                "correlation_id": correlation_id,
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    summary_raw = resp.text or ""
    summary = _redact_secrets(summary_raw)

    parsed: dict[str, Any] = {}
    try:
        if resp.content:
            pj = resp.json()
            parsed = pj if isinstance(pj, dict) else {}
    except (ValueError, json.JSONDecodeError, TypeError):
        parsed = {}

    if isinstance(parsed, dict):
        pipeline_run_id = parsed.get("pipeline_run_id")
        resp_correlation = parsed.get("correlation_id") or correlation_id
        api_success = parsed.get("success") is True if status == 200 else False
        rows_written = parsed.get("rows_written")
    else:
        pipeline_run_id = None
        resp_correlation = correlation_id
        api_success = False
        rows_written = None

    ok = status == 200 and api_success is True
    if ok:
        mapped_class = "success"
    elif status == 200:
        mapped_class = "unexpected_response"
    else:
        mapped_class = _error_class_for_status(status)

    out: dict[str, Any] = {
        "surface": _SURFACE,
        "slice": slice_obj,
        "execution_attempted": True,
        "success": ok,
        "http_status": status,
        "error_class": mapped_class,
        "pipeline_run_id": pipeline_run_id,
        "correlation_id": resp_correlation,
        "rows_written": rows_written,
        "response_body_summary": summary,
        "hermes_statement": base_statement,
    }

    if status == 400 and isinstance(parsed, dict):
        out["server_error_code"] = parsed.get("error_code")
        out["server_message"] = parsed.get("message")

    return json.dumps(out, ensure_ascii=False)


EXECUTE_OPTION_D_SCHEMA = {
    "name": "execute_powerunits_option_d_bounded_slice",
    "description": (
        "**Option D bounded execute** — validates PL / v1 / ≤24h UTC slice, then performs **one** "
        "HTTP POST to the Powerunits internal bounded API "
        f"`POST {_EXECUTE_PATH}` (Railway-native; no local product checkout). Requires "
        f"{_FEATURE_ENV}, {_BASE_ENV}, and {_SECRET_ENV}. Not a general-purpose database writer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Must be PL (first release)."},
            "start": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z.",
            },
            "end": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z.",
            },
            "version": {"type": "string", "description": "Must be v1 (first release)."},
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="execute_powerunits_option_d_bounded_slice",
    toolset="powerunits_option_d_execute",
    schema=EXECUTE_OPTION_D_SCHEMA,
    handler=lambda args, **kw: execute_powerunits_option_d_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_option_d_execute_requirements,
    requires_env=[
        _FEATURE_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="⚡",
)
