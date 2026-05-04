#!/usr/bin/env python3
"""
Bounded persistent workspace tools for Powerunits Hermes.

Workspace root is fixed under $HERMES_HOME/hermes_workspace (default /opt/data),
with allowlisted subdirectories:
- analysis
- notes
- drafts
- exports

Phase 1A posture (see docs/powerunits_hermes_progressive_posture_v1.md): optional
EXPORTS_PHASE1_OPERATOR.txt bootstrap under exports/ and read-only export summary tool.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_SUBDIRS = ("analysis", "notes", "drafts", "exports")
_ALLOWED_EXTS = (".md", ".txt", ".csv")
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}$")
_DEFAULT_MAX_CHARS = 16_000
_ABS_MAX_CHARS = 32_000
_ABS_MIN_CHARS = 2_000

_EXPORTS_PHASE1_POINTER_NAME = "EXPORTS_PHASE1_OPERATOR.txt"
_EXPORTS_PHASE1_POINTER_BODY = """Powerunits Hermes — Phase 1A exports posture (operator pointer).

Canonical roadmap (do not fork): docs/powerunits_hermes_progressive_posture_v1.md
Phase 1A export conventions + watcher hints: docs/powerunits_workspace_phase1_exports_v1.md
General workspace: docs/powerunits_workspace_v1.md

Read-only hygiene tool: summarize_powerunits_workspace_exports
Writes: save_hermes_workspace_note(kind=exports, ...) — overwrite_mode=forbid default; overwrite deliberate only.

Hermes-derived files here are NOT Repo B canon; Repo B stays authoritative HTTP/source of truth.
"""

# Soft caution thresholds — align with docs/powerunits_workspace_phase1_exports_v1.md
_CAUTION_EXPORT_FILE_COUNT = 150
_CAUTION_EXPORT_TOTAL_BYTES = 40 * 1024 * 1024
_CAUTION_SINGLE_FILE_BYTES = 8 * 1024 * 1024
# Max path segments under exports/ (excluding "exports" itself): a/b/file.csv -> 3
_MAX_EXPORT_DEPTH_PARTS = 8


def _workspace_root() -> Path:
    # Fixed production root under Railway persistent volume.
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    return (hermes_home / "hermes_workspace").resolve()


def _ensure_workspace_dirs() -> Path:
    root = _workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    for s in _ALLOWED_SUBDIRS:
        (root / s).mkdir(parents=True, exist_ok=True)
    _write_exports_phase1_pointer_if_missing(root)
    return root


def _write_exports_phase1_pointer_if_missing(root: Path) -> None:
    """One-time exports/ readme pointer; never overwrites."""

    try:
        exports_dir = root / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        marker = exports_dir / _EXPORTS_PHASE1_POINTER_NAME
        marker.resolve().relative_to(root.resolve())
        if marker.exists():
            return
        marker.write_text(_EXPORTS_PHASE1_POINTER_BODY.strip() + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.warning("Exports Phase 1A pointer skipped: %s", exc)


def summarize_powerunits_workspace_exports(**_: Any) -> str:
    """Aggregate read-only view of bounded exports subtree (Phase 1A hygiene)."""

    from tools.registry import tool_error

    try:
        root = _ensure_workspace_dirs().resolve()
        ex_dir = (root / "exports").resolve()
        ex_dir.relative_to(root)

        caution: list[str] = []
        file_rows: list[dict[str, Any]] = []

        deepest = 0

        if not ex_dir.is_dir():
            return json.dumps(
                {
                    "exports_root_relative": "exports",
                    "file_count": 0,
                    "total_bytes": 0,
                    "max_depth_under_exports": 0,
                    "largest_files": [],
                    "caution_flags": [],
                    "thresholds_hint": _export_summary_thresholds_payload(),
                    "read_only": True,
                    "phase": "1A",
                    "doc_hint": "docs/powerunits_workspace_phase1_exports_v1.md",
                },
                ensure_ascii=False,
            )

        skipped_symlink = 0
        seen_over_depth = False

        for raw in sorted(ex_dir.rglob("*")):
            if not raw.is_file():
                continue
            if raw.is_symlink():
                skipped_symlink += 1
                continue
            if not raw.name.lower().endswith(_ALLOWED_EXTS):
                continue
            resolved = raw.resolve()
            resolved.relative_to(root)
            resolved.relative_to(ex_dir)
            depth = len(raw.relative_to(ex_dir).parts)
            deepest = max(deepest, depth)
            if depth > _MAX_EXPORT_DEPTH_PARTS:
                seen_over_depth = True
                continue

            try:
                st = raw.stat()
            except OSError:
                caution.append(f"stat_failed:{raw.relative_to(root).as_posix()}")
                continue

            nbytes = int(st.st_size)
            if nbytes >= _CAUTION_SINGLE_FILE_BYTES:
                caution.append(f"large_single_file:{raw.name}:{nbytes}")

            rel = raw.relative_to(root).as_posix()
            file_rows.append(
                {"path": rel, "bytes": nbytes, "mtime_epoch": int(st.st_mtime)},
            )

        if skipped_symlink:
            caution.append(f"skipped_symlinks:{skipped_symlink}")
        if seen_over_depth:
            caution.append("skipped_paths_over_depth_cap")

        file_rows.sort(key=lambda r: int(r["bytes"]), reverse=True)
        total_bytes = sum(int(r["bytes"]) for r in file_rows)
        nfiles = len(file_rows)

        if nfiles >= _CAUTION_EXPORT_FILE_COUNT:
            caution.append(f"high_file_count:{nfiles}")
        if total_bytes >= _CAUTION_EXPORT_TOTAL_BYTES:
            caution.append(f"high_total_bytes:{total_bytes}")

        caution_sorted = sorted(set(caution))

        return json.dumps(
            {
                "exports_root_relative": "exports",
                "file_count": nfiles,
                "total_bytes": total_bytes,
                "max_depth_under_exports": deepest,
                "largest_files": file_rows[:12],
                "caution_flags": caution_sorted,
                "thresholds_hint": _export_summary_thresholds_payload(),
                "read_only": True,
                "phase": "1A",
                "doc_hint": "docs/powerunits_workspace_phase1_exports_v1.md",
            },
            ensure_ascii=False,
        )
    except ValueError:
        return tool_error("workspace layout invalid", error_code="invalid_workspace_layout")
    except Exception as exc:
        return tool_error(f"exports summary failed: {exc}", error_code="exports_summary_failed")


def _export_summary_thresholds_payload() -> dict[str, int]:
    return {
        "caution_files": _CAUTION_EXPORT_FILE_COUNT,
        "caution_bytes": _CAUTION_EXPORT_TOTAL_BYTES,
        "large_file_bytes": _CAUTION_SINGLE_FILE_BYTES,
        "max_depth_parts": _MAX_EXPORT_DEPTH_PARTS,
    }


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validate_subdir(subdir: str | None) -> str:
    if subdir is None or not str(subdir).strip():
        return ""
    s = str(subdir).strip().strip("/\\")
    if s not in _ALLOWED_SUBDIRS:
        raise ValueError(f"subdir must be one of: {', '.join(_ALLOWED_SUBDIRS)}")
    return s


def _validate_read_path(path: str) -> tuple[str, str]:
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
        raise ValueError("path must include subdir/file (e.g. notes/foo.md)")
    subdir = parts[0]
    if subdir not in _ALLOWED_SUBDIRS:
        raise ValueError(f"path must start with one of: {', '.join(_ALLOWED_SUBDIRS)}")
    fname = parts[-1]
    if not fname.lower().endswith(_ALLOWED_EXTS):
        raise ValueError("only .md, .txt, or .csv files are allowed")
    return subdir, "/".join(parts[1:])


def _validate_save_name(name: str) -> str:
    n = str(name or "").strip()
    if not n:
        raise ValueError("name is required")
    if "/" in n or "\\" in n:
        raise ValueError("name must be a file name without path separators")
    if ".." in n:
        raise ValueError("name must not contain '..'")
    if not _NAME_RE.match(n):
        raise ValueError("name contains invalid characters")
    if not n.lower().endswith(_ALLOWED_EXTS):
        raise ValueError("name must end with .md, .txt, or .csv")
    return n


def check_powerunits_workspace_requirements() -> bool:
    try:
        _ensure_workspace_dirs()
        return True
    except Exception as exc:
        logger.warning("Powerunits workspace tools disabled: %s", exc)
        return False


def list_hermes_workspace(subdir: str | None = None, **_: Any) -> str:
    from tools.registry import tool_error

    try:
        target_subdir = _validate_subdir(subdir)
        root = _ensure_workspace_dirs()
        target = root / target_subdir if target_subdir else root
        entries: list[dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            rel = child.relative_to(root).as_posix()
            if child.is_dir() and child.name not in _ALLOWED_SUBDIRS and target == root:
                continue
            if child.is_file() and not child.name.lower().endswith(_ALLOWED_EXTS):
                continue
            entries.append({"name": child.name, "type": "dir" if child.is_dir() else "file", "path": rel})
        return json.dumps(
            {
                "root": "hermes_workspace",
                "allowed_subdirs": list(_ALLOWED_SUBDIRS),
                "subdir": target_subdir,
                "entries": entries,
                "count": len(entries),
                "read_only": False,
                "write_scope": "bounded_workspace_only",
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_subdir")
    except Exception as exc:
        return tool_error(f"workspace list failed: {exc}", error_code="workspace_list_failed")


def read_hermes_workspace_file(path: str, max_output_chars: int | None = None, **_: Any) -> str:
    from tools.registry import tool_error

    try:
        subdir, tail = _validate_read_path(path)
        root = _ensure_workspace_dirs()
        file_path = (root / subdir / tail).resolve()
        file_path.relative_to(root)
        if not file_path.is_file():
            return tool_error("workspace file not found", error_code="not_found")
        text = file_path.read_text(encoding="utf-8", errors="replace")
        lim = _safe_int(max_output_chars, _DEFAULT_MAX_CHARS)
        lim = max(_ABS_MIN_CHARS, min(lim, _ABS_MAX_CHARS))
        truncated = len(text) > lim
        if truncated:
            text = text[:lim] + "\n\n[truncated to max_output_chars]"
        return json.dumps(
            {
                "path": file_path.relative_to(root).as_posix(),
                "chars_returned": len(text),
                "truncated": truncated,
                "content": text,
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")
    except Exception as exc:
        return tool_error(f"workspace read failed: {exc}", error_code="workspace_read_failed")


def save_hermes_workspace_note(
    kind: str,
    name: str,
    content: str,
    overwrite_mode: str | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    try:
        k = str(kind or "").strip()
        if k not in _ALLOWED_SUBDIRS:
            raise ValueError(f"kind must be one of: {', '.join(_ALLOWED_SUBDIRS)}")
        n = _validate_save_name(name)
        if content is None:
            raise ValueError("content is required")
        mode = (overwrite_mode or "forbid").strip().lower()
        if mode not in {"forbid", "overwrite"}:
            raise ValueError("overwrite_mode must be 'forbid' or 'overwrite'")

        root = _ensure_workspace_dirs()
        out_path = (root / k / n).resolve()
        out_path.relative_to(root)

        if mode == "forbid" and out_path.exists():
            return tool_error("file already exists (overwrite_mode=forbid)", error_code="already_exists")
        out_path.write_text(str(content), encoding="utf-8")
        return json.dumps(
            {
                "saved": True,
                "path": out_path.relative_to(root).as_posix(),
                "bytes": out_path.stat().st_size,
                "overwrite_mode": mode,
            },
            ensure_ascii=False,
        )
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_write_args")
    except Exception as exc:
        return tool_error(f"workspace write failed: {exc}", error_code="workspace_write_failed")


LIST_SCHEMA = {
    "name": "list_hermes_workspace",
    "description": (
        "List files/directories in bounded persistent workspace $HERMES_HOME/hermes_workspace "
        "(allowed subdirs: analysis, notes, drafts, exports). "
        "After Phase 1A bootstrap, exports/ may include EXPORTS_PHASE1_OPERATOR.txt (readme pointer)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subdir": {
                "type": "string",
                "description": "Optional: one of analysis|notes|drafts|exports.",
            }
        },
        "required": [],
    },
}

READ_SCHEMA = {
    "name": "read_hermes_workspace_file",
    "description": (
        "Read .md/.txt/.csv file from bounded workspace /opt/data/hermes_workspace/<allowed-subdir>/..."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path like notes/today.md"},
            "max_output_chars": {"type": "integer", "description": "Default 16000, cap 32000"},
        },
        "required": ["path"],
    },
}

SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_workspace_exports",
    "description": (
        "Read-only Phase 1A snapshot of bounded hermes_workspace/exports: counts, sizes, largest files, "
        "soft caution flags (thresholds: docs/powerunits_workspace_phase1_exports_v1.md). "
        "No writes; skips symlinks; bounded scan depth from exports root."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


WRITE_SCHEMA = {
    "name": "save_hermes_workspace_note",
    "description": (
        "Save text file in bounded workspace under one allowed subdir. "
        "overwrite_mode default forbid (no silent overwrite); use overwrite deliberately "
        "(Phase 1A: docs/powerunits_workspace_phase1_exports_v1.md)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "One of analysis|notes|drafts|exports"},
            "name": {"type": "string", "description": "File name ending with .md, .txt, or .csv"},
            "content": {"type": "string", "description": "Text content to save"},
            "overwrite_mode": {"type": "string", "enum": ["forbid", "overwrite"]},
        },
        "required": ["kind", "name", "content"],
    },
}


from tools.registry import registry

registry.register(
    name="summarize_powerunits_workspace_exports",
    toolset="powerunits_workspace",
    schema=SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_workspace_exports(**kw),
    check_fn=check_powerunits_workspace_requirements,
    emoji="📎",
)

registry.register(
    name="list_hermes_workspace",
    toolset="powerunits_workspace",
    schema=LIST_SCHEMA,
    handler=lambda args, **kw: list_hermes_workspace(
        subdir=args.get("subdir"),
        **kw,
    ),
    check_fn=check_powerunits_workspace_requirements,
    emoji="🗂️",
)

registry.register(
    name="read_hermes_workspace_file",
    toolset="powerunits_workspace",
    schema=READ_SCHEMA,
    handler=lambda args, **kw: read_hermes_workspace_file(
        path=args.get("path", ""),
        max_output_chars=args.get("max_output_chars"),
        **kw,
    ),
    check_fn=check_powerunits_workspace_requirements,
    emoji="📘",
)

registry.register(
    name="save_hermes_workspace_note",
    toolset="powerunits_workspace",
    schema=WRITE_SCHEMA,
    handler=lambda args, **kw: save_hermes_workspace_note(
        kind=args.get("kind", ""),
        name=args.get("name", ""),
        content=args.get("content", ""),
        overwrite_mode=args.get("overwrite_mode"),
        **kw,
    ),
    check_fn=check_powerunits_workspace_requirements,
    emoji="📝",
)
