#!/usr/bin/env python3
"""
Hermes bounded **outage repair** execute — one HTTP POST to Repo B Step A+B chain.

Runs ``entsoe_generation_outage_sync`` then ``outage_country_hourly_compute`` only.
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
    OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV,
    OUTAGE_REPAIR_BOUNDED_LEGACY_ENV,
    OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV,
    outage_repair_bounded_core_step_enabled,
    outage_repair_bounded_gate_requirement_text,
)
from tools.powerunits_outage_repair_bounded_slice import validate_outage_repair_bounded_slice

logger = logging.getLogger(__name__)

_STEP = "execute"
_LEGACY_ENV = OUTAGE_REPAIR_BOUNDED_LEGACY_ENV[_STEP]
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_outage_repair_bounded_execute"
_EXECUTE_PATH = "/internal/hermes/bounded/v1/outage-repair/recompute"
_DEFAULT_TIMEOUT_S = 3600
_MAX_SUMMARY_CHARS = 8000

_OPERATOR_NOT_AUTO = (
    "market_feature_job was NOT auto-run. market_driver_feature_job was NOT auto-run. "
    "expand_market_data was NOT auto-run. Refresh DE outage columns on market_features_hourly "
    "(bounded market-features execute / CLI / worker) separately when needed."
)

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_outage_repair_bounded_execute_requirements() -> bool:
    if not outage_repair_bounded_core_step_enabled(_STEP):
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


def execute_powerunits_outage_repair_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    if not check_powerunits_outage_repair_bounded_execute_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{outage_repair_bounded_gate_requirement_text(_STEP)}; "
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
        "Hermes performed no SQL. Exactly **one** HTTP POST to Powerunits bounded internal "
        f"outage repair (`POST {_EXECUTE_PATH}`): **Step A** `entsoe_generation_outage_sync` then "
        "**Step B** `outage_country_hourly_compute`; **does not auto-run** `market_feature_job`, "
        "`market_driver_feature_job`, or `expand_market_data`."
    )

    country_s = (country or "").strip()
    start_s = (start or "").strip()
    end_s = (end or "").strip()
    version_s = (version or "").strip()

    try:
        cc, start_dt, end_dt = validate_outage_repair_bounded_slice(country_s, start_s, end_s, version_s)
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
        logger.warning("outage repair bounded execute: HTTP timeout")
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
        logger.warning("outage repair bounded execute: HTTP error %s", e)
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
        "step_a_pipeline_run_id": parsed.get("step_a_pipeline_run_id"),
        "step_b_pipeline_run_id": parsed.get("step_b_pipeline_run_id"),
        "correlation_id": parsed.get("correlation_id") or correlation_id,
        "status": parsed.get("status"),
        "rows_written": parsed.get("rows_written"),
        "step_a": parsed.get("step_a"),
        "step_b": parsed.get("step_b"),
        "response_body_summary": summary,
        "hermes_statement": parsed.get("hermes_statement") or base_statement,
        "downstream_not_auto_triggered": parsed.get("downstream_not_auto_triggered")
        if isinstance(parsed.get("downstream_not_auto_triggered"), list)
        else None,
        "operator_statement": parsed.get("operator_statement")
        if isinstance(parsed.get("operator_statement"), str)
        else None,
    }
    if ok:
        out["operator_statement"] = (
            (out.get("operator_statement") or "")
            + " "
            + _OPERATOR_NOT_AUTO
        ).strip()
    if status == 400:
        out["error_class"] = "server_validation"
        out["server_message"] = parsed.get("message")
    elif status == 502:
        out["error_class"] = "job_failed"
    elif status != 200:
        out["error_class"] = "http_error"
    return json.dumps(out, ensure_ascii=False)


EXECUTE_OUTAGE_REPAIR_SCHEMA = {
    "name": "execute_powerunits_outage_repair_bounded_slice",
    "description": (
        "**Bounded DE outage repair execute** — one HTTP POST to Powerunits "
        f"`{_EXECUTE_PATH}` (DE / v1 / ≤7d UTC). Runs Step A + Step B only; **no** auto "
        "`market_feature_job` / `market_driver_feature_job`. "
        f"Gate `{OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV}` or `{_LEGACY_ENV}`; optional "
        f"`{OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV}`; {_BASE_ENV}, {_SECRET_ENV}."
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
    name="execute_powerunits_outage_repair_bounded_slice",
    toolset="powerunits_outage_repair_bounded_execute",
    schema=EXECUTE_OUTAGE_REPAIR_SCHEMA,
    handler=lambda args, **kw: execute_powerunits_outage_repair_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_outage_repair_bounded_execute_requirements,
    requires_env=[
        OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV,
        OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🔧",
)
