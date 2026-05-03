#!/usr/bin/env python3
"""
Bounded rollout **governance readout** — read-only POST to Repo B ``…/rollout-governance`` + optional Hermes overlay.

Repo B remains canonical for ``repo_b_allowed`` and ``*_ready`` flags; Hermes fills ``hermes_allowed_now`` /
``effective_status_cross_layer`` from Railway env (never overwrites Repo B truth fields in the JSON we return).
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

from tools.bounded_rollout_governance_projection_v1 import merge_repo_b_rollout_governance_payload_v1
from tools.powerunits_bounded_coverage_inventory_tool import _persist_csv_under_workspace_exports
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


GOVERNANCE_CSV_EXPORT_COLUMNS_V1: tuple[str, ...] = (
    "family",
    "country_code",
    "repo_b_allowed",
    "hermes_allowed_now",
    "inventory_ready",
    "execute_ready",
    "validate_ready",
    "summary_ready",
    "coverage_scan_ready",
    "campaign_ready",
    "planner_ready",
    "effective_status",
    "blocking_reason",
    "suggested_next_action",
    "effective_status_cross_layer",
    "blocking_reason_cross_layer",
)


def _governance_rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(GOVERNANCE_CSV_EXPORT_COLUMNS_V1)
    for row in rows:
        if not isinstance(row, dict):
            continue
        hnow = row.get("hermes_allowed_now")
        hnow_s = (
            json.dumps(hnow, ensure_ascii=False)
            if isinstance(hnow, dict)
            else ("" if hnow is None else json.dumps(hnow, ensure_ascii=False))
        )
        w.writerow(
            [
                row.get("family"),
                row.get("country_code"),
                row.get("repo_b_allowed"),
                hnow_s,
                row.get("inventory_ready"),
                row.get("execute_ready"),
                row.get("validate_ready"),
                row.get("summary_ready"),
                row.get("coverage_scan_ready"),
                row.get("campaign_ready"),
                row.get("planner_ready"),
                row.get("effective_status"),
                row.get("blocking_reason") if row.get("blocking_reason") is not None else "",
                row.get("suggested_next_action") if row.get("suggested_next_action") is not None else "",
                row.get("effective_status_cross_layer") if row.get("effective_status_cross_layer") else "",
                row.get("blocking_reason_cross_layer") if row.get("blocking_reason_cross_layer") else "",
            ]
        )
    return buf.getvalue()


def governance_powerunits_bounded_rollout_read_v1(
    *,
    country_codes_csv: str | None = None,
    version: str = "v1",
    apply_hermes_overlay: bool = True,
    export_format: str | None = None,
    exports_csv_workspace_filename: str | None = None,
    exports_csv_workspace_overwrite_mode: str | None = None,
    _http_post: Any = None,
) -> str:
    poster = _http_post or _default_http_post
    ef_raw = str(export_format or "").strip().lower()
    export_csv_requested = ef_raw in ("csv", "text/csv")

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

    if parsed.get("success") is True:
        _meta = parsed.get("meta")
        if isinstance(_meta, dict):
            ga = _meta.get("generated_at_utc")
            if isinstance(ga, str) and ga.strip():
                parsed["repo_b_rollout_governance_generated_at_utc"] = ga.strip()
            cm = _meta.get("canonical_bounded_entso_market_v1_iso2")
            cf = _meta.get("canonical_bounded_entso_forecast_v1_iso2")
            if isinstance(cm, list):
                parsed["repo_b_canonical_bounded_entso_market_v1_iso2"] = cm
            if isinstance(cf, list):
                parsed["repo_b_canonical_bounded_entso_forecast_v1_iso2"] = cf
            parsed.setdefault(
                "hint_governance_truth_vs_overlay_v1",
                "Repo B lane truth: **repo_b_allowed** + **execute_ready** on each row. "
                "**effective_status_cross_layer** reflects Hermes Railway gates + allowlist projection. "
                "If cross-layer says gated but HTTP to Repo B works, check **HERMES_POWERUNITS_ENTSOE_*_BOUNDED_ALLOWED_COUNTRIES** "
                "(market vs forecast are separate env vars). "
                "**repo_b_rollout_governance_generated_at_utc** + **repo_b_canonical_bounded_entso_*_v1_iso2** echo Repo B **meta** for Telegram-friendly reads.",
            )

    if status != 200 or not parsed.get("success"):
        parsed.setdefault(
            "response_body_summary",
            raw_text,
        )
        return json.dumps(parsed, ensure_ascii=False)

    persist_csv_stub = (
        str(exports_csv_workspace_filename or "").strip() if exports_csv_workspace_filename else ""
    )

    rows = parsed.get("rows")
    export_csv_body: str | None = None
    if export_csv_requested and isinstance(rows, list) and rows:
        export_csv_body = _governance_rows_to_csv(rows)
        parsed["governance_csv_export_columns_v1"] = list(GOVERNANCE_CSV_EXPORT_COLUMNS_V1)
        parsed["csv_export"] = export_csv_body
        parsed["hint_export_governance_csv"] = (
            "**`csv_export`**: Hermes-derived UTF‑8 CSV from **`rows`** in this reply (Repo B JSON remains canonical). "
            "Columns **`effective_status`** / **`blocking_reason`** are Repo‑B rollup; **`_*_cross_layer`** appear "
            "when **`apply_hermes_overlay`** merged Hermes gates. **`hermes_allowed_now`** is compact JSON in-cell. "
            "Optional **`exports_csv_workspace_filename`**: persists the same CSV to **`hermes_workspace/exports/`** — "
            "prefer a **timestamped** basename (e.g. `governance-20260430T120000Z.csv`) so clients do not silently "
            "reuse an older export; use **`exports_csv_workspace_overwrite_mode=overwrite`** when reusing a fixed name."
        )

        if persist_csv_stub:
            csv_ow = str(exports_csv_workspace_overwrite_mode or "forbid").strip().lower()
            saved, rel_path, pnote = _persist_csv_under_workspace_exports(
                basename=persist_csv_stub,
                csv_body=export_csv_body or "",
                overwrite_mode=csv_ow,
            )
            parsed["csv_workspace_saved"] = saved
            if rel_path:
                parsed["csv_workspace_path"] = rel_path
            parsed["csv_workspace_note"] = pnote

    return json.dumps(parsed, ensure_ascii=False)


BOUNDED_ROLLOUT_GOVERNANCE_SCHEMA_V1 = {
    "name": "governance_powerunits_bounded_rollout_read_v1",
    "description": (
        "**Read-only rollout governance v1**: single POST `POST /internal/hermes/bounded/v1/rollout-governance` "
        f"(Repo B). Optional Hermes merges Railway gate truth into **`hermes_allowed_now`** (+ cross-layer statuses) "
        f"without changing Repo canonical readiness flags. Gate `{BOUNDED_ROLLOUT_GOVERNANCE_PRIMARY_ENV}` "
        f"plus {_BASE_ENV} / {_SECRET_ENV}. Omit **country_codes_csv** ⇒ Repo B bounded default universe. "
        '**export_format=`csv`** (alias **text/csv**) fills **`csv_export`** (+ optional workspace save) from governance '
        "**`rows`** in this Hermes envelope only — Repo B remains JSON-canonical."
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
            "export_format": {
                "type": "string",
                "description": (
                    'Optional **`csv`** (**`text/csv`**): derives **`csv_export`** from Repo B **`rows`** (Hermes-rounded '
                    "envelope) in this reply; see **`hint_export_governance_csv`**."
                ),
            },
            "exports_csv_workspace_filename": {
                "type": "string",
                "description": (
                    "Optional basename ending in `.csv`; requires **`export_format=csv`**. Writes **`exports/`** on the "
                    "bounded Hermes workspace volume when **`csv_workspace_saved`**. Prefer ISO‑8601 timestamped names "
                    "to avoid stale workspace reads (e.g. `rollout-governance-20260430T120000Z.csv`)."
                ),
            },
            "exports_csv_workspace_overwrite_mode": {
                "type": "string",
                "description": "`forbid` (default) or `overwrite` when saving governance CSV under workspace exports.",
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
        export_format=str((args or {}).get("export_format") or "").strip() or None,
        exports_csv_workspace_filename=(
            str((args or {}).get("exports_csv_workspace_filename") or "").strip() or None
        ),
        exports_csv_workspace_overwrite_mode=(
            str((args or {}).get("exports_csv_workspace_overwrite_mode") or "").strip() or None
        ),
    ),
    check_fn=check_powerunits_bounded_rollout_governance_requirements,
    requires_env=[
        BOUNDED_ROLLOUT_GOVERNANCE_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="📋",
)
