"""Current bounded HTTP operation contracts (R0). Recorded reality, not a new taxonomy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tests.powerunits_golden.env import (
    FIXED_CAMPAIGN_END,
    FIXED_CORRELATION_ID,
    FIXED_WINDOW_END,
    FIXED_WINDOW_START,
)

ArgStyle = Literal[
    "slice",
    "window_de",
    "window_cc",
    "inventory",
    "freshness",
    "scan",
    "campaign",
    "preview",
    "plan",
    "governance",
    "empirical",
    "bzn_prices",
    "bzn_readiness",
    "country_coverage",
]

NegativeKind = Literal[
    "feature_disabled",
    "invalid_window",
    "invalid_country_codes",
]


@dataclass(frozen=True)
class BoundedHttpContract:
    operation: str
    module: str
    function: str
    route: str
    gate_envs: tuple[str, ...]
    arg_style: ArgStyle
    effect_class: str
    is_write: bool
    negative: NegativeKind
    happy_fields: tuple[str, ...]
    provenance_fields: tuple[str, ...] = ()
    extra_happy_args: dict[str, Any] = field(default_factory=dict)


_COMMON_READ_FIELDS = (
    "correlation_id",
)
_COMMON_WRITE_FIELDS = (
    "correlation_id",
    "execution_attempted",
)
_PRE_HTTP_REFUSALS = frozenset(
    {
        "feature_disabled",
        "invalid_window",
        "invalid_country_codes",
        "invalid_country_code",
        "read_config_incomplete",
        "execute_config_incomplete",
        "approval_denied",
        "approval_required",
        "execute_target_https_required",
        "execute_target_host_refused",
        "execute_target_host_allowlist_required",
    }
)


def _slice_args() -> dict[str, Any]:
    return {
        "country": "DE",
        "start": FIXED_WINDOW_START,
        "end": FIXED_WINDOW_END,
        "version": "v1",
    }


def _window_de_args() -> dict[str, Any]:
    return {
        "window_start_utc": FIXED_WINDOW_START,
        "window_end_utc": FIXED_WINDOW_END,
        "version": "v1",
    }


def _window_cc_args() -> dict[str, Any]:
    return {
        "country_codes": ["DE"],
        "window_start_utc": FIXED_WINDOW_START,
        "window_end_utc": FIXED_WINDOW_END,
        "version": "v1",
    }


def args_for(contract: BoundedHttpContract) -> dict[str, Any]:
    style = contract.arg_style
    if style == "slice":
        base = _slice_args()
        if "option_d" in contract.operation:
            base["country"] = "PL"
        return {**base, **contract.extra_happy_args}
    if style == "window_de":
        return {**_window_de_args(), **contract.extra_happy_args}
    if style in {"window_cc", "inventory"}:
        return {**_window_cc_args(), **contract.extra_happy_args}
    if style == "freshness":
        return {"national_country_codes": ["DE"], **contract.extra_happy_args}
    if style == "scan":
        return {
            "scan_start_utc": FIXED_WINDOW_START,
            "scan_end_utc": FIXED_WINDOW_END,
            "country": "DE",
            "version": "v1",
            **contract.extra_happy_args,
        }
    if style == "campaign":
        return {
            "campaign_start_utc": FIXED_WINDOW_START,
            "campaign_end_utc": FIXED_CAMPAIGN_END,
            "country": "DE",
            "version": "v1",
            **contract.extra_happy_args,
        }
    if style == "preview":
        return {
            "preview_start_utc": FIXED_WINDOW_START,
            "preview_end_utc": FIXED_WINDOW_END,
            "country_code": "DE",
            "version": "v1",
            **contract.extra_happy_args,
        }
    if style == "plan":
        return {
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
            "country_code": "DE",
            "version": "v1",
            **contract.extra_happy_args,
        }
    if style == "governance":
        return {"country_codes_csv": "DE", "version": "v1", **contract.extra_happy_args}
    if style == "empirical":
        return {
            "country_code": "DK",
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
            "version": "v1",
            **contract.extra_happy_args,
        }
    if style == "bzn_prices":
        return {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
            "table_version": "v1",
            **contract.extra_happy_args,
        }
    if style == "bzn_readiness":
        return {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
            "table_version": "v1",
            **contract.extra_happy_args,
        }
    if style == "country_coverage":
        return {
            "country": "AT",
            "dataset": "demand",
            "start": FIXED_WINDOW_START,
            "end": FIXED_WINDOW_END,
            **contract.extra_happy_args,
        }
    raise ValueError(style)


def negative_args(contract: BoundedHttpContract) -> dict[str, Any]:
    if contract.negative == "feature_disabled":
        return args_for(contract)
    if contract.negative == "invalid_window":
        out = args_for(contract)
        for key in ("window_start_utc", "start", "scan_start_utc", "preview_start_utc", "campaign_start_utc"):
            if key in out:
                out[key] = ""
        return out
    if contract.negative == "invalid_country_codes":
        out = args_for(contract)
        if "country_codes" in out:
            out["country_codes"] = []
        return out
    raise ValueError(contract.negative)


def happy_repo_b_payload(contract: BoundedHttpContract) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": True,
        "correlation_id": FIXED_CORRELATION_ID,
        "pipeline_run_id": "run-golden-1",
        "rows_written": 12,
    }
    if contract.arg_style == "campaign":
        payload["http_status"] = 200
    return payload


BOUNDED_HTTP_CONTRACTS: tuple[BoundedHttpContract, ...] = (
    BoundedHttpContract(
        "read_powerunits_coverage_snapshot_v1",
        "tools.powerunits_bounded_coverage_snapshot_tool",
        "read_powerunits_coverage_snapshot_v1",
        "/internal/hermes/bounded/v1/coverage-snapshot",
        ("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED",),
        "window_cc",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS + ("chat_summary", "read_attempted", "http_status_from_repo_b"),
        ("baseline_ready", "time_window"),
    ),
    BoundedHttpContract(
        "inventory_powerunits_bounded_coverage_v1",
        "tools.powerunits_bounded_coverage_inventory_tool",
        "inventory_powerunits_bounded_coverage_v1",
        "/internal/hermes/bounded/v1/coverage-inventory",
        ("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED",),
        "inventory",
        "READ",
        False,
        "feature_disabled",
        ("chat_summary", "hermes_statement"),
    ),
    BoundedHttpContract(
        "read_powerunits_worker_country_coverage_freshness_v1",
        "tools.powerunits_worker_country_coverage_freshness_tool",
        "read_powerunits_worker_country_coverage_freshness_v1",
        "/internal/hermes/bounded/v1/worker-country-coverage/freshness/read",
        ("HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED",),
        "freshness",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "inspect_powerunits_country_coverage_v1",
        "tools.powerunits_country_coverage_inspect_tool",
        "inspect_powerunits_country_coverage_v1",
        "/internal/hermes/bounded/v1/country-coverage/inspect",
        ("HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED",),
        "country_coverage",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS + ("chat_summary", "read_attempted", "http_status_from_repo_b"),
        ("items", "no_data"),
    ),
    BoundedHttpContract(
        "read_powerunits_entsoe_bzn_price_readiness_v1",
        "tools.powerunits_entsoe_bzn_price_readiness_tool",
        "read_powerunits_entsoe_bzn_price_readiness_v1",
        "/internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read",
        ("HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED",),
        "bzn_readiness",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "read_powerunits_entsoe_bzn_prices_v1",
        "tools.powerunits_entsoe_bzn_prices_tool",
        "read_powerunits_entsoe_bzn_prices_v1",
        "/internal/hermes/bounded/v1/entsoe-bzn-prices/read",
        ("HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED",),
        "bzn_prices",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "readiness_powerunits_option_d_bounded_window",
        "tools.powerunits_option_d_readiness_tool",
        "readiness_powerunits_option_d_bounded_window",
        "/internal/hermes/bounded/v1/market-features-hourly/readiness-window",
        ("HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED",),
        "slice",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_option_d_bounded_window",
        "tools.powerunits_option_d_summary_tool",
        "summarize_powerunits_option_d_bounded_window",
        "/internal/hermes/bounded/v1/market-features-hourly/summary-window",
        ("HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED",),
        "slice",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "validate_powerunits_option_d_bounded_window",
        "tools.powerunits_option_d_validate_tool",
        "validate_powerunits_option_d_bounded_window",
        "/internal/hermes/bounded/v1/market-features-hourly/validate-window",
        ("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED",),
        "slice",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_option_d_bounded_slice",
        "tools.powerunits_option_d_execute_tool",
        "execute_powerunits_option_d_bounded_slice",
        "/internal/hermes/bounded/v1/market-features-hourly/recompute",
        ("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED",),
        "slice",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "readiness_powerunits_market_features_bounded_de_window",
        "tools.powerunits_market_features_bounded_de_readiness_tool",
        "readiness_powerunits_market_features_bounded_de_window",
        "/internal/hermes/bounded/v1/market-features-hourly/readiness-window",
        ("HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_market_features_bounded_de_window",
        "tools.powerunits_market_features_bounded_de_summary_tool",
        "summarize_powerunits_market_features_bounded_de_window",
        "/internal/hermes/bounded/v1/market-features-hourly/summary-window",
        ("HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "validate_powerunits_market_features_bounded_de_window",
        "tools.powerunits_market_features_bounded_de_validate_tool",
        "validate_powerunits_market_features_bounded_de_window",
        "/internal/hermes/bounded/v1/market-features-hourly/validate-window",
        ("HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_market_features_bounded_de_slice",
        "tools.powerunits_market_features_bounded_de_execute_tool",
        "execute_powerunits_market_features_bounded_de_slice",
        "/internal/hermes/bounded/v1/market-features-hourly/recompute",
        ("HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "readiness_powerunits_market_driver_features_bounded_de_window",
        "tools.powerunits_market_driver_features_bounded_de_readiness_tool",
        "readiness_powerunits_market_driver_features_bounded_de_window",
        "/internal/hermes/bounded/v1/market-driver-features-hourly/readiness-window",
        ("HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_market_driver_features_bounded_de_window",
        "tools.powerunits_market_driver_features_bounded_de_summary_tool",
        "summarize_powerunits_market_driver_features_bounded_de_window",
        "/internal/hermes/bounded/v1/market-driver-features-hourly/summary-window",
        ("HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "validate_powerunits_market_driver_features_bounded_de_window",
        "tools.powerunits_market_driver_features_bounded_de_validate_tool",
        "validate_powerunits_market_driver_features_bounded_de_window",
        "/internal/hermes/bounded/v1/market-driver-features-hourly/validate-window",
        ("HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_market_driver_features_bounded_de_slice",
        "tools.powerunits_market_driver_features_bounded_de_execute_tool",
        "execute_powerunits_market_driver_features_bounded_de_slice",
        "/internal/hermes/bounded/v1/market-driver-features-hourly/recompute",
        ("HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED",),
        "window_de",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "validate_powerunits_entsoe_market_bounded_window",
        "tools.powerunits_entsoe_market_bounded_validate_tool",
        "validate_powerunits_entsoe_market_bounded_window",
        "/internal/hermes/bounded/v1/entsoe-market-sync/validate-window",
        ("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED",),
        "slice",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_entsoe_market_bounded_window",
        "tools.powerunits_entsoe_market_bounded_summary_tool",
        "summarize_powerunits_entsoe_market_bounded_window",
        "/internal/hermes/bounded/v1/entsoe-market-sync/summary-window",
        ("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED",),
        "slice",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_entsoe_market_bounded_slice",
        "tools.powerunits_entsoe_market_bounded_execute_tool",
        "execute_powerunits_entsoe_market_bounded_slice",
        "/internal/hermes/bounded/v1/entsoe-market-sync/recompute",
        ("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED",),
        "slice",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "scan_powerunits_entsoe_market_bounded_coverage_de",
        "tools.powerunits_entsoe_market_bounded_coverage_scan_tool",
        "scan_powerunits_entsoe_market_bounded_coverage_de",
        "/internal/hermes/bounded/v1/entsoe-market-sync/coverage-scan",
        ("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED",),
        "scan",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "campaign_powerunits_entsoe_market_bounded_de",
        "tools.powerunits_entsoe_market_bounded_campaign_tool",
        "campaign_powerunits_entsoe_market_bounded_de",
        "/internal/hermes/bounded/v1/entsoe-market-sync/recompute",
        (
            "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED",
            "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED",
        ),
        "campaign",
        "BOUNDED_WRITE_AMPLIFYING",
        True,
        "feature_disabled",
        ("windows_attempted", "windows_succeeded", "stopped_reason"),
    ),
    BoundedHttpContract(
        "validate_powerunits_entsoe_forecast_bounded_window",
        "tools.powerunits_entsoe_forecast_bounded_validate_tool",
        "validate_powerunits_entsoe_forecast_bounded_window",
        "/internal/hermes/bounded/v1/entsoe-forecast/validate-window",
        ("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED",),
        "slice",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_entsoe_forecast_bounded_window",
        "tools.powerunits_entsoe_forecast_bounded_summary_tool",
        "summarize_powerunits_entsoe_forecast_bounded_window",
        "/internal/hermes/bounded/v1/entsoe-forecast/summary-window",
        ("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED",),
        "slice",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_entsoe_forecast_bounded_slice",
        "tools.powerunits_entsoe_forecast_bounded_execute_tool",
        "execute_powerunits_entsoe_forecast_bounded_slice",
        "/internal/hermes/bounded/v1/entsoe-forecast/recompute",
        ("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED",),
        "slice",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "validate_powerunits_entsoe_empirical_candidate_window_v1",
        "tools.powerunits_entsoe_empirical_candidate_validate_tool",
        "validate_powerunits_entsoe_empirical_candidate_window_v1",
        "/internal/hermes/bounded/v1/entsoe-empirical-candidate/validate-window",
        ("HERMES_POWERUNITS_ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_ENABLED",),
        "empirical",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "validate_powerunits_era5_weather_bounded_window",
        "tools.powerunits_era5_weather_bounded_validate_tool",
        "validate_powerunits_era5_weather_bounded_window",
        "/internal/hermes/bounded/v1/era5-weather/validate-window",
        ("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED",),
        "slice",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_era5_weather_bounded_window",
        "tools.powerunits_era5_weather_bounded_summary_tool",
        "summarize_powerunits_era5_weather_bounded_window",
        "/internal/hermes/bounded/v1/era5-weather/summary-window",
        ("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED",),
        "slice",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_era5_weather_bounded_slice",
        "tools.powerunits_era5_weather_bounded_execute_tool",
        "execute_powerunits_era5_weather_bounded_slice",
        "/internal/hermes/bounded/v1/era5-weather/recompute",
        ("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED",),
        "slice",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "scan_powerunits_era5_weather_bounded_coverage_de",
        "tools.powerunits_era5_weather_bounded_coverage_scan_tool",
        "scan_powerunits_era5_weather_bounded_coverage_de",
        "/internal/hermes/bounded/v1/era5-weather/coverage-scan",
        ("HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED",),
        "scan",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "campaign_powerunits_era5_weather_bounded_de",
        "tools.powerunits_era5_weather_bounded_campaign_tool",
        "campaign_powerunits_era5_weather_bounded_de",
        "/internal/hermes/bounded/v1/era5-weather/recompute",
        (
            "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED",
            "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED",
        ),
        "campaign",
        "BOUNDED_WRITE_AMPLIFYING",
        True,
        "feature_disabled",
        ("windows_attempted", "windows_succeeded", "stopped_reason"),
    ),
    BoundedHttpContract(
        "validate_powerunits_outage_awareness_bounded_window",
        "tools.powerunits_outage_awareness_bounded_validate_tool",
        "validate_powerunits_outage_awareness_bounded_window",
        "/internal/hermes/bounded/v1/outage-awareness/validate-window",
        ("HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED",),
        "slice",
        "READ_WITH_SIDE_EFFECT",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "summarize_powerunits_outage_awareness_bounded_window",
        "tools.powerunits_outage_awareness_bounded_summary_tool",
        "summarize_powerunits_outage_awareness_bounded_window",
        "/internal/hermes/bounded/v1/outage-awareness/summary-window",
        ("HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED",),
        "slice",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "execute_powerunits_outage_repair_bounded_slice",
        "tools.powerunits_outage_repair_bounded_execute_tool",
        "execute_powerunits_outage_repair_bounded_slice",
        "/internal/hermes/bounded/v1/outage-repair/recompute",
        ("HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED",),
        "slice",
        "BOUNDED_WRITE",
        True,
        "feature_disabled",
        _COMMON_WRITE_FIELDS,
        ("pipeline_run_id",),
    ),
    BoundedHttpContract(
        "plan_powerunits_de_stack_remediation",
        "tools.powerunits_de_stack_remediation_planner_tool",
        "plan_powerunits_de_stack_remediation",
        "/internal/hermes/bounded/v1/remediation/de-stack-plan",
        ("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED",),
        "plan",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "preview_powerunits_baseline_layer_coverage_de",
        "tools.powerunits_baseline_layer_preview_tool",
        "preview_powerunits_baseline_layer_coverage_de",
        "/internal/hermes/bounded/v1/baseline/layer-coverage-preview",
        ("HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED",),
        "preview",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
    BoundedHttpContract(
        "governance_powerunits_bounded_rollout_read_v1",
        "tools.powerunits_bounded_rollout_governance_tool",
        "governance_powerunits_bounded_rollout_read_v1",
        "/internal/hermes/bounded/v1/rollout-governance",
        ("HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED",),
        "governance",
        "READ",
        False,
        "feature_disabled",
        _COMMON_READ_FIELDS,
    ),
)


def contract_by_operation() -> dict[str, BoundedHttpContract]:
    return {item.operation: item for item in BOUNDED_HTTP_CONTRACTS}
