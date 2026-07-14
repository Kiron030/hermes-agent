"""Telegram first_safe_v1 must expose Stage-1 execute families (env gates still apply)."""

from __future__ import annotations

from powerunits_telegram_overlays import (
    TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1,
    expected_telegram_toolsets_first_safe,
)

_HERMES_CORE_READ_TOOLSETS = (
    "web",
    "search",
    "vision",
)


_STAGE1_EXECUTE_FAMILIES = (
    "powerunits_market_features_bounded_de_execute",
    "powerunits_market_features_bounded_de_validate",
    "powerunits_market_driver_features_bounded_de_execute",
    "powerunits_market_driver_features_bounded_de_validate",
    "powerunits_entsoe_forecast_bounded_execute",
    "powerunits_outage_awareness_bounded_validate",
    "powerunits_outage_repair_bounded_execute",
    "powerunits_entsoe_market_bounded_campaign",
    "powerunits_era5_weather_bounded_campaign",
    "powerunits_de_stack_remediation_planner",
    "powerunits_multi_country_data_health",
    "powerunits_entsoe_empirical_candidate_validate",
    "powerunits_baseline_layer_preview",
    "powerunits_bounded_rollout_governance",
)


def test_first_safe_v1_telegram_includes_hermes_core_read_toolsets() -> None:
    base = set(TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1)
    for name in _HERMES_CORE_READ_TOOLSETS:
        assert name in base, f"missing hermes core read toolset: {name}"


def test_first_safe_v1_telegram_includes_stage1_modeling_and_outage_toolsets() -> None:
    base = set(TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1)
    for name in _STAGE1_EXECUTE_FAMILIES:
        assert name in base, f"missing telegram toolset: {name}"


def test_tier_zero_keeps_stage1_toolsets_after_workspace_insert() -> None:
    tg = expected_telegram_toolsets_first_safe(0)
    wi = tg.index("powerunits_workspace")
    assert tg[wi + 1] == "powerunits_timescale_read"
    for name in _STAGE1_EXECUTE_FAMILIES:
        assert name in tg
