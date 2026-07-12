#!/usr/bin/env python3
"""
Multi-country data-health orchestrator (read-only) — Hermes analyst synthesis v1.

Runs the triptychon (snapshot + inventory + worker freshness) for national Tier-1
countries and returns a cross-country rollup for Telegram / operator posture.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from powerunits_operator_country_scope_v1 import (
    default_triptychon_country_codes,
    normalize_country_codes,
    operator_country_scope_summary_v1,
)
from tools.powerunits_bounded_coverage_inventory_tool import (
    check_powerunits_bounded_coverage_inventory_requirements,
    inventory_powerunits_bounded_coverage_v1,
)
from tools.powerunits_bounded_coverage_snapshot_tool import (
    BOUNDED_COVERAGE_SNAPSHOT_PRIMARY_ENV,
    check_powerunits_bounded_coverage_snapshot_requirements,
    read_powerunits_coverage_snapshot_v1,
)
from tools.powerunits_bounded_family_gates import (
    BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV,
    WORKER_COUNTRY_COVERAGE_FRESHNESS_PRIMARY_ENV,
)
from tools.powerunits_worker_country_coverage_freshness_tool import (
    check_powerunits_worker_country_coverage_freshness_requirements,
    read_powerunits_worker_country_coverage_freshness_v1,
)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_SURFACE = "powerunits_multi_country_data_health_v1"
_DEFAULT_VERSION = "v1"
_DEFAULT_ROWS_WINDOW_DAYS = 7

_HERMES_NOTE_V1 = (
    "Hermes: read-only orchestration of Repo B triptychon for national Tier-1 countries. "
    "No jobs, ingestion, writes, or Tier promotion."
)

_INVENTORY_WORST = {"gaps": 4, "warnings": 3, "failed": 5, "skipped": 1, "ok": 0}


def check_powerunits_multi_country_data_health_requirements() -> bool:
    return (
        check_powerunits_bounded_coverage_snapshot_requirements()
        and check_powerunits_bounded_coverage_inventory_requirements()
        and check_powerunits_worker_country_coverage_freshness_requirements()
    )


def multi_country_data_health_requirement_text() -> str:
    return (
        f"{BOUNDED_COVERAGE_SNAPSHOT_PRIMARY_ENV}, "
        f"{BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV}, and "
        f"{WORKER_COUNTRY_COVERAGE_FRESHNESS_PRIMARY_ENV} must be truthy"
    )


def _default_window_utc() -> tuple[str, str]:
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=_DEFAULT_ROWS_WINDOW_DAYS)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _parse_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"parse_error": True, "raw": raw[:400]}
    except json.JSONDecodeError:
        return {"parse_error": True, "raw": raw[:400]}


def _baseline_by_country(snapshot: dict[str, Any]) -> dict[str, bool | None]:
    detail = snapshot.get("baseline_readiness_detail")
    if isinstance(detail, dict):
        out: dict[str, bool | None] = {}
        for cc, row in detail.items():
            if isinstance(row, dict):
                out[str(cc).upper()] = row.get("baseline_ready")
            else:
                out[str(cc).upper()] = None
        return out
    return {}


def _inventory_rollup(inventory: dict[str, Any]) -> dict[str, Any]:
    rows = inventory.get("rows") or inventory.get("inventory_rows") or []
    if not isinstance(rows, list):
        return {"rows_seen": 0, "by_country": {}, "action_pairs": []}

    by_country: dict[str, dict[str, str]] = {}
    action_pairs: list[dict[str, str]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        cc = str(row.get("country_code") or "").upper()
        fam = str(row.get("family") or "")
        status = str(row.get("status") or "?").lower()
        if not cc or not fam:
            continue
        prev = by_country.setdefault(cc, {})
        prev_fam = prev.get(fam)
        if prev_fam is None or _INVENTORY_WORST.get(status, -1) > _INVENTORY_WORST.get(prev_fam, -1):
            prev[fam] = status
        if status in {"gaps", "warnings", "failed"}:
            action_pairs.append(
                {
                    "country_code": cc,
                    "family": fam,
                    "status": status,
                    "suggested_next_action": str(row.get("suggested_next_action") or ""),
                }
            )

    return {
        "rows_seen": len(rows),
        "by_country": by_country,
        "action_pairs": action_pairs[:40],
    }


def _freshness_rollup(freshness: dict[str, Any]) -> dict[str, Any]:
    summary = freshness.get("summary") if isinstance(freshness.get("summary"), dict) else {}
    rows = freshness.get("rows") or []
    by_country: dict[str, list[str]] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            cc = str(row.get("country_code") or "").upper()
            outcome = str(row.get("outcome") or "").lower()
            surface = str(row.get("surface") or "")
            if cc and outcome in {"warning", "failed"}:
                by_country.setdefault(cc, []).append(f"{surface}:{outcome}")
    return {
        "summary": summary,
        "countries_with_warnings_or_failed": by_country,
    }


def _synthesize_operator_summary_v1(
    *,
    country_codes: list[str],
    window_start_utc: str,
    window_end_utc: str,
    snapshot: dict[str, Any],
    inventory: dict[str, Any],
    freshness: dict[str, Any],
) -> str:
    baseline = _baseline_by_country(snapshot)
    inv = _inventory_rollup(inventory)
    fresh = _freshness_rollup(freshness)

    green: list[str] = []
    action: list[str] = []

    for cc in country_codes:
        cc_u = cc.upper()
        reasons: list[str] = []
        br = baseline.get(cc_u)
        if br is False:
            reasons.append("baseline_not_ready")
        inv_fams = inv.get("by_country", {}).get(cc_u, {})
        bad_fams = [f for f, st in inv_fams.items() if st in {"gaps", "warnings", "failed"}]
        if bad_fams:
            reasons.append(f"inventory:{','.join(sorted(bad_fams)[:3])}")
        fresh_flags = fresh.get("countries_with_warnings_or_failed", {}).get(cc_u, [])
        if fresh_flags:
            reasons.append(f"freshness:{len(fresh_flags)}")
        if reasons:
            action.append(f"**{cc_u}** — {'; '.join(reasons)}")
        elif br is True and not bad_fams and not fresh_flags:
            green.append(cc_u)

    lines = [
        f"**Multi-country data health** ({len(country_codes)} ISO2, window `{window_start_utc}` → `{window_end_utc}`)",
        "",
        f"**Grün ({len(green)}):** {', '.join(green) if green else '—'}",
        f"**Ops-Aktion ({len(action)}):**",
    ]
    if action:
        lines.extend(f"• {a}" for a in action[:12])
        if len(action) > 12:
            lines.append(f"• … +{len(action) - 12} weitere")
    else:
        lines.append("• —")
    lines.append("")
    lines.append(
        "Read-only Triptychon — **kein Execute** ohne explizite Operator-Bestätigung."
    )
    return "\n".join(lines)


def read_powerunits_multi_country_data_health_v1(
    *,
    country_codes: Any = None,
    window_start_utc: str = "",
    window_end_utc: str = "",
    version: str = _DEFAULT_VERSION,
    rows_window_days: Any = None,
) -> str:
    """Return JSON: triptychon payloads plus ``operator_summary_v1`` cross-country synthesis."""
    if not check_powerunits_multi_country_data_health_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "read_attempted": False,
                "success": False,
                "message": (
                    f"{multi_country_data_health_requirement_text()}; "
                    f"also requires {_BASE_ENV} and {_SECRET_ENV}."
                ),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
                "country_scope_v1": operator_country_scope_summary_v1(),
            },
            ensure_ascii=False,
        )

    cc_list, cc_err = normalize_country_codes(country_codes)
    if cc_err or not cc_list:
        cc_list = default_triptychon_country_codes()

    ws = (window_start_utc or "").strip()
    we = (window_end_utc or "").strip()
    if not ws or not we:
        ws, we = _default_window_utc()

    ver = (version or "").strip() or _DEFAULT_VERSION
    rwd = rows_window_days
    if rwd is None:
        rwd = _DEFAULT_ROWS_WINDOW_DAYS

    snap_raw = read_powerunits_coverage_snapshot_v1(
        country_codes=cc_list,
        window_start_utc=ws,
        window_end_utc=we,
        version=ver,
    )
    inv_raw = inventory_powerunits_bounded_coverage_v1(
        country_codes=cc_list,
        window_start_utc=ws,
        window_end_utc=we,
        version=ver,
    )
    fresh_raw = read_powerunits_worker_country_coverage_freshness_v1(
        national_country_codes=cc_list,
        rows_window_days=rwd,
    )

    snapshot = _parse_json(snap_raw)
    inventory = _parse_json(inv_raw)
    freshness = _parse_json(fresh_raw)

    all_ok = all(
        p.get("success") is not False and p.get("http_status_from_repo_b") in (200, None)
        for p in (snapshot, inventory, freshness)
        if not p.get("parse_error")
    )

    baseline = _baseline_by_country(snapshot)
    inv_roll = _inventory_rollup(inventory)
    fresh_roll = _freshness_rollup(freshness)

    green_count = 0
    for cc in cc_list:
        cc_u = cc.upper()
        inv_fams = inv_roll.get("by_country", {}).get(cc_u, {})
        bad_fams = [f for f, st in inv_fams.items() if st in {"gaps", "warnings", "failed"}]
        fresh_bad = fresh_roll.get("countries_with_warnings_or_failed", {}).get(cc_u, [])
        if baseline.get(cc_u) is True and not bad_fams and not fresh_bad:
            green_count += 1

    operator_summary = _synthesize_operator_summary_v1(
        country_codes=cc_list,
        window_start_utc=ws,
        window_end_utc=we,
        snapshot=snapshot,
        inventory=inventory,
        freshness=freshness,
    )

    merged: dict[str, Any] = {
        "surface": _SURFACE,
        "read_attempted": True,
        "success": all_ok,
        "country_codes": cc_list,
        "window_start_utc": ws,
        "window_end_utc": we,
        "country_scope_v1": operator_country_scope_summary_v1(),
        "rollup_v1": {
            "countries_requested": len(cc_list),
            "baseline_ready_count": sum(1 for v in baseline.values() if v is True),
            "green_count": green_count,
            "inventory_action_pairs": len(inv_roll.get("action_pairs") or []),
            "freshness_flagged_countries": len(
                fresh_roll.get("countries_with_warnings_or_failed") or {}
            ),
        },
        "snapshot": {
            "success": snapshot.get("success"),
            "http_status_from_repo_b": snapshot.get("http_status_from_repo_b"),
            "baseline_ready": snapshot.get("baseline_ready"),
            "baseline_by_country": baseline,
            "correlation_id": snapshot.get("correlation_id"),
            "error_code": snapshot.get("error_code"),
        },
        "inventory": {
            "success": inventory.get("success"),
            "http_status_from_repo_b": inventory.get("http_status_from_repo_b"),
            "rollup": inv_roll,
            "correlation_id": inventory.get("correlation_id"),
            "error_code": inventory.get("error_code"),
        },
        "freshness": {
            "success": freshness.get("success"),
            "http_status_from_repo_b": freshness.get("http_status_from_repo_b"),
            "rollup": fresh_roll,
            "correlation_id": freshness.get("correlation_id"),
            "error_code": freshness.get("error_code"),
        },
        "operator_summary_v1": operator_summary,
        "hermes_operator_note_v1": _HERMES_NOTE_V1,
    }
    return json.dumps(merged, ensure_ascii=False)


MULTI_COUNTRY_DATA_HEALTH_SCHEMA_V1 = {
    "name": "read_powerunits_multi_country_data_health_v1",
    "description": (
        "**Multi-country data-health analyst (read-only)** — orchestrates the triptychon "
        "(`read_powerunits_coverage_snapshot_v1`, `inventory_powerunits_bounded_coverage_v1`, "
        "`read_powerunits_worker_country_coverage_freshness_v1`) for **national Tier-1** ISO2 "
        "(default 11 countries: DE, NL, BE, FR, AT, CZ, PL, FI, HU, SK, RO). Returns "
        "**`operator_summary_v1`** cross-country green vs ops-action rollup. "
        "**No** jobs, ingestion, or writes. Requires all three data-health gates plus "
        f"**`{_BASE_ENV}`**, **`{_SECRET_ENV}`**."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country_codes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "ISO2 list; default national Tier-1 (11). Omit for full national scope."
                ),
            },
            "window_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 (Z); default 7d ending today 00:00Z.",
            },
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 (Z).",
            },
            "version": {
                "type": "string",
                "description": "Dataset version; default v1.",
                "default": _DEFAULT_VERSION,
            },
            "rows_window_days": {
                "type": "integer",
                "description": "Worker freshness lookback days; default 7.",
            },
        },
        "required": [],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_multi_country_data_health_v1",
    toolset="powerunits_multi_country_data_health",
    schema=MULTI_COUNTRY_DATA_HEALTH_SCHEMA_V1,
    handler=lambda args, **kw: read_powerunits_multi_country_data_health_v1(
        country_codes=(args or {}).get("country_codes"),
        window_start_utc=str((args or {}).get("window_start_utc", "") or ""),
        window_end_utc=str((args or {}).get("window_end_utc", "") or ""),
        version=str((args or {}).get("version", "") or _DEFAULT_VERSION),
        rows_window_days=(args or {}).get("rows_window_days"),
    ),
    check_fn=check_powerunits_multi_country_data_health_requirements,
    requires_env=[
        BOUNDED_COVERAGE_SNAPSHOT_PRIMARY_ENV,
        BOUNDED_COVERAGE_INVENTORY_PRIMARY_ENV,
        WORKER_COUNTRY_COVERAGE_FRESHNESS_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🌍",
)
