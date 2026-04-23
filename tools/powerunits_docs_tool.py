#!/usr/bin/env python3
"""
Powerunits allowlisted documentation reader (manifest-keyed, read-only).

Primary knowledge path: GitHub (Kiron030/Powerunits.io, branch starting_the_seven_phases)
for paths declared in the doc-key allowlist (see config/powerunits_github_knowledge.json).

Secondary / degraded: bundled snapshot under docker/powerunits_docs/ (build-time only).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


class _BundleIntegrityError(Exception):
    """Bundled file SHA256 does not match MANIFEST.json."""


_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*\.md$")
_DEFAULT_MAX_OUT = 16_000
_ABS_MAX_OUT = 32_000
_ABS_MIN_OUT = 2_000

_DEFAULT_LIST_STALE_DAYS = 30
_TIER_STALE_DEFAULTS = {"stable": 90, "medium": 30, "volatile": 14}

_BUNDLED_DOCS_NOTICE = (
    "Content is from bundled allowlisted documentation (build-time snapshot), "
    "not live GitHub or database state."
)
_GITHUB_PRIMARY_NOTICE = (
    "Content is from allowlisted GitHub docs (primary Hermes knowledge path for Powerunits)."
)
_BUNDLE_UNAVAILABLE_WARNED = False
_LEGACY_BUNDLED_DOCS_NOTICE = (
    "Powerunits bundled docs reader is unavailable (legacy optional surface). "
    "Primary docs access is allowlisted GitHub read when a token is configured."
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _docs_source_mode() -> str:
    raw = os.getenv("HERMES_POWERUNITS_DOCS_SOURCE", "auto").strip().lower()
    if raw in ("auto", "github", "bundle"):
        return raw
    return "auto"


def _parse_generated_at(meta: dict[str, Any]) -> datetime | None:
    ga = meta.get("generated_at")
    if not isinstance(ga, str) or not ga.strip():
        return None
    text = ga.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _bundle_age_days(meta: dict[str, Any]) -> float | None:
    gen = _parse_generated_at(meta)
    if gen is None:
        return None
    if gen.tzinfo is None:
        gen = gen.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - gen
    return max(0.0, delta.total_seconds() / 86400.0)


def _tier_threshold_days(tier: str | None) -> int:
    t = (tier or "medium").strip().lower()
    if t not in _TIER_STALE_DEFAULTS:
        t = "medium"
    env_name = {
        "stable": "HERMES_POWERUNITS_DOCS_STALE_DAYS_STABLE",
        "medium": "HERMES_POWERUNITS_DOCS_STALE_DAYS_MEDIUM",
        "volatile": "HERMES_POWERUNITS_DOCS_STALE_DAYS_VOLATILE",
    }[t]
    return _env_int(env_name, _TIER_STALE_DEFAULTS[t])


def _list_stale_warning(age_days: float | None) -> str | None:
    if age_days is None:
        return None
    thr = _env_int("HERMES_POWERUNITS_DOCS_STALE_WARNING_DAYS", _DEFAULT_LIST_STALE_DAYS)
    if age_days > thr:
        return (
            f"Bundle snapshot is about {age_days:.0f} days old (threshold {thr}d). "
            "Treat as historical documentation; re-bundle and redeploy for current truth."
        )
    return None


def _read_stale_warning(age_days: float | None, tier: str | None) -> str | None:
    if age_days is None:
        return None
    thr = _tier_threshold_days(tier)
    if age_days > thr:
        label = (tier or "medium").strip().lower()
        return (
            f"freshness_tier={label}: bundle age ~{age_days:.0f}d exceeds soft threshold "
            f"({thr}d). Be cautious claiming current production truth; verify externally if needed."
        )
    return None


def _bundle_freshness_fields(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fld in (
        "generated_at",
        "source_repo_name",
        "source_repo_commit",
        "source_repo_branch",
        "source_ref",
        "bundle_version",
        "allowlist_version",
    ):
        val = meta.get(fld)
        if val is not None and isinstance(val, (str, int, float, bool)):
            out[fld] = val
    age = _bundle_age_days(meta)
    if age is not None:
        out["bundle_age_days"] = round(age, 2)
    sw = _list_stale_warning(age)
    if sw:
        out["stale_warning"] = sw
    return out


def _bundle_root() -> Path:
    override = os.getenv("HERMES_POWERUNITS_DOCS_BUNDLE", "").strip()
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent / "docker" / "powerunits_docs"


def _load_manifest(bundle: Path) -> dict[str, Any]:
    manifest_path = bundle / "MANIFEST.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("MANIFEST.json root must be an object")
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("MANIFEST.json must contain a non-empty entries list")
    by_key: dict[str, dict[str, Any]] = {}
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("each manifest entry must be an object")
        key = item.get("key")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise ValueError(f"invalid manifest key: {key!r}")
        if key in by_key:
            raise ValueError(f"duplicate manifest key: {key!r}")
        by_key[key] = item
    return {"meta": raw, "by_key": by_key}


def _bundle_requirements_ok() -> bool:
    global _BUNDLE_UNAVAILABLE_WARNED
    try:
        bundle = _bundle_root()
        if not bundle.is_dir():
            return False
        data = _load_manifest(bundle)
        root = bundle.resolve()
        for key in data["by_key"]:
            path = (bundle / key).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                return False
            if not path.is_file():
                return False
        return True
    except Exception:
        return False


def _github_doc_read_eligible() -> bool:
    try:
        from tools.powerunits_github_knowledge import (
            check_github_knowledge_available,
            doc_key_allowlist_path,
            load_doc_key_entries,
        )

        doc_key_allowlist_path()
        load_doc_key_entries()
    except Exception:
        return False
    return check_github_knowledge_available()


def check_powerunits_docs_requirements() -> bool:
    """Expose read_powerunits_doc when GitHub primary is available OR bundled snapshot is valid."""
    global _BUNDLE_UNAVAILABLE_WARNED
    if _github_doc_read_eligible():
        _BUNDLE_UNAVAILABLE_WARNED = False
        return True
    if _bundle_requirements_ok():
        _BUNDLE_UNAVAILABLE_WARNED = False
        return True
    if not _BUNDLE_UNAVAILABLE_WARNED:
        logger.info(
            "%s Configure POWERUNITS_GITHUB_TOKEN_READ and valid "
            "config/powerunits_github_knowledge.json + doc-key allowlist, "
            "or ship docker/powerunits_docs with MANIFEST.json.",
            _LEGACY_BUNDLED_DOCS_NOTICE,
        )
        _BUNDLE_UNAVAILABLE_WARNED = True
    return False


def _read_from_github(key: str, entry: dict[str, Any], max_out: int) -> dict[str, Any]:
    from tools.powerunits_github_knowledge import (
        extension_allowed,
        github_branch_tip_sha,
        github_fetch_raw_file,
        github_token,
        log_powerunits_docs_read,
        resolve_surface_for_repo_path,
    )

    token = github_token()
    if not token:
        raise RuntimeError("missing_token")

    rel = str(entry.get("source_relative", "")).strip().replace("\\", "/")
    if not rel or ".." in rel.split("/"):
        raise ValueError("bad source_relative")
    surface = resolve_surface_for_repo_path(rel)
    if not extension_allowed(rel, tuple(surface["allowed_extensions"])):
        raise ValueError("extension not allowed")

    root = str(surface["root_prefix"]).strip().strip("/")
    if not (rel == root or rel.startswith(root + "/")):
        raise ValueError("path outside surface root")

    try:
        text = github_fetch_raw_file(str(surface["repo"]), str(surface["branch"]), rel, token)
    except HTTPError as e:
        raise RuntimeError(f"github_http:{e.code}") from e
    except URLError as e:
        raise RuntimeError(f"github_net:{e}") from e

    truncated = len(text) > max_out
    if truncated:
        text = text[:max_out] + "\n\n[truncated to max_output_chars; use a smaller doc excerpt or raise max_output_chars within cap]"

    sha = github_branch_tip_sha(str(surface["repo"]), str(surface["branch"]), token)
    log_powerunits_docs_read(
        source="github_primary",
        repo=str(surface["repo"]),
        branch=str(surface["branch"]),
        commit_sha=sha,
        alias=str(surface["alias"]),
        relative_path=rel,
        key=key,
        extra="tool=read_powerunits_doc",
    )

    meta = entry
    tier = meta.get("freshness_tier") if isinstance(meta.get("freshness_tier"), str) else None
    payload: dict[str, Any] = {
        "key": key,
        "source_relative": rel,
        "chars_returned": len(text),
        "truncated": truncated,
        "content": text,
        "knowledge_actual_source": "github_primary",
        "knowledge_source_notice": _GITHUB_PRIMARY_NOTICE,
        "github_repo": surface["repo"],
        "github_branch": surface["branch"],
        "github_commit_sha": sha,
        "allowlist_surface_alias": surface["alias"],
    }
    for fld in ("doc_class", "freshness_tier", "summary"):
        val = meta.get(fld)
        if isinstance(val, str) and val.strip():
            payload[fld] = val.strip()
    if tier:
        payload["freshness_tier"] = tier
    return payload


def _read_from_bundle(
    key: str,
    by_key: dict[str, dict[str, Any]],
    bundle: Path,
    bundle_meta: dict[str, Any],
    max_out: int,
    *,
    fallback_reason: str,
) -> dict[str, Any]:
    meta = by_key[key]
    path = (bundle / key).resolve()
    try:
        path.relative_to(bundle.resolve())
    except ValueError as exc:
        raise ValueError("path_escape") from exc
    if not path.is_file():
        raise FileNotFoundError("missing_in_bundle")

    body = path.read_bytes()
    expected = meta.get("sha256")
    if isinstance(expected, str) and len(expected) == 64:
        actual = hashlib.sha256(body).hexdigest()
        if actual.lower() != expected.lower():
            raise _BundleIntegrityError("sha256 mismatch")

    text = body.decode("utf-8", errors="replace")
    truncated = len(text) > max_out
    if truncated:
        text = text[:max_out] + "\n\n[truncated to max_output_chars; use a smaller doc excerpt or raise max_output_chars within cap]"

    age_days = _bundle_age_days(bundle_meta)
    tier = meta.get("freshness_tier") if isinstance(meta.get("freshness_tier"), str) else None
    read_warn = _read_stale_warning(age_days, tier)

    surface_alias = "bundled_manifest"
    repo = str(bundle_meta.get("source_repo_name", "bundled"))
    branch = str(bundle_meta.get("source_repo_branch", "unknown"))
    sha = bundle_meta.get("source_repo_commit")
    sha_s = sha if isinstance(sha, str) and len(sha) >= 7 else None
    rel = str(meta.get("source_relative", key))

    from tools.powerunits_github_knowledge import log_powerunits_docs_read

    log_powerunits_docs_read(
        source="bundled_fallback",
        repo=repo,
        branch=branch,
        commit_sha=sha_s,
        alias=surface_alias,
        relative_path=rel,
        key=key,
        extra=f"tool=read_powerunits_doc reason={fallback_reason}",
    )

    payload: dict[str, Any] = {
        "key": key,
        "source_relative": meta.get("source_relative"),
        "chars_returned": len(text),
        "truncated": truncated,
        "sha256_verified": bool(isinstance(expected, str) and len(expected) == 64),
        "content": text,
        "bundled_docs_notice": _BUNDLED_DOCS_NOTICE,
        "knowledge_actual_source": "bundled_fallback",
        "knowledge_source_notice": _BUNDLED_DOCS_NOTICE,
        "bundled_fallback_reason": fallback_reason,
        "bundled_fallback_explicit": True,
        "github_repo": None,
        "github_branch": None,
        "github_commit_sha": None,
        "allowlist_surface_alias": surface_alias,
    }
    ga = bundle_meta.get("generated_at")
    if isinstance(ga, str):
        payload["bundle_generated_at"] = ga
    if age_days is not None:
        payload["bundle_age_days"] = round(age_days, 2)
    for fld in ("doc_class", "freshness_tier", "summary"):
        val = meta.get(fld)
        if isinstance(val, str) and val.strip():
            payload[fld] = val.strip()
    if read_warn:
        payload["stale_warning"] = read_warn
    return payload


def read_powerunits_doc(
    action: str,
    key: str | None = None,
    max_output_chars: int | None = None,
    **_: Any,
) -> str:
    from tools.powerunits_github_knowledge import load_doc_key_entries
    from tools.registry import tool_error

    action = (action or "").strip().lower()
    if action not in {"read", "list_keys"}:
        return tool_error('Invalid action. Use "read" or "list_keys".')

    limit = max_output_chars if max_output_chars is not None else _DEFAULT_MAX_OUT
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_MAX_OUT
    limit = max(_ABS_MIN_OUT, min(limit, _ABS_MAX_OUT))

    mode = _docs_source_mode()

    if action == "list_keys":
        keys: list[str] = []
        primary_hint = "bundled_manifest_only"
        gh_meta: dict[str, Any] = {}
        try:
            entries = load_doc_key_entries()
            keys = sorted(entries.keys())
            primary_hint = (
                "github_primary_when_token_configured"
                if _github_doc_read_eligible()
                else "github_configured_token_missing_use_bundle_or_token"
            )
            from tools.powerunits_github_knowledge import github_token, load_surfaces

            if github_token():
                s = next(iter(load_surfaces().values()))
                gh_meta = {
                    "github_repo": s.get("repo"),
                    "github_branch": s.get("branch"),
                }
        except Exception:
            keys = []

        if not keys:
            try:
                bundle = _bundle_root()
                data = _load_manifest(bundle)
                keys = sorted(data["by_key"])
                primary_hint = "bundled_manifest_only_no_allowlist_keys"
            except Exception:
                return tool_error(
                    "No doc keys available (allowlist unreadable and bundle missing).",
                    error_code="no_keys",
                )

        payload: dict[str, Any] = {
            "surface": "powerunits_doc_key_manifest",
            "key_style": "manifest_filename_with_md_suffix",
            "keys": keys,
            "count": len(keys),
            "primary_knowledge_path": "github_allowlisted_docs",
            "primary_knowledge_policy": (
                "Hermes Growth v1: GitHub docs (Kiron030/Powerunits.io, branch "
                "starting_the_seven_phases) are the default read path when "
                "POWERUNITS_GITHUB_TOKEN_READ is set. Bundled docker/powerunits_docs is "
                "legacy fallback / degraded mode only."
            ),
            "list_keys_primary_hint": primary_hint,
        }
        payload.update(gh_meta)
        try:
            bundle = _bundle_root()
            data = _load_manifest(bundle)
            meta = data["meta"]
            payload["bundled_snapshot_freshness"] = _bundle_freshness_fields(meta)
            payload["bundled_docs_notice"] = _BUNDLED_DOCS_NOTICE
        except Exception:
            payload["bundled_snapshot_freshness"] = {}
        return json.dumps(payload, ensure_ascii=False)

    # --- read ---
    if not key or not str(key).strip():
        return tool_error(
            "Parameter key is required for action=read (manifest file name, e.g. implementation_state.md).",
            error_code="key_required",
        )
    key = str(key).strip()
    if not _KEY_RE.match(key):
        return tool_error(
            "Invalid key format. Only manifest keys like implementation_state.md are accepted.",
            error_code="invalid_key_format",
        )

    try:
        entries = load_doc_key_entries()
    except Exception as exc:
        entries = {}
    meta = entries.get(key)
    if meta is None:
        return tool_error(
            f"Unknown manifest key {key!r}: not on the Powerunits docs allowlist.",
            error_code="unknown_key_not_allowlisted",
            known_key_count=len(entries),
        )

    if mode == "bundle":
        try:
            bundle = _bundle_root()
            data = _load_manifest(bundle)
            if key not in data["by_key"]:
                return tool_error(
                    f"Key {key!r} not present in bundle (bundle-only mode).",
                    error_code="missing_in_bundle",
                )
            out = _read_from_bundle(
                key,
                data["by_key"],
                bundle,
                data["meta"],
                limit,
                fallback_reason="HERMES_POWERUNITS_DOCS_SOURCE=bundle",
            )
            return json.dumps(out, ensure_ascii=False)
        except _BundleIntegrityError:
            return tool_error(
                "SHA256 mismatch: bundled file does not match MANIFEST.json (do not trust this file).",
                error_code="integrity_failure",
            )
        except Exception as exc:
            return tool_error(f"Bundle read failed: {exc}", error_code="bundle_read_failed")

    if mode == "github":
        try:
            out = _read_from_github(key, meta, limit)
            return json.dumps(out, ensure_ascii=False)
        except Exception as exc:
            return tool_error(
                f"GitHub primary read failed ({exc}).",
                error_code="github_read_failed",
            )

    # --- auto: GitHub first when token + config, else bundle; GitHub failure -> explicit bundle fallback ---
    if _github_doc_read_eligible():
        try:
            out = _read_from_github(key, meta, limit)
            return json.dumps(out, ensure_ascii=False)
        except Exception as gh_exc:
            if _bundle_requirements_ok():
                try:
                    bundle = _bundle_root()
                    data = _load_manifest(bundle)
                    if key in data["by_key"]:
                        out = _read_from_bundle(
                            key,
                            data["by_key"],
                            bundle,
                            data["meta"],
                            limit,
                            fallback_reason=f"github_primary_failed:{gh_exc!s}",
                        )
                        return json.dumps(out, ensure_ascii=False)
                except _BundleIntegrityError:
                    return tool_error(
                        "SHA256 mismatch: bundled file does not match MANIFEST.json (do not trust this file).",
                        error_code="integrity_failure",
                    )
                except Exception:
                    pass
            return tool_error(
                f"GitHub primary read failed ({gh_exc!s}) and bundle fallback unavailable.",
                error_code="github_read_failed",
            )

    if _bundle_requirements_ok():
        try:
            bundle = _bundle_root()
            data = _load_manifest(bundle)
            if key not in data["by_key"]:
                return tool_error(
                    f"Unknown key for bundle-only mode {key!r}.",
                    error_code="missing_in_bundle",
                )
            reason = (
                "missing_github_token_or_github_config"
                if not _github_doc_read_eligible()
                else "unreachable"
            )
            out = _read_from_bundle(
                key,
                data["by_key"],
                bundle,
                data["meta"],
                limit,
                fallback_reason=reason,
            )
            return json.dumps(out, ensure_ascii=False)
        except _BundleIntegrityError:
            return tool_error(
                "SHA256 mismatch: bundled file does not match MANIFEST.json (do not trust this file).",
                error_code="integrity_failure",
            )
        except Exception as exc:
            return tool_error(f"Bundle read failed: {exc}", error_code="bundle_read_failed")

    return tool_error(
        "Powerunits docs unavailable: configure GitHub token + knowledge config, "
        "or ship a valid docs bundle.",
        error_code="no_doc_source",
    )


READ_POWERUNITS_DOC_SCHEMA = {
    "name": "read_powerunits_doc",
    "description": (
        "Read-only **doc-key manifest** Powerunits documentation (keys like "
        "`implementation_state.md`, `runbook.md`). "
        "**Primary path:** GitHub (`Kiron030/Powerunits.io`, branch `starting_the_seven_phases`) "
        "for keys listed in the doc-key allowlist (see `config/powerunits_github_knowledge.json`). "
        "**Do not use this tool** for Repo B implementation allowlist reads "
        "(snake_case keys such as `job_market_feature`, Python paths under `backend/`): "
        "use **`read_powerunits_repo_b_allowlisted`** with `list_repo_b_keys` / `read_repo_b_key`. "
        "**Fallback:** bundled snapshot under `docker/powerunits_docs/` when GitHub is "
        "unavailable or after explicit degraded use — manifest keys only, never filesystem paths."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "list_keys"],
                "description": (
                    "read: fetch one doc by **manifest** key (*.md name). "
                    "list_keys: list **doc manifest** keys only (see response surface=powerunits_doc_key_manifest). "
                    "Not for Repo B allowlist snake_case keys — use read_powerunits_repo_b_allowlisted."
                ),
            },
            "key": {
                "type": "string",
                "description": (
                    "Required when action is read. Exact allowlist key "
                    "(e.g. roadmap.md, implementation_state.md)."
                ),
            },
            "max_output_chars": {
                "type": "integer",
                "description": (
                    f"Max characters of UTF-8 text to return for action=read "
                    f"(default {_DEFAULT_MAX_OUT}, hard cap {_ABS_MAX_OUT})."
                ),
            },
        },
        "required": ["action"],
    },
}


from tools.registry import registry

registry.register(
    name="read_powerunits_doc",
    toolset="powerunits_docs",
    schema=READ_POWERUNITS_DOC_SCHEMA,
    handler=lambda args, **kw: read_powerunits_doc(
        action=args.get("action", ""),
        key=args.get("key"),
        max_output_chars=args.get("max_output_chars"),
        **kw,
    ),
    check_fn=check_powerunits_docs_requirements,
    emoji="📚",
)
