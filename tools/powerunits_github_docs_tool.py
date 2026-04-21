#!/usr/bin/env python3
"""Narrow read-only GitHub docs reader using operator-managed allowlist surfaces."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_DEFAULT_REPO = "Kiron030/Powerunits.io"
_DEFAULT_BRANCH = "starting_the_seven_phases"
_DEFAULT_ROOT = "docs/roadmap"
_DEFAULT_ALIAS = "powerunits_roadmap"
_ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "powerunits_repo_read_allowlist.json"
_DEFAULT_MAX_CHARS = 16_000
_ABS_MAX_CHARS = 32_000
_ABS_MIN_CHARS = 2_000
_TOKEN_ENV = "POWERUNITS_GITHUB_TOKEN_READ"
_TOKEN_ENV_LEGACY = "POWERUNITS_GITHUB_DOCS_TOKEN"
_WARNED_MISSING_TOKEN = False
_WARNED_BAD_ALLOWLIST = False


def _cfg() -> dict[str, str]:
    token = os.getenv(_TOKEN_ENV, "").strip()
    if not token:
        token = os.getenv(_TOKEN_ENV_LEGACY, "").strip()
    return {"token": token}


def _load_allowlist() -> dict[str, dict[str, Any]]:
    raw = json.loads(_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("allowlist root must be object")
    surfaces = raw.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise ValueError("allowlist.surfaces must be non-empty list")
    out: dict[str, dict[str, Any]] = {}
    for item in surfaces:
        if not isinstance(item, dict):
            raise ValueError("allowlist surface must be object")
        alias = str(item.get("alias", "")).strip()
        repo = str(item.get("repo", "")).strip()
        branch = str(item.get("branch", "")).strip()
        root = str(item.get("root_prefix", "")).strip().strip("/")
        exts = item.get("allowed_extensions")
        enabled = bool(item.get("enabled", False))
        if not alias:
            raise ValueError("surface alias missing")
        if not repo or "/" not in repo:
            raise ValueError(f"surface {alias}: invalid repo")
        if not branch:
            raise ValueError(f"surface {alias}: invalid branch")
        if not root:
            raise ValueError(f"surface {alias}: invalid root_prefix")
        if not isinstance(exts, list) or not exts:
            raise ValueError(f"surface {alias}: allowed_extensions must be non-empty list")
        norm_exts = []
        for e in exts:
            es = str(e).strip().lower()
            if not es.startswith("."):
                raise ValueError(f"surface {alias}: extension must start with '.'")
            norm_exts.append(es)
        out[alias] = {
            "alias": alias,
            "repo": repo,
            "branch": branch,
            "root_prefix": root,
            "allowed_extensions": tuple(norm_exts),
            "enabled": enabled,
            "mode": "read_only",
        }
    return out


def _resolve_surface(alias: str | None) -> dict[str, Any]:
    wanted = (alias or _DEFAULT_ALIAS).strip() or _DEFAULT_ALIAS
    surfaces = _load_allowlist()
    s = surfaces.get(wanted)
    if not s:
        raise ValueError("unknown allowlisted surface alias")
    if not s.get("enabled"):
        raise ValueError("surface alias is disabled")
    return s


def _headers(token: str, *, raw: bool = False) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "hermes-powerunits-github-docs/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    if raw:
        h["Accept"] = "application/vnd.github.v3.raw"
    return h


def _github_json_request(url: str, token: str) -> Any:
    req = Request(url, headers=_headers(token), method="GET")
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _github_raw_request(url: str, token: str) -> str:
    req = Request(url, headers=_headers(token, raw=True), method="GET")
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _normalize_subpath(value: str | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip().replace("\\", "/").strip("/")
    if not raw:
        return ""
    if raw.startswith("/") or ".." in PurePosixPath(raw).parts:
        raise ValueError("subpath escapes allowlisted root")
    return raw


def _resolve_path(root: str, subpath: str) -> str:
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


def check_powerunits_github_docs_requirements() -> bool:
    global _WARNED_MISSING_TOKEN, _WARNED_BAD_ALLOWLIST
    try:
        _load_allowlist()
        _WARNED_BAD_ALLOWLIST = False
    except Exception as exc:
        if not _WARNED_BAD_ALLOWLIST:
            logger.warning("Powerunits GitHub docs tools disabled: invalid allowlist config (%s).", exc)
            _WARNED_BAD_ALLOWLIST = True
        return False
    token = _cfg()["token"]
    if token:
        _WARNED_MISSING_TOKEN = False
        return True
    if not _WARNED_MISSING_TOKEN:
        logger.warning(
            "Powerunits GitHub docs tools disabled: missing %s (read-only token for %s).",
            _TOKEN_ENV,
            _DEFAULT_REPO,
        )
        _WARNED_MISSING_TOKEN = True
    return False


def list_powerunits_roadmap_dir(subpath: str | None = None, alias: str | None = None, **_: Any) -> str:
    from tools.registry import tool_error

    c = _cfg()
    if not c["token"]:
        return tool_error(f"Missing {_TOKEN_ENV}.", error_code="missing_token")
    try:
        s = _resolve_surface(alias)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_alias")
    try:
        sp = _normalize_subpath(subpath)
        api_path = _resolve_path(str(s["root_prefix"]), sp)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_subpath")

    url = (
        f"https://api.github.com/repos/{quote(str(s['repo']), safe='/')}/contents/"
        f"{quote(api_path, safe='/')}?ref={quote(str(s['branch']), safe='')}"
    )
    try:
        payload = _github_json_request(url, str(c["token"]))
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
    return json.dumps(
        {
            "alias": s["alias"],
            "repo": s["repo"],
            "branch": s["branch"],
            "allowed_root": s["root_prefix"],
            "subpath": sp,
            "entries": out_entries,
            "count": len(out_entries),
            "read_only": True,
        },
        ensure_ascii=False,
    )


def read_powerunits_roadmap_file(
    name: str,
    max_output_chars: int | None = None,
    alias: str | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    c = _cfg()
    if not c["token"]:
        return tool_error(f"Missing {_TOKEN_ENV}.", error_code="missing_token")
    try:
        s = _resolve_surface(alias)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_alias")
    if not name or not str(name).strip():
        return tool_error("Parameter name is required.", error_code="name_required")
    try:
        sp = _normalize_subpath(name)
        api_path = _resolve_path(str(s["root_prefix"]), sp)
        _check_ext_for_read(api_path, tuple(s["allowed_extensions"]))
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_name")

    url = (
        f"https://api.github.com/repos/{quote(str(s['repo']), safe='/')}/contents/"
        f"{quote(api_path, safe='/')}?ref={quote(str(s['branch']), safe='')}"
    )
    try:
        text = _github_raw_request(url, str(c["token"]))
    except HTTPError as e:
        if e.code in (401, 403):
            return tool_error("GitHub token unauthorized/forbidden for this repo.", error_code="auth_failed")
        if e.code == 404:
            return tool_error("File not found inside allowlisted root.", error_code="not_found")
        return tool_error(f"GitHub API error: HTTP {e.code}", error_code="github_http_error")
    except URLError as e:
        return tool_error(f"GitHub API network error: {e}", error_code="github_network_error")

    lim = _safe_int(max_output_chars, _DEFAULT_MAX_CHARS)
    lim = max(_ABS_MIN_CHARS, min(lim, _ABS_MAX_CHARS))
    truncated = len(text) > lim
    if truncated:
        text = text[:lim] + "\n\n[truncated to max_output_chars]"

    return json.dumps(
        {
            "alias": s["alias"],
            "repo": s["repo"],
            "branch": s["branch"],
            "allowed_root": s["root_prefix"],
            "key": sp,
            "path": api_path,
            "chars_returned": len(text),
            "truncated": truncated,
            "read_only": True,
            "content": text,
        },
        ensure_ascii=False,
    )


LIST_SCHEMA = {
    "name": "list_powerunits_roadmap_dir",
    "description": (
        "List directory entries under the hard-allowlisted GitHub root docs/roadmap/ "
        "in Kiron030/Powerunits.io on branch starting_the_seven_phases. Read-only."
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
                "description": "Optional subdirectory within docs/roadmap/ (no absolute paths, no ..).",
            }
        },
        "required": [],
    },
}

READ_SCHEMA = {
    "name": "read_powerunits_roadmap_file",
    "description": (
        "Read one .md/.txt file under the hard-allowlisted GitHub root docs/roadmap/ "
        "in Kiron030/Powerunits.io on branch starting_the_seven_phases. Read-only."
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
                "description": "File path relative to docs/roadmap/ (e.g. phase1/overview.md).",
            },
            "max_output_chars": {
                "type": "integer",
                "description": "Max output size (default 16000, hard cap 32000).",
            },
        },
        "required": ["name"],
    },
}


from tools.registry import registry

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
