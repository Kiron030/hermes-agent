"""Run the modern half of the R3 comparison on a real pinned Hermes runtime.

R1 proved that pinned upstream v2026.8.19 boots and dispatches. R2 proved the
standalone plugin registers through the official plugin API. This probe puts the
two together on the *pinned upstream tree* rather than on this fork, and checks
that the generic ``agent.final_allowed_toolsets`` cap — the only shared-core
patch the modern architecture needs — enforces there too.

It is deliberately self-contained: it imports nothing from this fork, so the
runtime under test is the pinned tree and only the pinned tree.

    python scripts/r3_shadow_comparison/modern_runtime_probe.py \
        --hermes-root W:/cache/hermes-r3-modern \
        --plugin-src  W:/cache/hermes-r3/standalone/powerunits \
        --scratch     W:/cache/r3-modern-scratch \
        --out         docs/architecture/evidence/hermes_r3_modern_runtime_probe_v1.json

No live network (HTTP is replaced in-process), no production credential, and
nothing is written inside ``--hermes-root``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any

SYNTHETIC_HOST = "bounded.example.test"
SYNTHETIC_BASE_URL = f"https://{SYNTHETIC_HOST}"
SYNTHETIC_SECRET = "r3-probe-synthetic-secret"
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
# Same argument payloads the R0 contracts use, inlined so the probe stays
# independent of this fork's test tree.
CASE_ARGS: dict[str, dict[str, Any]] = {
    "read_powerunits_coverage_snapshot_v1": {
        "country_codes": ["DE"],
        "window_start_utc": "2024-01-01T00:00:00Z",
        "window_end_utc": "2024-01-02T00:00:00Z",
        "version": "v1",
    },
    "inventory_powerunits_bounded_coverage_v1": {
        "country_codes": ["DE"],
        "window_start_utc": "2024-01-01T00:00:00Z",
        "window_end_utc": "2024-01-02T00:00:00Z",
        "version": "v1",
    },
    "read_powerunits_entsoe_bzn_price_readiness_v1": {
        "country_codes": ["DE"],
        "window_start_utc": "2024-01-01T00:00:00Z",
        "window_end_utc": "2024-01-02T00:00:00Z",
        "table_version": "v1",
    },
    "readiness_powerunits_option_d_bounded_window": {
        "country": "PL",
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-01-02T00:00:00Z",
        "version": "v1",
    },
}
UNSAFE_NAMES = (
    "session_search",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "terminal",
    "execute_code",
    "process",
    "delegate_task",
    "browser",
)
PRODUCTION_AUTHORITY_NAMES = (
    "DATABASE_URL",
    "DATABASE_URL_TIMESCALE",
    "RAILWAY_TOKEN",
    "RAILWAY_API_TOKEN",
    "VERCEL_TOKEN",
)


class RecordingPoster:
    """Return a canned Repo-B body. Never opens a socket."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url, headers, json_body, timeout_s=None):
        from urllib.parse import urlparse

        parsed = urlparse(url)
        self.calls.append(
            {
                "url": url,
                "scheme": parsed.scheme,
                "hostname": parsed.hostname,
                "path": parsed.path,
                "headers": dict(headers),
                "json_body": dict(json_body),
            }
        )
        return _FakeResp(self.payload)


class _FakeResp:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._data = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict[str, Any]:
        return dict(self._data)


def _write_config(home: Path, payload: dict[str, Any]) -> None:
    import yaml

    (home / "config.yaml").write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    from model_tools import _clear_tool_defs_cache

    _clear_tool_defs_cache()


def _callable_names(**kwargs: Any) -> set[str]:
    from model_tools import get_tool_definitions

    return {t["function"]["name"] for t in get_tool_definitions(**kwargs)}


def _schema_cost(names: set[str], **kwargs: Any) -> dict[str, int]:
    from model_tools import get_tool_definitions

    selected = [d for d in get_tool_definitions(**kwargs) if d["function"]["name"] in names]
    blob = json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
    return {
        "tools": len(selected),
        "schema_chars": len(blob),
        "estimated_tokens_at_4_chars": round(len(blob) / 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", type=Path, required=True)
    parser.add_argument("--plugin-src", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    root = args.hermes_root.resolve()
    scratch = args.scratch.resolve()
    home = scratch / "home"
    if scratch.exists():
        shutil.rmtree(scratch)
    (home / "plugins").mkdir(parents=True)

    for name in PRODUCTION_AUTHORITY_NAMES:
        os.environ.pop(name, None)
    os.environ["HERMES_HOME"] = str(home)
    os.environ["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
    os.environ.pop("HERMES_POWERUNITS_RUNTIME_POLICY", None)
    os.environ["POWERUNITS_INTERNAL_EXECUTE_BASE_URL"] = SYNTHETIC_BASE_URL
    os.environ["POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS"] = SYNTHETIC_HOST
    os.environ["POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE"] = "enforce"
    os.environ["POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"] = SYNTHETIC_SECRET
    for flag in GATE_ENVS:
        os.environ[flag] = "1"

    # The runtime under test is the pinned tree, and only the pinned tree.
    sys.path.insert(0, str(root))

    boot_start = time.perf_counter()
    import model_tools  # noqa: F401
    import toolsets  # noqa: F401
    from hermes_cli.plugins import discover_plugins, get_plugin_manager

    boot_ms = (time.perf_counter() - boot_start) * 1000.0

    report: dict[str, Any] = {
        "runtime_root": str(root),
        "runtime_model_tools": model_tools.__file__,
        "fork_modules_leaked_into_runtime": sorted(
            name for name in sys.modules if name.startswith("powerunits_")
        ),
        "boot_ms": round(boot_ms, 2),
        "production_authority_present": sorted(
            name for name in PRODUCTION_AUTHORITY_NAMES if os.getenv(name)
        ),
        "cap_patch_present": hasattr(model_tools, "_read_final_toolset_cap"),
        "powerunits_references_in_runtime_model_tools": sum(
            1
            for line in Path(model_tools.__file__).read_text(encoding="utf-8").splitlines()
            if "powerunits" in line.lower()
        ),
    }

    shutil.copytree(args.plugin_src, home / "plugins" / PLUGIN_NAME)
    _write_config(home, {"plugins": {"enabled": [PLUGIN_NAME]}})

    load_start = time.perf_counter()
    discover_plugins(force=True)
    manager = get_plugin_manager()
    report["plugin_load_ms"] = round((time.perf_counter() - load_start) * 1000.0, 2)
    report["plugin_loaded"] = PLUGIN_NAME in manager._plugins

    from tools.registry import registry

    report["plugin_tools_registered"] = sorted(
        name for name in PLUGIN_TOOLS if registry.get_entry(name) is not None
    )

    # This runtime can assemble a `tool_search` bridge, in which case the schema
    # list the model receives is three meta-tools rather than the callable
    # catalog behind them. Whether it does depends on how wide the resolved
    # surface is, so the flag is sampled in both the uncapped and capped states.
    def _bridge_active() -> bool:
        return sorted(
            _callable_names(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True)
        ) == ["tool_call", "tool_describe", "tool_search"]

    report["tool_search_bridge"] = {"uncapped": _bridge_active()}

    # --- control: uncapped, the way R1/R2 found it ---
    uncapped = _callable_names(
        enabled_toolsets=None,
        disabled_toolsets=None,
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    report["uncapped"] = {
        "callable": len(uncapped),
        "unsafe_present": sorted(uncapped & set(UNSAFE_NAMES)),
        "plugin_visible": sorted(uncapped & set(PLUGIN_TOOLS)),
    }

    # --- the declared operator bound ---
    _write_config(
        home,
        {
            "plugins": {"enabled": [PLUGIN_NAME]},
            "agent": {"final_allowed_toolsets": [PLUGIN_TOOLSET]},
        },
    )
    capped_all = _callable_names(
        enabled_toolsets=None,
        disabled_toolsets=None,
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    capped_override = _callable_names(
        enabled_toolsets=["terminal", "file", "delegation", "browser", PLUGIN_TOOLSET],
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    capped_narrow = _callable_names(
        enabled_toolsets=["memory"], quiet_mode=True, skip_tool_search_assembly=True
    )
    report["capped"] = {
        "toolsets_all_callable": len(capped_all),
        "caller_override_callable": len(capped_override),
        "unsafe_present": sorted((capped_all | capped_override) & set(UNSAFE_NAMES)),
        "plugin_visible": sorted(capped_all & set(PLUGIN_TOOLS)),
        "narrow_caller_stays_narrow": sorted(capped_narrow),
    }

    # --- a cap that omits the plugin must beat plugin self-expansion ---
    _write_config(
        home,
        {
            "plugins": {"enabled": [PLUGIN_NAME]},
            "agent": {"final_allowed_toolsets": ["memory"]},
        },
    )
    self_expansion = _callable_names(
        enabled_toolsets=None,
        disabled_toolsets=None,
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    report["capped"]["plugin_self_expansion_blocked"] = not (
        self_expansion & set(PLUGIN_TOOLS)
    )

    _write_config(
        home,
        {
            "plugins": {"enabled": [PLUGIN_NAME]},
            "agent": {"final_allowed_toolsets": [PLUGIN_TOOLSET]},
        },
    )
    report["tool_search_bridge"]["capped"] = _bridge_active()
    report["schema_cost"] = {
        "capped_catalog": _schema_cost(
            capped_all,
            enabled_toolsets=None,
            disabled_toolsets=None,
            quiet_mode=True,
            skip_tool_search_assembly=True,
        ),
        "what_the_model_actually_receives": _schema_cost(
            _callable_names(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True),
            enabled_toolsets=None,
            disabled_toolsets=None,
            quiet_mode=True,
        ),
    }

    # --- dispatch the corpus through the pinned runtime ---
    import hermes_plugins.powerunits.client as plugin_client
    from model_tools import handle_function_call

    dispatch: dict[str, Any] = {}
    for tool_name, call_args in CASE_ARGS.items():
        poster = RecordingPoster({"success": True, "chat_summary": "probe", "hermes_statement": "probe"})
        plugin_client.http_post = poster
        out = json.loads(handle_function_call(tool_name, call_args))

        samples = []
        for _ in range(20):
            start = time.perf_counter()
            handle_function_call(tool_name, call_args)
            samples.append((time.perf_counter() - start) * 1000.0)

        dispatch[tool_name] = {
            "posted": len(poster.calls) > 0,
            "scheme": poster.calls[0]["scheme"] if poster.calls else None,
            "hostname": poster.calls[0]["hostname"] if poster.calls else None,
            "path": poster.calls[0]["path"] if poster.calls else None,
            "body_keys": sorted(poster.calls[0]["json_body"]) if poster.calls else [],
            "transport_field_in_body": bool(
                poster.calls and {"url", "host", "path", "sql"} & set(poster.calls[0]["json_body"])
            ),
            "response_keys": sorted(out),
            "median_ms": round(statistics.median(samples), 4),
        }
    report["dispatch"] = dispatch

    shutil.rmtree(scratch, ignore_errors=True)

    blob = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(blob + "\n", encoding="utf-8")
    print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
