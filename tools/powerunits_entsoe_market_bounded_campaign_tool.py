#!/usr/bin/env python3
"""
Hermes bounded ENTSO-E market sync **campaign v1** — sequential execute + summary
over contiguous ≤7d windows (Repo B bounded **DE/NL v1 Tier** ISO2 slice), fail-fast.

Orchestrates only the existing bounded Repo B HTTP endpoints (no route proliferation).

Gated by ``HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED`` and requires
bounded execute+summary access (``HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`` **or**
both legacy execute+summary flags), base URL, and bearer.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from tools.powerunits_bounded_family_gates import (
    ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ENTSOE_MARKET_BOUNDED_LEGACY_ENV,
    ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
    campaign_entsoe_bounded_http_primitives_enabled,
    entsoe_market_bounded_request_country_permitted,
)

from tools.powerunits_entsoe_market_bounded_execute_tool import (
    check_powerunits_entsoe_market_bounded_execute_requirements,
    execute_powerunits_entsoe_market_bounded_slice,
)
from tools.powerunits_entsoe_market_bounded_slice import validate_entsoe_bounded_campaign
from tools.powerunits_entsoe_market_bounded_countries import (
    BOUNDED_ENTSOE_MARKET_USER_FACING_ISO2_DOCUMENTATION_V1 as _ISO_DOC_ENTSOE_MARKET,
)

from tools.powerunits_entsoe_market_bounded_summary_tool import (
    check_powerunits_entsoe_market_bounded_summary_requirements,
    summarize_powerunits_entsoe_market_bounded_window,
)

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED"
_SURFACE = "powerunits_entsoe_market_bounded_campaign"


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_entsoe_market_bounded_campaign_requirements() -> bool:
    if not _truthy_env(_FEATURE_ENV):
        return False
    if not campaign_entsoe_bounded_http_primitives_enabled():
        return False
    if not (
        (os.getenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL") or "").strip()
        and (os.getenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET") or "").strip()
    ):
        return False
    return True


def _iso_z(dt: Any) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def campaign_powerunits_entsoe_market_bounded_de(
    *,
    campaign_start_utc: str,
    campaign_end_utc: str,
    country: str = "DE",
    version: str = "v1",
    _http_post: Any = None,
) -> str:
    """Run up to 5 contiguous ≤7d windows; execute then summary each; fail-fast."""

    base_statement = (
        "Hermes performed no direct SQL. This tool only chains existing bounded HTTP POSTs to "
        "Powerunits `…/entsoe-market-sync/recompute` and `…/entsoe-market-sync/summary-window` "
        "per sub-window. Does not call market_feature_job, market_driver_feature_job, or "
        "expand_market_data."
    )

    if not check_powerunits_entsoe_market_bounded_campaign_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": (
                    f"{_FEATURE_ENV} must be truthy; also need "
                    f"`{ENTSOE_MARKET_BOUNDED_PRIMARY_ENV}` (or both legacy execute+summary "
                    f"flags `{ENTSOE_MARKET_BOUNDED_LEGACY_ENV['execute']}` + "
                    f"`{ENTSOE_MARKET_BOUNDED_LEGACY_ENV['summary']}`) with optional "
                    f"`{ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV}` when primary is used; "
                    "and POWERUNITS_INTERNAL_EXECUTE_BASE_URL / POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET set."
                ),
                "campaign": None,
                "windows": [],
                "windows_planned": 0,
                "windows_attempted": 0,
                "windows_succeeded": 0,
                "stopped_reason": "feature_disabled",
                "next_manual_step": "Enable campaign + execute + summary flags and required env; redeploy.",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    start_s = (campaign_start_utc or "").strip()
    end_s = (campaign_end_utc or "").strip()
    country_s = (country or "").strip() or "DE"
    version_s = (version or "").strip() or "v1"

    try:
        cc, ver, windows = validate_entsoe_bounded_campaign(country_s, start_s, end_s, version_s)
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_messages": [str(e)],
                "campaign": {
                    "country": (country_s or "").strip().upper(),
                    "version": version_s,
                    "campaign_start_utc": start_s,
                    "campaign_end_utc_exclusive": end_s,
                },
                "windows": [],
                "windows_planned": 0,
                "windows_attempted": 0,
                "windows_succeeded": 0,
                "stopped_reason": "campaign_validation_failed",
                "next_manual_step": "Fix slice parameters (bounded DE or NL ISO2, v1, end > start, span ≤31d, implies ≤5 sub-windows).",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    if not entsoe_market_bounded_request_country_permitted(cc):
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_messages": [
                    f"Country `{cc}` not permitted under current bounded ENTSO-E gates: extend "
                    f"`{ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV}` when "
                    f"`{ENTSOE_MARKET_BOUNDED_PRIMARY_ENV}` is truthy (**env var omitted ⇒ implicit DE-only**)."
                ],
                "campaign": {
                    "country": cc,
                    "version": ver,
                    "campaign_start_utc": start_s,
                    "campaign_end_utc_exclusive": end_s,
                },
                "windows": [],
                "windows_planned": 0,
                "windows_attempted": 0,
                "windows_succeeded": 0,
                "stopped_reason": "country_not_permitted",
                "next_manual_step": "Adjust Railway allowlist so this Tier-v1 ENTSO ISO2 is explicitly permitted.",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    planned = len(windows)
    rows: list[dict[str, Any]] = []
    windows_attempted = 0
    windows_succeeded = 0
    stopped_reason = "completed"
    next_manual = (
        "Campaign completed. market_feature_job / market_driver_feature_job were not run; "
        "refresh features/drivers only via separate operator paths if needed."
    )

    for idx, (w_start, w_end) in enumerate(windows):
        ws = _iso_z(w_start)
        we = _iso_z(w_end)
        slice_echo = {
            "country": cc,
            "version": ver,
            "window_start_utc": ws,
            "window_end_utc_exclusive": we,
        }

        ex_raw = execute_powerunits_entsoe_market_bounded_slice(
            country=cc,
            start=ws,
            end=we,
            version=ver,
            _http_post=_http_post,
        )
        try:
            ex = json.loads(ex_raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("entsoe bounded campaign: execute returned non-JSON")
            rows.append(
                {
                    "index": idx,
                    "slice": slice_echo,
                    "execute_success": False,
                    "pipeline_run_id": None,
                    "rows_written": None,
                    "summary_outcome_class": None,
                    "summary_success": None,
                    "error": "execute_response_not_json",
                }
            )
            windows_attempted += 1
            stopped_reason = "execute_failed"
            next_manual = (
                f"Campaign stopped at window index {idx}: execute response was not JSON. "
                "Inspect Hermes logs and retry from this window."
            )
            break

        windows_attempted += 1
        ex_ok = bool(ex.get("success")) and int(ex.get("http_status") or 0) == 200
        prid = ex.get("pipeline_run_id")
        prid_s = str(prid).strip() if prid is not None else None
        rows_written = ex.get("rows_written")

        if not ex_ok:
            rows.append(
                {
                    "index": idx,
                    "slice": slice_echo,
                    "execute_success": False,
                    "http_status_execute": ex.get("http_status"),
                    "pipeline_run_id": prid_s,
                    "rows_written": rows_written,
                    "summary_outcome_class": None,
                    "summary_success": None,
                    "error_class": ex.get("error_class"),
                }
            )
            stopped_reason = "execute_failed"
            next_manual = (
                f"Campaign stopped at window index {idx}: execute did not succeed "
                f"(http_status={ex.get('http_status')}). Fix upstream and rerun from this window."
            )
            break

        sum_raw = summarize_powerunits_entsoe_market_bounded_window(
            country=cc,
            start=ws,
            end=we,
            version=ver,
            pipeline_run_id=prid_s,
            _http_post=_http_post,
        )
        try:
            su = json.loads(sum_raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            rows.append(
                {
                    "index": idx,
                    "slice": slice_echo,
                    "execute_success": True,
                    "http_status_execute": ex.get("http_status"),
                    "pipeline_run_id": prid_s,
                    "rows_written": rows_written,
                    "summary_outcome_class": None,
                    "summary_success": False,
                    "error": "summary_response_not_json",
                }
            )
            stopped_reason = "summary_failed"
            next_manual = (
                f"Campaign stopped at window index {idx}: summary response was not JSON. "
                "Inspect logs; re-run summary for this slice or retry campaign from this window."
            )
            break

        sum_ok = int(su.get("http_status") or 0) == 200 and bool(su.get("success"))
        oc = su.get("outcome_class") if isinstance(su.get("outcome_class"), str) else None
        rows.append(
            {
                "index": idx,
                "slice": slice_echo,
                "execute_success": True,
                "http_status_execute": ex.get("http_status"),
                "pipeline_run_id": prid_s,
                "rows_written": rows_written,
                "summary_outcome_class": oc,
                "summary_success": sum_ok,
                "http_status_summary": su.get("http_status"),
            }
        )

        if not sum_ok:
            stopped_reason = "summary_failed"
            next_manual = (
                f"Campaign stopped at window index {idx}: summary HTTP or outcome not ok "
                f"(http_status={su.get('http_status')}, outcome_class={oc!r}). "
                "Inspect Repo B / operator_next in summary body; retry from this window."
            )
            break

        windows_succeeded += 1

    return json.dumps(
        {
            "surface": _SURFACE,
            "campaign": {
                "country": cc,
                "version": ver,
                "campaign_start_utc": start_s,
                "campaign_end_utc_exclusive": end_s,
            },
            "windows": rows,
            "windows_planned": planned,
            "windows_attempted": windows_attempted,
            "windows_succeeded": windows_succeeded,
            "stopped_reason": stopped_reason,
            "next_manual_step": next_manual,
            "hermes_statement": base_statement,
        },
        ensure_ascii=False,
    )


CAMPAIGN_ENTSOE_SCHEMA = {
    "name": "campaign_powerunits_entsoe_market_bounded_de",
    "description": (
        "**Bounded ENTSO-E market sync campaign v1** — sequential execute + summary "
        "for contiguous sub-windows (Repo B Tier v1 ISO2 **DE** or **NL**, each ≤7 d); "
        "campaign span ≤31 d, ≤5 windows. "
        "Fail-fast on first failed execute or failed summary HTTP/outcome. Requires "
        f"{_FEATURE_ENV} plus `{ENTSOE_MARKET_BOUNDED_PRIMARY_ENV}` (or legacy execute+summary), "
        "POWERUNITS_INTERNAL_EXECUTE_BASE_URL, POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "campaign_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z (campaign range start).",
            },
            "campaign_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z (campaign range end).",
            },
            "country": {
                "type": "string",
                "description": _ISO_DOC_ENTSOE_MARKET,
                "default": "DE",
            },
            "version": {
                "type": "string",
                "description": "Must be v1 (default v1).",
                "default": "v1",
            },
        },
        "required": ["campaign_start_utc", "campaign_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="campaign_powerunits_entsoe_market_bounded_de",
    toolset="powerunits_entsoe_market_bounded_campaign",
    schema=CAMPAIGN_ENTSOE_SCHEMA,
    handler=lambda args, **kw: campaign_powerunits_entsoe_market_bounded_de(
        campaign_start_utc=str((args or {}).get("campaign_start_utc", "")),
        campaign_end_utc=str((args or {}).get("campaign_end_utc", "")),
        country=str((args or {}).get("country", "") or "DE"),
        version=str((args or {}).get("version", "") or "v1"),
    ),
    check_fn=check_powerunits_entsoe_market_bounded_campaign_requirements,
    requires_env=[
        _FEATURE_ENV,
        ENTSOE_MARKET_BOUNDED_PRIMARY_ENV,
        ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_ENV,
        ENTSOE_MARKET_BOUNDED_LEGACY_ENV["execute"],
        ENTSOE_MARKET_BOUNDED_LEGACY_ENV["summary"],
        "POWERUNITS_INTERNAL_EXECUTE_BASE_URL",
        "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET",
    ],
    emoji="🪜",
)
