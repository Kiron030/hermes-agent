#!/usr/bin/env python3
"""
Bounded **coverage + pipeline freshness snapshot** — thin read-only POST to Repo B.

One HTTP ``POST /internal/hermes/bounded/v1/coverage-snapshot`` (layer coverage +
latest core ``data_pipeline_runs``). Precursor to product ``GET /api/v1/market-data/trust-snapshot``.
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
    BOUNDED_COVERAGE_SNAPSHOT_PRIMARY_ENV,
    bounded_coverage_snapshot_enabled,
    bounded_coverage_snapshot_requirement_text,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_bounded_coverage_snapshot_v1"
_SNAPSHOT_PATH = "/internal/hermes/bounded/v1/coverage-snapshot"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 12000
_DEFAULT_VERSION = "v1"

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)

_HERMES_NOTE_V1 = (
    "Hermes: read-only bounded POST to Repo B coverage-snapshot. No jobs, no ingestion, no writes. "
    "Repo B JSON is canonical; rerun after bounded repairs for fresh reads."
)


def check_powerunits_bounded_coverage_snapshot_requirements() -> bool:
    if not bounded_coverage_snapshot_enabled():
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


def _snapshot_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_SNAPSHOT_PATH}"


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


def _normalize_country_codes(raw: Any) -> tuple[list[str] | None, str | None]:
    if raw is None:
        return None, "missing country_codes"
    if isinstance(raw, str):
        cc = [p.strip().upper() for p in raw.split(",") if p.strip()]
        return cc, None if cc else "country_codes resolved empty after parsing"
    if isinstance(raw, list):
        cc = [(str(x) or "").strip().upper() for x in raw if str(x or "").strip()]
        return cc, None if cc else "country_codes list was empty after normalization"
    return None, "country_codes must be a list of ISO2 strings or a comma-separated string"


def _chat_summary(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    baseline = payload.get("baseline_ready")
    reason = payload.get("baseline_readiness_reason")
    lines.append(f"**Baseline ready:** `{baseline}` — {reason or 'n/a'}")

    tw = payload.get("time_window") or {}
    lines.append(
        f"Window `[start,end)`: `{tw.get('start_utc')}` → `{tw.get('end_utc_exclusive')}` "
        f"(expected_hours={tw.get('expected_hours')})"
    )

    runs = payload.get("latest_pipeline_runs") or []
    if runs:
        lines.append("**Pipeline freshness:**")
        for row in runs:
            job = row.get("job_name") or "?"
            if not row.get("found"):
                lines.append(f"• `{job}` — **no run found**")
                continue
            status = row.get("status") or "?"
            finished = row.get("finished_at") or "n/a"
            lines.append(f"• `{job}` — **{status}** (finished `{finished}`)")

    per_country = payload.get("baseline_readiness_detail") or {}
    if isinstance(per_country, dict) and per_country:
        lines.append("**Per-country baseline:**")
        for cc in sorted(per_country.keys()):
            detail = per_country.get(cc) or {}
            ready = detail.get("baseline_ready")
            lines.append(f"• **{cc}** — ready `{ready}`")

    cid = payload.get("correlation_id") or "n/a"
    lines.append("")
    lines.append(
        "Read-only Repo B snapshot — complements product trust badges; **rerun after repairs**."
    )
    lines.append(f"_correlation_id: `{cid}`")
    return "\n".join(lines)


def read_powerunits_coverage_snapshot_v1(
    *,
    window_start_utc: str = "",
    window_end_utc: str = "",
    country_codes: Any = None,
    version: str = _DEFAULT_VERSION,
    _http_post: Any = None,
) -> str:
    """Return JSON: Repo B coverage-snapshot payload plus ``chat_summary`` and ``hermes_operator_note_v1``."""
    poster = _http_post or _default_http_post

    gate_off = json.dumps(
        {
            "error_code": "feature_disabled",
            "surface": _SURFACE,
            "read_attempted": False,
            "http_status_from_repo_b": None,
            "success": False,
            "message": (
                f"{bounded_coverage_snapshot_requirement_text()}; "
                f"also requires {_BASE_ENV} and {_SECRET_ENV}."
            ),
            "hermes_operator_note_v1": _HERMES_NOTE_V1,
        },
        ensure_ascii=False,
    )

    if not check_powerunits_bounded_coverage_snapshot_requirements():
        return gate_off

    cc_list, cc_err = _normalize_country_codes(country_codes)
    if cc_err or not cc_list:
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "error_code": "invalid_country_codes",
                "message": cc_err or "country_codes required",
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

    ver = (version or "").strip() or _DEFAULT_VERSION
    url = _snapshot_url()
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

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    body: dict[str, Any] = {
        "country_codes": cc_list,
        "window_start_utc": ws,
        "window_end_utc": we,
        "version": ver,
    }

    try:
        resp = poster(url, headers, body, _read_timeout_s())
    except httpx.TimeoutException:
        logger.warning("bounded coverage snapshot: HTTP timeout")
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
        logger.warning("bounded coverage snapshot: HTTP error %s", e)
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
    merged["surface"] = _SURFACE
    if status == 200 and merged.get("success") is not False:
        merged["chat_summary"] = _chat_summary(merged)
    else:
        merged.setdefault("response_body_summary", raw_text)

    return json.dumps(merged, ensure_ascii=False)


COVERAGE_SNAPSHOT_SCHEMA_V1 = {
    "name": "read_powerunits_coverage_snapshot_v1",
    "description": (
        "**Data health snapshot (coverage + pipeline freshness)** — read-only **single** Repo B "
        "**`POST /internal/hermes/bounded/v1/coverage-snapshot`**. Returns expand-style layer coverage, "
        "**baseline_ready**, and latest **`data_pipeline_runs`** for ENTSO-E market, ERA5, and market features. "
        "Same backend contract as the product trust-snapshot precursor (`GET /api/v1/market-data/trust-snapshot`). "
        "**Not** coverage-inventory (family matrix rows) — use **`inventory_powerunits_bounded_coverage_v1`** for that. "
        "**No** jobs, ingestion, or writes. Gate **`HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED`** plus "
        "**`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`**, **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`**."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "ISO2 list (e.g. DE, PL, FR); required.",
            },
            "window_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 (Z).",
            },
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 (Z); span ≤ 31d.",
            },
            "version": {
                "type": "string",
                "description": "Dataset version; default v1.",
                "default": _DEFAULT_VERSION,
            },
        },
        "required": ["country_codes", "window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_coverage_snapshot_v1",
    toolset="powerunits_bounded_coverage_snapshot",
    schema=COVERAGE_SNAPSHOT_SCHEMA_V1,
    handler=lambda args, **kw: read_powerunits_coverage_snapshot_v1(
        window_start_utc=str((args or {}).get("window_start_utc", "") or ""),
        window_end_utc=str((args or {}).get("window_end_utc", "") or ""),
        country_codes=(args or {}).get("country_codes"),
        version=str((args or {}).get("version", "") or _DEFAULT_VERSION),
    ),
    check_fn=check_powerunits_bounded_coverage_snapshot_requirements,
    requires_env=[
        BOUNDED_COVERAGE_SNAPSHOT_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🩺",
)
