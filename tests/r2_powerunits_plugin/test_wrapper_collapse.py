"""Measure wrapper-collapse potential. Do not delete old wrappers in R2."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
PLUGIN_DIR = REPO_ROOT / "standalone" / "powerunits"


def _powerunits_tool_files() -> list[Path]:
    return sorted(TOOLS_DIR.glob("powerunits_*tool*.py"))


def _http_wrapper_files() -> list[Path]:
    hits = []
    for path in _powerunits_tool_files():
        text = path.read_text(encoding="utf-8")
        if "POWERUNITS_INTERNAL_EXECUTE_BASE_URL" in text and "httpx" in text:
            hits.append(path)
    return hits


def test_wrapper_collapse_quantified() -> None:
    wrappers = _http_wrapper_files()
    all_tool_files = _powerunits_tool_files()
    plugin_clients = list(PLUGIN_DIR.glob("client.py"))
    plugin_tool_files = list(PLUGIN_DIR.glob("tools.py"))

    current_wrapper_files = len(wrappers)
    # Every bounded HTTP wrapper can move onto this one-client pattern.
    estimated_replaceable = current_wrapper_files
    # Shared core files that exist only to serve those wrappers (resolver + gates)
    # become unused once the complete bounded surface lives in the plugin.
    shared_support = [
        TOOLS_DIR / "powerunits_execute_base_url_v1.py",
        TOOLS_DIR / "powerunits_bounded_family_gates.py",
    ]
    existing_support = [path for path in shared_support if path.exists()]
    estimated_core_reduction = current_wrapper_files + len(existing_support)

    report = {
        "CURRENT_WRAPPER_FILES": current_wrapper_files,
        "CURRENT_POWERUNITS_TOOL_FILES": len(all_tool_files),
        "R2_PLUGIN_SHARED_CLIENTS": len(plugin_clients),
        "R2_PLUGIN_TOOL_FILES": len(plugin_tool_files),
        "ESTIMATED_WRAPPERS_REPLACEABLE": estimated_replaceable,
        "ESTIMATED_SHARED_CORE_POWERUNITS_REDUCTION": estimated_core_reduction,
    }

    assert report["R2_PLUGIN_SHARED_CLIENTS"] == 1
    assert report["R2_PLUGIN_TOOL_FILES"] == 1
    assert report["CURRENT_WRAPPER_FILES"] >= 20
    assert report["ESTIMATED_WRAPPERS_REPLACEABLE"] == report["CURRENT_WRAPPER_FILES"]
    assert report["ESTIMATED_SHARED_CORE_POWERUNITS_REDUCTION"] > report["CURRENT_WRAPPER_FILES"]
    # Measurement only — old wrappers must still exist.
    assert (TOOLS_DIR / "powerunits_bounded_coverage_snapshot_tool.py").exists()
