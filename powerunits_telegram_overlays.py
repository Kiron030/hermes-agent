"""
Powerunits Telegram toolset ordering + capability-tier progressive overlays.

Single source for:
- ``docker/apply_powerunits_runtime_policy`` merged ``platform_toolsets.telegram``
- ``model_tools.get_tool_definitions`` hard-cap allowlist sync
- optional posture comparisons

Overlays are inserted **immediately after** ``powerunits_workspace`` (Tier 1 … 5A).
"""

from __future__ import annotations

TIER_OVERLAY_TOOLSETS_ORDERED: tuple[str, ...] = (
    "powerunits_tier1_analysis",
    "powerunits_tier2_allowlisted_read",
    "powerunits_tier3_skills_integration",
    "powerunits_tier4a_skill_draft_proposals",
    "powerunits_tier4b_review_governance",
    "powerunits_tier5a_bounded_workflow_scaffolding",
)

OVERLAY_NAMES: frozenset[str] = frozenset(TIER_OVERLAY_TOOLSETS_ORDERED)

# Base Telegram toolsets for ``first_safe_v1`` **before** progressive tier inserts.
# Keep ``powerunits_operator_posture`` before ``powerunits_workspace`` so tier
# overlays remain at ``workspace_index + 1 … + 6`` (tests + docs rely on this).
TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1: tuple[str, ...] = (
    "memory",
    "session_search",
    "todo",
    # Hermes core read (no browser/terminal/file write/delegate)
    "web",
    "search",
    "vision",
    "powerunits_energy_web_research",
    "powerunits_docs",
    "powerunits_github_docs",
    "powerunits_operator_posture",
    "powerunits_workspace",
    "powerunits_timescale_read",
    "powerunits_repo_b_read",
    "powerunits_option_d_preflight",
    "powerunits_option_d_execute",
    "powerunits_option_d_validate",
    "powerunits_option_d_readiness",
    "powerunits_option_d_summary",
    # Modeling stack (Repo B market_features_hourly → market_driver_features_hourly).
    "powerunits_market_features_bounded_de_execute",
    "powerunits_market_features_bounded_de_validate",
    "powerunits_market_features_bounded_de_readiness",
    "powerunits_market_features_bounded_de_summary",
    "powerunits_market_driver_features_bounded_de_execute",
    "powerunits_market_driver_features_bounded_de_validate",
    "powerunits_market_driver_features_bounded_de_readiness",
    "powerunits_market_driver_features_bounded_de_summary",
    "powerunits_entsoe_market_bounded_preflight",
    "powerunits_entsoe_market_bounded_execute",
    "powerunits_entsoe_market_bounded_validate",
    "powerunits_entsoe_market_bounded_summary",
    "powerunits_entsoe_market_bounded_campaign",
    "powerunits_entsoe_market_bounded_coverage_scan",
    "powerunits_entsoe_forecast_bounded_preflight",
    "powerunits_entsoe_forecast_bounded_execute",
    "powerunits_entsoe_forecast_bounded_validate",
    "powerunits_entsoe_forecast_bounded_summary",
    "powerunits_entsoe_empirical_candidate_validate",
    "powerunits_entsoe_bzn_price_readiness",
    "powerunits_entsoe_bzn_prices",
    "powerunits_bounded_coverage_snapshot",
    "powerunits_bounded_coverage_inventory",
    "powerunits_worker_country_coverage_freshness",
    "powerunits_multi_country_data_health",
    "powerunits_baseline_layer_preview",
    "powerunits_bounded_rollout_governance",
    "powerunits_era5_weather_bounded_preflight",
    "powerunits_era5_weather_bounded_execute",
    "powerunits_era5_weather_bounded_validate",
    "powerunits_era5_weather_bounded_summary",
    "powerunits_era5_weather_bounded_campaign",
    "powerunits_era5_weather_bounded_coverage_scan",
    "powerunits_outage_awareness_bounded_validate",
    "powerunits_outage_awareness_bounded_summary",
    "powerunits_outage_repair_bounded_execute",
    "powerunits_de_stack_remediation_planner",
)


def merge_capability_overlays_into_telegram(telegram: list[str], tier: int) -> list[str]:
    """Return a copy of *telegram* with tier overlays inserted after ``powerunits_workspace``."""

    overlays: list[str] = []
    if tier >= 1:
        overlays.append("powerunits_tier1_analysis")
    if tier >= 2:
        overlays.append("powerunits_tier2_allowlisted_read")
    if tier >= 3:
        overlays.append("powerunits_tier3_skills_integration")
    if tier >= 4:
        overlays.append("powerunits_tier4a_skill_draft_proposals")
    if tier >= 5:
        overlays.append("powerunits_tier4b_review_governance")
    if tier >= 6:
        overlays.append("powerunits_tier5a_bounded_workflow_scaffolding")

    cleaned = [x for x in telegram if x not in OVERLAY_NAMES]
    try:
        wi = cleaned.index("powerunits_workspace")
    except ValueError:
        return cleaned + overlays
    return cleaned[: wi + 1] + overlays + cleaned[wi + 1 :]


def expected_telegram_toolsets_first_safe(tier: int) -> list[str]:
    """Canonical merged list (policy revision) for the given capability tier."""

    return merge_capability_overlays_into_telegram(
        list(TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1), tier
    )


def progressive_capability_overlays_aligned(telegram: list[str], tier: int) -> bool | None:
    """
    Return whether ``telegram`` has the progressive overlay toolsets in the canonical
    positions (immediately after ``powerunits_workspace``).

    ``None`` if ``powerunits_workspace`` is missing — caller cannot verify ordering
    (abbreviated test configs / manual edits).
    """

    expected: list[str] = []
    if tier >= 1:
        expected.append("powerunits_tier1_analysis")
    if tier >= 2:
        expected.append("powerunits_tier2_allowlisted_read")
    if tier >= 3:
        expected.append("powerunits_tier3_skills_integration")
    if tier >= 4:
        expected.append("powerunits_tier4a_skill_draft_proposals")
    if tier >= 5:
        expected.append("powerunits_tier4b_review_governance")
    if tier >= 6:
        expected.append("powerunits_tier5a_bounded_workflow_scaffolding")
    if not expected:
        return True
    try:
        wi = telegram.index("powerunits_workspace")
    except ValueError:
        return None
    end = wi + 1 + len(expected)
    if end > len(telegram):
        return False
    return telegram[wi + 1 : end] == expected
