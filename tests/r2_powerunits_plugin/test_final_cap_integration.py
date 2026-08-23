"""GATE_2 acceptance: the generic final cap bounds the real R2 plugin.

The plugin is loaded through the official user-plugin discovery path (see
``conftest.loaded_plugin``) and is the fixture, not the subject — what is under
test is the domain-agnostic ``agent.final_allowed_toolsets`` cap in
``model_tools``. The core knows nothing about this plugin; it is used here
precisely because it is a real, default-self-expanding third-party toolset.

No live Repo-B request is made; the HTTP poster is mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import yaml

from tests.powerunits_golden.env import (
    FIXED_CORRELATION_ID,
    FIXED_WINDOW_END,
    FIXED_WINDOW_START,
)
from tests.powerunits_golden.http import RecordingPoster
from tests.r2_powerunits_plugin.conftest import PLUGIN_NAME, PLUGIN_TOOLS, TOOLSET_NAME


def _set_cap(home: Path, cap: Optional[list[str]]) -> None:
    """Rewrite the isolated config with a final cap, keeping the plugin enabled."""
    payload: dict = {"plugins": {"enabled": [PLUGIN_NAME]}}
    if cap is not None:
        payload["agent"] = {"final_allowed_toolsets": cap}
    (home / "config.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")

    from hermes_cli import config as config_mod
    from model_tools import _clear_tool_defs_cache

    config_mod._LOAD_CONFIG_CACHE.clear()
    config_mod._RAW_CONFIG_CACHE.clear()
    _clear_tool_defs_cache()


def _surface(enabled, disabled=None) -> set[str]:
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    _clear_tool_defs_cache()
    defs = get_tool_definitions(
        enabled_toolsets=enabled, disabled_toolsets=disabled, quiet_mode=True
    )
    return {item["function"]["name"] for item in defs}


# ---------------------------------------------------------------------------
# PLUGIN_UNLISTED — absent from the final callable surface
# ---------------------------------------------------------------------------


def test_unlisted_plugin_is_absent_even_when_caller_enables_it(loaded_plugin) -> None:
    home = loaded_plugin["home"]
    assert set(PLUGIN_TOOLS) <= _surface(["memory", TOOLSET_NAME])

    _set_cap(home, ["memory", "todo"])

    assert set(PLUGIN_TOOLS).isdisjoint(_surface(["memory", TOOLSET_NAME]))


def test_unlisted_plugin_is_absent_under_toolsets_all(loaded_plugin) -> None:
    home = loaded_plugin["home"]
    assert set(PLUGIN_TOOLS) <= _surface(None)

    _set_cap(home, ["memory", "todo"])

    assert set(PLUGIN_TOOLS).isdisjoint(_surface(None))


def test_plugin_self_expansion_cannot_bypass_the_cap(loaded_plugin) -> None:
    """The R1 self-expansion path feeds its widened list straight into the cap.

    ``_get_platform_tools`` default-enables plugin toolsets the operator never
    declared. That widened list is exactly what the gateway hands to
    ``get_tool_definitions``, so it is what the cap has to survive.
    """
    from unittest.mock import patch

    from hermes_cli.tools_config import _get_platform_tools

    home = loaded_plugin["home"]
    declared = ["memory", "todo"]
    config = {
        "platform_toolsets": {"cli": list(declared)},
        "agent": {"disabled_toolsets": []},
        "known_plugin_toolsets": {},
    }
    with patch(
        "hermes_cli.tools_config._get_plugin_toolset_keys",
        return_value={TOOLSET_NAME},
    ):
        expanded = sorted(_get_platform_tools(config, "cli"))

    # Precondition: the R2 finding still reproduces.
    assert TOOLSET_NAME in expanded
    assert TOOLSET_NAME not in declared

    _set_cap(home, declared)

    assert set(PLUGIN_TOOLS).isdisjoint(_surface(expanded))


def test_unlisted_plugin_is_absent_from_the_tool_search_catalog(loaded_plugin) -> None:
    """The bridge's own catalog read routes through the same capped seam."""
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    home = loaded_plugin["home"]
    _set_cap(home, ["memory", "todo"])
    _clear_tool_defs_cache()

    defs = get_tool_definitions(
        enabled_toolsets=None,
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    names = {item["function"]["name"] for item in defs}

    assert set(PLUGIN_TOOLS).isdisjoint(names)


# ---------------------------------------------------------------------------
# PLUGIN_ALLOWED — visible and dispatchable when explicitly inside the cap
# ---------------------------------------------------------------------------


def test_allowlisted_plugin_is_visible(loaded_plugin) -> None:
    home = loaded_plugin["home"]
    _set_cap(home, ["memory", TOOLSET_NAME])

    names = _surface(["memory", TOOLSET_NAME])

    assert set(PLUGIN_TOOLS) <= names
    assert "memory" in names


def test_allowlisted_plugin_survives_toolsets_all(loaded_plugin) -> None:
    home = loaded_plugin["home"]
    _set_cap(home, ["memory", TOOLSET_NAME])

    names = _surface(None)

    assert set(PLUGIN_TOOLS) <= names
    assert {"terminal", "process"}.isdisjoint(names)


def test_allowlisted_plugin_is_dispatchable(loaded_plugin, monkeypatch) -> None:
    """Visibility is not enough — the allowlisted tool must still execute."""
    import hermes_plugins.powerunits.client as plugin_client
    from model_tools import handle_function_call

    home = loaded_plugin["home"]
    _set_cap(home, ["memory", TOOLSET_NAME])
    assert set(PLUGIN_TOOLS) <= _surface(["memory", TOOLSET_NAME])

    poster = RecordingPoster(
        {
            "success": True,
            "correlation_id": FIXED_CORRELATION_ID,
            "baseline_ready": True,
            "time_window": {
                "start_utc": FIXED_WINDOW_START,
                "end_utc_exclusive": FIXED_WINDOW_END,
                "expected_hours": 24,
            },
            "rows": [],
            "readiness": "go",
        }
    )
    monkeypatch.setattr(plugin_client, "http_post", poster)

    out = json.loads(
        handle_function_call(
            "read_powerunits_coverage_snapshot_v1",
            {
                "country_codes": ["DE"],
                "window_start_utc": FIXED_WINDOW_START,
                "window_end_utc": FIXED_WINDOW_END,
            },
        )
    )

    assert out.get("error_code") not in {"unknown_operation_id", "unexpected_field"}
    assert poster.count == 1


def test_allowlisted_plugin_still_respects_disabled_toolsets(loaded_plugin) -> None:
    """The cap is an upper bound; it does not override a normal disable."""
    home = loaded_plugin["home"]
    _set_cap(home, ["memory", TOOLSET_NAME])

    names = _surface(["memory", TOOLSET_NAME], disabled=[TOOLSET_NAME])

    assert set(PLUGIN_TOOLS).isdisjoint(names)


def test_no_cap_reproduces_the_r2_baseline(loaded_plugin) -> None:
    """Without the config field, the R2 unpatched findings are unchanged."""
    home = loaded_plugin["home"]
    _set_cap(home, None)

    assert set(PLUGIN_TOOLS) <= _surface(None)
    assert set(PLUGIN_TOOLS) <= _surface(["memory", TOOLSET_NAME])
    assert set(PLUGIN_TOOLS).isdisjoint(_surface(["memory", "todo"]))
