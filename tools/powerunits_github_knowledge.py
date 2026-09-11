"""
Central Powerunits GitHub knowledge configuration and read helpers.

Used by read_powerunits_doc (primary GitHub path) and powerunits_github_docs_tool.
No secrets in-repo; token from POWERUNITS_GITHUB_TOKEN_READ (or legacy POWERUNITS_GITHUB_DOCS_TOKEN).

All reads are pinned to an immutable reviewed commit (``approved_ref``, 40 lowercase hex).
Moving branch names are rejected fail-closed; repinning requires a separate reviewed decision.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KNOWLEDGE_CONFIG = _REPO_ROOT / "config" / "powerunits_github_knowledge.json"
_TOKEN_ENV = "POWERUNITS_GITHUB_TOKEN_READ"
_TOKEN_ENV_LEGACY = "POWERUNITS_GITHUB_DOCS_TOKEN"

_SHA40_RE = re.compile(r"[0-9a-f]{40}")
_READ_SOURCES = ("github", "bundle")

# Uniform provenance block present on every Powerunits read/list payload.
PROVENANCE_FIELDS = (
    "read_sha",
    "read_commit_time",
    "read_age_days",
    "read_is_current_or_approved",
    "read_source",
    "read_provenance_complete",
)


class PinnedRefError(ValueError):
    """Config does not pin reads to an immutable 40-hex commit SHA (fail closed)."""


def is_pinned_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA40_RE.fullmatch(value) is not None


def validate_pinned_ref(
    value: Any,
    *,
    context: str,
    field: str = "ref",
    legacy_branch: Any = None,
) -> str:
    """Return ``value`` if it is a 40 lowercase hex commit SHA; raise PinnedRefError otherwise.

    ``legacy_branch`` is read only to produce a clear error; it is never usable as a ref.
    """
    if legacy_branch is not None:
        raise PinnedRefError(
            f"{context}: legacy moving 'branch' ({str(legacy_branch)[:80]!r}) is not a usable read ref; "
            f"remove it and configure an immutable '{field}' (40 lowercase hex commit SHA)"
        )
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PinnedRefError(f"{context}: missing '{field}' (40 lowercase hex commit SHA required)")
    if not is_pinned_sha(value):
        raise PinnedRefError(
            f"{context}: '{field}' {str(value)[:80]!r} is not a 40 lowercase hex commit SHA "
            "(branch names, tags and short SHAs are rejected)"
        )
    return value


def parse_commit_time(value: Any) -> datetime | None:
    """ISO-8601 timestamp with explicit UTC offset -> aware datetime; None otherwise."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt


def load_approved_pin(raw: dict[str, Any], *, context: str) -> tuple[str, str]:
    """Validate top-level ``approved_ref`` + ``approved_ref_commit_time`` of a config root."""
    ref = validate_pinned_ref(raw.get("approved_ref"), context=context, field="approved_ref")
    commit_time = raw.get("approved_ref_commit_time")
    if parse_commit_time(commit_time) is None:
        raise PinnedRefError(
            f"{context}: 'approved_ref_commit_time' must be ISO-8601 with UTC offset "
            f"(got {str(commit_time)[:64]!r})"
        )
    return ref, str(commit_time).strip()


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
    load_approved_pin(raw, context="knowledge config")
    return raw


def load_knowledge_pin() -> tuple[str, str]:
    """(approved_ref, approved_ref_commit_time) from the knowledge config (fail closed)."""
    return load_approved_pin(load_knowledge_config(), context="knowledge config")


def load_surfaces() -> dict[str, dict[str, Any]]:
    raw = load_knowledge_config()
    surfaces = raw.get("surfaces")
    assert isinstance(surfaces, list)
    approved_ref, _ = load_approved_pin(raw, context="knowledge config")
    out: dict[str, dict[str, Any]] = {}
    for item in surfaces:
        if not isinstance(item, dict):
            raise ValueError("surface must be object")
        alias = str(item.get("alias", "")).strip()
        repo = str(item.get("repo", "")).strip()
        root = str(item.get("root_prefix", "")).strip().strip("/")
        exts = item.get("allowed_extensions")
        enabled = bool(item.get("enabled", False))
        if not alias:
            raise ValueError("surface alias missing")
        if not repo or "/" not in repo:
            raise ValueError(f"surface {alias}: invalid repo")
        ref = validate_pinned_ref(
            item.get("ref"),
            context=f"surface {alias}",
            legacy_branch=item.get("branch"),
        )
        if ref != approved_ref:
            raise PinnedRefError(
                f"surface {alias}: 'ref' {ref} differs from approved_ref {approved_ref}; "
                "only the approved commit is readable"
            )
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
            "ref": ref,
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


def _contents_url(repo: str, ref: str, api_path: str) -> str:
    validate_pinned_ref(ref, context="github contents read")
    return (
        f"https://api.github.com/repos/{quote(repo, safe='/')}/contents/"
        f"{quote(api_path, safe='/')}?ref={ref}"
    )


def github_fetch_raw_file(repo: str, ref: str, api_path: str, token: str) -> str:
    req = Request(_contents_url(repo, ref, api_path), headers=_headers(token, raw=True), method="GET")
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def github_fetch_json(repo: str, ref: str, api_path: str, token: str) -> Any:
    req = Request(_contents_url(repo, ref, api_path), headers=_headers(token), method="GET")
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_read_provenance(
    *,
    read_sha: Any,
    read_commit_time: Any,
    approved_ref: Any,
    read_source: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Uniform provenance block (see PROVENANCE_FIELDS); never contains credentials."""
    if read_source not in _READ_SOURCES:
        raise ValueError(f"read_source must be one of {_READ_SOURCES}")
    sha = read_sha if is_pinned_sha(read_sha) else None
    approved = approved_ref if is_pinned_sha(approved_ref) else None
    commit_dt = parse_commit_time(read_commit_time)
    age_days: float | None = None
    if commit_dt is not None:
        ref_now = now or datetime.now(timezone.utc)
        age_days = round(max(0.0, (ref_now - commit_dt).total_seconds() / 86400.0), 2)
    complete = bool(sha and approved and commit_dt is not None)
    return {
        "read_sha": sha,
        "read_commit_time": str(read_commit_time).strip() if commit_dt is not None else None,
        "read_age_days": age_days,
        # Incomplete provenance (e.g. old-format bundle without commit time) never counts as approved.
        "read_is_current_or_approved": bool(complete and sha == approved),
        "read_source": read_source,
        "read_provenance_complete": complete,
    }


def github_read_provenance(
    *,
    read_sha: str,
    approved_ref: str | None,
    approved_ref_commit_time: str | None,
) -> dict[str, Any]:
    """Provenance for a GitHub read: READ_SHA is the pinned ref actually requested (no network).

    Loaders only admit ``ref == approved_ref``, so the commit time is the validated
    ``approved_ref_commit_time``; any other SHA gets no commit time (incomplete, not approved).
    """
    commit_time = approved_ref_commit_time if approved_ref is not None and read_sha == approved_ref else None
    return build_read_provenance(
        read_sha=read_sha,
        read_commit_time=commit_time,
        approved_ref=approved_ref,
        read_source="github",
    )


def pinned_listing_provenance(
    refs: list[str],
    *,
    approved_ref: str | None,
    approved_ref_commit_time: str | None,
) -> dict[str, Any]:
    """Provenance for a key listing built from config (no network): one shared ref or incomplete."""
    unique = set(refs)
    sha = next(iter(unique)) if len(unique) == 1 else None
    commit_time = approved_ref_commit_time if sha is not None and sha == approved_ref else None
    return build_read_provenance(
        read_sha=sha,
        read_commit_time=commit_time,
        approved_ref=approved_ref,
        read_source="github",
    )


def format_provenance_for_log(provenance: dict[str, Any]) -> str:
    return " ".join(f"{k}={provenance.get(k)}" for k in PROVENANCE_FIELDS)


def check_github_knowledge_available() -> bool:
    try:
        load_knowledge_config()
        load_surfaces()
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
    provenance: dict[str, Any] | None = None,
) -> None:
    """Log one read. ``branch`` carries the pinned ref requested (legacy field name)."""
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
    if provenance:
        msg += " " + format_provenance_for_log(provenance)
    if extra:
        msg += f" extra={extra}"
    logger.info(msg)


def extension_allowed(path: str, allowed: tuple[str, ...]) -> bool:
    low = path.lower()
    return any(low.endswith(ext) for ext in allowed)
