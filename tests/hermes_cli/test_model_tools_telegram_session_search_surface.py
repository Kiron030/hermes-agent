"""model_tools × Telegram first_safe_v1: session_search is clamped out."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _invalidate_tool_caches() -> None:
    from model_tools import _clear_tool_defs_cache
    from tools.registry import invalidate_check_fn_cache

    invalidate_check_fn_cache()
    _clear_tool_defs_cache()
    yield
    invalidate_check_fn_cache()
    _clear_tool_defs_cache()


def _final_names(enabled_toolsets: list[str]) -> set[str]:
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    _clear_tool_defs_cache()
    return {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=enabled_toolsets, quiet_mode=True)
    }


@pytest.mark.parametrize("tier", range(7))
def test_session_search_absent_from_final_surface_all_tiers(
    monkeypatch: pytest.MonkeyPatch,
    tier: int,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", str(tier))

    from hermes_cli.tools_config import _get_platform_tools
    from powerunits_telegram_overlays import expected_telegram_toolsets_first_safe
    from toolsets import resolve_toolset

    allowed: set[str] = set()
    for ts_name in expected_telegram_toolsets_first_safe(tier):
        allowed.update(resolve_toolset(ts_name))
    assert "session_search" not in allowed

    # Platform resolution may still list session_search (hermes-telegram
    # default / leftover config). The first-safe clamp is the final gate.
    enabled = sorted(_get_platform_tools({}, "telegram"))
    assert "session_search" not in _final_names(enabled)


@pytest.mark.parametrize("tier", range(7))
def test_explicit_session_search_toolset_cannot_bypass_first_safe_clamp(
    monkeypatch: pytest.MonkeyPatch,
    tier: int,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", str(tier))

    from hermes_cli.tools_config import _get_platform_tools
    from toolsets import resolve_toolset, validate_toolset

    assert validate_toolset("session_search")
    assert "session_search" in resolve_toolset("session_search")

    enabled = set(_get_platform_tools({}, "telegram"))
    enabled.add("session_search")
    names = _final_names(sorted(enabled))
    assert "session_search" not in names

    isolated = _final_names(["session_search"])
    assert "session_search" not in isolated
