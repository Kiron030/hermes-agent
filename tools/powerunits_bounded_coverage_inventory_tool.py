#!/usr/bin/env python3
"""
Bounded **multi-country coverage inventory** — thin read-only POST to Repo B.

Aggregates Repo B bounded evaluators (HTTP contract documented in EU-PP-Database).
Hermes maintains **no** authoritative matrix; rerun after bounded repairs for fresh Repo B reads.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from tools.powerunits_bounded_family_gates import (
    BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV,
    bounded_coverage_inventory_enabled,
    bounded_coverage_inventory_requirement_text,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_bounded_coverage_inventory_v1"
_INVENTORY_PATH = "/internal/hermes/bounded/v1/coverage-inventory"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 12000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def check_powerunits_bounded_coverage_inventory_requirements() -> bool:
    if not bounded_coverage_inventory_enabled():
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


def _inventory_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_INVENTORY_PATH}"


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


def _normalize_families_arg(raw: Any) -> tuple[list[str] | None, str | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, "families must be an array of v1 inventory family ids or omitted"
    out = [(str(x) or "").strip() for x in raw if str(x or "").strip()]
    if not out:
        return None, None
    return out, None


def _chat_summary(rows: list[dict[str, Any]], *, correlation_id: str | None) -> str:
    if not rows:
        return f"No inventory rows (correlation_id={correlation_id})."
    order = {"gaps": 3, "warnings": 2, "skipped": 1, "ok": 0}
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        cc = str(row.get("country_code") or "")
        fam = str(row.get("family") or "")
        status = str(row.get("status") or "?").lower()
        buckets = counts.setdefault((cc, fam), {})
        buckets[status] = buckets.get(status, 0) + 1
    lines_out: list[str] = []
    for (cc, fam) in sorted(counts.keys()):
        buck = counts[(cc, fam)]
        dominant = max(buck.keys(), key=lambda s: order.get(s, -1))
        parts = ",".join(f"{s}:{buck[s]}" for s in sorted(buck.keys()))
        short_fam = fam.replace("bounded_", "").replace("_normalized_v1", "")
        lines_out.append(f"• **{cc} / {short_fam}** — worst **{dominant}** ({parts})")
    cid = correlation_id or "n/a"
    lines_out.append("")
    lines_out.append(
        "Read-only Repo B aggregation — **rerun inventory after bounded repairs** (no Hermes matrix)."
    )
    lines_out.append(f"_correlation_id: `{cid}`")
    return "\n".join(lines_out)


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    cols = (
        "country_code",
        "family",
        "version",
        "overall_window_start_utc",
        "overall_window_end_utc_exclusive",
        "window_start_utc",
        "window_end_utc_exclusive",
        "subwindow_index",
        "status",
        "summary_code",
        "rollup_scan_outcome",
        "tool_hint_hermes",
        "suggested_next_action",
        "coverage_metrics_json",
    )
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for row in rows:
        metrics = json.dumps(row.get("coverage_metrics") or {}, ensure_ascii=False)
        w.writerow(
            [
                row.get("country_code"),
                row.get("family"),
                row.get("version"),
                row.get("overall_window_start_utc"),
                row.get("overall_window_end_utc_exclusive"),
                row.get("window_start_utc"),
                row.get("window_end_utc_exclusive"),
                row.get("subwindow_index"),
                row.get("status"),
                row.get("summary_code"),
                row.get("rollup_scan_outcome"),
                row.get("tool_hint_hermes"),
                row.get("suggested_next_action"),
                metrics,
            ]
        )
    return buf.getvalue()


def inventory_powerunits_bounded_coverage_v1(
    *,
    window_start_utc: str,
    window_end_utc: str,
    country_codes: Any,
    families: Any = None,
    version: str = "v1",
    export_format: str | None = None,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post
    stmt = (
        "Hermes performed no direct SQL. One read-only POST to Repo B "
        "`/internal/hermes/bounded/v1/coverage-inventory` — aggregates bounded coverage-scan "
        "evaluators server-side (**no writes**, **no campaigns**)."
    )

    if not check_powerunits_bounded_coverage_inventory_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{bounded_coverage_inventory_requirement_text()}; "
                    f"also {_BASE_ENV} / {_SECRET_ENV} must be set."
                ),
                "inventory_attempted": False,
                "http_status": None,
                "chat_summary": "Inventory disabled.",
                "hermes_statement": stmt,
            },
            ensure_ascii=False,
        )

    ccs, err_cc = _normalize_country_codes(country_codes)
    if err_cc or ccs is None:
        return json.dumps(
            {
                "surface": _SURFACE,
                "error_code": "client_validation",
                "validation_messages": [err_cc or "invalid_country_codes"],
                "inventory_attempted": False,
                "http_status": None,
                "chat_summary": "",
                "hermes_statement": stmt,
            },
            ensure_ascii=False,
        )

    fam_body: list[str] | None = None
    if families is not None:
        parsed, err_fm = _normalize_families_arg(families)
        if err_fm:
            return json.dumps(
                {
                    "surface": _SURFACE,
                    "error_code": "client_validation",
                    "validation_messages": [err_fm],
                    "inventory_attempted": False,
                    "http_status": None,
                    "chat_summary": "",
                    "hermes_statement": stmt,
                },
                ensure_ascii=False,
            )
        fam_body = parsed

    xf = ((export_format or "").strip().lower())
    export_csv_requested = xf in {"csv", "text/csv"}
    if xf and xf not in {"csv", "text/csv", "none", "", "null"}:
        return json.dumps(
            {
                "surface": _SURFACE,
                "error_code": "client_validation",
                "validation_messages": [f"export_format not supported: {export_format!r} (use csv or omit)"],
                "inventory_attempted": False,
                "http_status": None,
                "chat_summary": "",
                "hermes_statement": stmt,
            },
            ensure_ascii=False,
        )

    ws = (window_start_utc or "").strip()
    we = (window_end_utc or "").strip()
    ver = (version or "").strip() or "v1"
    url = _inventory_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "execute_config_incomplete",
                "surface": _SURFACE,
                "inventory_attempted": False,
                "http_status": None,
                "chat_summary": "",
                "hermes_statement": stmt,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    body_doc: dict[str, Any] = {
        "window_start_utc": ws,
        "window_end_utc": we,
        "country_codes": ccs,
        "version": ver,
    }
    if isinstance(fam_body, list) and len(fam_body) > 0:
        body_doc["families"] = list(fam_body)

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }

    timeout_s = _read_timeout_s()
    try:
        resp = poster(url, headers, body_doc, timeout_s)
    except httpx.TimeoutException:
        logger.warning("bounded coverage inventory: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "inventory_attempted": True,
                "http_status": None,
                "error_class": "timeout",
                "chat_summary": "",
                "hermes_statement": stmt,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("bounded coverage inventory: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "inventory_attempted": True,
                "http_status": None,
                "error_class": "http_client_error",
                "network_message": _redact_secrets(str(e)[:500]),
                "chat_summary": "",
                "hermes_statement": stmt,
            },
            ensure_ascii=False,
        )

    raw_text = getattr(resp, "text", "") or ""
    parsed: dict[str, Any]
    try:
        parsed = resp.json()
        if isinstance(parsed, list):
            parsed = {"success": False, "error_code": "unexpected_array_body", "raw": parsed}
    except ValueError:
        parsed = {}

    cid = correlation_id
    http_status = int(resp.status_code)
    rows = parsed.get("rows") if isinstance(parsed, dict) else None
    rows_ok = isinstance(rows, list)
    corr_from_body = None
    if isinstance(parsed.get("correlation_id"), str):
        corr_from_body = parsed["correlation_id"]
    if corr_from_body:
        cid = corr_from_body

    export_csv_body: str | None = None
    if rows_ok and export_csv_requested:
        export_csv_body = _rows_to_csv(rows)

    chat = _chat_summary(rows if isinstance(rows, list) else [], correlation_id=cid)

    out: dict[str, Any] = {
        "surface": _SURFACE,
        "inventory_attempted": True,
        "http_status": http_status,
        "success": bool(parsed.get("success")) if isinstance(parsed, dict) else False,
        "chat_summary": chat,
        "repo_b_inventory": parsed if isinstance(parsed, dict) else {"raw_body": raw_text[:2000]},
        "hermes_statement": stmt,
        "request_echo": {"path": _INVENTORY_PATH, "body": body_doc, "gate_env": BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV},
        "csv_export": export_csv_body,
        "hint_export": (
            "`csv_export` is derived-only from `repo_b_inventory.rows` in **this response** "
            "(no persisted matrix)."
        ),
    }

    if not rows_ok:
        content_type = resp.headers.get("content-type", "")
        snippet = raw_text[:2400]
        out["repository_response_content_type"] = content_type
        out["repository_response_preview"] = _redact_secrets(snippet)
        err_code = parsed.get("error_code") if isinstance(parsed, dict) else None
        msg = parsed.get("message") if isinstance(parsed, dict) else None
        if err_code:
            out["repository_error_code"] = err_code
        if isinstance(msg, str):
            out["repository_error_message"] = msg

    return json.dumps(out, ensure_ascii=False)


INVENTORY_BOUNDED_SCHEMA = {
    "name": "inventory_powerunits_bounded_coverage_v1",
    "description": (
        "**Bounded multi-country coverage inventory (Repo B read-only)** — aggregates "
        "`bounded_era5_weather_normalized_v1` and "
        "`bounded_entsoe_market_normalized_v1` via Repo B bounded evaluators "
        "(`coverage-inventory`). No writes/jobs — **Hermes caches no authoritative matrix**; rerun "
        f"after repairs. Requires `{BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV}`, "
        f"{_BASE_ENV}, {_SECRET_ENV}. Optional `export_format=csv` returns `csv_export` derived from "
        "the same embedded `repo_b_inventory.rows` only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "window_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z.",
            },
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z (max 31d span vs start, Repo B-validated).",
            },
            "country_codes": {
                "description": "ISO country codes (`[\"DE\",\"FR\"]`) OR comma-separated `DE,FR`.",
                "oneOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "string"},
                ],
            },
            "families": {
                "type": "array",
                "description": (
                    "Optional subset; allowed v1 ids: `bounded_era5_weather_normalized_v1`, "
                    "`bounded_entsoe_market_normalized_v1`. Omit or empty → Repo B defaults."
                ),
                "items": {"type": "string"},
            },
            "version": {"type": "string", "description": "v1.", "default": "v1"},
            "export_format": {
                "type": "string",
                "description": 'Optional. Set to "csv" to fill `csv_export` from Repo B rows in this response.',
            },
        },
        "required": ["window_start_utc", "window_end_utc", "country_codes"],
    },
}


from tools.registry import registry

registry.register(
    name="inventory_powerunits_bounded_coverage_v1",
    toolset="powerunits_bounded_coverage_inventory",
    schema=INVENTORY_BOUNDED_SCHEMA,
    handler=lambda args, **kw: inventory_powerunits_bounded_coverage_v1(
        window_start_utc=str((args or {}).get("window_start_utc", "")),
        window_end_utc=str((args or {}).get("window_end_utc", "")),
        country_codes=(args or {}).get("country_codes"),
        families=(args or {}).get("families"),
        version=str((args or {}).get("version", "") or "v1"),
        export_format=(
            None
            if (args or {}).get("export_format") is None
            else str((args or {}).get("export_format", "")).strip()
        ),
    ),
    check_fn=check_powerunits_bounded_coverage_inventory_requirements,
    requires_env=[BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV, _BASE_ENV, _SECRET_ENV],
    emoji="📊",
)
