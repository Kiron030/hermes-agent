"""Emit the reproducible R3 measurement artifact.

    python scripts/r3_shadow_comparison/emit_evidence.py

Writes JSON to stdout (and to --out when given). No live network, no production
credential, no repository mutation. Everything it measures is also asserted as
behaviour by ``tests/r3_shadow_comparison``; this script exists so the report can
quote exact numbers rather than adjectives.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402
from _pytest.monkeypatch import MonkeyPatch  # noqa: E402

from tests.powerunits_golden.contracts import happy_repo_b_payload  # noqa: E402
from tests.powerunits_golden.env import (  # noqa: E402
    UNSAFE_FREEDOMS_FIRST_SAFE_DENIES,
    apply_operator_ready_env,
)
from tests.powerunits_golden.http import RecordingPoster  # noqa: E402
from tests.r3_shadow_comparison.conftest import (  # noqa: E402
    PLUGIN_NAME,
    PLUGIN_TOOLS,
    PLUGIN_TOOLSET,
)
from tests.r3_shadow_comparison.corpus import BOUNDED_CASES, CORPUS  # noqa: E402
from tests.r3_shadow_comparison.wire import modern_plugin_loaded  # noqa: E402

DISPATCH_ITERATIONS = 40


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _callable_names(**kwargs: Any) -> set[str]:
    from model_tools import get_tool_definitions

    return {t["function"]["name"] for t in get_tool_definitions(**kwargs)}


def _definitions(**kwargs: Any) -> list[dict[str, Any]]:
    from model_tools import get_tool_definitions

    return get_tool_definitions(**kwargs)


def _schema_cost(definitions: list[dict[str, Any]], names: set[str]) -> dict[str, int]:
    """Serialized JSON size of the selected tool schemas.

    Characters, not tokens. A token estimate is derived with a fixed divisor and
    labelled as an estimate — the sample is far too small to claim dollars.
    """
    selected = [d for d in definitions if d["function"]["name"] in names]
    blob = json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
    return {
        "tools": len(selected),
        "schema_chars": len(blob),
        "estimated_tokens_at_4_chars": round(len(blob) / 4),
    }


def _time_dispatch(fn: Callable[[], Any], iterations: int) -> dict[str, float]:
    samples: list[float] = []
    fn()  # warm the import / check_fn caches; measure steady state
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "iterations": iterations,
        "median_ms": round(statistics.median(samples), 4),
        "p95_ms": round(sorted(samples)[max(0, int(len(samples) * 0.95) - 1)], 4),
        "mean_ms": round(statistics.fmean(samples), 4),
    }


def _write_config(home: Path, payload: dict[str, Any]) -> None:
    (home / "config.yaml").write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    from model_tools import _clear_tool_defs_cache

    _clear_tool_defs_cache()


# ---------------------------------------------------------------------------
# measurements
# ---------------------------------------------------------------------------


def measure_current_fork(root: Path) -> dict[str, Any]:
    import importlib

    import model_tools  # noqa: F401 — registers the wrappers

    out: dict[str, Any] = {"tiers": {}, "dispatch_ms": {}, "schema_cost": {}}

    for tier in range(7):
        with MonkeyPatch.context() as mp:
            home = root / f"fork-tier{tier}"
            home.mkdir(parents=True, exist_ok=True)
            mp.setenv("HERMES_HOME", str(home))
            apply_operator_ready_env(mp, tier=tier)
            names = _callable_names(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True)
            out["tiers"][str(tier)] = {
                "callable": len(names),
                "leaked_unsafe": sorted(names & set(UNSAFE_FREEDOMS_FIRST_SAFE_DENIES)),
            }

    with MonkeyPatch.context() as mp:
        home = root / "fork-cost"
        home.mkdir(parents=True, exist_ok=True)
        mp.setenv("HERMES_HOME", str(home))
        apply_operator_ready_env(mp, tier=6)
        definitions = _definitions(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True)
        all_names = {d["function"]["name"] for d in definitions}
        out["schema_cost"]["whole_operator_surface"] = _schema_cost(definitions, all_names)
        out["schema_cost"]["four_bounded_reads"] = _schema_cost(definitions, set(PLUGIN_TOOLS))
        out["callable_total_tier6"] = len(all_names)

        from model_tools import handle_function_call

        for case in BOUNDED_CASES:
            poster = RecordingPoster(happy_repo_b_payload(case.contract))
            mp.setattr(
                importlib.import_module(case.contract.module), "_default_http_post", poster
            )
            args = case.args()
            out["dispatch_ms"][case.case_id] = _time_dispatch(
                lambda tool=case.current_fork_tool, a=args: handle_function_call(tool, a),
                DISPATCH_ITERATIONS,
            )

    return out


def measure_modern(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"dispatch_ms": {}, "schema_cost": {}, "cap": {}}
    home = root / "modern"

    with MonkeyPatch.context() as mp:
        with modern_plugin_loaded(home, mp):
            import hermes_plugins.powerunits.client as plugin_client
            from model_tools import handle_function_call

            # --- control: what the surface looks like with the cap removed ---
            _write_config(home, {"plugins": {"enabled": [PLUGIN_NAME]}})
            uncapped = _callable_names(
                enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True
            )
            out["cap"]["uncapped_callable"] = len(uncapped)
            out["cap"]["uncapped_unsafe_present"] = sorted(
                uncapped & set(UNSAFE_FREEDOMS_FIRST_SAFE_DENIES)
            )
            out["cap"]["uncapped_plugin_visible"] = sorted(uncapped & set(PLUGIN_TOOLS))

            # --- the declared operator bound ---
            _write_config(
                home,
                {
                    "plugins": {"enabled": [PLUGIN_NAME]},
                    "agent": {"final_allowed_toolsets": [PLUGIN_TOOLSET]},
                },
            )
            capped_all = _callable_names(
                enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True
            )
            capped_override = _callable_names(
                enabled_toolsets=["terminal", "file", "delegation", "browser", PLUGIN_TOOLSET],
                quiet_mode=True,
            )
            out["cap"]["capped_callable_toolsets_all"] = len(capped_all)
            out["cap"]["capped_callable_caller_override"] = len(capped_override)
            out["cap"]["capped_unsafe_present"] = sorted(
                (capped_all | capped_override) & set(UNSAFE_FREEDOMS_FIRST_SAFE_DENIES)
            )
            out["cap"]["capped_plugin_visible"] = sorted(capped_all & set(PLUGIN_TOOLS))

            definitions = _definitions(
                enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True
            )
            out["schema_cost"]["whole_operator_surface"] = _schema_cost(
                definitions, {d["function"]["name"] for d in definitions}
            )
            out["schema_cost"]["four_bounded_reads"] = _schema_cost(definitions, set(PLUGIN_TOOLS))
            out["callable_total_capped"] = len(capped_all)

            for case in BOUNDED_CASES:
                poster = RecordingPoster(happy_repo_b_payload(case.contract))
                mp.setattr(plugin_client, "http_post", poster)
                args = case.args()
                out["dispatch_ms"][case.case_id] = _time_dispatch(
                    lambda tool=case.modern_tool, a=args: handle_function_call(tool, a),
                    DISPATCH_ITERATIONS,
                )

    return out


def measure_wire_parity(root: Path) -> dict[str, Any]:
    from tests.r3_shadow_comparison.wire import (
        capture_current_fork_request,
        capture_modern_exchange,
    )

    rows: dict[str, Any] = {}
    for case in BOUNDED_CASES:
        with MonkeyPatch.context() as mp:
            fork_call, fork_out = capture_current_fork_request(
                case, root / f"wire-fork-{case.case_id}", mp
            )
        with MonkeyPatch.context() as mp:
            modern_call, modern_out = capture_modern_exchange(
                case, root / f"wire-modern-{case.case_id}", mp
            )
        rows[case.case_id] = {
            "route_identical": fork_call["path"] == modern_call["path"],
            "host_identical": fork_call["hostname"] == modern_call["hostname"],
            "body_identical": fork_call["json_body"] == modern_call["json_body"],
            "body_keys": sorted(fork_call["json_body"]),
            "r0_happy_fields_present_fork": all(
                f in fork_out for f in case.contract.happy_fields
            ),
            "r0_happy_fields_present_modern": all(
                f in modern_out for f in case.contract.happy_fields
            ),
            "fork_only_response_fields": sorted(set(fork_out) - set(modern_out)),
            "modern_only_response_fields": sorted(set(modern_out) - set(fork_out)),
        }
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="r3-evidence-") as tmp:
        root = Path(tmp)
        report = {
            "corpus": [
                {
                    "case_id": c.case_id,
                    "intent": c.intent,
                    "current_fork_tool": c.current_fork_tool,
                    "modern_tool": c.modern_tool,
                    "modern_gap": c.modern_gap,
                }
                for c in CORPUS
            ],
            "current_fork": measure_current_fork(root),
            "modern": measure_modern(root),
            "wire_parity": measure_wire_parity(root),
        }

    blob = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(blob + "\n", encoding="utf-8")
    print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
