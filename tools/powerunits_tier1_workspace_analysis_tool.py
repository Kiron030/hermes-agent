#!/usr/bin/env python3
"""
Phase 2A — Tier-1 workspace analysis overlay (read-heavy, bounded).

Active only when ``HERMES_POWERUNITS_CAPABILITY_TIER >= 1`` (see canonical roadmap
``docs/powerunits_hermes_progressive_posture_v1.md``). Same workspace root and
extension allowlist as ``powerunits_workspace``; no Repo B access, no curator.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.powerunits_workspace_tool import (
    _ALLOWED_EXTS,
    _ALLOWED_SUBDIRS,
    _ensure_workspace_dirs,
)
from tools.registry import registry

_MAX_REL_DEPTH = 8
_MAX_TOTAL_FILES_FULL = 6000
_CAUTION_SUBDIR_FILES = 1800
_CAUTION_SUBDIR_BYTES = 60 * 1024 * 1024

_MAX_SEARCH_QUERY_LEN = 220
_MAX_SEARCH_HITS_DEFAULT = 40
_MAX_SEARCH_HITS_CAP = 80
_MAX_SEARCH_FILE_BYTES = 2 * 1024 * 1024
_MAX_FILES_SCANNED_SEARCH = 480


def check_powerunits_tier1_analysis_overlay() -> bool:
    from powerunits_capability_tier import read_powerunits_capability_tier

    return read_powerunits_capability_tier() >= 1


def _validate_optional_subdir(subdir: str | None) -> str | None:
    if subdir is None or not str(subdir).strip():
        return None
    s = str(subdir).strip().strip("/\\")
    for allowed in _ALLOWED_SUBDIRS:
        if allowed.lower() == s.lower():
            return allowed
    raise ValueError(f"subdir must be one of: {', '.join(_ALLOWED_SUBDIRS)}")


def _iter_workspace_text_files(
    root: Path, subdirs_to_walk: tuple[str, ...]
) -> tuple[list[Path], list[str]]:
    """Return (files, caution flags). Skips symlinks; enforces depth and extension."""

    caution_notes: list[str] = []
    files: list[Path] = []
    deep_skip_total = 0

    for sd in subdirs_to_walk:
        base = (root / sd).resolve()
        base.relative_to(root)
        if not base.is_dir():
            continue
        deep_here = 0
        for raw in sorted(base.rglob("*")):
            if not raw.is_file():
                continue
            if raw.is_symlink():
                continue
            if not raw.name.lower().endswith(_ALLOWED_EXTS):
                continue
            resolved = raw.resolve()
            resolved.relative_to(root)
            depth = len(raw.relative_to(base).parts)
            if depth > _MAX_REL_DEPTH:
                deep_here += 1
                continue
            files.append(raw)
        if deep_here:
            deep_skip_total += deep_here
            caution_notes.append(f"subdir_{sd}_skipped_deep_files:{deep_here}")

    if deep_skip_total:
        caution_notes.append(f"skipped_paths_over_depth_cap_total:{deep_skip_total}")

    return files, caution_notes


def summarize_powerunits_workspace_full(**_: Any) -> str:
    """Read-only totals and per-subdirectory file/byte counts across hermes_workspace."""

    from tools.registry import tool_error

    if not check_powerunits_tier1_analysis_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=1 required for Phase 2A workspace overlay",
            error_code="tier_gate",
        )

    try:
        root = _ensure_workspace_dirs().resolve()
        files, walk_cautions = _iter_workspace_text_files(root, _ALLOWED_SUBDIRS)

        if len(files) > _MAX_TOTAL_FILES_FULL:
            return tool_error(
                f"workspace file count {len(files)} exceeds scan cap {_MAX_TOTAL_FILES_FULL}",
                error_code="workspace_full_scan_cap",
            )

        per: dict[str, dict[str, Any]] = {}
        for sd in _ALLOWED_SUBDIRS:
            per[sd] = {"files": 0, "bytes": 0}

        caution = list(walk_cautions)

        for fp in files:
            rel = fp.relative_to(root)
            top = rel.parts[0]
            if top not in per:
                continue
            try:
                sz = int(fp.stat().st_size)
            except OSError:
                caution.append(f"stat_failed:{fp.as_posix()}")
                continue
            per[top]["files"] += 1
            per[top]["bytes"] += sz

        grand_files = sum(p["files"] for p in per.values())
        grand_bytes = sum(int(p["bytes"]) for p in per.values())

        for sd, pv in per.items():
            if pv["files"] >= _CAUTION_SUBDIR_FILES:
                caution.append(f"high_file_count:{sd}:{pv['files']}")
            if int(pv["bytes"]) >= _CAUTION_SUBDIR_BYTES:
                caution.append(f"high_bytes:{sd}:{pv['bytes']}")

        largest = []
        try:
            ranked = sorted(files, key=lambda p: p.stat().st_size, reverse=True)[:16]
            for fp in ranked:
                largest.append(
                    {
                        "path": fp.relative_to(root).as_posix(),
                        "bytes": int(fp.stat().st_size),
                    }
                )
        except OSError:
            caution.append("largest_files_partial")

        return json.dumps(
            {
                "read_only": True,
                "phase": "2A",
                "overlay": "tier1_workspace_analysis",
                "tier_gate": "HERMES_POWERUNITS_CAPABILITY_TIER>=1",
                "workspace_root_relative": "hermes_workspace",
                "per_subdir": per,
                "total_files": grand_files,
                "total_bytes": grand_bytes,
                "largest_files": largest,
                "caution_flags": sorted(set(caution)),
                "doc_hint": "docs/powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_workspace_layout")
    except Exception as exc:
        return tool_error(f"workspace full summary failed: {exc}", error_code="workspace_full_failed")


def search_powerunits_workspace_text(
    query: str,
    subdir: str | None = None,
    max_hits: int | None = None,
    **_: Any,
) -> str:
    """Bounded case-insensitive substring search across workspace text files."""

    from tools.registry import tool_error

    if not check_powerunits_tier1_analysis_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=1 required for Phase 2A workspace overlay",
            error_code="tier_gate",
        )

    try:
        q = str(query or "").strip()
        if not q:
            return tool_error("query is required", error_code="missing_query")
        if "\x00" in q or "\r" in q:
            return tool_error("query contains disallowed control characters", error_code="bad_query")
        if len(q) > _MAX_SEARCH_QUERY_LEN:
            return tool_error(
                f"query exceeds max length {_MAX_SEARCH_QUERY_LEN}",
                error_code="query_too_long",
            )

        needle = q.casefold()

        target_subdirs: tuple[str, ...]
        validated = _validate_optional_subdir(subdir)
        if validated is None:
            target_subdirs = _ALLOWED_SUBDIRS
        else:
            target_subdirs = (validated,)

        hits_cap = int(max_hits) if max_hits is not None else _MAX_SEARCH_HITS_DEFAULT
        hits_cap = max(1, min(hits_cap, _MAX_SEARCH_HITS_CAP))

        root = _ensure_workspace_dirs().resolve()
        files, walk_cautions = _iter_workspace_text_files(root, target_subdirs)

        caution = list(walk_cautions)
        if len(files) > _MAX_FILES_SCANNED_SEARCH:
            files = files[:_MAX_FILES_SCANNED_SEARCH]
            caution.append("truncated_file_list_at_search_cap")

        matches: list[dict[str, Any]] = []
        files_scanned = 0
        skipped_large = 0

        for fp in files:
            if len(matches) >= hits_cap:
                caution.append("hit_cap_reached")
                break
            try:
                sz = int(fp.stat().st_size)
            except OSError:
                continue
            if sz > _MAX_SEARCH_FILE_BYTES:
                skipped_large += 1
                continue

            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            files_scanned += 1
            hay = text.casefold()
            pos = hay.find(needle)
            if pos < 0:
                continue

            line_start = hay.rfind("\n", 0, pos) + 1
            line_end = hay.find("\n", pos)
            line_end = len(hay) if line_end < 0 else line_end
            line = text[line_start:line_end]
            if len(line) > 400:
                line = line[:397] + "..."

            matches.append(
                {
                    "path": fp.relative_to(root).as_posix(),
                    "line_preview": line,
                    "match_index_in_file": pos - line_start,
                }
            )

        if skipped_large:
            caution.append(f"skipped_oversized_files:{skipped_large}")

        return json.dumps(
            {
                "read_only": True,
                "phase": "2A",
                "overlay": "tier1_workspace_analysis",
                "tier_gate": "HERMES_POWERUNITS_CAPABILITY_TIER>=1",
                "query_display": q,
                "subdir_filter": validated,
                "hit_cap": hits_cap,
                "matches": matches,
                "match_count": len(matches),
                "files_considered": len(files),
                "files_scanned": files_scanned,
                "caution_flags": sorted(set(caution)),
                "doc_hint": "docs/powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_subdir")
    except Exception as exc:
        return tool_error(f"workspace search failed: {exc}", error_code="workspace_search_failed")


FULL_SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_workspace_full",
    "description": (
        "Phase 2A (tier>=1): read-only summary of bounded hermes_workspace — per-subdir file/byte counts, "
        "largest paths, caution flags. No writes. See docs/powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "search_powerunits_workspace_text",
    "description": (
        "Phase 2A (tier>=1): bounded case-insensitive substring search across .md/.txt/.csv under "
        "hermes_workspace analysis|notes|drafts|exports (optional subdir filter)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Non-empty substring; max ~220 chars."},
            "subdir": {
                "type": "string",
                "description": "Optional: narrow to analysis|notes|drafts|exports",
            },
            "max_hits": {"type": "integer", "description": f"Default {_MAX_SEARCH_HITS_DEFAULT}, cap {_MAX_SEARCH_HITS_CAP}"},
        },
        "required": ["query"],
    },
}

registry.register(
    name="summarize_powerunits_workspace_full",
    toolset="powerunits_tier1_analysis",
    schema=FULL_SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_workspace_full(**kw),
    check_fn=check_powerunits_tier1_analysis_overlay,
    emoji="📊",
)

registry.register(
    name="search_powerunits_workspace_text",
    toolset="powerunits_tier1_analysis",
    schema=SEARCH_SCHEMA,
    handler=lambda args, **kw: search_powerunits_workspace_text(
        query=str(args.get("query", "")),
        subdir=args.get("subdir"),
        max_hits=args.get("max_hits"),
        **kw,
    ),
    check_fn=check_powerunits_tier1_analysis_overlay,
    emoji="🔎",
)
