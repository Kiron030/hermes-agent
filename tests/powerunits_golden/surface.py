"""Mechanical first_safe_v1 surface enumeration (catalogued / requested / callable)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from tests.powerunits_golden.env import UNSAFE_FREEDOMS_FIRST_SAFE_DENIES, invalidate_tool_surface_caches


def _sorted_unique(names: Iterable[str]) -> list[str]:
    return sorted(set(names))


def capability_groups(names: Iterable[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for name in _sorted_unique(names):
        grouped[_group_for(name)].append(name)
    return {key: grouped[key] for key in sorted(grouped)}


def _group_for(name: str) -> str:
    if name in {"memory", "todo", "visual_qa"}:
        return name if name == "visual_qa" else "memory_todo"
    if name in {"web_search", "web_extract"}:
        return "web_search"
    if name == "research_powerunits_energy_web_v1":
        return "energy_web_research"
    if name.startswith("read_powerunits_doc") or name.startswith("list_powerunits_roadmap") or name.startswith(
        "read_powerunits_roadmap"
    ):
        return "docs"
    if "workspace" in name or name.startswith("list_hermes_workspace") or name.startswith("read_hermes_workspace") or name.startswith(
        "save_hermes_workspace"
    ):
        return "workspace"
    if "timescale" in name:
        return "timescale"
    if "repo_b" in name:
        return "repo_b"
    if "option_d" in name:
        return "option_d"
    if "market_driver_features" in name:
        return "market_driver_features"
    if "market_features" in name:
        return "market_features"
    if "entsoe_forecast" in name:
        return "entsoe_forecast"
    if "entsoe_empirical" in name:
        return "entsoe_empirical"
    if "entsoe_bzn" in name:
        return "entsoe_bzn"
    if "entsoe_market" in name:
        return "entsoe_market"
    if "era5" in name:
        return "era5"
    if "outage" in name:
        return "outage"
    if "coverage" in name or "freshness" in name or name.startswith("inventory_powerunits"):
        return "coverage"
    if "remediation" in name:
        return "remediation"
    if "baseline" in name:
        return "baseline"
    if "rollout" in name or "governance_powerunits_bounded_rollout" in name:
        return "rollout_governance"
    if "skill" in name or "tier3" in name or name.startswith("browse_powerunits") or name.startswith(
        "diagnose_powerunits"
    ):
        return "skills_tier"
    if "governance" in name or name.startswith("ensure_powerunits_governance"):
        return "tier4b_governance"
    if "workflow" in name:
        return "tier5a_workflow"
    if name.startswith("summarize_powerunits_operator_posture"):
        return "operator_posture"
    if name.startswith("search_powerunits") or name.startswith("manifest_powerunits") or name.startswith(
        "read_powerunits_local"
    ) or name.startswith("read_powerunits_allowlisted"):
        return "tier2_allowlisted"
    return "other"


def catalogued_tool_names(tier: int) -> list[str]:
    from powerunits_telegram_overlays import expected_telegram_toolsets_first_safe
    from toolsets import resolve_toolset

    names: set[str] = set()
    for toolset_name in expected_telegram_toolsets_first_safe(tier):
        names.update(resolve_toolset(toolset_name))
    return _sorted_unique(names)


def requested_toolsets(tier: int) -> list[str]:
    from hermes_cli.tools_config import _get_platform_tools
    from powerunits_telegram_overlays import expected_telegram_toolsets_first_safe

    telegram = _get_platform_tools({}, "telegram")
    expected = expected_telegram_toolsets_first_safe(tier)
    # Platform resolution may add leftover keys; first_safe clamp is the final gate.
    return _sorted_unique(list(telegram) + list(expected))


def requested_tool_names(tier: int) -> list[str]:
    from toolsets import resolve_toolset, validate_toolset

    names: set[str] = set()
    for toolset_name in requested_toolsets(tier):
        if validate_toolset(toolset_name):
            names.update(resolve_toolset(toolset_name))
    return _sorted_unique(names)


def callable_tool_names(enabled_toolsets: list[str]) -> list[str]:
    from model_tools import get_tool_definitions

    invalidate_tool_surface_caches()
    return _sorted_unique(
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled_toolsets), quiet_mode=True)
    )


def capture_tier_surface(tier: int) -> dict[str, Any]:
    catalogued = catalogued_tool_names(tier)
    toolsets = requested_toolsets(tier)
    requested = requested_tool_names(tier)
    callable_names = callable_tool_names(toolsets)
    return {
        "tier": tier,
        "catalogued": catalogued,
        "requested": requested,
        "requested_toolsets": toolsets,
        "callable": callable_names,
        "tool_count": len(callable_names),
        "capability_groups": capability_groups(callable_names),
        "catalogued_not_callable": _sorted_unique(set(catalogued) - set(callable_names)),
        "requested_not_callable": _sorted_unique(set(requested) - set(callable_names)),
        "callable_not_catalogued": _sorted_unique(set(callable_names) - set(catalogued)),
    }


def explicit_request_cannot_restore(names: Iterable[str], extra_toolsets: Iterable[str]) -> list[str]:
    """Return extra tool names that remain callable after an explicit toolset request."""

    enabled = _sorted_unique(list(requested_toolsets(0)) + list(extra_toolsets))
    callable_names = set(callable_tool_names(enabled))
    return _sorted_unique(name for name in names if name in callable_names)


def absent_unsafe_freedoms(callable_names: Iterable[str]) -> list[str]:
    present = set(callable_names)
    return [name for name in UNSAFE_FREEDOMS_FIRST_SAFE_DENIES if name in present]
