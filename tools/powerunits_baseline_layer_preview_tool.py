#!/usr/bin/env python3
"""
Hermes bounded **baseline layer coverage preview** — read-only POST to Repo B.

Single-window DE / v1 / ≤31d, validated locally before HTTP.
Gated by ``HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED``.

Does **not** run ``expand_market_data``, ingestion jobs, or campaigns.
``rollup.suggested_next_bounded_action`` is produced by Repo B only; Hermes does not add steps.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from tools.powerunits_baseline_layer_preview_slice import validate_baseline_preview_slice

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED"
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_baseline_layer_preview"
_PREVIEW_PATH = "/internal/hermes/bounded/v1/baseline/layer-coverage-preview"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 14000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_baseline_layer_preview_requirements() -> bool:
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


def _preview_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_PREVIEW_PATH}"


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


def preview_powerunits_baseline_layer_coverage_de(
    *,
    preview_start_utc: str,
    preview_end_utc: str,
    country_code: str = "DE",
    version: str = "v1",
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    base_statement = (
        "Hermes performed no SQL. Read-only preview via **one** HTTP POST to Powerunits bounded "
        "`…/baseline/layer-coverage-preview`. "
        "**No** ingestion jobs ran (`entsoe_market_job`, `era5_weather_job`, `market_feature_job`, "
        "`market_driver_feature_job`, etc.). "
        "**No** campaigns started and **no** `expand_market_data` executed. "
        "Field `rollup.suggested_next_bounded_action` (if present) originates from **Repo B only** — "
        "Hermes adds no local remediation plan."
    )

    if not check_powerunits_baseline_layer_preview_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{_FEATURE_ENV} must be truthy and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "preview_attempted": False,
                "http_status": None,
            },
            ensure_ascii=False,
        )

    cc_in = (country_code or "").strip() or "DE"
    ver_in = (version or "").strip() or "v1"
    start_raw = (preview_start_utc or "").strip()
    end_raw = (preview_end_utc or "").strip()

    try:
        cc, ver, start_s, end_s = validate_baseline_preview_slice(
            cc_in, start_raw, end_raw, ver_in
        )
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "preview_messages": [str(e)],
                "preview_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    url = _preview_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "preview_config_incomplete",
                "surface": _SURFACE,
                "preview_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    body = {
        "country_code": cc,
        "version": ver,
        "preview_start_utc": start_s,
        "preview_end_utc": end_s,
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
        logger.warning("baseline layer preview: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "preview_attempted": True,
                "http_status": None,
                "error_class": "timeout",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("baseline layer preview: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "preview_attempted": True,
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

    out: dict[str, Any] = {
        "surface": _SURFACE,
        "preview_attempted": True,
        "http_status": status,
        "http_ok": status == 200,
        "correlation_id": parsed.get("correlation_id") or correlation_id,
        "scanner": parsed.get("scanner"),
        "hermes_statement": parsed.get("hermes_statement") or base_statement,
        "slice": parsed.get("slice"),
        "rollup": parsed.get("rollup"),
        "expected_hours": parsed.get("expected_hours"),
        "baseline_gate_criteria": parsed.get("baseline_gate_criteria"),
        "model_dataset_read_pilot": parsed.get("model_dataset_read_pilot"),
        "read_target_note": parsed.get("read_target_note"),
        "baseline_ready_preview": parsed.get("baseline_ready_preview"),
        "baseline_readiness_reason": parsed.get("baseline_readiness_reason"),
        "baseline_readiness_detail": parsed.get("baseline_readiness_detail"),
        "semantics_notes": parsed.get("semantics_notes"),
        "layers_country": parsed.get("layers_country"),
        "error_message": parsed.get("error_message"),
        "success": parsed.get("success"),
        "error_code": parsed.get("error_code"),
        "message": parsed.get("message"),
        "response_body_summary": summary,
    }

    if status == 400:
        out["error_class"] = "server_validation"
        if out.get("message") is None:
            out["message"] = parsed.get("message")
    elif status != 200:
        out["error_class"] = "http_error"

    return json.dumps(out, ensure_ascii=False)


BASELINE_PREVIEW_SCHEMA = {
    "name": "preview_powerunits_baseline_layer_coverage_de",
    "description": (
        "**Bounded baseline layer-coverage preview (read-only, v1 DE)** — single HTTP POST. "
        "Window `[preview_start_utc, preview_end_utc)` exclusive; span **≤ 31 days**. "
        "Does **not** run Repo B jobs, campaigns, or `expand_market_data`. "
        "Uses Repo B `rollup.suggested_next_bounded_action` only (no Hermes-added actions). "
        f"Requires {_FEATURE_ENV}, {_BASE_ENV}, {_SECRET_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "preview_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z.",
            },
            "preview_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z.",
            },
            "country_code": {
                "type": "string",
                "description": "Must be DE (default DE).",
                "default": "DE",
            },
            "version": {"type": "string", "description": "Must be v1.", "default": "v1"},
        },
        "required": ["preview_start_utc", "preview_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="preview_powerunits_baseline_layer_coverage_de",
    toolset="powerunits_baseline_layer_preview",
    schema=BASELINE_PREVIEW_SCHEMA,
    handler=lambda args, **kw: preview_powerunits_baseline_layer_coverage_de(
        preview_start_utc=str((args or {}).get("preview_start_utc", "")),
        preview_end_utc=str((args or {}).get("preview_end_utc", "")),
        country_code=str((args or {}).get("country_code", "") or "DE"),
        version=str((args or {}).get("version", "") or "v1"),
    ),
    check_fn=check_powerunits_baseline_layer_preview_requirements,
    requires_env=[_FEATURE_ENV, _BASE_ENV, _SECRET_ENV],
    emoji="📊",
)
