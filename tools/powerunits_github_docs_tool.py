#!/usr/bin/env python3
"""Narrow read-only GitHub docs reader using operator-managed allowlist surfaces."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError

from tools.powerunits_github_knowledge import (
    PinnedRefError,
    github_fetch_json,
    github_fetch_raw_file,
    github_read_provenance,
    github_token,
    load_knowledge_pin,
    load_surfaces,
    log_powerunits_docs_read,
    normalize_subpath,
)
from tools.registry import registry

logger = logging.getLogger(__name__)

_WARNED_MISSING_TOKEN = False
_WARNED_BAD_ALLOWLIST = False


def _resolve_path(root: str, subpath: str) -> str:
    from pathlib import PurePosixPath

    p = PurePosixPath(root)
    if subpath:
        p = p / subpath
    s = str(p).strip("/")
    if not s.startswith(root):
        raise ValueError("resolved path escaped allowlisted root")
    return s


def _check_ext_for_read(path: str, allowed_exts: tuple[str, ...]) -> None:
    name = path.lower()
    if not any(name.endswith(ext) for ext in allowed_exts):
        raise ValueError("file extension is not allowlisted for this surface")


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_pinned_config() -> tuple[dict[str, dict[str, Any]], str, str]:
    """Surfaces plus (approved_ref, approved_ref_commit_time); raises before any network call."""
    surfaces = load_surfaces()
    approved_ref, approved_ref_commit_time = load_knowledge_pin()
    return surfaces, approved_ref, approved_ref_commit_time


def _config_error(exc: Exception) -> str:
    from tools.registry import tool_error

    code = "pinned_ref_invalid" if isinstance(exc, PinnedRefError) else "config_invalid"
    return tool_error(f"Powerunits GitHub knowledge config rejected (fail closed): {exc}", error_code=code)


def check_powerunits_github_docs_requirements() -> bool:
    global _WARNED_MISSING_TOKEN, _WARNED_BAD_ALLOWLIST
    try:
        _load_pinned_config()
        _WARNED_BAD_ALLOWLIST = False
    except Exception as exc:
        if not _WARNED_BAD_ALLOWLIST:
            logger.warning("Powerunits GitHub docs tools disabled: invalid knowledge config (%s).", exc)
            _WARNED_BAD_ALLOWLIST = True
        return False
    token = github_token()
    if token:
        _WARNED_MISSING_TOKEN = False
        return True
    if not _WARNED_MISSING_TOKEN:
        logger.warning(
            "Powerunits GitHub docs tools disabled: missing %s (read-only token).",
            "POWERUNITS_GITHUB_TOKEN_READ",
        )
        _WARNED_MISSING_TOKEN = True
    return False


def list_powerunits_roadmap_dir(subpath: str | None = None, alias: str | None = None, **_: Any) -> str:
    from tools.registry import tool_error

    token = github_token()
    if not token:
        return tool_error("Missing POWERUNITS_GITHUB_TOKEN_READ.", error_code="missing_token")
    try:
        surfaces, approved_ref, approved_ref_commit_time = _load_pinned_config()
    except (ValueError, OSError) as exc:
        return _config_error(exc)
    wanted = (alias or "powerunits_roadmap").strip() or "powerunits_roadmap"
    s = surfaces.get(wanted)
    if not s:
        return tool_error("unknown allowlisted surface alias", error_code="invalid_alias")
    if not s.get("enabled"):
        return tool_error("surface alias is disabled", error_code="invalid_alias")
    try:
        sp = normalize_subpath(subpath)
        api_path = _resolve_path(str(s["root_prefix"]), sp)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_subpath")

    ref = str(s["ref"])
    try:
        payload = github_fetch_json(str(s["repo"]), ref, api_path, token)
    except HTTPError as e:
        if e.code in (401, 403):
            return tool_error("GitHub token unauthorized/forbidden for this repo.", error_code="auth_failed")
        if e.code == 404:
            return tool_error("Path not found inside allowlisted root.", error_code="not_found")
        return tool_error(f"GitHub API error: HTTP {e.code}", error_code="github_http_error")
    except URLError as e:
        return tool_error(f"GitHub API network error: {e}", error_code="github_network_error")

    entries = payload if isinstance(payload, list) else [payload]
    out_entries: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        p = str(item.get("path", ""))
        if not p.startswith(str(s["root_prefix"])):
            continue
        out_entries.append(
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "path": p,
            }
        )
    out_entries.sort(key=lambda x: (x.get("type") != "dir", str(x.get("name", "")).lower()))
    provenance = github_read_provenance(
        repo=str(s["repo"]),
        read_sha=ref,
        approved_ref=approved_ref,
        approved_ref_commit_time=approved_ref_commit_time,
        token=token,
    )
    log_powerunits_docs_read(
        source="github_primary",
        repo=str(s["repo"]),
        branch=ref,
        commit_sha=provenance["read_sha"],
        alias=str(s["alias"]),
        relative_path=api_path,
        extra="tool=list_powerunits_roadmap_dir",
        provenance=provenance,
    )
    result: dict[str, Any] = {
        "alias": s["alias"],
        "repo": s["repo"],
        "branch": ref,
        "ref": ref,
        "commit_sha": provenance["read_sha"],
        "allowed_root": s["root_prefix"],
        "subpath": sp,
        "entries": out_entries,
        "count": len(out_entries),
        "read_only": True,
    }
    result.update(provenance)
    return json.dumps(result, ensure_ascii=False)


def read_powerunits_roadmap_file(
    name: str,
    max_output_chars: int | None = None,
    alias: str | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    token = github_token()
    if not token:
        return tool_error("Missing POWERUNITS_GITHUB_TOKEN_READ.", error_code="missing_token")
    try:
        surfaces, approved_ref, approved_ref_commit_time = _load_pinned_config()
    except (ValueError, OSError) as exc:
        return _config_error(exc)
    wanted = (alias or "powerunits_roadmap").strip() or "powerunits_roadmap"
    s = surfaces.get(wanted)
    if not s:
        return tool_error("unknown allowlisted surface alias", error_code="invalid_alias")
    if not s.get("enabled"):
        return tool_error("surface alias is disabled", error_code="invalid_alias")
    if not name or not str(name).strip():
        return tool_error("Parameter name is required.", error_code="name_required")
    try:
        sp = normalize_subpath(name)
        api_path = _resolve_path(str(s["root_prefix"]), sp)
        _check_ext_for_read(api_path, tuple(s["allowed_extensions"]))
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_name")

    ref = str(s["ref"])
    try:
        text = github_fetch_raw_file(str(s["repo"]), ref, api_path, token)
    except HTTPError as e:
        if e.code in (401, 403):
            return tool_error("GitHub token unauthorized/forbidden for this repo.", error_code="auth_failed")
        if e.code == 404:
            return tool_error("File not found inside allowlisted root.", error_code="not_found")
        return tool_error(f"GitHub API error: HTTP {e.code}", error_code="github_http_error")
    except URLError as e:
        return tool_error(f"GitHub API network error: {e}", error_code="github_network_error")

    lim = _safe_int(max_output_chars, 16_000)
    lim = max(2_000, min(lim, 32_000))
    truncated = len(text) > lim
    if truncated:
        text = text[:lim] + "\n\n[truncated to max_output_chars]"

    provenance = github_read_provenance(
        repo=str(s["repo"]),
        read_sha=ref,
        approved_ref=approved_ref,
        approved_ref_commit_time=approved_ref_commit_time,
        token=token,
    )
    log_powerunits_docs_read(
        source="github_primary",
        repo=str(s["repo"]),
        branch=ref,
        commit_sha=provenance["read_sha"],
        alias=str(s["alias"]),
        relative_path=api_path,
        extra="tool=read_powerunits_roadmap_file",
        provenance=provenance,
    )
    result: dict[str, Any] = {
        "alias": s["alias"],
        "repo": s["repo"],
        "branch": ref,
        "ref": ref,
        "commit_sha": provenance["read_sha"],
        "allowed_root": s["root_prefix"],
        "key": sp,
        "path": api_path,
        "chars_returned": len(text),
        "truncated": truncated,
        "read_only": True,
        "content": text,
    }
    result.update(provenance)
    return json.dumps(result, ensure_ascii=False)


LIST_SCHEMA = {
    "name": "list_powerunits_roadmap_dir",
    "description": (
        "List directory entries under an allowlisted GitHub root for Powerunits "
        "(default alias powerunits_roadmap -> docs/roadmap). "
        "Repo/roots and the pinned reviewed commit (see approved_ref) are defined only in "
        "config/powerunits_github_knowledge.json. Read-only; payload includes read_sha provenance."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Allowlisted surface alias (default: powerunits_roadmap).",
            },
            "subpath": {
                "type": "string",
                "description": "Optional subdirectory within the alias root (no absolute paths, no ..).",
            },
        },
        "required": [],
    },
}

READ_SCHEMA = {
    "name": "read_powerunits_roadmap_file",
    "description": (
        "Read one .md/.txt file under an allowlisted GitHub root for Powerunits. "
        "Repo/roots and the pinned reviewed commit (see approved_ref) come only from "
        "config/powerunits_github_knowledge.json. Read-only; payload includes read_sha provenance."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "alias": {
                "type": "string",
                "description": "Allowlisted surface alias (default: powerunits_roadmap).",
            },
            "name": {
                "type": "string",
                "description": "File path relative to the alias root (e.g. phase1/overview.md).",
            },
            "max_output_chars": {
                "type": "integer",
                "description": "Max output size (default 16000, hard cap 32000).",
            },
        },
        "required": ["name"],
    },
}


registry.register(
    name="list_powerunits_roadmap_dir",
    toolset="powerunits_github_docs",
    schema=LIST_SCHEMA,
    handler=lambda args, **kw: list_powerunits_roadmap_dir(
        subpath=args.get("subpath"),
        alias=args.get("alias"),
        **kw,
    ),
    check_fn=check_powerunits_github_docs_requirements,
    emoji="📁",
)

registry.register(
    name="read_powerunits_roadmap_file",
    toolset="powerunits_github_docs",
    schema=READ_SCHEMA,
    handler=lambda args, **kw: read_powerunits_roadmap_file(
        name=args.get("name", ""),
        max_output_chars=args.get("max_output_chars"),
        alias=args.get("alias"),
        **kw,
    ),
    check_fn=check_powerunits_github_docs_requirements,
    emoji="📄",
)
