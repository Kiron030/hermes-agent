"""Prove official modern plugin registration — not a direct handler import."""

from __future__ import annotations

from tests.r2_powerunits_plugin.conftest import PLUGIN_TOOLS, TOOLSET_NAME


def test_plugin_loads_through_official_user_plugin_path(loaded_plugin) -> None:
    loaded = loaded_plugin["loaded"]
    assert loaded is not None
    assert loaded.enabled is True
    assert loaded.error is None
    assert loaded.manifest.source == "user"
    assert loaded.manifest.name == "powerunits"
    assert set(loaded.tools_registered) == set(PLUGIN_TOOLS)


def test_registered_tool_metadata_and_check_fn(loaded_plugin, plugin_env) -> None:
    from tools.registry import registry

    for name in PLUGIN_TOOLS:
        entry = registry.get_entry(name)
        assert entry is not None, name
        assert entry.toolset == TOOLSET_NAME
        assert entry.schema["name"] == name
        assert entry.schema["parameters"]["additionalProperties"] is False
        assert callable(entry.check_fn)
        assert entry.check_fn() is True
        assert callable(entry.handler)
        params = entry.schema["parameters"]["properties"]
        assert "url" not in params
        assert "host" not in params
        assert "route" not in params
        assert "path" not in params
        assert "sql" not in params


def test_plugin_toolset_is_discoverable(loaded_plugin) -> None:
    from hermes_cli.plugins import get_plugin_toolsets
    from toolsets import validate_toolset

    keys = {key for key, _label, _desc in get_plugin_toolsets()}
    assert TOOLSET_NAME in keys
    assert validate_toolset(TOOLSET_NAME) is True
