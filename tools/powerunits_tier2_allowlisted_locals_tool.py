#!/usr/bin/env python3
"""
Phase 2B — Tier-2 allowlisted local read overlay (read-heavy, bounded).

Requires ``HERMES_POWERUNITS_CAPABILITY_TIER >= 2`` (see canonical roadmap
``docs/powerunits_hermes_progressive_posture_v1.md``).

Read scope (all under ``$HERMES_HOME``):
- ``hermes_workspace`` — same allowlisted subdirs as ``powerunits_workspace`` tools.
- ``powerunits_local_reference`` — optional operator tree for reference drops (never created by Hermes).

Extensions: ``.md``, ``.txt``, ``.csv``, ``.json``, ``.yaml``, ``.yml``.

No Repo B, no curator, no shell, no arbitrary path escape.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tools.powerunits_workspace_tool import (
    _ALLOWED_SUBDIRS,
    _ensure_workspace_dirs,
)
from tools.registry import registry

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}$")

_TIER2_EXTENSIONS = (".md", ".txt", ".csv", ".json", ".yaml", ".yml")

_REFERENCE_ROOT_SEGMENT = "powerunits_local_reference"

_MAX_REL_DEPTH_WORKSPACE = 8
_MAX_REL_DEPTH_REFERENCE = 10

_MAX_TOTAL_FILES_SUMMARY = 12_000
_CAUTION_FILES_PER_SURFACE = 2_600
_CAUTION_BYTES_PER_SURFACE = 75 * 1024 * 1024

_MAX_SEARCH_QUERY_LEN = 220
_MAX_SEARCH_HITS_DEFAULT = 48
_MAX_SEARCH_HITS_CAP = 96
_MAX_SEARCH_FILE_BYTES = 4 * 1024 * 1024
_MAX_FILES_SCANNED_SEARCH = 900

_DEFAULT_READ_CHARS = 20_000
_ABS_MAX_READ_CHARS = 48_000
_ABS_MIN_READ_CHARS = 2_000


def check_powerunits_tier2_allowlisted_read_overlay() -> bool:
    from powerunits_capability_tier import read_powerunits_capability_tier

    return read_powerunits_capability_tier() >= 2


def _hermes_home() -> Path:
    return Path(os.getenv("HERMES_HOME", "/opt/data")).resolve()


def _workspace_root_extended() -> Path:
    return _ensure_workspace_dirs().resolve()


def _reference_root() -> tuple[Path, bool]:
    """Return (resolved reference root path, exists)."""
    home = _hermes_home()
    raw = home / _REFERENCE_ROOT_SEGMENT
    resolved = raw.resolve()
    resolved.relative_to(home)
    return resolved, resolved.is_dir()


def _validate_optional_subdir(subdir: str | None) -> str | None:
    if subdir is None or not str(subdir).strip():
        return None
    s = str(subdir).strip().strip("/\\")
    for allowed in _ALLOWED_SUBDIRS:
        if allowed.lower() == s.lower():
            return allowed
    raise ValueError(f"subdir must be one of: {', '.join(_ALLOWED_SUBDIRS)}")


def _validate_workspace_path_tier2(path: str) -> tuple[str, str]:
    raw = str(path or "").strip().replace("\\", "/").strip("/")
    if not raw:
        raise ValueError("path is required")
    p = Path(raw)
    parts = list(p.parts)
    if any(part == ".." for part in parts):
        raise ValueError("path escape is not allowed")
    if p.is_absolute():
        raise ValueError("absolute paths are not allowed")
    if len(parts) < 2:
        raise ValueError("path must include subdir/file (e.g. notes/foo.json)")
    subdir = parts[0]
    if subdir not in _ALLOWED_SUBDIRS:
        raise ValueError(f"path must start with one of: {', '.join(_ALLOWED_SUBDIRS)}")
    fname = parts[-1]
    if not fname.lower().endswith(_TIER2_EXTENSIONS):
        raise ValueError(f"only {', '.join(_TIER2_EXTENSIONS)} files are allowed")
    return subdir, "/".join(parts[1:])


def _validate_reference_rel_path(path: str) -> str:
    raw = str(path or "").strip().replace("\\", "/").strip("/")
    if not raw:
        raise ValueError("path is required")
    p = Path(raw)
    if p.is_absolute():
        raise ValueError("absolute paths are not allowed")
    parts = list(p.parts)
    if any(part == ".." for part in parts):
        raise ValueError("path escape is not allowed")
    if len(parts) > 24:
        raise ValueError("path too deep")
    for part in parts:
        if not _NAME_RE.match(part):
            raise ValueError(f"invalid path segment: {part!r}")
    if not parts[-1].lower().endswith(_TIER2_EXTENSIONS):
        raise ValueError(f"reference path must end with one of {_TIER2_EXTENSIONS}")
    return "/".join(parts)


def _iter_workspace_tier2_files(
    root: Path, subdirs_to_walk: tuple[str, ...]
) -> tuple[list[Path], list[str]]:
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
            if not raw.is_file() or raw.is_symlink():
                continue
            if not raw.name.lower().endswith(_TIER2_EXTENSIONS):
                continue
            resolved = raw.resolve()
            resolved.relative_to(root)
            depth = len(raw.relative_to(base).parts)
            if depth > _MAX_REL_DEPTH_WORKSPACE:
                deep_here += 1
                continue
            files.append(raw)
        if deep_here:
            deep_skip_total += deep_here

    if deep_skip_total:
        caution_notes.append(f"workspace_skipped_deep_files:{deep_skip_total}")

    return files, caution_notes


def _iter_reference_files(root: Path) -> tuple[list[Path], list[str]]:
    caution_notes: list[str] = []
    files: list[Path] = []
    if not root.is_dir():
        return files, caution_notes

    deep_skip_total = 0

    try:
        for raw in sorted(root.rglob("*")):
            if not raw.is_file() or raw.is_symlink():
                continue
            if not raw.name.lower().endswith(_TIER2_EXTENSIONS):
                continue
            try:
                resolved = raw.resolve()
                resolved.relative_to(root)
            except ValueError:
                continue
            depth = len(raw.relative_to(root).parts)
            if depth > _MAX_REL_DEPTH_REFERENCE:
                deep_skip_total += 1
                continue
            files.append(raw)
    except OSError:
        caution_notes.append("reference_tree_walk_partial")

    if deep_skip_total:
        caution_notes.append(f"reference_skipped_deep_files:{deep_skip_total}")

    return files, caution_notes


def manifest_powerunits_tier2_allowlisted_read_scope(**_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier2_allowlisted_read_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=2 required for Phase 2B allowlisted read overlay",
            error_code="tier_gate",
        )
    _, ref_present = _reference_root()
    return json.dumps(
        {
            "read_only": True,
            "phase": "2B",
            "overlay": "tier2_allowlisted_locals",
            "tier_gate": "HERMES_POWERUNITS_CAPABILITY_TIER>=2",
            "roots_relative_to_HERMES_HOME": [
                {
                    "key": "hermes_workspace",
                    "subdirs": list(_ALLOWED_SUBDIRS),
                    "max_rel_depth_per_subdir": _MAX_REL_DEPTH_WORKSPACE,
                },
                {
                    "key": _REFERENCE_ROOT_SEGMENT,
                    "present": ref_present,
                    "max_rel_depth": _MAX_REL_DEPTH_REFERENCE,
                    "note": "Optional operator-managed directory; Hermes does not mkdir it.",
                },
            ],
            "extensions_allowed": list(_TIER2_EXTENSIONS),
            "tools_in_toolset": [
                "manifest_powerunits_tier2_allowlisted_read_scope",
                "summarize_powerunits_allowlisted_locals",
                "search_powerunits_allowlisted_local_text",
                "read_powerunits_allowlisted_workspace_extended_file",
                "read_powerunits_local_reference_file",
            ],
            "doc_hint": "docs/powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def summarize_powerunits_allowlisted_locals(
    subdir: str | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier2_allowlisted_read_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=2 required for Phase 2B allowlisted read overlay",
            error_code="tier_gate",
        )
    try:
        validated = _validate_optional_subdir(subdir)
        target_subdirs: tuple[str, ...] = (
            _ALLOWED_SUBDIRS if validated is None else (validated,)
        )

        caution: list[str] = []

        ws_root = _workspace_root_extended()
        ws_files, ws_caution = _iter_workspace_tier2_files(ws_root, target_subdirs)
        caution.extend(ws_caution)

        ref_root, ref_exists = _reference_root()
        ref_files: list[Path] = []
        if validated is None:
            ref_files, ref_caution = _iter_reference_files(ref_root)
            caution.extend(ref_caution)
        else:
            caution.append("reference_root_skipped:subdir_filter_workspace_only")

        total_count = len(ws_files) + len(ref_files)
        if total_count > _MAX_TOTAL_FILES_SUMMARY:
            return tool_error(
                f"aggregate file count {total_count} exceeds scan cap {_MAX_TOTAL_FILES_SUMMARY}",
                error_code="tier2_locals_full_scan_cap",
            )

        def ext_hist(paths: list[Path]) -> dict[str, int]:
            hist: dict[str, int] = {}
            for fp in paths:
                suf = ""
                lower = fp.name.lower()
                for e in _TIER2_EXTENSIONS:
                    if lower.endswith(e):
                        suf = e
                        break
                hist[suf or "unknown"] = hist.get(suf or "unknown", 0) + 1
            return hist

        def nbytes(paths: list[Path]) -> int:
            total = 0
            for fp in paths:
                try:
                    total += int(fp.stat().st_size)
                except OSError:
                    caution.append(f"stat_failed:{fp.as_posix()}")
            return total

        ws_bytes = nbytes(ws_files)
        ref_bytes = nbytes(ref_files)

        ws_per_sd: dict[str, dict[str, Any]] = {sd: {"files": 0, "bytes": 0} for sd in target_subdirs}
        for fp in ws_files:
            top = fp.relative_to(ws_root).parts[0]
            if top in ws_per_sd:
                ws_per_sd[top]["files"] += 1
                try:
                    ws_per_sd[top]["bytes"] += int(fp.stat().st_size)
                except OSError:
                    pass

        for label, count, bts in (
            ("hermes_workspace", len(ws_files), ws_bytes),
            (_REFERENCE_ROOT_SEGMENT, len(ref_files), ref_bytes),
        ):
            if count >= _CAUTION_FILES_PER_SURFACE:
                caution.append(f"high_file_count:{label}:{count}")
            if bts >= _CAUTION_BYTES_PER_SURFACE:
                caution.append(f"high_bytes:{label}:{bts}")

        largest: list[dict[str, Any]] = []
        all_for_rank = [(fp, "hermes_workspace") for fp in ws_files] + [
            (fp, _REFERENCE_ROOT_SEGMENT) for fp in ref_files
        ]
        try:
            ranked = sorted(all_for_rank, key=lambda t: t[0].stat().st_size, reverse=True)[:20]
            for fp, surface in ranked:
                if surface == "hermes_workspace":
                    rel = f"hermes_workspace/{fp.relative_to(ws_root).as_posix()}"
                else:
                    rel = f"{_REFERENCE_ROOT_SEGMENT}/{fp.relative_to(ref_root).as_posix()}"
                largest.append({"path": rel, "bytes": int(fp.stat().st_size)})
        except OSError:
            caution.append("largest_files_partial")

        return json.dumps(
            {
                "read_only": True,
                "phase": "2B",
                "overlay": "tier2_allowlisted_locals",
                "tier_gate": "HERMES_POWERUNITS_CAPABILITY_TIER>=2",
                "subdir_filter": validated,
                "hermes_workspace": {
                    "root_relative": "hermes_workspace",
                    "files": len(ws_files),
                    "bytes": ws_bytes,
                    "per_subdir": ws_per_sd,
                    "extension_counts": ext_hist(ws_files),
                },
                "powerunits_local_reference": {
                    "root_relative": _REFERENCE_ROOT_SEGMENT,
                    "present": ref_exists,
                    "files": len(ref_files),
                    "bytes": ref_bytes,
                    "extension_counts": ext_hist(ref_files),
                },
                "largest_files": largest,
                "caution_flags": sorted(set(caution)),
                "doc_hint": "docs/powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_subdir")
    except Exception as exc:
        return tool_error(f"summarize allowlisted locals failed: {exc}", error_code="tier2_summary_failed")


def search_powerunits_allowlisted_local_text(
    query: str,
    root_scope: str | None = None,
    subdir: str | None = None,
    max_hits: int | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier2_allowlisted_read_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=2 required for Phase 2B allowlisted read overlay",
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

        scope = (root_scope or "all").strip().lower()
        if scope not in {"all", "hermes_workspace", _REFERENCE_ROOT_SEGMENT}:
            return tool_error(
                "root_scope must be 'all', 'hermes_workspace', or 'powerunits_local_reference'",
                error_code="invalid_root_scope",
            )

        validated = _validate_optional_subdir(subdir)
        target_subdirs: tuple[str, ...] = (
            _ALLOWED_SUBDIRS if validated is None else (validated,)
        )

        ws_root = _workspace_root_extended()
        ref_root, _ = _reference_root()

        files: list[tuple[Path, str]] = []
        caution: list[str] = []

        if scope in {"all", "hermes_workspace"}:
            ws_files, wsc = _iter_workspace_tier2_files(ws_root, target_subdirs)
            caution.extend(wsc)
            files.extend((p, "hermes_workspace") for p in ws_files)
        if scope in {"all", _REFERENCE_ROOT_SEGMENT}:
            if validated is not None:
                caution.append("reference_skipped_under_subdir_filter")
            else:
                rf, rc = _iter_reference_files(ref_root)
                caution.extend(rc)
                files.extend((p, _REFERENCE_ROOT_SEGMENT) for p in rf)

        needle = q.casefold()
        hits_cap = int(max_hits) if max_hits is not None else _MAX_SEARCH_HITS_DEFAULT
        hits_cap = max(1, min(hits_cap, _MAX_SEARCH_HITS_CAP))

        if len(files) > _MAX_FILES_SCANNED_SEARCH:
            files = files[: _MAX_FILES_SCANNED_SEARCH]
            caution.append("truncated_file_list_at_search_cap")

        matches: list[dict[str, Any]] = []
        files_scanned = 0
        skipped_large = 0

        for fp, surface in files:
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

            if surface == "hermes_workspace":
                display = f"hermes_workspace/{fp.relative_to(ws_root).as_posix()}"
            else:
                display = f"{_REFERENCE_ROOT_SEGMENT}/{fp.relative_to(ref_root).as_posix()}"

            matches.append(
                {
                    "path": display,
                    "line_preview": line,
                    "match_index_in_file": pos - line_start,
                }
            )

        if skipped_large:
            caution.append(f"skipped_oversized_files:{skipped_large}")

        return json.dumps(
            {
                "read_only": True,
                "phase": "2B",
                "overlay": "tier2_allowlisted_locals",
                "tier_gate": "HERMES_POWERUNITS_CAPABILITY_TIER>=2",
                "query_display": q,
                "root_scope": scope,
                "subdir_filter": validated,
                "hit_cap": hits_cap,
                "matches": matches,
                "match_count": len(matches),
                "files_scanned": files_scanned,
                "caution_flags": sorted(set(caution)),
                "doc_hint": "docs/powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_subdir")
    except Exception as exc:
        return tool_error(f"allowlisted locals search failed: {exc}", error_code="tier2_search_failed")


def _safe_int(v: Any, default: int) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def read_powerunits_allowlisted_workspace_extended_file(
    path: str,
    max_output_chars: int | None = None,
    **_: Any,
) -> str:
    """Read `.json`/`.yaml`/`.md`/etc. under bounded workspace dirs (tier>=2 only)."""

    from tools.registry import tool_error

    if not check_powerunits_tier2_allowlisted_read_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=2 required for Phase 2B allowlisted read overlay",
            error_code="tier_gate",
        )
    try:
        subdir, tail = _validate_workspace_path_tier2(path)
        root = _workspace_root_extended()
        file_path = (root / subdir / tail).resolve()
        file_path.relative_to(root)
        if not file_path.is_file():
            return tool_error("workspace file not found", error_code="not_found")
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lim = _safe_int(max_output_chars, _DEFAULT_READ_CHARS)
        lim = max(_ABS_MIN_READ_CHARS, min(lim, _ABS_MAX_READ_CHARS))
        truncated = len(text) > lim
        if truncated:
            text = text[:lim] + "\n\n[truncated to max_output_chars]"
        return json.dumps(
            {
                "read_only": True,
                "phase": "2B",
                "path": file_path.relative_to(root).as_posix(),
                "chars_returned": len(text),
                "truncated": truncated,
                "content": text,
                "doc_hint": "docs/powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")
    except Exception as exc:
        return tool_error(f"workspace extended read failed: {exc}", error_code="tier2_read_failed")


def read_powerunits_local_reference_file(
    path: str,
    max_output_chars: int | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier2_allowlisted_read_overlay():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=2 required for Phase 2B allowlisted read overlay",
            error_code="tier_gate",
        )
    try:
        rel = _validate_reference_rel_path(path)
        ref_root, exists = _reference_root()
        if not exists:
            return tool_error(
                "powerunits_local_reference directory does not exist",
                error_code="reference_root_missing",
            )
        file_path = (ref_root / rel).resolve()
        file_path.relative_to(ref_root)
        if not file_path.is_file() or file_path.is_symlink():
            return tool_error("reference file not found", error_code="not_found")
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lim = _safe_int(max_output_chars, _DEFAULT_READ_CHARS)
        lim = max(_ABS_MIN_READ_CHARS, min(lim, _ABS_MAX_READ_CHARS))
        truncated = len(text) > lim
        if truncated:
            text = text[:lim] + "\n\n[truncated to max_output_chars]"
        return json.dumps(
            {
                "read_only": True,
                "phase": "2B",
                "path": f"{_REFERENCE_ROOT_SEGMENT}/{rel}",
                "chars_returned": len(text),
                "truncated": truncated,
                "content": text,
                "doc_hint": "docs/powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")
    except Exception as exc:
        return tool_error(f"reference read failed: {exc}", error_code="tier2_read_failed")


MANIFEST_SCHEMA = {
    "name": "manifest_powerunits_tier2_allowlisted_read_scope",
    "description": (
        "Phase 2B (tier>=2): static manifest of allowlisted read roots, extensions, and tool names. Read-only."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_allowlisted_locals",
    "description": (
        "Phase 2B (tier>=2): read-only inventory across hermes_workspace (optional subdir filter) and "
        "optional powerunits_local_reference — counts, bytes, extension histogram, largest paths."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subdir": {
                "type": "string",
                "description": "Optional: narrow workspace leg to analysis|notes|drafts|exports",
            },
        },
        "required": [],
    },
}

SEARCH_SCHEMA = {
    "name": "search_powerunits_allowlisted_local_text",
    "description": (
        "Phase 2B (tier>=2): bounded substring search across tier-2 text extensions; "
        "root_scope all|hermes_workspace|powerunits_local_reference."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Non-empty substring; max ~220 chars."},
            "root_scope": {
                "type": "string",
                "description": "Default 'all'; or one surface only.",
            },
            "subdir": {
                "type": "string",
                "description": "Optional workspace subdir filter (analysis|notes|drafts|exports)",
            },
            "max_hits": {"type": "integer", "description": f"Default {_MAX_SEARCH_HITS_DEFAULT}, cap {_MAX_SEARCH_HITS_CAP}"},
        },
        "required": ["query"],
    },
}

READ_WS_EXT_SCHEMA = {
    "name": "read_powerunits_allowlisted_workspace_extended_file",
    "description": (
        "Phase 2B (tier>=2): read a single hermes_workspace file including .json/.yaml/.yml bounds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative workspace path subdir/name.ext (.md/.txt/.csv/.json/.yaml/.yml)",
            },
            "max_output_chars": {"type": "integer"},
        },
        "required": ["path"],
    },
}

READ_REF_SCHEMA = {
    "name": "read_powerunits_local_reference_file",
    "description": (
        "Phase 2B (tier>=2): read a single file under $HERMES_HOME/powerunits_local_reference (must exist)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to powerunits_local_reference (no '..').",
            },
            "max_output_chars": {"type": "integer"},
        },
        "required": ["path"],
    },
}

registry.register(
    name="manifest_powerunits_tier2_allowlisted_read_scope",
    toolset="powerunits_tier2_allowlisted_read",
    schema=MANIFEST_SCHEMA,
    handler=lambda args, **kw: manifest_powerunits_tier2_allowlisted_read_scope(**kw),
    check_fn=check_powerunits_tier2_allowlisted_read_overlay,
    emoji="📋",
)

registry.register(
    name="summarize_powerunits_allowlisted_locals",
    toolset="powerunits_tier2_allowlisted_read",
    schema=SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_allowlisted_locals(subdir=args.get("subdir"), **kw),
    check_fn=check_powerunits_tier2_allowlisted_read_overlay,
    emoji="🗂️",
)

registry.register(
    name="search_powerunits_allowlisted_local_text",
    toolset="powerunits_tier2_allowlisted_read",
    schema=SEARCH_SCHEMA,
    handler=lambda args, **kw: search_powerunits_allowlisted_local_text(
        query=str(args.get("query", "")),
        root_scope=args.get("root_scope"),
        subdir=args.get("subdir"),
        max_hits=args.get("max_hits"),
        **kw,
    ),
    check_fn=check_powerunits_tier2_allowlisted_read_overlay,
    emoji="🔍",
)

registry.register(
    name="read_powerunits_allowlisted_workspace_extended_file",
    toolset="powerunits_tier2_allowlisted_read",
    schema=READ_WS_EXT_SCHEMA,
    handler=lambda args, **kw: read_powerunits_allowlisted_workspace_extended_file(
        path=str(args.get("path", "")),
        max_output_chars=args.get("max_output_chars"),
        **kw,
    ),
    check_fn=check_powerunits_tier2_allowlisted_read_overlay,
    emoji="📄",
)

registry.register(
    name="read_powerunits_local_reference_file",
    toolset="powerunits_tier2_allowlisted_read",
    schema=READ_REF_SCHEMA,
    handler=lambda args, **kw: read_powerunits_local_reference_file(
        path=str(args.get("path", "")),
        max_output_chars=args.get("max_output_chars"),
        **kw,
    ),
    check_fn=check_powerunits_tier2_allowlisted_read_overlay,
    emoji="🗃️",
)
