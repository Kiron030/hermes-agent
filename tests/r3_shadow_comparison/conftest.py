"""Fixtures that stand up the two systems R3 compares.

CURRENT_FORK        built-in ``tools/powerunits_*`` wrappers, fork first_safe clamp on.
MODERN_HERMES_PROOF standalone plugin loaded through the official user-plugin path,
                    bounded by the generic ``agent.final_allowed_toolsets`` cap.

Both run in this process against the same registry, so the measured difference is
architecture, not interpreter. Pinned-runtime evidence for the modern side is
separate: R1 (`docs/architecture/hermes_r1_proof_report_v1.md`) and the probe in
`scripts/r3_shadow_comparison/modern_runtime_probe.py`.
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
    apply_operator_ready_env,
    invalidate_tool_surface_caches,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "standalone" / "powerunits"
PLUGIN_NAME = "powerunits"
PLUGIN_TOOLSET = "powerunits_bounded_reads"
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
def current_fork(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """This fork as deployed: wrappers registered, first_safe clamp active."""

    import model_tools  # noqa: F401 — registers the built-in wrappers

    home = tmp_path / ".hermes-current"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    apply_operator_ready_env(monkeypatch, tier=6)
    yield {"home": home}
    invalidate_tool_surface_caches()


def _write_config(home: Path, payload: dict[str, Any]) -> None:
    (home / "config.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=True), encoding="utf-8"
    )


@pytest.fixture
def modern_stack(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Modern architecture: plugin via official discovery + generic final cap.

    The fork's PowerUnits-specific clamp is explicitly *off* here, so anything
    the surface refuses is refused by the domain-agnostic cap alone.
    """

    import model_tools  # noqa: F401 — builtin wrappers register first
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from model_tools import _clear_tool_defs_cache
    from tools.registry import invalidate_check_fn_cache, registry

    home = tmp_path / ".hermes-modern"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_POWERUNITS_RUNTIME_POLICY", raising=False)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    for flag in GATE_ENVS:
        monkeypatch.setenv(flag, "1")

    shutil.copytree(PLUGIN_SRC, home / "plugins" / PLUGIN_NAME)
    _write_config(
        home,
        {
            "plugins": {"enabled": [PLUGIN_NAME]},
            "agent": {"final_allowed_toolsets": [PLUGIN_TOOLSET]},
        },
    )

    saved: dict[str, dict[str, Any]] = {}
    for name in PLUGIN_TOOLS:
        entry = registry.get_entry(name)
        if entry is not None:
            saved[name] = _save_entry(entry)
            registry.deregister(name)

    discover_plugins(force=True)
    manager = get_plugin_manager()
    invalidate_check_fn_cache()
    _clear_tool_defs_cache()

    yield {
        "home": home,
        "manager": manager,
        "loaded": manager._plugins.get(PLUGIN_NAME),
        "write_config": lambda payload: (
            _write_config(home, payload),
            _clear_tool_defs_cache(),
        ),
    }

    for name in PLUGIN_TOOLS:
        if registry.get_entry(name) is not None:
            registry.deregister(name)
        manager._plugin_tool_names.discard(name)
    manager._plugins.pop(PLUGIN_NAME, None)
    for name, entry in saved.items():
        registry.register(**entry)
    invalidate_check_fn_cache()
    _clear_tool_defs_cache()
