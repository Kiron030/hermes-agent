#!/usr/bin/env python3
"""
Read-only **BZN day-ahead price readiness** for advisory ISO2 (thin POST to Repo B).

One HTTP ``POST /internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read``.
Hermes does not recompute readiness logic; response body is returned with a short operator note only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED"
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_entsoe_bzn_price_readiness_v1"
_READ_PATH = "/internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read"
_DEFAULT_TIMEOUT_S = 90
_MAX_SUMMARY_CHARS = 200000

_DEFAULT_COUNTRY_CODES_ADVISORY_V1: tuple[str, ...] = ("DK", "NO", "SE", "IT", "IE")
_DEFAULT_TABLE_VERSION = "bzn_advisory_v1"

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_entsoe_bzn_price_readiness_requirements() -> bool:
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


def _normalize_country_codes(raw: Any) -> tuple[str, ...] | None:
    if raw is None:
        return tuple(_DEFAULT_COUNTRY_CODES_ADVISORY_V1)
    if isinstance(raw, str):
        parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
        return tuple(parts) if parts else tuple(_DEFAULT_COUNTRY_CODES_ADVISORY_V1)
    if isinstance(raw, (list, tuple)):
        out: list[str] = []
        for x in raw:
            s = str(x).strip().upper()
            if s:
                out.append(s)
        return tuple(out) if out else tuple(_DEFAULT_COUNTRY_CODES_ADVISORY_V1)
    return None


_HERMES_NOTE_V1 = (
    "Hermes: read-only bounded POST to Repo B. No jobs, no ingestion, no writes, no Hermes-side DB. "
    "Does not open Tier-1 national bounded market promotion. "
    "DK / NO / SE may show bzn_price readiness in Repo B; they are not Tier-1 national market-ready from this surface. "
    "Full JSON is Repo B; Hermes adds only hermes_operator_note_v1."
)


def read_powerunits_entsoe_bzn_price_readiness_v1(
    *,
    country_codes: Any = None,
    window_start_utc: str = "",
    window_end_utc: str = "",
    table_version: str = _DEFAULT_TABLE_VERSION,
    _http_post: Any = None,
) -> str:
    """Return JSON string: Repo B payload plus ``hermes_operator_note_v1`` on success paths."""
    poster = _http_post or _default_http_post

    gate_off = json.dumps(
        {
            "error_code": "feature_disabled",
            "surface": _SURFACE,
            "read_attempted": False,
            "http_status": None,
            "success": False,
            "message": (
                f"{_FEATURE_ENV} must be truthy and {_BASE_ENV} / {_SECRET_ENV} must be set."
            ),
            "hermes_operator_note_v1": _HERMES_NOTE_V1,
        },
        ensure_ascii=False,
    )

    if not check_powerunits_entsoe_bzn_price_readiness_requirements():
        return gate_off

    cc_tuple = _normalize_country_codes(country_codes)
    if cc_tuple is None:
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status": None,
                "success": False,
                "error_code": "invalid_country_codes",
                "message": "country_codes must be omitted, or a non-empty list of ISO2 strings, or a comma-separated ISO2 string.",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    ws = (window_start_utc or "").strip()
    we = (window_end_utc or "").strip()
    if not ws or not we:
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status": None,
                "success": False,
                "error_code": "invalid_window",
                "message": "window_start_utc and window_end_utc must be non-empty UTC ISO-8601 strings.",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    ver = (table_version or "").strip() or _DEFAULT_TABLE_VERSION
    url = _read_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "read_config_incomplete",
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status": None,
                "success": False,
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    body: dict[str, Any] = {
        "country_codes": list(cc_tuple),
        "window_start_utc": ws,
        "window_end_utc": we,
        "table_version": ver,
    }
    timeout_s = _read_timeout_s()

    try:
        resp = poster(url, headers, body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("entsoe bzn price readiness: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status": None,
                "success": False,
                "error_class": "timeout",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("entsoe bzn price readiness: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status": None,
                "success": False,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    raw_text = _redact_secrets(resp.text or "")
    parsed: dict[str, Any]
    try:
        parsed = resp.json() if resp.content else {}
        if not isinstance(parsed, dict):
            parsed = {"repo_b_non_object_json": parsed}
    except (ValueError, TypeError):
        parsed = {
            "parse_error": True,
            "response_body_summary": raw_text[:8000],
        }

    merged: dict[str, Any] = dict(parsed)
    merged["http_status_from_repo_b"] = status
    merged["read_attempted"] = True
    merged.setdefault("correlation_id", correlation_id)
    merged["hermes_operator_note_v1"] = _HERMES_NOTE_V1
    if status != 200 or merged.get("success") is False:
        merged.setdefault("response_body_summary", raw_text)

    return json.dumps(merged, ensure_ascii=False)


BZN_PRICE_READINESS_SCHEMA_V1 = {
    "name": "read_powerunits_entsoe_bzn_price_readiness_v1",
    "description": (
        "**Read-only** Repo B **`POST …/entsoe-bzn-price-readiness/read`**: persisted BZN table coverage slice + candidate matrix "
        "price readiness metadata (`bzn_price` vs `unresolved_price_path`, etc.). "
        "Does **not** run jobs, ingestion, writes, or Tier-1 national bounded promotion. "
        "DK / NO / SE may be BZN-price-ready in Repo B; not national Tier-1 market-ready from this tool. "
        f"Gate `{_FEATURE_ENV}` plus `{_BASE_ENV}`, `{_SECRET_ENV}`; optional `{_TIMEOUT_ENV}`. "
        "Omit **country_codes** to default **DK, NO, SE, IT, IE**."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Advisory-registry ISO2 list (e.g. DK, NO, SE, IT, IE). Omit to use the default advisory batch."
                ),
            },
            "window_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 (Z), same as Repo B bounded body.",
            },
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 (Z); span <= 31 days (Repo B validates).",
            },
            "table_version": {
                "type": "string",
                "description": "BZN logical table version; default bzn_advisory_v1.",
                "default": _DEFAULT_TABLE_VERSION,
            },
        },
        "required": ["window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_entsoe_bzn_price_readiness_v1",
    toolset="powerunits_entsoe_bzn_price_readiness",
    schema=BZN_PRICE_READINESS_SCHEMA_V1,
    handler=lambda args, **kw: read_powerunits_entsoe_bzn_price_readiness_v1(
        country_codes=(args or {}).get("country_codes"),
        window_start_utc=str((args or {}).get("window_start_utc", "") or ""),
        window_end_utc=str((args or {}).get("window_end_utc", "") or ""),
        table_version=str((args or {}).get("table_version", "") or _DEFAULT_TABLE_VERSION),
    ),
    check_fn=check_powerunits_entsoe_bzn_price_readiness_requirements,
    requires_env=[_FEATURE_ENV, _BASE_ENV, _SECRET_ENV],
    emoji="📗",
)
