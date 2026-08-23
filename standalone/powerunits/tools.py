"""Read-only PowerUnits plugin handlers.

Early-fail only. Never turns an invalid Repo-B operation into an
authoritative valid one.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping

from . import client
from .host import base_url_is_configured
from .operations import (
    BASE_URL_ENV,
    FORBIDDEN_TRANSPORT_KEYS,
    SECRET_ENV,
    TOOLSET_NAME,
    OperationSpec,
    get_operation,
)

_HERMES_NOTE_SNAPSHOT = (
    "Hermes plugin: read-only bounded POST to Repo B coverage-snapshot. "
    "No jobs, no ingestion, no writes. Repo B JSON is canonical."
)
_HERMES_NOTE_BZN = (
    "Hermes plugin: read-only bounded POST to Repo B. No jobs, no ingestion, "
    "no writes, no Hermes-side DB. Full JSON is Repo B."
)
_HERMES_STATEMENT_INVENTORY = (
    "Hermes performed no direct SQL. One read-only POST to Repo B "
    "`/internal/hermes/bounded/v1/coverage-inventory`."
)
_HERMES_STATEMENT_OPTION_D = (
    "Hermes performed no direct SQL. Readiness used exactly one HTTP POST to "
    "the Powerunits bounded internal readiness-window API."
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False)


def gate_enabled(spec: OperationSpec) -> bool:
    if not _truthy_env(spec.gate_env):
        return False
    if not base_url_is_configured():
        return False
    if not (os.getenv(SECRET_ENV) or "").strip():
        return False
    return True


def check_coverage_snapshot() -> bool:
    return gate_enabled(get_operation("read_powerunits_coverage_snapshot_v1"))


def check_inventory() -> bool:
    return gate_enabled(get_operation("inventory_powerunits_bounded_coverage_v1"))


def check_bzn_readiness() -> bool:
    return gate_enabled(get_operation("read_powerunits_entsoe_bzn_price_readiness_v1"))


def check_option_d_readiness() -> bool:
    return gate_enabled(get_operation("readiness_powerunits_option_d_bounded_window"))


def _feature_disabled(spec: OperationSpec) -> dict[str, Any]:
    return {
        "error_code": "feature_disabled",
        "surface": spec.operation_id,
        "success": False,
        "read_attempted": False,
        "inventory_attempted": False,
        "readiness_attempted": False,
        "http_status": None,
        "http_status_from_repo_b": None,
        "message": (
            f"{spec.gate_env} must be truthy and {BASE_URL_ENV} / {SECRET_ENV} must be set."
        ),
    }


def _unexpected_fields(args: Mapping[str, Any], spec: OperationSpec) -> list[str]:
    extra = sorted(set(args) - spec.allowed_request_fields)
    transport = sorted(set(args) & FORBIDDEN_TRANSPORT_KEYS)
    return sorted(set(extra) | set(transport))


def _validate_request(args: Mapping[str, Any], spec: OperationSpec) -> dict[str, Any] | None:
    unexpected = _unexpected_fields(args, spec)
    if unexpected:
        return {
            "success": False,
            "error_code": "unexpected_field",
            "surface": spec.operation_id,
            "read_attempted": False,
            "rejected_fields": unexpected,
            "message": f"unknown or forbidden fields: {unexpected}",
        }
    missing = [key for key in sorted(spec.required_request_fields) if not _present(args.get(key))]
    if missing:
        code = "invalid_window" if any("window" in key or key in {"start", "end"} for key in missing) else "client_validation"
        if "country_codes" in missing or "country" in missing:
            code = "invalid_country_codes" if "country_codes" in missing else "client_validation"
        return {
            "success": False,
            "error_code": code,
            "surface": spec.operation_id,
            "read_attempted": False,
            "message": f"required fields missing or empty: {missing}",
        }
    return None


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return bool(value)
    return True


def _normalize_country_codes(raw: Any, *, required: bool) -> tuple[list[str] | None, str | None]:
    if raw is None:
        if required:
            return None, "missing country_codes"
        return None, None
    if isinstance(raw, str):
        cc = [part.strip().upper() for part in raw.split(",") if part.strip()]
        if not cc:
            return None, "country_codes resolved empty after parsing"
        return cc, None
    if isinstance(raw, list):
        cc = [(str(item) or "").strip().upper() for item in raw if str(item or "").strip()]
        if not cc:
            return None, "country_codes list was empty after normalization"
        return cc, None
    return None, "country_codes must be a list of ISO2 strings or a comma-separated string"


def _snapshot_chat_summary(payload: Mapping[str, Any]) -> str:
    lines: list[str] = []
    baseline = payload.get("baseline_ready")
    reason = payload.get("baseline_readiness_reason")
    lines.append(f"**Baseline ready:** `{baseline}` — {reason or 'n/a'}")
    tw = payload.get("time_window") or {}
    if isinstance(tw, dict):
        lines.append(
            f"Window `[start,end)`: `{tw.get('start_utc')}` → `{tw.get('end_utc_exclusive')}` "
            f"(expected_hours={tw.get('expected_hours')})"
        )
    cid = payload.get("correlation_id") or "n/a"
    lines.append("")
    lines.append("Read-only Repo B snapshot — **rerun after repairs**.")
    lines.append(f"_correlation_id: `{cid}`")
    return "\n".join(lines)


def _inventory_chat_summary(payload: Mapping[str, Any]) -> str:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        repo = payload.get("repo_b_inventory")
        if isinstance(repo, dict) and isinstance(repo.get("rows"), list):
            rows = repo["rows"]
        else:
            rows = []
    cid = payload.get("correlation_id") or "n/a"
    if not rows:
        return f"No inventory rows (correlation_id={cid})."
    return f"Inventory rows={len(rows)} (correlation_id={cid})."


def read_powerunits_coverage_snapshot_v1(args: dict | None = None, **_kwargs: Any) -> str:
    spec = get_operation("read_powerunits_coverage_snapshot_v1")
    args = args or {}
    if not gate_enabled(spec):
        out = _feature_disabled(spec)
        out["hermes_operator_note_v1"] = _HERMES_NOTE_SNAPSHOT
        return _dump(out)
    refused = _validate_request(args, spec)
    if refused:
        refused["hermes_operator_note_v1"] = _HERMES_NOTE_SNAPSHOT
        return _dump(refused)
    codes, err = _normalize_country_codes(args.get("country_codes"), required=True)
    if err or not codes:
        return _dump(
            {
                "surface": spec.operation_id,
                "read_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "error_code": "invalid_country_codes",
                "message": err or "country_codes required",
                "hermes_operator_note_v1": _HERMES_NOTE_SNAPSHOT,
            }
        )
    body = {
        "country_codes": codes,
        "window_start_utc": str(args.get("window_start_utc") or "").strip(),
        "window_end_utc": str(args.get("window_end_utc") or "").strip(),
        "version": str(args.get("version") or "v1").strip() or "v1",
    }
    merged = client.invoke(spec.operation_id, body)
    merged["hermes_operator_note_v1"] = _HERMES_NOTE_SNAPSHOT
    if merged.get("http_status_from_repo_b") == 200 and merged.get("success") is not False:
        merged["chat_summary"] = _snapshot_chat_summary(merged)
    return _dump(merged)


def inventory_powerunits_bounded_coverage_v1(args: dict | None = None, **_kwargs: Any) -> str:
    spec = get_operation("inventory_powerunits_bounded_coverage_v1")
    args = args or {}
    if not gate_enabled(spec):
        out = _feature_disabled(spec)
        out["chat_summary"] = "Inventory disabled."
        out["hermes_statement"] = _HERMES_STATEMENT_INVENTORY
        return _dump(out)
    refused = _validate_request(args, spec)
    if refused:
        refused["chat_summary"] = ""
        refused["hermes_statement"] = _HERMES_STATEMENT_INVENTORY
        return _dump(refused)
    codes, err = _normalize_country_codes(args.get("country_codes"), required=True)
    if err or not codes:
        return _dump(
            {
                "surface": spec.operation_id,
                "error_code": "client_validation",
                "validation_messages": [err or "invalid_country_codes"],
                "inventory_attempted": False,
                "http_status": None,
                "success": False,
                "chat_summary": "",
                "hermes_statement": _HERMES_STATEMENT_INVENTORY,
            }
        )
    body: dict[str, Any] = {
        "window_start_utc": str(args.get("window_start_utc") or "").strip(),
        "window_end_utc": str(args.get("window_end_utc") or "").strip(),
        "country_codes": codes,
        "version": str(args.get("version") or "v1").strip() or "v1",
    }
    families = args.get("families")
    if families is not None:
        if not isinstance(families, list):
            return _dump(
                {
                    "surface": spec.operation_id,
                    "error_code": "client_validation",
                    "success": False,
                    "inventory_attempted": False,
                    "chat_summary": "",
                    "hermes_statement": _HERMES_STATEMENT_INVENTORY,
                    "validation_messages": ["families must be an array of v1 inventory family ids or omitted"],
                }
            )
        parsed = [(str(item) or "").strip() for item in families if str(item or "").strip()]
        if parsed:
            body["families"] = parsed
    merged = client.invoke(spec.operation_id, body)
    merged["inventory_attempted"] = bool(merged.get("read_attempted"))
    merged["hermes_statement"] = _HERMES_STATEMENT_INVENTORY
    if "repo_b_inventory" not in merged:
        merged["repo_b_inventory"] = {
            key: value
            for key, value in merged.items()
            if key
            not in {
                "surface",
                "read_attempted",
                "inventory_attempted",
                "http_status",
                "http_status_from_repo_b",
                "hermes_statement",
                "chat_summary",
                "effect_class",
                "response_body_summary",
            }
        }
    merged["chat_summary"] = _inventory_chat_summary(merged)
    return _dump(merged)


def read_powerunits_entsoe_bzn_price_readiness_v1(args: dict | None = None, **_kwargs: Any) -> str:
    spec = get_operation("read_powerunits_entsoe_bzn_price_readiness_v1")
    args = args or {}
    if not gate_enabled(spec):
        out = _feature_disabled(spec)
        out["hermes_operator_note_v1"] = _HERMES_NOTE_BZN
        return _dump(out)
    refused = _validate_request(args, spec)
    if refused:
        refused["hermes_operator_note_v1"] = _HERMES_NOTE_BZN
        return _dump(refused)
    codes, err = _normalize_country_codes(args.get("country_codes"), required=False)
    if err:
        return _dump(
            {
                "surface": spec.operation_id,
                "read_attempted": False,
                "http_status": None,
                "success": False,
                "error_code": "invalid_country_codes",
                "message": err,
                "hermes_operator_note_v1": _HERMES_NOTE_BZN,
            }
        )
    body: dict[str, Any] = {
        "window_start_utc": str(args.get("window_start_utc") or "").strip(),
        "window_end_utc": str(args.get("window_end_utc") or "").strip(),
        "table_version": str(args.get("table_version") or "bzn_advisory_v1").strip()
        or "bzn_advisory_v1",
    }
    if codes:
        body["country_codes"] = codes
    merged = client.invoke(spec.operation_id, body)
    merged["hermes_operator_note_v1"] = _HERMES_NOTE_BZN
    return _dump(merged)


def readiness_powerunits_option_d_bounded_window(args: dict | None = None, **_kwargs: Any) -> str:
    spec = get_operation("readiness_powerunits_option_d_bounded_window")
    args = args or {}
    if not gate_enabled(spec):
        out = _feature_disabled(spec)
        out["slice"] = None
        out["readiness"] = None
        return _dump(out)
    refused = _validate_request(args, spec)
    if refused:
        refused["slice"] = None
        refused["readiness"] = None
        refused["readiness_attempted"] = False
        refused["hermes_statement"] = _HERMES_STATEMENT_OPTION_D
        return _dump(refused)
    country = str(args.get("country") or "").strip()
    start = str(args.get("start") or "").strip()
    end = str(args.get("end") or "").strip()
    version = str(args.get("version") or "").strip()
    # Early-fail on emptiness only. Country/window domain rules stay in Repo B.
    body: dict[str, Any] = {
        "country_code": country.upper(),
        "version": version,
        "window_start_utc": start,
        "window_end_utc": end,
    }
    pipeline_run_id = str(args.get("pipeline_run_id") or "").strip()
    if pipeline_run_id:
        body["pipeline_run_id"] = pipeline_run_id
    merged = client.invoke(spec.operation_id, body)
    merged["readiness_attempted"] = bool(merged.get("read_attempted"))
    merged["hermes_statement"] = _HERMES_STATEMENT_OPTION_D
    merged.setdefault(
        "slice",
        {
            "country": country.upper(),
            "version": version,
            "start_utc": start,
            "end_utc_exclusive": end,
        },
    )
    if "readiness" not in merged:
        merged["readiness"] = None
    return _dump(merged)


HANDLERS = {
    "read_powerunits_coverage_snapshot_v1": read_powerunits_coverage_snapshot_v1,
    "inventory_powerunits_bounded_coverage_v1": inventory_powerunits_bounded_coverage_v1,
    "read_powerunits_entsoe_bzn_price_readiness_v1": read_powerunits_entsoe_bzn_price_readiness_v1,
    "readiness_powerunits_option_d_bounded_window": readiness_powerunits_option_d_bounded_window,
}

CHECK_FNS = {
    "read_powerunits_coverage_snapshot_v1": check_coverage_snapshot,
    "inventory_powerunits_bounded_coverage_v1": check_inventory,
    "read_powerunits_entsoe_bzn_price_readiness_v1": check_bzn_readiness,
    "readiness_powerunits_option_d_bounded_window": check_option_d_readiness,
}

assert TOOLSET_NAME
