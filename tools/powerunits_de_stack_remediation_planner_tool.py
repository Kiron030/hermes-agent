#!/usr/bin/env python3
"""
Read-only DE bounded stack remediation **planner** — one HTTP POST to Repo B.

Aggregates signals from Repo B bounded read-only evaluators; **starts no jobs**.
Gated by ``HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED``.
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

_FEATURE_ENV = "HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED"
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_de_stack_remediation_planner"
_PLAN_PATH = "/internal/hermes/bounded/v1/remediation/de-stack-plan"
_DEFAULT_TIMEOUT_S = 180
_MAX_SUMMARY_CHARS = 28000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_de_stack_remediation_planner_requirements() -> bool:
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


def _plan_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_PLAN_PATH}"


def _read_timeout_s() -> float:
    raw = (os.getenv(_TIMEOUT_ENV) or "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT_S)
    try:
        return max(45.0, float(raw))
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


def plan_powerunits_de_stack_remediation(
    *,
    window_start_utc: str,
    window_end_utc: str,
    country_code: str = "DE",
    version: str = "v1",
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    base_statement = (
        "**Read-only remediation plan** via **one** HTTP POST (`…/remediation/de-stack-plan`). "
        "Hermes started **no** Repo B jobs, campaigns, ingest, SQL, or writes. "
        "`recommended_sequence` and `family_states` originate from Repo B aggregation — treat "
        "`tool_hint_hermes` as manual **suggestions**, not automation."
    )

    if not check_powerunits_de_stack_remediation_planner_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{_FEATURE_ENV} must be truthy and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "plan_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    cc_in = (country_code or "").strip() or "DE"
    ver_in = (version or "").strip() or "v1"
    start_raw = (window_start_utc or "").strip()
    end_raw = (window_end_utc or "").strip()

    try:
        cc, ver, start_s, end_s = validate_baseline_preview_slice(
            cc_in, start_raw, end_raw, ver_in
        )
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_messages": [str(e)],
                "plan_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    url = _plan_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "planner_config_incomplete",
                "surface": _SURFACE,
                "plan_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    cid = str(uuid.uuid4())
    body = {
        "country_code": cc,
        "version": ver,
        "window_start_utc": start_s,
        "window_end_utc": end_s,
    }
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": cid,
    }
    timeout_s = _read_timeout_s()

    try:
        resp = poster(url, headers, body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("de-stack remediation planner: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "plan_attempted": True,
                "http_status": None,
                "error_class": "timeout",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("de-stack remediation planner: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "plan_attempted": True,
                "http_status": None,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    parsed: dict[str, Any] = {}
    summary = _redact_secrets(resp.text or "")
    try:
        if resp.content:
            pj = resp.json()
            parsed = pj if isinstance(pj, dict) else {}
    except (ValueError, json.JSONDecodeError, TypeError):
        parsed = {}

    out: dict[str, Any] = {
        "surface": _SURFACE,
        "plan_attempted": True,
        "http_status": status,
        "http_ok": status == 200,
        "hermes_statement": parsed.get("hermes_statement") or base_statement,
        "correlation_id": parsed.get("correlation_id") or cid,
        "planner": parsed.get("planner"),
        "slice": parsed.get("slice"),
        "plan_outcome": parsed.get("plan_outcome"),
        "family_states": parsed.get("family_states"),
        "recommended_sequence": parsed.get("recommended_sequence"),
        "notes": parsed.get("notes"),
        "error_code": parsed.get("error_code"),
        "message": parsed.get("message"),
        "response_body_summary": summary,
    }

    if status == 400:
        out["error_class"] = "server_validation"
    elif status != 200:
        out["error_class"] = "http_error"

    return json.dumps(out, ensure_ascii=False)


PLAN_SCHEMA = {
    "name": "plan_powerunits_de_stack_remediation",
    "description": (
        "**Bounded DE stack read-only remediation planner** — single POST to Powerunits "
        "`…/remediation/de-stack-plan`. Combines Repo B bounded coverage scans, baseline preview, "
        "market-features/driver summaries over sub-windows (Repo B-internal), forecast validation — "
        "**no jobs** started. **`tool_hint_hermes`** values are **manual follow-up hints only**. "
        f"Requires `{_FEATURE_ENV}`, `{_BASE_ENV}`, `{_SECRET_ENV}`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "window_start_utc": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z.",
            },
            "country_code": {"type": "string", "default": "DE", "description": "Must be DE (v1)."},
            "version": {"type": "string", "default": "v1", "description": "Must be v1."},
        },
        "required": ["window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="plan_powerunits_de_stack_remediation",
    toolset="powerunits_de_stack_remediation_planner",
    schema=PLAN_SCHEMA,
    handler=lambda args, **kw: plan_powerunits_de_stack_remediation(
        window_start_utc=str((args or {}).get("window_start_utc", "")),
        window_end_utc=str((args or {}).get("window_end_utc", "")),
        country_code=str((args or {}).get("country_code", "") or "DE"),
        version=str((args or {}).get("version", "") or "v1"),
    ),
    check_fn=check_powerunits_de_stack_remediation_planner_requirements,
    requires_env=[_FEATURE_ENV, _BASE_ENV, _SECRET_ENV],
    emoji="🧭",
)
