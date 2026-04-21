#!/usr/bin/env python3
"""
Powerunits allowlisted documentation reader (manifest-keyed, read-only).

Reads only from docker/powerunits_docs/ next to the Hermes install root.
Lookup uses MANIFEST.json keys only — no arbitrary paths or model-supplied paths.
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

logger = logging.getLogger(__name__)

_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*\.md$")
_DEFAULT_MAX_OUT = 16_000
_ABS_MAX_OUT = 32_000
_ABS_MIN_OUT = 2_000

# Default soft-stale age (days) when no freshness_tier applies (list_keys).
_DEFAULT_LIST_STALE_DAYS = 30
# Per-tier defaults (days) for action=read; overridable via env HERMES_POWERUNITS_DOCS_STALE_DAYS_<TIER>.
_TIER_STALE_DEFAULTS = {"stable": 90, "medium": 30, "volatile": 14}

_BUNDLED_DOCS_NOTICE = (
    "Content is from bundled allowlisted documentation (build-time snapshot), "
    "not live monorepo or database state."
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


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
    """Safe, model-facing bundle metadata (no filesystem paths)."""
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
    # tools/ -> repo install root (e.g. /opt/hermes in Docker)
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


def check_powerunits_docs_requirements() -> bool:
    """Expose the bundled docs surface only when manifest and files are present."""
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
    except Exception as exc:
        logger.debug("powerunits docs bundle unavailable: %s", exc)
        return False


def read_powerunits_doc(
    action: str,
    key: str | None = None,
    max_output_chars: int | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    action = (action or "").strip().lower()
    if action not in {"read", "list_keys"}:
        return tool_error('Invalid action. Use "read" or "list_keys".')

    bundle = _bundle_root()
    if not bundle.is_dir():
        return tool_error(
            "Powerunits docs bundle directory is missing.",
            error_code="bundle_missing",
        )

    try:
        data = _load_manifest(bundle)
    except FileNotFoundError:
        return tool_error(
            "MANIFEST.json is missing from the Powerunits docs bundle.",
            error_code="manifest_missing",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return tool_error(
            f"Invalid MANIFEST.json: {exc}",
            error_code="manifest_invalid",
        )

    by_key: dict[str, dict[str, Any]] = data["by_key"]

    if action == "list_keys":
        keys = sorted(by_key)
        meta = data["meta"]
        payload: dict[str, Any] = {
            "keys": keys,
            "count": len(keys),
            "bundled_docs_notice": _BUNDLED_DOCS_NOTICE,
        }
        payload.update(_bundle_freshness_fields(meta))
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

    meta = by_key.get(key)
    if meta is None:
        return tool_error(
            f"Unknown manifest key {key!r}: not on the Powerunits docs allowlist.",
            error_code="unknown_key_not_allowlisted",
            known_key_count=len(by_key),
        )

    path = (bundle / key).resolve()
    try:
        path.relative_to(bundle.resolve())
    except ValueError:
        return tool_error(
            "Resolved path left the bundle directory (rejected).",
            error_code="path_escape",
        )

    if not path.is_file():
        return tool_error(
            f"Bundled file for key {key!r} is missing on disk (bundle incomplete or corrupt).",
            error_code="missing_in_bundle",
        )

    body = path.read_bytes()
    expected = meta.get("sha256")
    if isinstance(expected, str) and len(expected) == 64:
        actual = hashlib.sha256(body).hexdigest()
        if actual.lower() != expected.lower():
            return tool_error(
                "SHA256 mismatch: bundled file does not match MANIFEST.json (do not trust this file).",
                error_code="integrity_failure",
                expected_prefix=expected[:12],
                actual_prefix=actual[:12],
            )

    limit = max_output_chars if max_output_chars is not None else _DEFAULT_MAX_OUT
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = _DEFAULT_MAX_OUT
    limit = max(_ABS_MIN_OUT, min(limit, _ABS_MAX_OUT))

    text = body.decode("utf-8", errors="replace")
    truncated = len(text) > limit
    if truncated:
        text = text[:limit] + "\n\n[truncated to max_output_chars; use a smaller doc excerpt or raise max_output_chars within cap]"

    bundle_meta = data["meta"]
    age_days = _bundle_age_days(bundle_meta)
    tier = meta.get("freshness_tier") if isinstance(meta.get("freshness_tier"), str) else None
    read_warn = _read_stale_warning(age_days, tier)

    payload: dict[str, Any] = {
        "key": key,
        "source_relative": meta.get("source_relative"),
        "chars_returned": len(text),
        "truncated": truncated,
        "sha256_verified": bool(isinstance(expected, str) and len(expected) == 64),
        "content": text,
        "bundled_docs_notice": _BUNDLED_DOCS_NOTICE,
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

    return json.dumps(payload, ensure_ascii=False)


READ_POWERUNITS_DOC_SCHEMA = {
    "name": "read_powerunits_doc",
    "description": (
        "Read-only access to **allowlisted Powerunits documentation** shipped inside "
        "this Hermes image. Use **manifest keys only** (flat filenames like "
        "`implementation_state.md`) — never filesystem paths. "
        'Use action=list_keys to list allowed keys plus bundle freshness metadata. '
        "Does not access the live monorepo, database, or arbitrary files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "list_keys"],
                "description": 'read: fetch one doc by manifest key; list_keys: return all allowed keys.',
            },
            "key": {
                "type": "string",
                "description": (
                    "Required when action is read. Exact manifest key "
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
