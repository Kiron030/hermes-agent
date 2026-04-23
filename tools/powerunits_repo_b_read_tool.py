#!/usr/bin/env python3
"""
Bounded read-only access to allowlisted Repo B files via GitHub API (no local clone).

Keys and paths come only from config/powerunits_repo_b_read_allowlist.json (or
HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST). No free path arguments.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ALLOWLIST = _REPO_ROOT / "config" / "powerunits_repo_b_read_allowlist.json"
_FEATURE_ENV = "HERMES_POWERUNITS_REPO_B_READ_ENABLED"
_ALLOWLIST_ENV = "HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST"

_DEFAULT_MAX = 24_000
_ABS_MAX = 48_000
_ABS_MIN = 2_000


def repo_b_allowlist_path() -> Path:
    raw = os.getenv(_ALLOWLIST_ENV, "").strip()
    if raw:
        return Path(raw).resolve()
    return _DEFAULT_ALLOWLIST.resolve()


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_repo_b_read_requirements() -> bool:
    if not _truthy_env(_FEATURE_ENV):
        return False
    try:
        from tools.powerunits_github_knowledge import github_token

        if not github_token():
            return False
        _load_allowlist_entries()
    except Exception as exc:
        logger.warning("powerunits_repo_b_read disabled: %s", exc)
        return False
    return True


def _load_allowlist_entries() -> dict[str, dict[str, Any]]:
    p = repo_b_allowlist_path()
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("repo b allowlist root must be object")
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("repo b allowlist: entries must be non-empty list")
    by_key: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        repo = item.get("repo")
        branch = item.get("branch")
        path = item.get("path")
        if not isinstance(key, str) or not key.strip():
            continue
        if not isinstance(repo, str) or "/" not in repo:
            raise ValueError(f"repo b allowlist entry {key!r}: invalid repo")
        if not isinstance(branch, str) or not branch.strip():
            raise ValueError(f"repo b allowlist entry {key!r}: invalid branch")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"repo b allowlist entry {key!r}: invalid path")
        norm = path.strip().replace("\\", "/").lstrip("/")
        if ".." in norm.split("/"):
            raise ValueError(f"repo b allowlist entry {key!r}: path must not contain '..'")
        cleaned = {**item, "path": norm}
        by_key[key.strip()] = cleaned
    if not by_key:
        raise ValueError("repo b allowlist: no valid entries")
    return by_key


def _resolve_entry(key: str) -> dict[str, Any]:
    k = (key or "").strip()
    if not k:
        raise ValueError("key is required")
    entries = _load_allowlist_entries()
    if k not in entries:
        raise ValueError(f"unknown key: {k!r}; use action=list_keys")
    return entries[k]


def _clamp_max_chars(raw: Any) -> int:
    if raw is None:
        return _DEFAULT_MAX
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = _DEFAULT_MAX
    return max(_ABS_MIN, min(n, _ABS_MAX))


def read_powerunits_repo_b_allowlisted(
    action: str,
    key: str | None = None,
    max_output_chars: int | None = None,
    *,
    _fetch_raw: Callable[..., str] | None = None,
    **_: Any,
) -> str:
    """List allowlist keys or read one file from GitHub (raw contents API)."""
    from tools.powerunits_github_knowledge import github_branch_tip_sha, github_fetch_raw_file, github_token
    from tools.registry import tool_error

    if not _truthy_env(_FEATURE_ENV):
        return tool_error(
            f"{_FEATURE_ENV} must be truthy (e.g. 1) to use this tool.",
            error_code="feature_disabled",
        )
    token = github_token()
    if not token:
        return tool_error("Missing GitHub read token (POWERUNITS_GITHUB_TOKEN_READ).", error_code="missing_token")

    act = (action or "").strip().lower()
    if act not in ("list_keys", "read"):
        return tool_error('action must be "list_keys" or "read".', error_code="invalid_action")

    try:
        entries = _load_allowlist_entries()
    except Exception as exc:
        logger.warning("repo_b_read allowlist error: %s", type(exc).__name__)
        return tool_error(f"Allowlist invalid or unreadable: {exc}", error_code="allowlist_error")

    if act == "list_keys":
        keys = sorted(entries.keys())
        logger.info(
            "repo_b_read target=github action=list_keys keys_count=%s outcome=success",
            len(keys),
        )
        return json.dumps(
            {
                "surface": "powerunits_repo_b_read",
                "action": "list_keys",
                "keys": keys,
                "allowlist_path": str(repo_b_allowlist_path()),
            },
            ensure_ascii=False,
        )

    try:
        entry = _resolve_entry(str(key or ""))
    except ValueError as exc:
        logger.info("repo_b_read target=github action=read outcome=rejected_input key=%r", key)
        return tool_error(str(exc), error_code="invalid_key")

    repo = str(entry["repo"])
    branch = str(entry["branch"])
    api_path = str(entry["path"])
    lim = _clamp_max_chars(max_output_chars)
    fetch = _fetch_raw or github_fetch_raw_file

    try:
        body = fetch(repo, branch, api_path, token)
    except Exception as exc:
        logger.warning("repo_b_read target=github outcome=github_error type=%s", type(exc).__name__)
        return tool_error("GitHub fetch failed (see logs for error type).", error_code="github_error")

    tip = github_branch_tip_sha(repo, branch, token)
    truncated = len(body) > lim
    out = body if not truncated else body[:lim] + "\n\n[... truncated to max_output_chars ...]\n"

    logger.info(
        "repo_b_read target=github action=read key=%s path=%s chars_returned=%s truncated=%s outcome=success",
        entry.get("key"),
        api_path,
        len(out),
        truncated,
    )
    return json.dumps(
        {
            "surface": "powerunits_repo_b_read",
            "action": "read",
            "key": entry.get("key"),
            "repo": repo,
            "branch": branch,
            "path": api_path,
            "branch_tip_sha": tip,
            "content_type": entry.get("content_type"),
            "truncated": truncated,
            "content": out,
        },
        ensure_ascii=False,
    )


READ_POWERUNITS_REPO_B_SCHEMA = {
    "name": "read_powerunits_repo_b_allowlisted",
    "description": (
        "Read-only allowlisted Repo B files via GitHub API (keys from "
        "config/powerunits_repo_b_read_allowlist.json). No free paths. "
        "Supplemental to primary GitHub docs reader; requires "
        f"{_FEATURE_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": 'Use "list_keys" or "read".',
                "enum": ["list_keys", "read"],
            },
            "key": {
                "type": "string",
                "description": 'Allowlist key (required when action is "read").',
            },
            "max_output_chars": {
                "type": "integer",
                "description": f"Max characters of file body for read (default {_DEFAULT_MAX}, cap {_ABS_MAX}).",
            },
        },
        "required": ["action"],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_repo_b_allowlisted",
    toolset="powerunits_repo_b_read",
    schema=READ_POWERUNITS_REPO_B_SCHEMA,
    handler=lambda args, **kw: read_powerunits_repo_b_allowlisted(
        action=args.get("action", ""),
        key=args.get("key"),
        max_output_chars=args.get("max_output_chars"),
        **kw,
    ),
    check_fn=check_powerunits_repo_b_read_requirements,
    requires_env=[_FEATURE_ENV, "POWERUNITS_GITHUB_TOKEN_READ"],
    emoji="📂",
)
