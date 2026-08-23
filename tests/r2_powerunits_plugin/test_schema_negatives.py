"""Model-facing schemas expose no host/path/URL/SQL surface."""

from __future__ import annotations

from tests.r2_powerunits_plugin.conftest import PLUGIN_TOOLS, TOOLSET_NAME

FORBIDDEN = {"url", "host", "hostname", "base_url", "path", "route", "sql", "query", "file_path", "filepath"}


def test_schemas_forbid_transport_and_unknown_fields(loaded_plugin) -> None:
    from tools.registry import registry

    for name in PLUGIN_TOOLS:
        entry = registry.get_entry(name)
        assert entry is not None
        params = entry.schema["parameters"]
        assert params["additionalProperties"] is False
        props = set(params.get("properties") or {})
        assert not (props & FORBIDDEN), f"{name} leaked {props & FORBIDDEN}"


def test_single_toolset_namespace(loaded_plugin) -> None:
    from tools.registry import registry

    toolsets = {registry.get_entry(name).toolset for name in PLUGIN_TOOLS}
    assert toolsets == {TOOLSET_NAME}
