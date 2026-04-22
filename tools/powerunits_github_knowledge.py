"""
Central Powerunits GitHub knowledge configuration and read helpers.

Used by read_powerunits_doc (primary GitHub path) and powerunits_github_docs_tool.
No secrets in-repo; token from POWERUNITS_GITHUB_TOKEN_READ (or legacy POWERUNITS_GITHUB_DOCS_TOKEN).
"""

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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KNOWLEDGE_CONFIG = _REPO_ROOT / "config" / "powerunits_github_knowledge.json"
_TOKEN_ENV = "POWERUNITS_GITHUB_TOKEN_READ"
_TOKEN_ENV_LEGACY = "POWERUNITS_GITHUB_DOCS_TOKEN"


def knowledge_config_path() -> Path:
    override = os.getenv("HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG", "").strip()
    if override:
        return Path(override).resolve()
    return _DEFAULT_KNOWLEDGE_CONFIG.resolve()


def doc_key_allowlist_path() -> Path:
    """JSON with entries[].key and entries[].source_relative (repo-relative paths)."""
    override = os.getenv("HERMES_POWERUNITS_DOC_KEY_ALLOWLIST", "").strip()
    if override:
        return Path(override).resolve()
    cfg = load_knowledge_config()
    rel = str(cfg.get("doc_key_allowlist_relative", "scripts/powerunits_docs_allowlist.json")).strip()
    return (_REPO_ROOT / rel).resolve()


def load_knowledge_config() -> dict[str, Any]:
    p = knowledge_config_path()
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("knowledge config root must be object")
    surfaces = raw.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        raise ValueError("knowledge config: surfaces must be non-empty list")
    return raw


def load_surfaces() -> dict[str, dict[str, Any]]:
    raw = load_knowledge_config()
    surfaces = raw.get("surfaces")
    assert isinstance(surfaces, list)
    out: dict[str, dict[str, Any]] = {}
    for item in surfaces:
        if not isinstance(item, dict):
            raise ValueError("surface must be object")
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
        }
    return out


def resolve_surface_for_repo_path(repo_relative_path: str) -> dict[str, Any]:
    """Pick the longest enabled root_prefix that is a prefix of repo_relative_path."""
    path = str(repo_relative_path).strip().replace("\\", "/").strip("/")
    best: dict[str, Any] | None = None
    best_len = -1
    for s in load_surfaces().values():
        if not s.get("enabled"):
            continue
        root = str(s["root_prefix"]).strip().strip("/")
        if path == root or path.startswith(root + "/"):
            ln = len(root)
            if ln > best_len:
                best_len = ln
                best = s
    if best is None:
        raise ValueError("path is not under any enabled allowlisted surface root")
    return best


def _headers(token: str, *, raw: bool = False) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "hermes-powerunits-github-knowledge/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    if raw:
        h["Accept"] = "application/vnd.github.v3.raw"
    return h


def github_token() -> str:
    t = os.getenv(_TOKEN_ENV, "").strip()
    if t:
        return t
    return os.getenv(_TOKEN_ENV_LEGACY, "").strip()


def github_branch_tip_sha(repo: str, branch: str, token: str) -> str | None:
    url = f"https://api.github.com/repos/{quote(repo, safe='/')}/commits/{quote(branch, safe='')}"
    try:
        req = Request(url, headers=_headers(token), method="GET")
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict):
            sha = data.get("sha")
            if isinstance(sha, str) and len(sha) >= 7:
                return sha
    except (HTTPError, URLError, OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def github_fetch_raw_file(repo: str, branch: str, api_path: str, token: str) -> str:
    url = (
        f"https://api.github.com/repos/{quote(repo, safe='/')}/contents/"
        f"{quote(api_path, safe='/')}?ref={quote(branch, safe='')}"
    )
    req = Request(url, headers=_headers(token, raw=True), method="GET")
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def github_fetch_json(repo: str, branch: str, api_path: str, token: str) -> Any:
    url = (
        f"https://api.github.com/repos/{quote(repo, safe='/')}/contents/"
        f"{quote(api_path, safe='/')}?ref={quote(branch, safe='')}"
    )
    req = Request(url, headers=_headers(token), method="GET")
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_github_knowledge_available() -> bool:
    try:
        load_knowledge_config()
        doc_key_allowlist_path()
        load_doc_key_entries()
    except Exception as exc:
        logger.warning("Powerunits GitHub knowledge config invalid: %s", exc)
        return False
    if not github_token():
        return False
    return True


def load_doc_key_entries() -> dict[str, dict[str, Any]]:
    p = doc_key_allowlist_path()
    raw = json.loads(p.read_text(encoding="utf-8"))
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("doc key allowlist: entries must be non-empty list")
    by_key: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        rel = item.get("source_relative")
        if not isinstance(key, str) or not isinstance(rel, str):
            continue
        by_key[key] = item
    if not by_key:
        raise ValueError("doc key allowlist: no valid entries")
    return by_key


def normalize_subpath(value: str | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip().replace("\\", "/").strip("/")
    if not raw:
        return ""
    if raw.startswith("/") or ".." in PurePosixPath(raw).parts:
        raise ValueError("subpath escapes allowlisted root")
    return raw


def log_powerunits_docs_read(
    *,
    source: str,
    repo: str,
    branch: str,
    commit_sha: str | None,
    alias: str,
    relative_path: str,
    key: str | None = None,
    extra: str | None = None,
) -> None:
    msg = (
        "powerunits_docs_read repo=%s branch=%s commit_sha=%s alias=%s relative_path=%s "
        "source=%s key=%s"
        % (
            repo,
            branch,
            commit_sha or "unknown",
            alias,
            relative_path,
            source,
            key or "",
        )
    )
    if extra:
        msg += f" extra={extra}"
    logger.info(msg)


def extension_allowed(path: str, allowed: tuple[str, ...]) -> bool:
    low = path.lower()
    return any(low.endswith(ext) for ext in allowed)
