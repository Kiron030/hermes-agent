"""Non-authoritative Hermes envelope for Repo B rollout governance payloads (v1).

Overlay rules:
- **Never** mutate ``repo_b_allowed``, ``*_ready`` flags derived from Repo B, or Repo B ``rollup``.
- Populate ``hermes_allowed_now`` and optional cross-layer diagnostics only.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

import tools.powerunits_bounded_family_gates as g


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


ERA5_FAMILY = "bounded_era5_weather_normalized_v1"
ENTSOE_MARKET_FAMILY = "bounded_entsoe_market_normalized_v1"
ENTSOE_FORECAST_FAMILY = "bounded_entsoe_forecast_v1"
OUTAGE_FAMILY = "bounded_outage_awareness_v1"
MARKET_FEATURES_FAMILY = "bounded_market_features_hourly_v1"
MARKET_DRIVER_FAMILY = "bounded_market_driver_features_v1"
PLANNER_FAMILY = "bounded_de_stack_remediation_planner_v1"

_MARKET_FEATURES_ISO2_V1 = frozenset({"DE", "PL"})


def _base_http_ready() -> bool:
    return bool((os.getenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL") or "").strip()) and bool(
        (os.getenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET") or "").strip()
    )


def remediation_planner_hermes_surface_open() -> bool:
    return _truthy_env("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED") and _base_http_ready()


def era5_coverage_scan_open() -> bool:
    return _truthy_env("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED") and _base_http_ready()


def entsoe_market_coverage_scan_open() -> bool:
    return _truthy_env("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED") and _base_http_ready()


def era5_campaign_open() -> bool:
    return _truthy_env("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED") and g.campaign_era5_bounded_http_primitives_enabled()


def entsoe_market_campaign_open() -> bool:
    return _truthy_env("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED") and g.campaign_entsoe_bounded_http_primitives_enabled()


def entsoe_forecast_campaign_open() -> bool:
    """No dedicated forecast campaign modifier in Hermes — sequential POST parity with execute+summary gates."""
    return g.entsoe_forecast_bounded_core_step_enabled("execute") and g.entsoe_forecast_bounded_core_step_enabled(
        "summary"
    )


def compute_hermes_allowed_now_v1(*, family: str, country_code: str) -> dict[str, Any]:
    cc = (country_code or "").strip().upper()
    inventory_tool = g.bounded_coverage_inventory_enabled() and _base_http_ready()

    base_overlay: dict[str, Any | None] = {
        "coverage_inventory_tool_open": inventory_tool,
        "preflight_tool_open": None,
        "execute_tool_open": None,
        "validate_tool_open": None,
        "summary_tool_open": None,
        "readiness_tool_open": None,
        "coverage_scan_tool_open": None,
        "campaign_tool_open": None,
        "planner_tool_open": None,
    }

    http = _base_http_ready()

    if family == ERA5_FAMILY:
        pf = g.era5_weather_bounded_core_step_enabled("preflight")
        ex = (
            g.era5_weather_bounded_core_step_enabled("execute")
            and g.era5_weather_bounded_request_country_permitted(cc)
            and http
        )
        va = (
            g.era5_weather_bounded_core_step_enabled("validate")
            and g.era5_weather_bounded_request_country_permitted(cc)
            and http
        )
        su = (
            g.era5_weather_bounded_core_step_enabled("summary")
            and g.era5_weather_bounded_request_country_permitted(cc)
            and http
        )
        sc = era5_coverage_scan_open() and g.era5_weather_bounded_request_country_permitted(cc)
        ca = era5_campaign_open() and g.era5_weather_bounded_request_country_permitted(cc)
        return {
            **base_overlay,
            "preflight_tool_open": pf,
            "execute_tool_open": ex,
            "validate_tool_open": va,
            "summary_tool_open": su,
            "coverage_scan_tool_open": sc,
            "campaign_tool_open": ca,
            "readiness_tool_open": None,
            "planner_tool_open": None,
        }

    if family == ENTSOE_MARKET_FAMILY:
        ex = (
            g.entsoe_market_bounded_core_step_enabled("execute")
            and g.entsoe_market_bounded_request_country_permitted(cc)
            and http
        )
        va = (
            g.entsoe_market_bounded_core_step_enabled("validate")
            and g.entsoe_market_bounded_request_country_permitted(cc)
            and http
        )
        su = (
            g.entsoe_market_bounded_core_step_enabled("summary")
            and g.entsoe_market_bounded_request_country_permitted(cc)
            and http
        )
        sc = entsoe_market_coverage_scan_open() and g.entsoe_market_bounded_request_country_permitted(cc)
        ca = entsoe_market_campaign_open() and g.entsoe_market_bounded_request_country_permitted(cc)
        return {
            **base_overlay,
            "preflight_tool_open": g.entsoe_market_bounded_core_step_enabled("preflight"),
            "execute_tool_open": ex,
            "validate_tool_open": va,
            "summary_tool_open": su,
            "coverage_scan_tool_open": sc,
            "campaign_tool_open": ca,
        }

    if family == ENTSOE_FORECAST_FAMILY:
        ex = (
            g.entsoe_forecast_bounded_core_step_enabled("execute")
            and g.entsoe_forecast_bounded_request_country_permitted(cc)
            and http
        )
        va = (
            g.entsoe_forecast_bounded_core_step_enabled("validate")
            and g.entsoe_forecast_bounded_request_country_permitted(cc)
            and http
        )
        su = (
            g.entsoe_forecast_bounded_core_step_enabled("summary")
            and g.entsoe_forecast_bounded_request_country_permitted(cc)
            and http
        )
        cf = (
            entsoe_forecast_campaign_open()
            and g.entsoe_forecast_bounded_request_country_permitted(cc)
            and http
        )
        return {
            **base_overlay,
            "preflight_tool_open": g.entsoe_forecast_bounded_core_step_enabled("preflight"),
            "execute_tool_open": ex,
            "validate_tool_open": va,
            "summary_tool_open": su,
            "coverage_scan_tool_open": False,
            "campaign_tool_open": cf,
        }

    if family == OUTAGE_FAMILY:
        base = cc == "DE"
        vo = (
            base
            and g.outage_awareness_bounded_core_step_enabled("validate")
            and http
        )
        so = (
            base
            and g.outage_awareness_bounded_core_step_enabled("summary")
            and http
        )
        return {
            **base_overlay,
            "execute_tool_open": False,
            "validate_tool_open": vo,
            "summary_tool_open": so,
            "coverage_scan_tool_open": False,
        }

    if family == MARKET_FEATURES_FAMILY:
        in_slice = cc in _MARKET_FEATURES_ISO2_V1
        return {
            **base_overlay,
            "execute_tool_open": in_slice and g.market_features_bounded_step_enabled("execute") and http,
            "validate_tool_open": in_slice and g.market_features_bounded_step_enabled("validate") and http,
            "summary_tool_open": in_slice and g.market_features_bounded_step_enabled("summary") and http,
            "readiness_tool_open": in_slice and g.market_features_bounded_step_enabled("readiness") and http,
        }

    if family == MARKET_DRIVER_FAMILY:
        in_de = cc == "DE"
        return {
            **base_overlay,
            "execute_tool_open": in_de and g.market_driver_features_bounded_step_enabled("execute") and http,
            "validate_tool_open": in_de and g.market_driver_features_bounded_step_enabled("validate") and http,
            "summary_tool_open": in_de and g.market_driver_features_bounded_step_enabled("summary") and http,
            "readiness_tool_open": in_de and g.market_driver_features_bounded_step_enabled("readiness") and http,
        }

    if family == PLANNER_FAMILY:
        ok = cc == "DE" and remediation_planner_hermes_surface_open()
        return {
            **base_overlay,
            "planner_tool_open": ok,
        }

    raise ValueError(f"unknown governance family for Hermes overlay: {family!r}")


def _entso_bounded_allowlist_narrowing_hint(family: str) -> str | None:
    """When Repo B is open but Hermes execute/validate gates close, Railway allowlists are a common cause."""
    if family == ENTSOE_MARKET_FAMILY:
        return (
            "narrowing_hint:omit_HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES_for_full_Tier1_mirror_intersection"
            " (non-empty_list_intentionally_narrow; explicit_empty_fail_closed)"
        )
    if family == ENTSOE_FORECAST_FAMILY:
        return (
            "narrowing_hint:omit_HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_for_full_Tier1_mirror_intersection"
            " (non-empty_list_intentionally_narrow; explicit_empty_fail_closed)"
        )
    return None


def _cross_layer_effective(row: dict[str, Any], hnow: dict[str, Any]) -> tuple[str, str | None]:
    """Hermes-informed status; does not redefine Repo truth keys."""
    if not row.get("repo_b_allowed"):
        return str(row.get("effective_status") or ""), row.get("blocking_reason")

    family_s = str(row.get("family") or "")

    ex_r = bool(row.get("execute_ready"))
    ex_h = hnow.get("execute_tool_open") is True

    va_r = bool(row.get("validate_ready"))
    va_h = hnow.get("validate_tool_open") is True

    if ex_r and not ex_h:
        msg = "hermes_gate_or_allowlist_blocks_execute_tool_surface"
        hint = _entso_bounded_allowlist_narrowing_hint(family_s)
        if hint:
            msg = f"{msg}; {hint}"
        return "repo_execute_ready_hermes_gated", msg
    if va_r and not va_h:
        msg = "hermes_gate_blocks_validate_tool_surface"
        hint = _entso_bounded_allowlist_narrowing_hint(family_s)
        if hint:
            msg = f"{msg}; {hint}"
        return "repo_validate_ready_hermes_gated", msg

    if ex_r and ex_h:
        return "bounded_execute_open_repo_b_and_hermes", None
    if not ex_r and (row.get("inventory_ready") or row.get("validate_ready")):
        if va_r and va_h:
            return "read_only_signals_open_repo_b_and_hermes", None
        if va_r and not va_h:
            return "read_only_signals_repo_b_hermes_gated_validate", (
                "hermes_gate_blocks_validate_even_though_repo_b_slice_valid_for_read_signals"
            )
        return str(row.get("effective_status") or ""), row.get("blocking_reason")

    if row.get("planner_ready"):
        if hnow.get("planner_tool_open") is True:
            return "planner_surface_open_repo_b_and_hermes", None
        return "repo_planner_ready_hermes_gated", "hermes_REMEDIATION_PLANNER_gate_or_missing_http_env"

    return str(row.get("effective_status") or ""), row.get("blocking_reason")


def merge_repo_b_rollout_governance_payload_v1(repo_b_payload: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(repo_b_payload)
    out.setdefault("meta", {})
    meta = out["meta"]
    if isinstance(meta, dict):
        meta["hermes_overlay_version"] = "bounded_rollout_governance_hermes_overlay_v1"
        meta["hermes_overlay_note"] = (
            "hermes_allowed_now + cross-layer fields projected from Railway env only; Repo B numeric/bool readiness "
            "flags remain authoritative for technical slice acceptance."
        )
    rows = out.get("rows")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        family = str(row.get("family") or "")
        cc = str(row.get("country_code") or "")
        hnow = compute_hermes_allowed_now_v1(family=family, country_code=cc)
        row["hermes_allowed_now"] = hnow
        eff_x, blk_x = _cross_layer_effective(row, hnow)
        row["effective_status_cross_layer"] = eff_x
        row["blocking_reason_cross_layer"] = blk_x
    return out

