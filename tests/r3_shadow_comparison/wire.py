"""Capture the HTTP request each system produces for one corpus case.

The wire request — scheme, host, path, JSON body — is the part of "did both
systems do the same thing" that is objectively comparable. Response prose is
not, and R0 explicitly does not freeze it.
"""

from __future__ import annotations

import importlib
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

from tests.powerunits_golden.contracts import happy_repo_b_payload
from tests.powerunits_golden.env import (
    SYNTHETIC_EXECUTE_BASE_URL,
    SYNTHETIC_EXECUTE_HOST,
    SYNTHETIC_EXECUTE_SECRET,
    apply_operator_ready_env,
)
from tests.powerunits_golden.http import RecordingPoster
from tests.r3_shadow_comparison.conftest import (
    GATE_ENVS,
    PLUGIN_NAME,
    PLUGIN_SRC,
    PLUGIN_TOOLS,
    PLUGIN_TOOLSET,
    _save_entry,
)
from tests.r3_shadow_comparison.corpus import CorpusCase


def _dispatch(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    import json

    from model_tools import handle_function_call

    return json.loads(handle_function_call(tool_name, args))


def capture_current_fork_request(
    case: CorpusCase, home: Path, monkeypatch
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Dispatch on the fork wrappers; return (wire request, tool response)."""

    import model_tools  # noqa: F401 — registers the built-in wrappers

    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    apply_operator_ready_env(monkeypatch, tier=6)

    poster = RecordingPoster(happy_repo_b_payload(case.contract))
    monkeypatch.setattr(
        importlib.import_module(case.contract.module), "_default_http_post", poster
    )
    out = _dispatch(case.current_fork_tool, case.args())
    return poster.calls[0], out


@contextmanager
def modern_plugin_loaded(home: Path, monkeypatch) -> Iterator[None]:
    """Load the standalone plugin through the official user-plugin path."""

    import model_tools  # noqa: F401
    from hermes_cli.plugins import discover_plugins, get_plugin_manager
    from model_tools import _clear_tool_defs_cache
    from tools.registry import invalidate_check_fn_cache, registry

    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_POWERUNITS_RUNTIME_POLICY", raising=False)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    for flag in GATE_ENVS:
        monkeypatch.setenv(flag, "1")

    dest = home / "plugins" / PLUGIN_NAME
    if not dest.exists():
        shutil.copytree(PLUGIN_SRC, dest)
    (home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "plugins": {"enabled": [PLUGIN_NAME]},
                "agent": {"final_allowed_toolsets": [PLUGIN_TOOLSET]},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
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
    try:
        yield
    finally:
        for name in PLUGIN_TOOLS:
            if registry.get_entry(name) is not None:
                registry.deregister(name)
            manager._plugin_tool_names.discard(name)
        manager._plugins.pop(PLUGIN_NAME, None)
        for name, entry in saved.items():
            registry.register(**entry)
        invalidate_check_fn_cache()
        _clear_tool_defs_cache()


def capture_modern_request(
    case: CorpusCase, tmp_path: Path, monkeypatch
) -> dict[str, Any]:
    """Dispatch the same intent on the modern stack; return the wire request."""

    request, _ = capture_modern_exchange(case, tmp_path, monkeypatch)
    return request


def capture_modern_exchange(
    case: CorpusCase, tmp_path: Path, monkeypatch
) -> tuple[dict[str, Any], dict[str, Any]]:
    with modern_plugin_loaded(tmp_path / ".hermes-modern-wire", monkeypatch):
        import hermes_plugins.powerunits.client as plugin_client

        poster = RecordingPoster(happy_repo_b_payload(case.contract))
        monkeypatch.setattr(plugin_client, "http_post", poster)
        out = _dispatch(case.modern_tool, case.args())
        return poster.calls[0], out
