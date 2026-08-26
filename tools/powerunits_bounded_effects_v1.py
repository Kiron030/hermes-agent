#!/usr/bin/env python3
"""Declarative PowerUnits effect classification (S0-B).

One authoritative mapping: registered operation/tool identity → effect class.

This is only an inventory. It is not a capability language, policy DSL,
authorization framework, or audit service.

Unknown operations fail closed. Do not default them to READ.
"""

from __future__ import annotations

from typing import Iterable

READ = "READ"
READ_WITH_SIDE_EFFECT = "READ_WITH_SIDE_EFFECT"
BOUNDED_WRITE = "BOUNDED_WRITE"
BOUNDED_WRITE_AMPLIFYING = "BOUNDED_WRITE_AMPLIFYING"
DESTRUCTIVE = "DESTRUCTIVE"

EFFECT_CLASSES: frozenset[str] = frozenset(
    {
        READ,
        READ_WITH_SIDE_EFFECT,
        BOUNDED_WRITE,
        BOUNDED_WRITE_AMPLIFYING,
        DESTRUCTIVE,
    }
)

WRITE_EFFECT_CLASSES: frozenset[str] = frozenset({BOUNDED_WRITE, BOUNDED_WRITE_AMPLIFYING})

# Idempotent directory/pointer setup only. Durable content mutators are BOUNDED_WRITE.
_LOCAL_IDEMPOTENT_SCAFFOLDING: tuple[str, ...] = (
    "ensure_powerunits_governance_workspace",
    "ensure_powerunits_bounded_workflow_workspace",
)


class UnclassifiedPowerUnitsOperation(LookupError):
    """Raised when a PowerUnits operation has no effect class."""


EFFECT_CLASS_BY_OPERATION: dict[str, str] = {
    # --- READ ---
    "browse_powerunits_skills_tree": READ,
    "diagnose_powerunits_skills_signals": READ,
    "governance_powerunits_bounded_rollout_read_v1": READ,
    "inspect_powerunits_country_coverage_v1": READ,
    "inventory_powerunits_bounded_coverage_v1": READ,
    "list_hermes_workspace": READ,
    "list_powerunits_bounded_workflow_workspace": READ,
    "list_powerunits_governance_workspace": READ,
    "list_powerunits_roadmap_dir": READ,
    "list_powerunits_skill_draft_proposals": READ,
    "manifest_powerunits_tier2_allowlisted_read_scope": READ,
    "manifest_powerunits_tier4a_skill_draft_scope": READ,
    "manifest_powerunits_tier4b_governance_scope": READ,
    "manifest_powerunits_tier5a_bounded_workflow_scope": READ,
    "plan_powerunits_de_stack_remediation": READ,
    "preflight_powerunits_entsoe_forecast_bounded_slice": READ,
    "preflight_powerunits_entsoe_market_bounded_slice": READ,
    "preflight_powerunits_era5_weather_bounded_slice": READ,
    "preflight_powerunits_option_d_bounded_slice": READ,
    "preview_powerunits_baseline_layer_coverage_de": READ,
    "propose_powerunits_skill_integration_actions": READ,
    "read_hermes_workspace_file": READ,
    "read_powerunits_allowlisted_workspace_extended_file": READ,
    "read_powerunits_bounded_workflow_run": READ,
    "read_powerunits_coverage_snapshot_v1": READ,
    "read_powerunits_db_health_indexes_v1": READ,
    "read_powerunits_db_health_planner_v1": READ,
    "read_powerunits_db_health_sessions_v1": READ,
    "read_powerunits_db_health_statements_v1": READ,
    "read_powerunits_db_health_storage_v1": READ,
    "read_powerunits_db_health_vacuum_v1": READ,
    "read_powerunits_doc": READ,
    "read_powerunits_entsoe_bzn_price_readiness_v1": READ,
    "read_powerunits_entsoe_bzn_prices_v1": READ,
    "read_powerunits_governance_note": READ,
    "read_powerunits_local_reference_file": READ,
    "read_powerunits_multi_country_data_health_v1": READ,
    "read_powerunits_repo_b_allowlisted": READ,
    "read_powerunits_roadmap_file": READ,
    "read_powerunits_skill_body_preview": READ,
    "read_powerunits_skill_draft_proposal": READ,
    "read_powerunits_timescale_dataset": READ,
    "read_powerunits_timescale_observe_v1": READ,
    "read_powerunits_worker_country_coverage_freshness_v1": READ,
    "readiness_powerunits_market_driver_features_bounded_de_window": READ,
    "readiness_powerunits_market_features_bounded_de_window": READ,
    "readiness_powerunits_option_d_bounded_window": READ,
    "resolve_powerunits_skill_slug": READ,
    "review_powerunits_bounded_workflow_runs": READ,
    "review_powerunits_skill_draft_proposals": READ,
    "review_powerunits_tier4b_skill_drafts": READ,
    "search_powerunits_allowlisted_local_text": READ,
    "search_powerunits_workspace_text": READ,
    "summarize_powerunits_allowlisted_locals": READ,
    "summarize_powerunits_entsoe_forecast_bounded_window": READ,
    "summarize_powerunits_entsoe_market_bounded_window": READ,
    "summarize_powerunits_era5_weather_bounded_window": READ,
    "summarize_powerunits_market_driver_features_bounded_de_window": READ,
    "summarize_powerunits_market_features_bounded_de_window": READ,
    "summarize_powerunits_operator_posture": READ,
    "summarize_powerunits_option_d_bounded_window": READ,
    "summarize_powerunits_outage_awareness_bounded_window": READ,
    "summarize_powerunits_skill_draft_proposals": READ,
    "summarize_powerunits_skills_observer": READ,
    "summarize_powerunits_tier4b_governance_lane": READ,
    "summarize_powerunits_tier5a_bounded_workflow_lane": READ,
    "summarize_powerunits_workspace_exports": READ,
    "summarize_powerunits_workspace_full": READ,
    # --- READ_WITH_SIDE_EFFECT (classified, not write-gated in S0-B) ---
    "research_powerunits_energy_web_v1": READ_WITH_SIDE_EFFECT,
    "scan_powerunits_entsoe_market_bounded_coverage_de": READ_WITH_SIDE_EFFECT,
    "scan_powerunits_era5_weather_bounded_coverage_de": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_entsoe_empirical_candidate_window_v1": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_entsoe_forecast_bounded_window": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_entsoe_market_bounded_window": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_era5_weather_bounded_window": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_market_driver_features_bounded_de_window": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_market_features_bounded_de_window": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_option_d_bounded_window": READ_WITH_SIDE_EFFECT,
    "validate_powerunits_outage_awareness_bounded_window": READ_WITH_SIDE_EFFECT,
    # --- BOUNDED_WRITE ---
    "execute_powerunits_entsoe_forecast_bounded_slice": BOUNDED_WRITE,
    "execute_powerunits_entsoe_market_bounded_slice": BOUNDED_WRITE,
    "execute_powerunits_era5_weather_bounded_slice": BOUNDED_WRITE,
    "execute_powerunits_market_driver_features_bounded_de_slice": BOUNDED_WRITE,
    "execute_powerunits_market_features_bounded_de_slice": BOUNDED_WRITE,
    "execute_powerunits_option_d_bounded_slice": BOUNDED_WRITE,
    "execute_powerunits_outage_repair_bounded_slice": BOUNDED_WRITE,
    "save_hermes_workspace_note": BOUNDED_WRITE,
    "write_powerunits_skill_draft_proposal": BOUNDED_WRITE,
    "set_powerunits_skill_draft_review_status": BOUNDED_WRITE,
    "append_powerunits_governance_note": BOUNDED_WRITE,
    "upsert_powerunits_bounded_workflow_run": BOUNDED_WRITE,
    "append_powerunits_bounded_workflow_note": BOUNDED_WRITE,
    # --- BOUNDED_WRITE_AMPLIFYING ---
    "campaign_powerunits_entsoe_market_bounded_de": BOUNDED_WRITE_AMPLIFYING,
    "campaign_powerunits_era5_weather_bounded_de": BOUNDED_WRITE_AMPLIFYING,
}

EFFECT_CLASS_BY_OPERATION.update(
    {name: READ_WITH_SIDE_EFFECT for name in _LOCAL_IDEMPOTENT_SCAFFOLDING}
)


def effect_class_for(operation: str) -> str:
    """Return the effect class for ``operation``.

    Raises ``UnclassifiedPowerUnitsOperation`` when missing. Never defaults to READ.
    """

    key = (operation or "").strip()
    classified = EFFECT_CLASS_BY_OPERATION.get(key)
    if classified is None:
        raise UnclassifiedPowerUnitsOperation(key or "<empty>")
    return classified


def is_write_effect(effect_class: str) -> bool:
    return effect_class in WRITE_EFFECT_CLASSES


def is_powerunits_registry_entry(entry: object) -> bool:
    """True for a registered PowerUnits operation (toolset or name)."""

    toolset = str(getattr(entry, "toolset", "") or "")
    name = str(getattr(entry, "name", "") or "")
    return toolset.startswith("powerunits_") or "powerunits" in name or name in {
        "list_hermes_workspace",
        "read_hermes_workspace_file",
        "save_hermes_workspace_note",
    }


def registered_powerunits_operations() -> list[str]:
    """Discover currently registered PowerUnits operations from the live registry."""

    from tools.registry import discover_builtin_tools, registry

    discover_builtin_tools()
    names = {
        entry.name
        for entry in registry._snapshot_entries()
        if is_powerunits_registry_entry(entry)
    }
    return sorted(names)


def unclassified_registered_operations(
    operations: Iterable[str] | None = None,
) -> list[str]:
    names = list(operations) if operations is not None else registered_powerunits_operations()
    return [name for name in names if name not in EFFECT_CLASS_BY_OPERATION]
