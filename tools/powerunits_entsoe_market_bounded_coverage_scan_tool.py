#!/usr/bin/env python3
"""
Hermes bounded ENTSO-E **coverage-scan** — read-only POST to Repo B (multi-subwindow).

Uses the same slice caps as the ENTSO-E bounded campaign (≤31d, ≤5 × ≤7d partitions),
validated locally before HTTP. Gated by ``HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from tools.powerunits_bounded_family_gates import entsoe_market_bounded_request_country_permitted
from tools.powerunits_entsoe_market_bounded_countries import (
    BOUNDED_ENTSOE_MARKET_USER_FACING_ISO2_DOCUMENTATION_V1 as _ISO_DOC_ENTSOE_MARKET,
)
from tools.powerunits_entsoe_market_bounded_slice import validate_entsoe_bounded_campaign

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED"
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_entsoe_market_bounded_coverage_scan"
_SCAN_PATH = "/internal/hermes/bounded/v1/entsoe-market-sync/coverage-scan"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 12000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_entsoe_market_bounded_coverage_scan_requirements() -> bool:
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


def _scan_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_SCAN_PATH}"


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


def scan_powerunits_entsoe_market_bounded_coverage_de(
    *,
    scan_start_utc: str,
    scan_end_utc: str,
    country: str = "DE",
    version: str = "v1",
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post

    base_statement = (
        "Hermes performed no direct SQL. Read-only scan via one HTTP POST to "
        "Powerunits bounded `…/entsoe-market-sync/coverage-scan`. "
        "Does not run entsoe_market_job, campaigns, or downstream feature jobs."
    )

    if not check_powerunits_entsoe_market_bounded_coverage_scan_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{_FEATURE_ENV} must be truthy and {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "scan_attempted": False,
                "http_status": None,
            },
            ensure_ascii=False,
        )

    country_s = (country or "").strip() or "DE"
    version_s = (version or "").strip() or "v1"
    start_s = (scan_start_utc or "").strip()
    end_s = (scan_end_utc or "").strip()

    try:
        cc, ver, _planned = validate_entsoe_bounded_campaign(
            country_s, start_s, end_s, version_s
        )
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "scan_messages": [str(e)],
                "scan_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    if not entsoe_market_bounded_request_country_permitted(cc):
        return json.dumps(
            {
                "surface": _SURFACE,
                "error_code": "country_not_permitted",
                "scan_messages": [
                    (
                        f"Country `{cc}` rejected by **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`** vs Repo B Tier‑1 "
                        f"(or `{cc}` is outside mirrored Tier‑1). With primary: **omit env** ⇒ Tier‑1 bundle; non‑empty ⇒ intersection; explicit **empty** ⇒ fail‑closed."
                    ),
                ],
                "scan_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    url = _scan_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "scan_config_incomplete",
                "surface": _SURFACE,
                "scan_attempted": False,
                "http_status": None,
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    body = {
        "country_code": cc,
        "version": ver,
        "scan_start_utc": start_s,
        "scan_end_utc": end_s,
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
        logger.warning("entsoe bounded coverage-scan: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "scan_attempted": True,
                "http_status": None,
                "error_class": "timeout",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("entsoe bounded coverage-scan: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "scan_attempted": True,
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
        "scan_attempted": True,
        "http_status": status,
        "http_ok": status == 200,
        "correlation_id": parsed.get("correlation_id") or correlation_id,
        "rollup": parsed.get("rollup"),
        "scanner": parsed.get("scanner"),
        "hermes_statement": parsed.get("hermes_statement") or base_statement,
        "slice": parsed.get("slice"),
        "subwindows": parsed.get("subwindows"),
        "partition": parsed.get("partition"),
        "response_body_summary": summary,
    }

    if status == 400:
        out["error_class"] = "server_validation"
        out["message"] = parsed.get("message")
    elif status != 200:
        out["error_class"] = "http_error"

    return json.dumps(out, ensure_ascii=False)


SCAN_ENTSOE_SCHEMA = {
    "name": "scan_powerunits_entsoe_market_bounded_coverage_de",
    "description": (
        "**Bounded ENTSO-E normalized market coverage-scan** (read-only; mirrored Repo B Tier‑v1 ISO2 bundle via `country`) — one HTTP POST. "
        "Span ≤31d, partitioned like campaign (≤5 × ≤7d). "
        f"Requires {_FEATURE_ENV}, {_BASE_ENV}, {_SECRET_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scan_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z (campaign-style max 31d span).",
            },
            "scan_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z.",
            },
            "country": {"type": "string", "description": _ISO_DOC_ENTSOE_MARKET, "default": "DE"},
            "version": {"type": "string", "description": "Must be v1.", "default": "v1"},
        },
        "required": ["scan_start_utc", "scan_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="scan_powerunits_entsoe_market_bounded_coverage_de",
    toolset="powerunits_entsoe_market_bounded_coverage_scan",
    schema=SCAN_ENTSOE_SCHEMA,
    handler=lambda args, **kw: scan_powerunits_entsoe_market_bounded_coverage_de(
        scan_start_utc=str((args or {}).get("scan_start_utc", "")),
        scan_end_utc=str((args or {}).get("scan_end_utc", "")),
        country=str((args or {}).get("country", "") or "DE"),
        version=str((args or {}).get("version", "") or "v1"),
    ),
    check_fn=check_powerunits_entsoe_market_bounded_coverage_scan_requirements,
    requires_env=[_FEATURE_ENV, _BASE_ENV, _SECRET_ENV],
    emoji="🔎",
)
