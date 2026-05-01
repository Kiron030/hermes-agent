#!/usr/bin/env python3
"""
Hermes bounded ERA5 weather sync **summary-window** — one HTTP POST to Repo B.
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
    ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ERA5_WEATHER_BOUNDED_LEGACY_ENV,
    ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
    era5_weather_bounded_core_step_enabled,
    era5_weather_bounded_gate_requirement_text,
    era5_weather_bounded_request_country_permitted,
)
from tools.powerunits_era5_weather_bounded_slice import validate_era5_bounded_slice

logger = logging.getLogger(__name__)

_STEP = "summary"
_LEGACY_ENV = ERA5_WEATHER_BOUNDED_LEGACY_ENV[_STEP]
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_era5_weather_bounded_summary"
_SUMMARY_PATH = "/internal/hermes/bounded/v1/era5-weather/summary-window"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 8000

_OPERATOR_NOT_AUTO = (
    "Summary reflects ERA5 + validate only; market_feature_job was NOT auto-run and "
    "market_driver_feature_job was NOT auto-run. Bounded market-features execute covers "
    "DE/PL; for DE hourly features after weather refresh use Repo B worker/runbook/CLI."
)

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_era5_weather_bounded_summary_requirements() -> bool:
    if not era5_weather_bounded_core_step_enabled(_STEP):
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


def _summary_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_SUMMARY_PATH}"


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


def _pipeline_run_id_from_args(args: Any) -> str | None:
    if not args or "pipeline_run_id" not in args or args.get("pipeline_run_id") is None:
        return None
    s = str(args.get("pipeline_run_id", "")).strip()
    return s or None


def summarize_powerunits_era5_weather_bounded_window(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    pipeline_run_id: str | None = None,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    if not check_powerunits_era5_weather_bounded_summary_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{era5_weather_bounded_gate_requirement_text(_STEP)}; "
                    f"and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "slice": None,
                "summary_attempted": False,
                "http_status": None,
                "outcome_class": None,
            },
            ensure_ascii=False,
        )

    base_statement = (
        "Hermes performed no direct SQL. Summary used exactly one HTTP POST to the "
        "Powerunits bounded internal era5-weather summary-window API. "
        "Validation subset includes `normalized_time_grain` and `semantics_notes` from Repo B."
    )

    country_s = (country or "").strip()
    start_s = (start or "").strip()
    end_s = (end or "").strip()
    version_s = (version or "").strip()
    prid = (pipeline_run_id or "").strip() or None

    try:
        cc, start_dt, end_dt = validate_era5_bounded_slice(country_s, start_s, end_s, version_s)
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": None,
                "summary_messages": [str(e)],
                "summary_attempted": False,
                "http_status": None,
                "outcome_class": None,
                "error_class": "client_validation",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    if not era5_weather_bounded_request_country_permitted(cc):
        slim = {
            "country": cc,
            "version": version_s,
            "start_utc": start_dt.isoformat().replace("+00:00", "Z"),
            "end_utc_exclusive": end_dt.isoformat().replace("+00:00", "Z"),
        }
        return json.dumps(
            {
                "error_code": "country_not_permitted",
                "surface": _SURFACE,
                "slice": slim,
                "summary_attempted": False,
                "http_status": None,
                "outcome_class": None,
                "summary_messages": [
                    f"Country `{cc}` not permitted under current bounded ERA5 gate: set "
                    f"`{ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV}` when "
                    f"`{ERA5_WEATHER_BOUNDED_PRIMARY_ENV}` is on (unset ⇒ DE only)."
                ],
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

    url = _summary_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "summary_config_incomplete",
                "surface": _SURFACE,
                "slice": slice_obj,
                "summary_attempted": False,
                "http_status": None,
                "outcome_class": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    body: dict[str, Any] = {
        "country_code": cc,
        "version": version_s,
        "window_start_utc": start_s,
        "window_end_utc": end_s,
    }
    if prid:
        body["pipeline_run_id"] = prid

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    timeout_s = _read_timeout_s()

    try:
        resp = poster(url, headers, body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("era5 bounded summary: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "summary_attempted": True,
                "http_status": None,
                "outcome_class": None,
                "error_class": "timeout",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("era5 bounded summary: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "summary_attempted": True,
                "http_status": None,
                "outcome_class": None,
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

    oc = parsed.get("outcome_class") if isinstance(parsed.get("outcome_class"), str) else None

    out: dict[str, Any] = {
        "surface": _SURFACE,
        "slice": slice_obj,
        "summary_attempted": True,
        "http_status": status,
        "outcome_class": oc,
        "flags": parsed.get("flags") if isinstance(parsed.get("flags"), dict) else None,
        "validation": parsed.get("validation") if isinstance(parsed.get("validation"), dict) else None,
        "execution": parsed.get("execution") if isinstance(parsed.get("execution"), dict) else None,
        "operator_next": parsed.get("operator_next") if isinstance(parsed.get("operator_next"), str) else None,
        "caveats": parsed.get("caveats") if isinstance(parsed.get("caveats"), list) else [],
        "correlation_id": parsed.get("correlation_id") or correlation_id,
        "http_ok": status == 200,
        "success": status == 200 and oc in ("ok", "ok_with_warnings"),
        "response_body_summary": summary,
        "hermes_statement": base_statement,
        "downstream_not_auto_triggered": parsed.get("downstream_not_auto_triggered")
        if isinstance(parsed.get("downstream_not_auto_triggered"), list)
        else None,
    }
    if status == 200 and oc in ("ok", "ok_with_warnings"):
        out["operator_statement"] = _OPERATOR_NOT_AUTO

    if status == 400:
        out["error_class"] = "server_validation"
        out["server_message"] = parsed.get("message")
    elif status != 200:
        out["error_class"] = "http_error"

    return json.dumps(out, ensure_ascii=False)


SUMMARY_ERA5_SCHEMA = {
    "name": "summarize_powerunits_era5_weather_bounded_window",
    "description": (
        "**Bounded ERA5 weather summary-window** — DE / v1 / ≤7d; one HTTP POST. "
        "Composed validate + optional pipeline echo; does not run market_feature_job or "
        "market_driver_feature_job. "
        f"Gate `{ERA5_WEATHER_BOUNDED_PRIMARY_ENV}` or `{_LEGACY_ENV}`; optional "
        f"`{ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV}`; {_BASE_ENV}, {_SECRET_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {
                "type": "string",
                "description": "Bounded ERA5 v1 ISO2 (DE or FR; same set as Repo B bounded ERA5 allowlist).",
            },
            "start": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "end": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
            "version": {"type": "string", "description": "Must be v1."},
            "pipeline_run_id": {"type": "string", "description": "Optional UUID from execute."},
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="summarize_powerunits_era5_weather_bounded_window",
    toolset="powerunits_era5_weather_bounded_summary",
    schema=SUMMARY_ERA5_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_era5_weather_bounded_window(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
        pipeline_run_id=_pipeline_run_id_from_args(args or {}),
    ),
    check_fn=check_powerunits_era5_weather_bounded_summary_requirements,
    requires_env=[
        ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
        ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="📋",
)
