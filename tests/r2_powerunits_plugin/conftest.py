"""Shared fixtures for the standalone PowerUnits plugin proof.

Loads the plugin through the official user-plugin discovery path.
Does not call wrapper handlers directly for registration/dispatch proofs.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.powerunits_golden.env import (
    SYNTHETIC_EXECUTE_BASE_URL,
    SYNTHETIC_EXECUTE_HOST,
    SYNTHETIC_EXECUTE_SECRET,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "standalone" / "powerunits"
PLUGIN_NAME = "powerunits"
TOOLSET_NAME = "powerunits_bounded_reads"
PLUGIN_TOOLS = (
    "read_powerunits_coverage_snapshot_v1",
    "inventory_powerunits_bounded_coverage_v1",
    "read_powerunits_entsoe_bzn_price_readiness_v1",
    "readiness_powerunits_option_d_bounded_window",
)
GATE_ENVS = (
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED",
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED",
    "HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED",
)


def _save_entry(entry: Any) -> dict[str, Any]:
    return {
        "name": entry.name,
        "toolset": entry.toolset,
        "schema": entry.schema,
        "handler": entry.handler,
        "check_fn": entry.check_fn,
        "requires_env": list(entry.requires_env or []),
        "is_async": entry.is_async,
        "description": entry.description,
        "emoji": entry.emoji,
        "max_result_size_chars": entry.max_result_size_chars,
        "dynamic_schema_overrides": entry.dynamic_schema_overrides,
    }


@pytest.fixture
def isolated_hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    # Unpatched upstream behaviour: do not activate the fork first_safe clamp.
    monkeypatch.delenv("HERMES_POWERUNITS_RUNTIME_POLICY", raising=False)
    return home


@pytest.fixture
def plugin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    for flag in GATE_ENVS:
        monkeypatch.setenv(flag, "1")


@pytest.fixture
def loaded_plugin(isolated_hermes_home: Path, plugin_env: None):
    """Install + enable + load via official PluginManager user-plugin discovery."""

    import model_tools  # noqa: F401 — ensure builtin wrappers are registered first
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from model_tools import _clear_tool_defs_cache
    from tools.registry import invalidate_check_fn_cache, registry

    dest = isolated_hermes_home / "plugins" / PLUGIN_NAME
    shutil.copytree(PLUGIN_SRC, dest)
    (isolated_hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"plugins": {"enabled": [PLUGIN_NAME]}}),
        encoding="utf-8",
    )

    saved = {}
    for name in PLUGIN_TOOLS:
        entry = registry.get_entry(name)
        if entry is not None:
            saved[name] = _save_entry(entry)
            registry.deregister(name)

    discover_plugins(force=True)
    mgr = get_plugin_manager()
    loaded = mgr._plugins.get(PLUGIN_NAME)
    invalidate_check_fn_cache()
    _clear_tool_defs_cache()
    yield {"manager": mgr, "loaded": loaded, "home": isolated_hermes_home}

    for name in PLUGIN_TOOLS:
        if registry.get_entry(name) is not None:
            registry.deregister(name)
        mgr._plugin_tool_names.discard(name)
    mgr._plugins.pop(PLUGIN_NAME, None)
    for name, entry in saved.items():
        registry.register(**entry)
    invalidate_check_fn_cache()
    _clear_tool_defs_cache()
