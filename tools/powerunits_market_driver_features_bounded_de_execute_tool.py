#!/usr/bin/env python3
"""
Hermes **DE** bounded `market_driver_features_hourly` execute — one HTTP POST to Repo B.

**`POST …/market-driver-features-hourly/recompute`** with **`country_code=DE`**. Gated by
**`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`** or legacy **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_EXECUTE_ENABLED`**.

**Not** market-features Option D or `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*`.
Repo B runs **`market_driver_feature_job` only** — no `market_feature_job` / seed auto-run,
see response **`downstream_not_auto_triggered`**.
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
    MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV,
    MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV,
    MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV,
    market_driver_features_bounded_gate_requirement_text,
    market_driver_features_bounded_step_enabled,
)
from tools.powerunits_market_features_bounded_de_slice import validate_de_market_features_bounded_window

logger = logging.getLogger(__name__)

_STEP = "execute"
_LEGACY_ENV = MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV[_STEP]
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_market_driver_features_bounded_de_execute"
_EXECUTE_PATH = "/internal/hermes/bounded/v1/market-driver-features-hourly/recompute"
_DEFAULT_TIMEOUT_S = 3600
_MAX_SUMMARY_CHARS = 8000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_market_driver_features_bounded_de_execute_requirements() -> bool:
    if not market_driver_features_bounded_step_enabled(_STEP):
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


def execute_powerunits_market_driver_features_bounded_de_slice(
    *,
    window_start_utc: str,
    window_end_utc: str,
    version: str = "v1",
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    base_statement = (
        "**DE** bounded **`market_driver_features_hourly`** execute — distinct from market-features tools. "
        "Hermes did no SQL; **one** Repo B POST to `…/market-driver-features-hourly/recompute`. "
        "Runs **`market_driver_feature_job` only**; **no** `market_feature_job` / **`market_input_prices_seed_job`** "
        "from this handler. Prefer **`≤24h`** slice; cost columns depend on **`MARKET_DRIVER_INCLUDE_COST_INPUTS`** "
        "and commodity/carbon/FX freshness (see Repo B operator note)."
    )

    if not check_powerunits_market_driver_features_bounded_de_execute_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{market_driver_features_bounded_gate_requirement_text(_STEP)}; "
                    f"and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "slice": None,
                "execution_attempted": False,
                "success": False,
                "http_status": None,
                "error_class": "feature_disabled",
            },
            ensure_ascii=False,
        )

    start_s = (window_start_utc or "").strip()
    end_s = (window_end_utc or "").strip()
    ver_s = (version or "").strip() or "v1"

    try:
        cc, ver, st_trim, en_trim, start_dt, end_dt = validate_de_market_features_bounded_window(
            start_s, end_s, ver_s
        )
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
        "version": ver,
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
        "version": ver,
        "window_start_utc": st_trim,
        "window_end_utc": en_trim,
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
        logger.warning("market_driver_features DE bounded execute: HTTP timeout")
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
        logger.warning("market_driver_features DE bounded execute: HTTP error %s", e)
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
    summary = _redact_secrets(resp.text or "")

    parsed: dict[str, Any] = {}
    try:
        if resp.content:
            pj = resp.json()
            parsed = pj if isinstance(pj, dict) else {}
    except (ValueError, json.JSONDecodeError, TypeError):
        parsed = {}

    pipeline_run_id = parsed.get("pipeline_run_id") if isinstance(parsed, dict) else None
    resp_correlation = (
        (parsed.get("correlation_id") if isinstance(parsed, dict) else None) or correlation_id
    )
    api_success = parsed.get("success") is True if isinstance(parsed, dict) and status == 200 else False
    rows_written = parsed.get("rows_written") if isinstance(parsed, dict) else None
    downstream = parsed.get("downstream_not_auto_triggered") if isinstance(parsed, dict) else None
    operator_note = parsed.get("operator_note") if isinstance(parsed, dict) else None

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
        "downstream_not_auto_triggered": downstream,
        "operator_note": operator_note,
        "response_body_summary": summary,
        "hermes_statement": base_statement,
    }

    if status == 400 and isinstance(parsed, dict):
        out["server_error_code"] = parsed.get("error_code")
        out["server_message"] = parsed.get("message")

    return json.dumps(out, ensure_ascii=False)


EXEC_MDRIVER_DE_SCHEMA = {
    "name": "execute_powerunits_market_driver_features_bounded_de_slice",
    "description": (
        "**Bounded DE `market_driver_features_hourly` execute** — **DE / v1 / ≤24h** local validation, "
        "then Repo B **`…/market-driver-features-hourly/recompute`** (`market_driver_feature_job`). "
        "Separate from **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*`** and Option D. "
        f"Gate: `{MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV}` or legacy `{_LEGACY_ENV}`; "
        f"optional `{MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV}`; {_BASE_ENV}, {_SECRET_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "window_start_utc": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "window_end_utc": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
            "version": {"type": "string", "description": "Must be v1.", "default": "v1"},
        },
        "required": ["window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="execute_powerunits_market_driver_features_bounded_de_slice",
    toolset="powerunits_market_driver_features_bounded_de_execute",
    schema=EXEC_MDRIVER_DE_SCHEMA,
    handler=lambda args, **kw: execute_powerunits_market_driver_features_bounded_de_slice(
        window_start_utc=str((args or {}).get("window_start_utc", "")),
        window_end_utc=str((args or {}).get("window_end_utc", "")),
        version=str((args or {}).get("version", "") or "v1"),
    ),
    check_fn=check_powerunits_market_driver_features_bounded_de_execute_requirements,
    requires_env=[
        MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV,
        MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🧭",
)
