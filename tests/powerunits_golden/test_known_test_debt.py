"""Task G — classify known test debt. Do not silently fix product or suite-wide cache issues."""

from __future__ import annotations

from pathlib import Path

from tests.powerunits_golden.env import invalidate_tool_surface_caches

# Observed: tests/hermes_cli/test_tools_config.py gate-off cases can fail when
# sharing one pytest process with earlier get_tool_definitions() calls, while
# isolated execution passes.
#
# Root cause: model_tools.get_tool_definitions(quiet_mode=True) caches by
# toolset/registry/config fingerprint and does NOT include env/gate flags.
# registry.get_definitions additionally TTL-caches check_fn. A prior gate-on
# resolution can therefore leak into a later gate-off assertion in the same
# process. Product comment in model_tools.py treats the first-safe env as
# process-lifetime. This is therefore test isolation / cache debt, not a
# first_safe production bug.
#
# Reproduction:
#   pytest tests/hermes_cli/test_tools_config.py
#   pytest tests/hermes_cli/test_tools_config.py::test_telegram_first_safe_bzn_not_in_schema_when_gate_off
#
# Isolated command is the passing one. Full-file order can fail if an earlier
# test populated the cache without invalidate_check_fn_cache/_clear_tool_defs_cache.

TEST_DEBT = "TEST_ISOLATION/CACHE_DEBT"
REPRO_FULL_FILE = "pytest tests/hermes_cli/test_tools_config.py"
REPRO_ISOLATED = (
    "pytest tests/hermes_cli/test_tools_config.py::"
    "test_telegram_first_safe_bzn_not_in_schema_when_gate_off"
)


def test_known_tools_config_debt_is_isolation_not_product_bug() -> None:
    tools_config = Path(__file__).resolve().parents[1] / "hermes_cli" / "test_tools_config.py"
    assert tools_config.is_file()
    source = tools_config.read_text(encoding="utf-8")
    assert "test_telegram_first_safe_bzn_not_in_schema_when_gate_off" in source
    # The gate-off test does not invalidate caches; that is the debt.
    gate_off = source.split("def test_telegram_first_safe_bzn_not_in_schema_when_gate_off", 1)[1]
    gate_off = gate_off.split("\n\n\n", 1)[0]
    assert "invalidate_check_fn_cache" not in gate_off
    assert "_clear_tool_defs_cache" not in gate_off
    assert TEST_DEBT == "TEST_ISOLATION/CACHE_DEBT"


def test_golden_suite_resets_surface_caches() -> None:
    invalidate_tool_surface_caches()
    from model_tools import _tool_defs_cache

    assert _tool_defs_cache == {} or len(_tool_defs_cache) == 0
