"""Count the PowerUnits footprint on both sides of the migration decision.

Read-only file/symbol counting. Emits JSON.

    python scripts/r3_shadow_comparison/measure_migration_cost.py [--out PATH]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Generic Hermes files that a fork should ideally not have to touch at all.
SHARED_CORE = (
    "model_tools.py",
    "toolsets.py",
    "toolset_distributions.py",
    "run_agent.py",
    "cli.py",
    "hermes_constants.py",
    "hermes_state.py",
    "trajectory_compressor.py",
    "mcp_serve.py",
    "hermes_cli/tools_config.py",
    "hermes_cli/commands.py",
    "hermes_cli/banner.py",
    "hermes_cli/web_server.py",
    "hermes_cli/setup.py",
    "gateway/run.py",
    "gateway/config.py",
    "gateway/slash_commands.py",
    "tools/registry.py",
)
HTTP_WRAPPER_MARKERS = (
    "POWERUNITS_INTERNAL_EXECUTE_BASE_URL",
    "powerunits_execute_base_url_v1",
)
POWERUNITS = re.compile("powerunits", re.IGNORECASE)


def _lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _top_level_symbols(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    ]


def _powerunits_line_count(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if POWERUNITS.search(line)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report: dict[str, object] = {}

    # --- fork-owned top-level modules -------------------------------------
    top_level = sorted(REPO_ROOT.glob("powerunits_*.py"))
    report["fork_top_level_modules"] = {
        "count": len(top_level),
        "lines": sum(_lines(p) for p in top_level),
        "files": [
            {"path": p.name, "lines": _lines(p), "symbols": len(_top_level_symbols(p))}
            for p in top_level
        ],
    }

    # --- tools/ wrappers ---------------------------------------------------
    tool_files = sorted((REPO_ROOT / "tools").glob("powerunits_*.py"))
    http_wrappers: list[Path] = []
    other_tools: list[Path] = []
    for path in tool_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        (http_wrappers if any(m in text for m in HTTP_WRAPPER_MARKERS) else other_tools).append(path)

    # R2 counted a narrower set — `*tool*.py` that import httpx *and* reach the
    # execute Base URL. Both definitions are reported so the two slices agree.
    r2_definition = [
        p
        for p in tool_files
        if "tool" in p.name
        and "import httpx" in p.read_text(encoding="utf-8", errors="replace")
        and any(m in p.read_text(encoding="utf-8", errors="replace") for m in HTTP_WRAPPER_MARKERS)
    ]

    report["fork_tool_files"] = {
        "total": len(tool_files),
        "total_lines": sum(_lines(p) for p in tool_files),
        "tool_modules": len([p for p in tool_files if "tool" in p.name]),
        "support_modules": len([p for p in tool_files if "tool" not in p.name]),
        "r2_wrapper_definition": {
            "count": len(r2_definition),
            "lines": sum(_lines(p) for p in r2_definition),
        },
        "http_wrappers": {
            "count": len(http_wrappers),
            "lines": sum(_lines(p) for p in http_wrappers),
            "files": [p.name for p in http_wrappers],
        },
        "non_http": {
            "count": len(other_tools),
            "lines": sum(_lines(p) for p in other_tools),
            "files": [p.name for p in other_tools],
        },
    }

    # --- domain knowledge inside generic shared core -----------------------
    core_rows = []
    for rel in SHARED_CORE:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        hits = _powerunits_line_count(path)
        if hits:
            core_rows.append({"path": rel, "powerunits_lines": hits, "file_lines": _lines(path)})
    report["shared_core_domain_touchpoints"] = {
        "files": len(core_rows),
        "powerunits_lines": sum(int(r["powerunits_lines"]) for r in core_rows),
        "rows": sorted(core_rows, key=lambda r: r["powerunits_lines"], reverse=True),
    }

    # --- the modern side ---------------------------------------------------
    plugin_files = sorted((REPO_ROOT / "standalone" / "powerunits").iterdir())
    report["modern_plugin"] = {
        "files": len(plugin_files),
        "lines": sum(_lines(p) for p in plugin_files if p.is_file()),
        "rows": [
            {"path": p.name, "lines": _lines(p), "symbols": len(_top_level_symbols(p))}
            for p in plugin_files
            if p.is_file()
        ],
    }
    cap_source = (REPO_ROOT / "model_tools.py").read_text(encoding="utf-8")
    report["modern_shared_core_patch"] = {
        "files": 1,
        "file": "model_tools.py",
        "symbols": ["_read_final_toolset_cap", "_resolve_final_allowed_tools"],
        "domain_specific": False,
        "added_lines_measured_by_git": 96,
        "helpers_present": all(
            name in cap_source
            for name in ("_read_final_toolset_cap", "_resolve_final_allowed_tools")
        ),
    }

    # --- toolset registration in shared core -------------------------------
    toolsets_src = (REPO_ROOT / "toolsets.py").read_text(encoding="utf-8", errors="replace")
    toolset_names = sorted(set(re.findall(r'"(powerunits[^"]*)":', toolsets_src)))
    report["shared_core_toolset_registration"] = {
        "file": "toolsets.py",
        "powerunits_toolsets": len(toolset_names),
        "names": toolset_names,
    }

    # --- coupling: who depends on the shared support modules ---------------
    all_py = [
        p
        for p in REPO_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts and ".venv" not in p.parts
    ]
    coupling = {}
    for module in ("powerunits_execute_base_url_v1", "powerunits_bounded_family_gates"):
        pattern = re.compile(rf"(?:from tools\.{module} import|import tools\.{module})")
        coupling[module] = sum(
            1
            for p in all_py
            if p.name != f"{module}.py"
            and pattern.search(p.read_text(encoding="utf-8", errors="replace"))
        )
    report["support_module_importers"] = coupling

    # --- test burden -------------------------------------------------------
    # R3's own harness is separated out: counting it as migration burden would
    # bill the measurement for the thing it measures.
    buckets: dict[str, dict[str, int]] = {}
    for path in (REPO_ROOT / "tests").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if "powerunits" not in rel.lower() and not POWERUNITS.search(text):
            continue
        bucket = rel.rsplit("/", 1)[0]
        row = buckets.setdefault(bucket, {"files": 0, "lines": 0})
        row["files"] += 1
        row["lines"] += len(text.splitlines())

    r3_own = buckets.get("tests/r3_shadow_comparison", {"files": 0, "lines": 0})
    total_files = sum(r["files"] for r in buckets.values())
    total_lines = sum(r["lines"] for r in buckets.values())
    report["test_burden"] = {
        "files": total_files,
        "lines": total_lines,
        "excluding_r3_harness": {
            "files": total_files - r3_own["files"],
            "lines": total_lines - r3_own["lines"],
        },
        "r3_harness": r3_own,
        "by_directory": dict(sorted(buckets.items())),
    }

    blob = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(blob + "\n", encoding="utf-8")
    sys.stdout.write(blob + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
