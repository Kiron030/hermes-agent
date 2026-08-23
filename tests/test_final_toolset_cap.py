"""Final callable-surface cap (``agent.final_allowed_toolsets``).

Every test drives the public ``get_tool_definitions`` entry point so the
property under test is the surface a model actually receives, not the shape of
an internal helper. The cap is a security primitive, so the assertions are
mechanical: a tool is either in the final surface or it is not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

import pytest
import yaml

# Tools that must never survive a cap that excludes the `terminal` toolset.
TERMINAL_TOOLS = {"terminal", "process"}


@pytest.fixture
def capped_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An isolated HERMES_HOME whose config can be rewritten mid-test.

    Never touches the developer's real ``~/.hermes``.
    """
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    # The generic cap must be provable on its own; keep the fork's
    # env-gated clamp out of the picture.
    monkeypatch.delenv("HERMES_POWERUNITS_RUNTIME_POLICY", raising=False)

    def write(agent: Optional[dict] = None, *, invalidate: bool = True) -> None:
        payload: dict[str, Any] = {}
        if agent is not None:
            payload["agent"] = agent
        (home / "config.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")
        if invalidate:
            _reset_config_caches()

    write(None)
    yield write
    _reset_config_caches()


def _reset_config_caches() -> None:
    from hermes_cli import config as config_mod
    from model_tools import _clear_tool_defs_cache

    config_mod._LOAD_CONFIG_CACHE.clear()
    config_mod._RAW_CONFIG_CACHE.clear()
    _clear_tool_defs_cache()


def _surface(
    enabled: Optional[Iterable[str]] = None,
    disabled: Optional[Iterable[str]] = None,
    *,
    quiet: bool = True,
) -> set[str]:
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    _clear_tool_defs_cache()
    defs = get_tool_definitions(
        enabled_toolsets=list(enabled) if enabled is not None else None,
        disabled_toolsets=list(disabled) if disabled is not None else None,
        quiet_mode=quiet,
    )
    return {item["function"]["name"] for item in defs}


# ---------------------------------------------------------------------------
# No configuration: upstream-equivalent
# ---------------------------------------------------------------------------


def test_absent_cap_leaves_surface_untouched(capped_home) -> None:
    baseline = _surface(["memory", "todo", "terminal"])
    capped_home({"disabled_toolsets": []})
    assert _surface(["memory", "todo", "terminal"]) == baseline
    assert TERMINAL_TOOLS <= baseline


def test_absent_cap_leaves_the_all_surface_untouched(capped_home) -> None:
    baseline = _surface(None)
    capped_home({"disabled_toolsets": []})
    assert _surface(None) == baseline


# ---------------------------------------------------------------------------
# Security property: nothing can widen past the cap
# ---------------------------------------------------------------------------


def test_caller_cannot_widen_beyond_cap(capped_home) -> None:
    """An explicit caller request for an out-of-cap toolset is refused."""
    assert TERMINAL_TOOLS <= _surface(["memory", "terminal"])

    capped_home({"final_allowed_toolsets": ["memory", "todo"]})
    names = _surface(["memory", "terminal"])

    assert TERMINAL_TOOLS.isdisjoint(names)
    assert "memory" in names


def test_toolsets_all_cannot_widen_beyond_cap(capped_home) -> None:
    """`--toolsets all` reaches the seam as ``enabled_toolsets=None``."""
    assert TERMINAL_TOOLS <= _surface(None)

    capped_home({"final_allowed_toolsets": ["memory", "todo"]})
    names = _surface(None)

    assert TERMINAL_TOOLS.isdisjoint(names)
    assert names <= {"memory", "todo"}


def test_explicit_all_alias_cannot_widen_beyond_cap(capped_home) -> None:
    capped_home({"final_allowed_toolsets": ["memory", "todo"]})
    assert TERMINAL_TOOLS.isdisjoint(_surface(["all"]))
    assert TERMINAL_TOOLS.isdisjoint(_surface(["*"]))


def test_cap_applies_without_quiet_mode(capped_home) -> None:
    """The cap lives below the memo, so the uncached path is capped too."""
    capped_home({"final_allowed_toolsets": ["memory"]})
    assert TERMINAL_TOOLS.isdisjoint(_surface(["terminal", "memory"], quiet=False))


def test_cap_applies_to_the_pre_assembly_catalog(capped_home) -> None:
    """The tool_search bridge reads the catalog through the same seam.

    ``skip_tool_search_assembly=True`` is the call the bridge makes to see the
    uncollapsed catalog it may search and invoke through; capping it there is
    what keeps the bridge from becoming a hole in the cap.
    """
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    capped_home({"final_allowed_toolsets": ["memory"]})
    _clear_tool_defs_cache()
    defs = get_tool_definitions(
        enabled_toolsets=None, quiet_mode=True, skip_tool_search_assembly=True
    )

    assert {item["function"]["name"] for item in defs} == {"memory"}


# ---------------------------------------------------------------------------
# Intersection semantics: upper bound, not replacement
# ---------------------------------------------------------------------------


def test_narrow_caller_stays_narrow(capped_home) -> None:
    """A caller asking for less than the cap is not expanded up to it."""
    capped_home({"final_allowed_toolsets": ["memory", "todo", "terminal"]})
    names = _surface(["memory"])

    assert "memory" in names
    assert "todo" not in names
    assert TERMINAL_TOOLS.isdisjoint(names)


def test_cap_never_adds_a_tool(capped_home) -> None:
    """Every capped surface is a subset of the same uncapped surface."""
    uncapped = _surface(["memory"])
    capped_home({"final_allowed_toolsets": ["memory", "todo", "terminal", "file"]})
    assert _surface(["memory"]) <= uncapped


def test_disabled_toolsets_are_not_resurrected(capped_home) -> None:
    """A cap entry does not undo a normal disabled_toolsets subtraction."""
    capped_home({"final_allowed_toolsets": ["memory", "terminal"]})
    names = _surface(["memory", "terminal"], disabled=["terminal"])

    assert TERMINAL_TOOLS.isdisjoint(names)
    assert "memory" in names


# ---------------------------------------------------------------------------
# Unknown / malformed allowlist entries are fail-closed
# ---------------------------------------------------------------------------


def test_unknown_entry_contributes_nothing(capped_home) -> None:
    """An unknown name is never read as 'allow everything'."""
    capped_home({"final_allowed_toolsets": ["not_a_real_toolset_xyz"]})
    assert _surface(None) == set()
    assert _surface(["memory", "terminal"]) == set()


def test_unknown_entry_does_not_void_known_entries(capped_home) -> None:
    capped_home({"final_allowed_toolsets": ["memory", "not_a_real_toolset_xyz"]})
    names = _surface(["memory", "terminal"])

    assert names == {"memory"}


def test_empty_list_is_an_empty_allowlist(capped_home) -> None:
    """`[]` is a declared cap of nothing, not an absent cap."""
    capped_home({"final_allowed_toolsets": []})
    assert _surface(None) == set()


def test_null_value_means_uncapped(capped_home) -> None:
    """An explicit null is 'key present but unset' — upstream behaviour."""
    baseline = _surface(["memory", "terminal"])
    capped_home({"final_allowed_toolsets": None})
    assert _surface(["memory", "terminal"]) == baseline


def test_scalar_string_is_a_single_entry(capped_home) -> None:
    capped_home({"final_allowed_toolsets": "memory"})
    assert _surface(["memory", "terminal"]) == {"memory"}


def test_malformed_value_fails_closed(capped_home) -> None:
    """A cap that cannot be parsed caps to nothing rather than to everything."""
    capped_home({"final_allowed_toolsets": {"memory": True}})
    assert _surface(None) == set()


def test_legacy_toolset_name_is_honoured_in_cap(capped_home) -> None:
    """Legacy `*_tools` names resolve in the cap as they do when enabling."""
    capped_home({"final_allowed_toolsets": ["terminal_tools"]})
    names = _surface(["memory", "terminal"])

    assert names == {"terminal"}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_editing_the_cap_invalidates_the_memo(capped_home) -> None:
    """The existing cfg fingerprint already covers the cap — no new cache key.

    This test deliberately does not clear the memo between the two reads; it
    only clears it once up front, then relies on the config-mtime fingerprint
    that is already part of the ``get_tool_definitions`` cache key.
    """
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    def read() -> set[str]:
        defs = get_tool_definitions(
            enabled_toolsets=["memory", "terminal"], quiet_mode=True
        )
        return {item["function"]["name"] for item in defs}

    capped_home({"final_allowed_toolsets": ["memory", "todo", "terminal"]})
    _clear_tool_defs_cache()
    warm = read()
    assert TERMINAL_TOOLS <= warm

    # Rewrite the cap only. Nothing below invalidates the memo explicitly.
    capped_home({"final_allowed_toolsets": ["memory"]}, invalidate=False)
    from hermes_cli import config as config_mod

    config_mod._LOAD_CONFIG_CACHE.clear()

    assert TERMINAL_TOOLS.isdisjoint(read())


# ---------------------------------------------------------------------------
# Domain agnosticism
# ---------------------------------------------------------------------------


def test_cap_implementation_names_no_domain(capped_home) -> None:
    """The generic primitive must not learn about any product or transport."""
    import inspect

    import model_tools

    source = "\n".join(
        inspect.getsource(obj)
        for obj in (
            model_tools._read_final_toolset_cap,
            model_tools._resolve_final_allowed_tools,
        )
    )
    lowered = source.lower()
    for term in ("powerunits", "telegram", "entsoe", "tier", "repo_b", "coverage"):
        assert term not in lowered
