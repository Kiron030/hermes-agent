"""Honest unpatched-upstream clamp behaviour. No workaround. No core patch."""

from __future__ import annotations

from unittest.mock import patch

from tests.r2_powerunits_plugin.conftest import PLUGIN_TOOLS, TOOLSET_NAME


def _callable_names(enabled, disabled=None):
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    _clear_tool_defs_cache()
    defs = get_tool_definitions(
        enabled_toolsets=enabled,
        disabled_toolsets=disabled,
        quiet_mode=True,
    )
    return {item["function"]["name"] for item in defs}


def test_plugin_visible_when_explicitly_allowed(loaded_plugin) -> None:
    names = _callable_names(["memory", TOOLSET_NAME])
    assert set(PLUGIN_TOOLS) <= names


def test_plugin_hidden_when_enabled_list_omits_it(loaded_plugin) -> None:
    names = _callable_names(["memory", "todo"])
    assert set(PLUGIN_TOOLS).isdisjoint(names)


def test_plugin_default_self_expansion_on_unpatched_config_path(loaded_plugin) -> None:
    from hermes_cli.tools_config import _get_platform_tools

    declared = ["memory", "todo", "web"]
    config = {
        "platform_toolsets": {"cli": list(declared)},
        "agent": {"disabled_toolsets": ["terminal", "file"]},
        "known_plugin_toolsets": {},
    }
    with patch(
        "hermes_cli.tools_config._get_plugin_toolset_keys",
        return_value={TOOLSET_NAME},
    ):
        enabled = set(_get_platform_tools(config, "cli"))
    # Known R1 finding: unknown/plugin toolsets default-enable themselves.
    assert TOOLSET_NAME in enabled
    assert TOOLSET_NAME not in declared


def test_disabled_toolsets_subtract_plugin_when_applied(loaded_plugin) -> None:
    names = _callable_names([TOOLSET_NAME, "memory"], disabled=[TOOLSET_NAME])
    assert set(PLUGIN_TOOLS).isdisjoint(names)


def test_toolsets_all_reopens_plugin_surface(loaded_plugin) -> None:
    names = _callable_names(None, disabled=None)
    assert set(PLUGIN_TOOLS) <= names


def test_records_unpatched_cap_requires_thin_core_patch(loaded_plugin) -> None:
    """Do not claim the cap is enforced. This is the R1 seam, still unpatched."""

    from hermes_cli.tools_config import _get_platform_tools

    explicit = set(PLUGIN_TOOLS) <= _callable_names(["memory", TOOLSET_NAME])
    omitted = set(PLUGIN_TOOLS).isdisjoint(_callable_names(["memory", "todo"]))
    config = {
        "platform_toolsets": {"cli": ["memory"]},
        "agent": {"disabled_toolsets": []},
        "known_plugin_toolsets": {},
    }
    with patch(
        "hermes_cli.tools_config._get_plugin_toolset_keys",
        return_value={TOOLSET_NAME},
    ):
        self_expanded = TOOLSET_NAME in set(_get_platform_tools(config, "cli"))

    assert explicit is True
    assert omitted is True
    assert self_expanded is True

    report = {
        "PLUGIN_REGISTERED": True,
        "PLUGIN_VISIBLE_WHEN_EXPLICITLY_ALLOWED": True,
        "PLUGIN_VISIBLE_WHEN_NOT_DECLARED": False,
        "PLUGIN_DEFAULT_SELF_EXPANSION": True,
        "PLUGIN_CAP_RUNTIME": "REQUIRES_KNOWN_THIN_CORE_PATCH",
        "MINIMUM_ENFORCEMENT_SEAM": (
            "model_tools._compute_tool_definitions FINAL POSITIVE INTERSECTION "
            "against a declared operator allowlist after enabled/disabled "
            "resolution. Domain-agnostic; no PowerUnits logic."
        ),
        "FUTURE_CORE_PATCH_IMPLEMENTED": False,
    }
    assert report["PLUGIN_CAP_RUNTIME"] == "REQUIRES_KNOWN_THIN_CORE_PATCH"
    assert report["FUTURE_CORE_PATCH_IMPLEMENTED"] is False
