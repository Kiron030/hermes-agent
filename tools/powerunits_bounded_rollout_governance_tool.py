#!/usr/bin/env python3
"""
Bounded rollout **governance readout** — read-only POST to Repo B ``…/rollout-governance`` + optional Hermes overlay.

Repo B remains canonical for ``repo_b_allowed`` and ``*_ready`` flags; Hermes fills ``hermes_allowed_now`` /
``effective_status_cross_layer`` from Railway env (never overwrites Repo B truth fields in the JSON we return).
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from tools.bounded_rollout_governance_projection_v1 import merge_repo_b_rollout_governance_payload_v1
from tools.powerunits_bounded_family_gates import (
    BOUNDED_ROLLOUT_GOVERNANCE_PRIMARY_ENV,
    bounded_rollout_governance_enabled,
    bounded_rollout_governance_requirement_text,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_bounded_rollout_governance_v1"
_GOVERNANCE_PATH = "/internal/hermes/bounded/v1/rollout-governance"
_DEFAULT_TIMEOUT_S = 90
_MAX_SUMMARY_CHARS = 120000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_bounded_rollout_governance_requirements() -> bool:
    if not bounded_rollout_governance_enabled():
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


def _governance_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_GOVERNANCE_PATH}"


def _read_timeout_s() -> float:
    raw = (os.getenv(_TIMEOUT_ENV) or "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT_S)
    try:
        return max(20.0, float(raw))
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


def governance_powerunits_bounded_rollout_read_v1(
    *,
    country_codes_csv: str | None = None,
    version: str = "v1",
    apply_hermes_overlay: bool = True,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    base_stmt = (
        "Hermes performed no writes. One read-only POST to Repo B bounded rollout-governance. "
        "Overlay is optional Hermes gate projection only—Repo B readiness flags are authoritative."
    )

    if not check_powerunits_bounded_rollout_governance_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": f"{bounded_rollout_governance_requirement_text()}; need {_BASE_ENV} and {_SECRET_ENV}.",
                "governance_attempted": False,
                "success": False,
                "hermes_statement": base_stmt,
            },
            ensure_ascii=False,
        )

    url = _governance_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "governance_config_incomplete",
                "surface": _SURFACE,
                "governance_attempted": False,
                "success": False,
                "hermes_statement": base_stmt,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    timeout_s = _read_timeout_s()

    body: dict[str, Any] = {"version": (version or "").strip() or "v1"}
    if (country_codes_csv or "").strip():
        parts = [p.strip().upper() for p in (country_codes_csv or "").split(",") if p.strip()]
        body["country_codes"] = parts
    else:
        body["country_codes"] = None

    try:
        resp = poster(url, headers, body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("bounded rollout governance: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "governance_attempted": True,
                "success": False,
                "error_class": "timeout",
                "hermes_statement": base_stmt,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("bounded rollout governance: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "governance_attempted": True,
                "success": False,
                "error_class": "http_client_error",
                "detail": _redact_secrets(str(e)[:500]),
                "hermes_statement": base_stmt,
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    raw_text = _redact_secrets(resp.text or "")
    parsed: dict[str, Any]
    try:
        parsed = resp.json() if resp.content else {}
        if not isinstance(parsed, dict):
            parsed = {}
    except (ValueError, TypeError):
        parsed = {}

    parsed["http_status_from_repo_b"] = status
    parsed["governance_attempted"] = True
    if apply_hermes_overlay and parsed.get("success") is True:
        try:
            parsed = merge_repo_b_rollout_governance_payload_v1(parsed)
            parsed["hermes_overlay_applied"] = True
        except Exception as e:
            parsed["hermes_overlay_applied"] = False
            parsed["hermes_overlay_error"] = str(e)

    parsed.setdefault("hermes_statement", base_stmt)
    if status != 200 or not parsed.get("success"):
        parsed.setdefault(
            "response_body_summary",
            raw_text,
        )
        return json.dumps(parsed, ensure_ascii=False)

    return json.dumps(parsed, ensure_ascii=False)


BOUNDED_ROLLOUT_GOVERNANCE_SCHEMA_V1 = {
    "name": "governance_powerunits_bounded_rollout_read_v1",
    "description": (
        "**Read-only rollout governance v1**: single POST `POST /internal/hermes/bounded/v1/rollout-governance` "
        f"(Repo B). Optional Hermes merges Railway gate truth into **`hermes_allowed_now`** (+ cross-layer statuses) "
        f"without changing Repo canonical readiness flags. Gate `{BOUNDED_ROLLOUT_GOVERNANCE_PRIMARY_ENV}` "
        f"plus {_BASE_ENV} / {_SECRET_ENV}. Omit **country_codes_csv** ⇒ Repo B bounded default universe."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country_codes_csv": {
                "type": "string",
                "description": "Optional comma-separated ISO2 (e.g. `DE,NL,PL`). Empty ⇒ server default union.",
            },
            "version": {"type": "string", "description": "Must be v1."},
            "apply_hermes_overlay": {
                "type": "boolean",
                "description": "When true (default), merge Hermes env projection into each row.",
            },
        },
        "required": [],
    },
}


from tools.registry import registry

registry.register(
    name="governance_powerunits_bounded_rollout_read_v1",
    toolset="powerunits_bounded_rollout_governance",
    schema=BOUNDED_ROLLOUT_GOVERNANCE_SCHEMA_V1,
    handler=lambda args, **kw: governance_powerunits_bounded_rollout_read_v1(
        country_codes_csv=str((args or {}).get("country_codes_csv") or "").strip() or None,
        version=str((args or {}).get("version") or "v1"),
        apply_hermes_overlay=bool((args or {}).get("apply_hermes_overlay", True)),
    ),
    check_fn=check_powerunits_bounded_rollout_governance_requirements,
    requires_env=[
        BOUNDED_ROLLOUT_GOVERNANCE_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="📋",
)
