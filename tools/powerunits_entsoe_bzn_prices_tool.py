#!/usr/bin/env python3
"""
Read-only **BZN day-ahead price rows** for advisory bidding zones (thin POST to Repo B).

One HTTP ``POST /internal/hermes/bounded/v1/entsoe-bzn-prices/read``.
Hermes does not read Timescale or duplicate Repo B filtering; response is returned with a short operator note only.
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

_FEATURE_ENV = "HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED"
_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_entsoe_bzn_prices_v1"
_READ_PATH = "/internal/hermes/bounded/v1/entsoe-bzn-prices/read"
_DEFAULT_TIMEOUT_S = 90
_MAX_SUMMARY_CHARS = 200000

_DEFAULT_COUNTRY_CODES_V1: tuple[str, ...] = ("DK", "NO", "SE")
_DEFAULT_PRICE_AREA_LABELS_V1: tuple[str, ...] = (
    "DK1",
    "DK2",
    "NO1",
    "NO2",
    "NO3",
    "NO4",
    "NO5",
    "SE1",
    "SE2",
    "SE3",
    "SE4",
)
_DEFAULT_TABLE_VERSION = "bzn_advisory_v1"
_DEFAULT_LIMIT = 500

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_entsoe_bzn_prices_requirements() -> bool:
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
        return tuple(_DEFAULT_COUNTRY_CODES_V1)
    if isinstance(raw, str):
        parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
        return tuple(parts) if parts else tuple(_DEFAULT_COUNTRY_CODES_V1)
    if isinstance(raw, (list, tuple)):
        out: list[str] = []
        for x in raw:
            s = str(x).strip().upper()
            if s:
                out.append(s)
        return tuple(out) if out else tuple(_DEFAULT_COUNTRY_CODES_V1)
    return None


def _normalize_str_list(raw: Any, *, default: tuple[str, ...]) -> tuple[str, ...]:
    """Return stripped strings list; ``None`` means use *default* (always include list in Repo B body)."""
    if raw is None:
        return tuple(default)
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return tuple(parts) if parts else tuple(default)
    if isinstance(raw, (list, tuple)):
        out = [str(x).strip() for x in raw if str(x).strip()]
        return tuple(out) if out else tuple(default)
    return tuple(default)


def _optional_str_list(raw: Any) -> list[str] | None:
    """``None`` = omit JSON key. Empty list omitted. Else non-empty stripped strings."""
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts if parts else None
    if isinstance(raw, (list, tuple)):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return parts if parts else None
    return None


_HERMES_NOTE_V1 = (
    "Hermes: read-only bounded POST to Repo B. No jobs, no ingestion, no writes, no Hermes-side DB. "
    "BZN prices are bidding-zone scoped and do not imply national Tier-v1 market promotion."
)


def read_powerunits_entsoe_bzn_prices_v1(
    *,
    country_codes: Any = None,
    price_area_labels: Any = None,
    price_area_eics: Any = None,
    window_start_utc: str = "",
    window_end_utc: str = "",
    table_version: str = _DEFAULT_TABLE_VERSION,
    limit: Any = None,
    _http_post: Any = None,
) -> str:
    """Return JSON string: Repo B payload plus ``hermes_operator_note_v1`` (and Hermes metrics) on all paths."""
    poster = _http_post or _default_http_post

    gate_off = json.dumps(
        {
            "error_code": "feature_disabled",
            "surface": _SURFACE,
            "read_attempted": False,
            "http_status_from_repo_b": None,
            "success": False,
            "message": (
                f"{_FEATURE_ENV} must be truthy and {_BASE_ENV} / {_SECRET_ENV} must be set."
            ),
            "hermes_operator_note_v1": _HERMES_NOTE_V1,
        },
        ensure_ascii=False,
    )

    if not check_powerunits_entsoe_bzn_prices_requirements():
        return gate_off

    cc_tuple = _normalize_country_codes(country_codes)
    if cc_tuple is None:
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status_from_repo_b": None,
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
                "http_status_from_repo_b": None,
                "success": False,
                "error_code": "invalid_window",
                "message": "window_start_utc and window_end_utc must be non-empty UTC ISO-8601 strings.",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    ver = (table_version or "").strip() or _DEFAULT_TABLE_VERSION

    lim: int = _DEFAULT_LIMIT
    if limit is not None and str(limit).strip() != "":
        try:
            lim = max(1, int(limit))
        except (TypeError, ValueError):
            return json.dumps(
                {
                    "surface": _SURFACE,
                    "read_attempted": False,
                    "http_status_from_repo_b": None,
                    "success": False,
                    "error_code": "invalid_limit",
                    "message": "limit must be a positive integer when provided.",
                    "hermes_operator_note_v1": _HERMES_NOTE_V1,
                },
                ensure_ascii=False,
            )

    url = _read_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "read_config_incomplete",
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    labels_tuple = _normalize_str_list(price_area_labels, default=_DEFAULT_PRICE_AREA_LABELS_V1)
    eics_list = _optional_str_list(price_area_eics)

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    body: dict[str, Any] = {
        "country_codes": list(cc_tuple),
        "price_area_labels": list(labels_tuple),
        "window_start_utc": ws,
        "window_end_utc": we,
        "table_version": ver,
        "limit": lim,
    }
    if eics_list is not None:
        body["price_area_eics"] = eics_list

    timeout_s = _read_timeout_s()

    try:
        resp = poster(url, headers, body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("entsoe bzn prices: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "timeout",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("entsoe bzn prices: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status_from_repo_b": None,
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


BZN_PRICES_SCHEMA_V1 = {
    "name": "read_powerunits_entsoe_bzn_prices_v1",
    "description": (
        "**Read-only** Repo B **`POST …/entsoe-bzn-prices/read`**: persisted **hourly EUR/MWh** BZN "
        "(bidding-zone) day-ahead price rows plus coverage summary. Does **not** run jobs, ingestion, writes, Timescale reads, "
        "or Tier-1 national bounded market promotion. IT/IE may appear in Repo B responses as partial/unresolved — treat as "
        "authoritative only when Repo B says so. Gate **`HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED`** plus "
        "**`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`**, **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`**; optional "
        "**`POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S`**."
        "\nDefaults when omitted: **country_codes DK, NO, SE**; **price_area_labels DK1/DK2, NO1–NO5, SE1–SE4**; "
        "**limit 500**; **table_version bzn_advisory_v1**. "
        "**price_area_eics** is omitted unless explicitly provided."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Advisory-registry ISO2 list; omit for default **DK, NO, SE**.",
            },
            "price_area_labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Global advisory labels (Repo B resolves to countries); omit for default DK/NO/SE BZN labels.",
            },
            "price_area_eics": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional ENTSO‑E bidding-zone codes; Repo B validates against advisory registry. "
                    "Omit entirely unless you intend an EIC filter."
                ),
            },
            "window_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 (Z), Repo B bounded body.",
            },
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 (Z); span capped by Repo B (≤ 31 d UTC).",
            },
            "table_version": {
                "type": "string",
                "description": "BZN logical table version; default bzn_advisory_v1.",
                "default": _DEFAULT_TABLE_VERSION,
            },
            "limit": {
                "type": "integer",
                "description": (
                    "Max price rows Repo B returns in the payload slice (summary still reflects full matched window). Default 500."
                ),
                "default": _DEFAULT_LIMIT,
            },
        },
        "required": ["window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_entsoe_bzn_prices_v1",
    toolset="powerunits_entsoe_bzn_prices",
    schema=BZN_PRICES_SCHEMA_V1,
    handler=lambda args, **kw: read_powerunits_entsoe_bzn_prices_v1(
        country_codes=(args or {}).get("country_codes"),
        price_area_labels=(args or {}).get("price_area_labels"),
        price_area_eics=(args or {}).get("price_area_eics"),
        window_start_utc=str((args or {}).get("window_start_utc", "") or ""),
        window_end_utc=str((args or {}).get("window_end_utc", "") or ""),
        table_version=str((args or {}).get("table_version", "") or _DEFAULT_TABLE_VERSION),
        limit=(args or {}).get("limit", _DEFAULT_LIMIT),
    ),
    check_fn=check_powerunits_entsoe_bzn_prices_requirements,
    requires_env=[_FEATURE_ENV, _BASE_ENV, _SECRET_ENV],
    emoji="💶",
)
