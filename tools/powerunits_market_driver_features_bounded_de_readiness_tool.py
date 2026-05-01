#!/usr/bin/env python3
"""
Hermes **DE** bounded readiness-window for **driver** workload (checks **`market_features_hourly`** inputs).

POST `…/market-driver-features-hourly/readiness-window` with **`country_code: "DE"`**.
Gated by **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`** or legacy
**`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_READINESS_ENABLED`**
— **not** **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*`** legacy market-features flags.
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

_STEP = "readiness"
_LEGACY_ENV = MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV[_STEP]
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_market_driver_features_bounded_de_readiness"
_READINESS_PATH = "/internal/hermes/bounded/v1/market-driver-features-hourly/readiness-window"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 8000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_market_driver_features_bounded_de_readiness_requirements() -> bool:
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


def _readiness_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_READINESS_PATH}"


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


def readiness_powerunits_market_driver_features_bounded_de_window(
    *,
    window_start_utc: str,
    window_end_utc: str,
    version: str = "v1",
    pipeline_run_id: str | None = None,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    base_statement = (
        "**DE** bounded **`market_driver_features`** readiness — Repo B evaluates upstream **`market_features_hourly`**; "
        "same **≤24h** bounded window."
    )

    if not check_powerunits_market_driver_features_bounded_de_readiness_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{market_driver_features_bounded_gate_requirement_text(_STEP)}; "
                    f"and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "slice": None,
                "readiness_attempted": False,
                "http_status": None,
                "readiness": None,
            },
            ensure_ascii=False,
        )

    ver_s = (version or "").strip() or "v1"
    prid = (pipeline_run_id or "").strip() or None

    try:
        cc, ver, st_trim, en_trim, start_dt, end_dt = validate_de_market_features_bounded_window(
            window_start_utc, window_end_utc, ver_s
        )
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": None,
                "readiness_messages": [str(e)],
                "readiness_attempted": False,
                "http_status": None,
                "readiness": None,
                "error_class": "client_validation",
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

    url = _readiness_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "readiness_config_incomplete",
                "surface": _SURFACE,
                "slice": slice_obj,
                "readiness_attempted": False,
                "http_status": None,
                "readiness": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    body: dict[str, Any] = {
        "country_code": cc,
        "version": ver,
        "window_start_utc": st_trim,
        "window_end_utc": en_trim,
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
        logger.warning("market_driver_features DE bounded readiness: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "readiness_attempted": True,
                "http_status": None,
                "readiness": None,
                "error_class": "timeout",
                "response_body_summary": "",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("market_driver_features DE bounded readiness: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "readiness_attempted": True,
                "http_status": None,
                "readiness": None,
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

    srv_readiness = parsed.get("readiness") if isinstance(parsed.get("readiness"), str) else None
    dominant = parsed.get("dominant_blocker")
    if dominant is not None and not isinstance(dominant, str):
        dominant = None

    out: dict[str, Any] = {
        "surface": _SURFACE,
        "slice": slice_obj,
        "readiness_attempted": True,
        "http_status": status,
        "readiness": srv_readiness,
        "readiness_go": srv_readiness == "go",
        "dominant_blocker": dominant,
        "reason_codes": parsed.get("reason_codes") if isinstance(parsed.get("reason_codes"), list) else [],
        "warnings": parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else [],
        "checks": parsed.get("checks") if isinstance(parsed.get("checks"), dict) else None,
        "explanation": parsed.get("explanation") if isinstance(parsed.get("explanation"), str) else None,
        "correlation_id": parsed.get("correlation_id") or correlation_id,
        "http_ok": status == 200,
        "success": status == 200 and srv_readiness == "go",
        "response_body_summary": summary,
        "hermes_statement": base_statement,
    }

    if status == 400:
        out["error_class"] = "server_validation"
        out["server_message"] = parsed.get("explanation") or parsed.get("message")
    elif status != 200:
        out["error_class"] = "http_error"

    return json.dumps(out, ensure_ascii=False)


READINESS_MDRIVER_DE_SCHEMA = {
    "name": "readiness_powerunits_market_driver_features_bounded_de_window",
    "description": (
        "**Bounded DE market-driver readiness-window** — **DE / v1 / ≤24h**, then one read-only Repo B POST "
        "(checks **`market_features_hourly`** for the driver job). "
        f"Gate: `{MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV}` or legacy `{_LEGACY_ENV}`; "
        f"optional `{MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV}`; {_BASE_ENV}, {_SECRET_ENV}. "
        "Optional `pipeline_run_id`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "window_start_utc": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "window_end_utc": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
            "version": {"type": "string", "description": "Must be v1.", "default": "v1"},
            "pipeline_run_id": {
                "type": "string",
                "description": "Optional; forwarded for symmetry with validate/summary.",
            },
        },
        "required": ["window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="readiness_powerunits_market_driver_features_bounded_de_window",
    toolset="powerunits_market_driver_features_bounded_de_readiness",
    schema=READINESS_MDRIVER_DE_SCHEMA,
    handler=lambda args, **kw: readiness_powerunits_market_driver_features_bounded_de_window(
        window_start_utc=str((args or {}).get("window_start_utc", "")),
        window_end_utc=str((args or {}).get("window_end_utc", "")),
        version=str((args or {}).get("version", "") or "v1"),
        pipeline_run_id=_pipeline_run_id_from_args(args or {}),
    ),
    check_fn=check_powerunits_market_driver_features_bounded_de_readiness_requirements,
    requires_env=[
        MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV,
        MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🟢",
)
