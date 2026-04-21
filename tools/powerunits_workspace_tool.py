#!/usr/bin/env python3
"""
Bounded persistent workspace tools for Powerunits Hermes.

Workspace root is fixed to /opt/data/hermes_workspace (via HERMES_HOME default),
with allowlisted subdirectories:
- analysis
- notes
- drafts
- exports
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
_ALLOWED_EXTS = (".md", ".txt")
_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}$")
_DEFAULT_MAX_CHARS = 16_000
_ABS_MAX_CHARS = 32_000
_ABS_MIN_CHARS = 2_000


def _workspace_root() -> Path:
    # Fixed production root under Railway persistent volume.
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    return (hermes_home / "hermes_workspace").resolve()


def _ensure_workspace_dirs() -> Path:
    root = _workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    for s in _ALLOWED_SUBDIRS:
        (root / s).mkdir(parents=True, exist_ok=True)
    return root


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
        raise ValueError("only .md/.txt files are allowed")
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
        raise ValueError("name must end with .md or .txt")
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
        "List files/directories in bounded persistent workspace /opt/data/hermes_workspace "
        "(allowed subdirs: analysis, notes, drafts, exports). No repo/file-system escape."
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
        "Read .md/.txt file from bounded workspace /opt/data/hermes_workspace/<allowed-subdir>/..."
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

WRITE_SCHEMA = {
    "name": "save_hermes_workspace_note",
    "description": (
        "Save text file in bounded workspace under one allowed subdir. "
        "No delete/rename/generic path writes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "One of analysis|notes|drafts|exports"},
            "name": {"type": "string", "description": "File name ending with .md or .txt"},
            "content": {"type": "string", "description": "Text content to save"},
            "overwrite_mode": {"type": "string", "enum": ["forbid", "overwrite"]},
        },
        "required": ["kind", "name", "content"],
    },
}


from tools.registry import registry

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
