#!/usr/bin/env python3
"""
Tier 4A — bounded skill draft / proposal artifacts (Powerunits progressive posture).

Requires ``HERMES_POWERUNITS_CAPABILITY_TIER >= 4``. Writes are **only** under
``hermes_workspace/drafts/powerunits_skill_proposals/**`` — never ``$HERMES_HOME/skills``,
never live merge/apply, never Repo B mutation.

Canonical roadmap: ``docs/powerunits_hermes_progressive_posture_v1.md``.
Detail: ``docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tools.registry import registry

logger = logging.getLogger(__name__)

_REL_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}$")
_LEAF_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}\.(md|txt)$")
_MAX_REL_PARTS = 12
_MAX_BODY_CHARS = 120_000
_LIST_CAP = 2500
_STALE_DAYS = 30
_CAUTION_FILE_COUNT = 120
_CAUTION_TOTAL_BYTES = 20 * 1024 * 1024
_CAUTION_TOUCHED_24H = 28
_CAUTION_STALE_FILES = 45
_TIER4A_POINTER_NAME = "README_POWERUNITS_TIER4A.txt"
_TIER4A_POINTER_BODY = """Powerunits Hermes — Tier 4A skill draft proposals (operator pointer).

Canonical roadmap (do not fork): docs/powerunits_hermes_progressive_posture_v1.md
Tier 4A bounded writes + watchdog thresholds: docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md
Workspace layout: docs/powerunits_workspace_v1.md

Writes from Tier 4A tools land ONLY under this directory tree (hermes_workspace/drafts/powerunits_skill_proposals).
They are drafts — requires_human_review / not_auto_applied — and MUST NOT be treated as live skills.

Live skills remain under $HERMES_HOME/skills and are not modified by Tier 4A.
"""


def check_powerunits_tier4a_skill_draft_proposals() -> bool:
    from powerunits_capability_tier import read_powerunits_capability_tier

    return read_powerunits_capability_tier() >= 4


def _workspace_root() -> Path:
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    return (hermes_home / "hermes_workspace").resolve()


def _proposals_root() -> Path:
    return (_workspace_root() / "drafts" / "powerunits_skill_proposals").resolve()


def _ensure_proposals_tree() -> Path:
    root = _workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    drafts = (root / "drafts").resolve()
    drafts.mkdir(parents=True, exist_ok=True)
    proposals = (drafts / "powerunits_skill_proposals").resolve()
    proposals.mkdir(parents=True, exist_ok=True)
    _write_tier4a_pointer_if_missing(proposals)
    return proposals


def _write_tier4a_pointer_if_missing(proposals_dir: Path) -> None:
    try:
        marker = proposals_dir / _TIER4A_POINTER_NAME
        marker.resolve().relative_to(_workspace_root().resolve())
        if marker.exists():
            return
        marker.write_text(_TIER4A_POINTER_BODY.strip() + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.warning("Tier 4A pointer skipped: %s", exc)


def _normalize_rel(rel: str) -> str:
    s = str(rel or "").strip().replace("\\", "/").lstrip("/")
    parts_raw = [p for p in s.split("/") if p]
    if any(p == ".." for p in parts_raw):
        raise ValueError("path_contains_parent_segment")
    parts = [p for p in parts_raw if p != "."]
    return "/".join(parts)


def _validated_rel_path(rel: str) -> Path:
    """Return a relative Path under proposals root (POSIX-style parts)."""
    try:
        nrel = _normalize_rel(rel)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if not nrel:
        raise ValueError("relative_path_required")
    parts = nrel.split("/")
    if len(parts) > _MAX_REL_PARTS:
        raise ValueError("relative_path_too_deep")
    for seg in parts[:-1]:
        if not _REL_SEGMENT_RE.match(seg):
            raise ValueError(f"invalid_path_segment:{seg}")
    if not _LEAF_NAME_RE.match(parts[-1]):
        raise ValueError("invalid_leaf_name")
    return Path(*parts)


def _safe_target(rel_norm: str, proposals: Path) -> Path:
    """Resolve ``rel_norm`` strictly under ``proposals``."""
    rel_p = _validated_rel_path(rel_norm)
    out = (proposals / rel_p).resolve()
    out.relative_to(proposals)
    return out


def _is_bootstrap_pointer(fp: Path) -> bool:
    return fp.name == _TIER4A_POINTER_NAME


def _iter_proposal_files(proposals: Path, *, exclude_bootstrap_pointer: bool = False) -> list[Path]:
    if not proposals.is_dir():
        return []
    out: list[Path] = []
    for raw in sorted(proposals.rglob("*")):
        if not raw.is_file():
            continue
        try:
            raw.relative_to(proposals)
        except ValueError:
            continue
        if raw.is_symlink():
            continue
        if exclude_bootstrap_pointer and _is_bootstrap_pointer(raw):
            continue
        out.append(raw)
        if len(out) >= _LIST_CAP:
            break
    return out


def _prefix_ok(prefix: str, proposals: Path) -> bool:
    if not prefix.strip():
        return True
    try:
        p = _normalize_rel(prefix)
    except ValueError:
        return False
    if not p:
        return True
    base = (proposals / p).resolve()
    try:
        base.relative_to(proposals)
    except ValueError:
        return False
    return True


def manifest_powerunits_tier4a_skill_draft_scope(**_: Any) -> str:
    """Static JSON: bounded subtree + safety metadata."""

    from tools.registry import tool_error

    if not check_powerunits_tier4a_skill_draft_proposals():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=4 required for Tier 4A skill draft proposals overlay",
            error_code="tier_gate",
        )
    proposals = _ensure_proposals_tree()
    return json.dumps(
        {
            "read_only": True,
            "tier": "4a_skill_draft_proposals",
            "proposals_root_relative": "drafts/powerunits_skill_proposals",
            "proposals_root_resolved": str(proposals),
            "live_skills_directory_never_written": str(
                (Path(os.getenv("HERMES_HOME", "/opt/data")) / "skills").resolve()
            ),
            "requires_human_review": True,
            "not_auto_applied": True,
            "allowed_extensions": [".md", ".txt"],
            "max_body_chars_per_write": _MAX_BODY_CHARS,
            "max_list_entries": _LIST_CAP,
            "doc_hint": "docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def write_powerunits_skill_draft_proposal(
    relative_file_path: str,
    body: str,
    proposal_kind: str,
    *,
    target_skill_name: str | None = None,
    overwrite_mode: str = "forbid",
    **_: Any,
) -> str:
    """Write one draft file under the proposals root only."""

    from tools.registry import tool_error

    if not check_powerunits_tier4a_skill_draft_proposals():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=4 required for Tier 4A skill draft proposals overlay",
            error_code="tier_gate",
        )
    text = str(body if body is not None else "")
    if len(text) > _MAX_BODY_CHARS:
        return tool_error("body_too_large", error_code="limit_exceeded")

    kind = str(proposal_kind or "").strip()
    if kind not in {"skill_draft_md", "patch_style_diff_txt"}:
        return tool_error(
            "proposal_kind must be skill_draft_md or patch_style_diff_txt",
            error_code="invalid_kind",
        )
    omode = str(overwrite_mode or "forbid").strip().lower()
    if omode not in {"forbid", "overwrite"}:
        return tool_error("overwrite_mode must be forbid or overwrite", error_code="invalid_mode")

    proposals = _ensure_proposals_tree()
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _safe_target(nrel, proposals)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")

    if target.exists() and omode == "forbid":
        return tool_error("target_exists_use_overwrite_or_new_name", error_code="exists")

    tier_raw = os.getenv("HERMES_POWERUNITS_CAPABILITY_TIER", "")
    meta_lines = [
        "---",
        "powerunits_tier_4a_proposal: true",
        "requires_human_review: true",
        "not_auto_applied: true",
        f"proposal_kind: {kind}",
        f"created_at_utc: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"hermes_capability_tier_env_raw: {tier_raw!r}",
    ]
    slug = str(target_skill_name or "").strip()
    if slug:
        safe_slug = slug.replace("\n", " ").replace("\r", "")[:200]
        meta_lines.append(f"target_skill_name: {safe_slug!r}")

    meta_lines.append("---")

    stripped = text.lstrip()
    if stripped.startswith("---"):
        payload = text
    else:
        payload = "\n".join(meta_lines) + "\n\n" + text

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8", newline="\n")
    except OSError as exc:
        return tool_error(str(exc), error_code="write_failed")

    return json.dumps(
        {
            "read_only": False,
            "tier": "4a_skill_draft_proposals",
            "requires_human_review": True,
            "not_auto_applied": True,
            "path_relative_to_hermes_workspace": (Path("drafts") / "powerunits_skill_proposals")
            .joinpath(target.relative_to(proposals))
            .as_posix(),
            "bytes_written": len(payload.encode("utf-8")),
            "doc_hint": "docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def list_powerunits_skill_draft_proposals(
    subpath_prefix: str | None = None, **_: Any
) -> str:
    """List draft files with sizes and mtimes (bounded)."""

    from tools.registry import tool_error

    if not check_powerunits_tier4a_skill_draft_proposals():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=4 required for Tier 4A skill draft proposals overlay",
            error_code="tier_gate",
        )
    proposals = _ensure_proposals_tree()
    prefix = _normalize_rel(subpath_prefix or "")
    if not _prefix_ok(subpath_prefix or "", proposals):
        return tool_error("invalid subpath_prefix", error_code="invalid_prefix")

    base = proposals if not prefix else (proposals / prefix).resolve()
    try:
        base.relative_to(proposals)
    except ValueError:
        return tool_error("invalid subpath_prefix", error_code="invalid_prefix")

    rows: list[dict[str, Any]] = []
    if base.is_dir():
        for fp in sorted(base.rglob("*")):
            if not fp.is_file() or fp.is_symlink():
                continue
            try:
                rel = fp.relative_to(proposals).as_posix()
            except ValueError:
                continue
            st = fp.stat()
            rows.append(
                {
                    "relative_path": rel,
                    "size_bytes": st.st_size,
                    "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                }
            )
            if len(rows) >= _LIST_CAP:
                break

    return json.dumps(
        {
            "read_only": True,
            "tier": "4a_skill_draft_proposals",
            "listing_truncated": len(rows) >= _LIST_CAP,
            "entries": rows,
            "doc_hint": "docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def read_powerunits_skill_draft_proposal(relative_file_path: str, **_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier4a_skill_draft_proposals():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=4 required for Tier 4A skill draft proposals overlay",
            error_code="tier_gate",
        )
    proposals = _ensure_proposals_tree()
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _safe_target(nrel, proposals)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")

    if not target.is_file():
        return tool_error("not_found", error_code="not_found")
    try:
        body = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return tool_error(str(exc), error_code="read_failed")

    return json.dumps(
        {
            "read_only": True,
            "tier": "4a_skill_draft_proposals",
            "requires_human_review": True,
            "not_auto_applied": True,
            "path_relative_to_proposals_root": target.relative_to(proposals).as_posix(),
            "chars_returned": len(body),
            "body": body,
            "doc_hint": "docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def summarize_powerunits_skill_draft_proposals(**_: Any) -> str:
    """Proposal volume / stale / churn heuristics for operators."""

    from tools.registry import tool_error

    if not check_powerunits_tier4a_skill_draft_proposals():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=4 required for Tier 4A skill draft proposals overlay",
            error_code="tier_gate",
        )
    proposals = _ensure_proposals_tree()
    caution: list[str] = []

    files = _iter_proposal_files(proposals, exclude_bootstrap_pointer=True)
    now = datetime.now(timezone.utc)
    cutoff_stale = now - timedelta(days=_STALE_DAYS)
    cutoff_24h = now - timedelta(hours=24)

    total_bytes = 0
    stale_ct = 0
    touched_24h = 0
    largest: list[tuple[int, str]] = []

    for fp in files:
        try:
            st = fp.stat()
        except OSError:
            continue
        total_bytes += st.st_size
        mdt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        rel = fp.relative_to(proposals).as_posix()
        largest.append((st.st_size, rel))
        if mdt < cutoff_stale:
            stale_ct += 1
        if mdt >= cutoff_24h:
            touched_24h += 1

    largest.sort(key=lambda x: -x[0])
    largest = largest[:12]

    if len(files) >= _LIST_CAP:
        caution.append(f"tier4a_proposals_list_truncated_at_{_LIST_CAP}")
    if len(files) > _CAUTION_FILE_COUNT:
        caution.append(
            f"tier4a_draft_file_count_high:{len(files)}>threshold_{_CAUTION_FILE_COUNT}"
        )
    if total_bytes > _CAUTION_TOTAL_BYTES:
        caution.append(
            f"tier4a_draft_total_bytes_high:{total_bytes}>threshold_{_CAUTION_TOTAL_BYTES}"
        )
    if stale_ct > _CAUTION_STALE_FILES:
        caution.append(
            f"tier4a_many_stale_drafts:{stale_ct}>threshold_{_CAUTION_STALE_FILES}"
        )
    if touched_24h > _CAUTION_TOUCHED_24H:
        caution.append(
            f"tier4a_draft_churn_24h:{touched_24h}>threshold_{_CAUTION_TOUCHED_24H}"
        )

    return json.dumps(
        {
            "read_only": True,
            "tier": "4a_skill_draft_proposals",
            "proposal_file_count": len(files),
            "proposal_total_bytes": total_bytes,
            "stale_file_count_older_than_days": stale_ct,
            "stale_age_days_threshold": _STALE_DAYS,
            "touched_last_24h_count": touched_24h,
            "largest_files": [{"size_bytes": sz, "relative_path": p} for sz, p in largest],
            "thresholds": {
                "caution_file_count": _CAUTION_FILE_COUNT,
                "caution_total_bytes": _CAUTION_TOTAL_BYTES,
                "caution_touched_24h": _CAUTION_TOUCHED_24H,
                "caution_stale_files": _CAUTION_STALE_FILES,
            },
            "requires_human_review": True,
            "not_auto_applied": True,
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier4a_skill_draft_proposals_overlay_v1.md",
        },
        ensure_ascii=False,
    )


MANIFEST_SCHEMA = {
    "name": "manifest_powerunits_tier4a_skill_draft_scope",
    "description": (
        "Tier>=4: show bounded proposals/drafts root under hermes_workspace (never live skills)."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

WRITE_SCHEMA = {
    "name": "write_powerunits_skill_draft_proposal",
    "description": (
        "Tier>=4: write one draft under drafts/powerunits_skill_proposals only; "
        "never touches $HERMES_HOME/skills."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "relative_file_path": {"type": "string"},
            "proposal_kind": {
                "type": "string",
                "enum": ["skill_draft_md", "patch_style_diff_txt"],
            },
            "body": {"type": "string"},
            "target_skill_name": {"type": "string"},
            "overwrite_mode": {"type": "string", "enum": ["forbid", "overwrite"]},
        },
        "required": ["relative_file_path", "proposal_kind", "body"],
    },
}

LIST_SCHEMA = {
    "name": "list_powerunits_skill_draft_proposals",
    "description": "Tier>=4: list draft proposal files (relative paths, sizes).",
    "parameters": {
        "type": "object",
        "properties": {"subpath_prefix": {"type": "string"}},
        "required": [],
    },
}

READ_SCHEMA = {
    "name": "read_powerunits_skill_draft_proposal",
    "description": "Tier>=4: read one draft file from drafts/powerunits_skill_proposals.",
    "parameters": {
        "type": "object",
        "properties": {"relative_file_path": {"type": "string"}},
        "required": ["relative_file_path"],
    },
}

SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_skill_draft_proposals",
    "description": (
        "Tier>=4: draft volume + stale/churn caution signals for Tier 4A proposals subtree."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


registry.register(
    name="manifest_powerunits_tier4a_skill_draft_scope",
    toolset="powerunits_tier4a_skill_draft_proposals",
    schema=MANIFEST_SCHEMA,
    handler=lambda args, **kw: manifest_powerunits_tier4a_skill_draft_scope(**kw),
    check_fn=check_powerunits_tier4a_skill_draft_proposals,
    emoji="📌",
)

registry.register(
    name="write_powerunits_skill_draft_proposal",
    toolset="powerunits_tier4a_skill_draft_proposals",
    schema=WRITE_SCHEMA,
    handler=lambda args, **kw: write_powerunits_skill_draft_proposal(
        relative_file_path=str(args.get("relative_file_path", "")),
        body=str(args.get("body", "")),
        proposal_kind=str(args.get("proposal_kind", "")),
        target_skill_name=args.get("target_skill_name"),
        overwrite_mode=str(args.get("overwrite_mode") or "forbid"),
        **kw,
    ),
    check_fn=check_powerunits_tier4a_skill_draft_proposals,
    emoji="✍️",
)

registry.register(
    name="list_powerunits_skill_draft_proposals",
    toolset="powerunits_tier4a_skill_draft_proposals",
    schema=LIST_SCHEMA,
    handler=lambda args, **kw: list_powerunits_skill_draft_proposals(
        subpath_prefix=args.get("subpath_prefix"),
        **kw,
    ),
    check_fn=check_powerunits_tier4a_skill_draft_proposals,
    emoji="📂",
)

registry.register(
    name="read_powerunits_skill_draft_proposal",
    toolset="powerunits_tier4a_skill_draft_proposals",
    schema=READ_SCHEMA,
    handler=lambda args, **kw: read_powerunits_skill_draft_proposal(
        relative_file_path=str(args.get("relative_file_path", "")),
        **kw,
    ),
    check_fn=check_powerunits_tier4a_skill_draft_proposals,
    emoji="📄",
)

registry.register(
    name="summarize_powerunits_skill_draft_proposals",
    toolset="powerunits_tier4a_skill_draft_proposals",
    schema=SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_skill_draft_proposals(**kw),
    check_fn=check_powerunits_tier4a_skill_draft_proposals,
    emoji="📊",
)
