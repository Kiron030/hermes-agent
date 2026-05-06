#!/usr/bin/env python3
"""
Tier 4B — review-state workflow and bounded workspace governance (Powerunits progressive posture).

Requires ``HERMES_POWERUNITS_CAPABILITY_TIER >= 5``. Writes are **only** under:

- ``hermes_workspace/governance/**`` (operator notes / scaffolding), and
- **Frontmatter field patches** on existing files under
  ``hermes_workspace/drafts/powerunits_skill_proposals/**`` (same subtree as Tier 4A).

Never ``$HERMES_HOME/skills``, never live merge/apply, never Repo B mutation.

Canonical roadmap: ``docs/powerunits_hermes_progressive_posture_v1.md``.
Detail: ``docs/powerunits_tier4b_review_governance_overlay_v1.md``.
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

# Shared caps / patterns with Tier 4A
_REL_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}$")
_LEAF_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}\.(md|txt)$")
_MAX_REL_PARTS = 12
_MAX_GOVERNANCE_BODY = 64_000
_MAX_NOTE_APPEND = 32_000
_GOV_LIST_CAP = 2000
_GOVERNANCE_SUBDIRS = (
    "review_decisions",
    "incidents",
    "automation_logs",
    "experiments",
    "skill_integration_tests",
)
_UNRESOLVED_STATUSES = frozenset({"new", "under_review", "needs_revision"})
_REVIEW_STATUSES = frozenset(
    {"new", "under_review", "needs_revision", "accepted_for_promotion", "rejected"}
)
_STALE_UNRESOLVED_DAYS = 14
_CAUTION_GOVERNANCE_FILES = 180
_CAUTION_UNRESOLVED = 35
_CAUTION_STALE_UNRESOLVED = 12
_TIER4B_POINTER_NAME = "README_POWERUNITS_TIER4B.txt"
_TIER4B_POINTER_BODY = """Powerunits Hermes — Tier 4B review + governance scaffolding (operator pointer).

Canonical roadmap: docs/powerunits_hermes_progressive_posture_v1.md
Tier 4B detail: docs/powerunits_tier4b_review_governance_overlay_v1.md

Bounded writes:
- governance/* — operator notes and decisions (not live skills).
- Draft frontmatter patches — review_status only on Tier 4A proposal files.

Rollback: set HERMES_POWERUNITS_CAPABILITY_TIER=4 (drops this toolset; on-disk files remain).
"""


def check_powerunits_tier4b_review_governance() -> bool:
    from powerunits_capability_tier import read_powerunits_capability_tier

    return read_powerunits_capability_tier() >= 5


def _workspace_root() -> Path:
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    return (hermes_home / "hermes_workspace").resolve()


def _governance_root() -> Path:
    return (_workspace_root() / "governance").resolve()


def _write_tier4b_pointer_if_missing(gov: Path) -> None:
    try:
        marker = gov / _TIER4B_POINTER_NAME
        marker.resolve().relative_to(_governance_root().resolve())
        if marker.exists():
            return
        marker.write_text(_TIER4B_POINTER_BODY.strip() + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.warning("Tier 4B pointer skipped: %s", exc)


def _normalize_rel(rel: str) -> str:
    s = str(rel or "").strip().replace("\\", "/").lstrip("/")
    parts_raw = [p for p in s.split("/") if p]
    if any(p == ".." for p in parts_raw):
        raise ValueError("path_contains_parent_segment")
    parts = [p for p in parts_raw if p != "."]
    return "/".join(parts)


def _safe_proposal_target(rel_norm: str, proposals: Path) -> Path:
    from tools.powerunits_tier4a_skill_draft_proposals_tool import _safe_target

    return _safe_target(rel_norm, proposals)


def _validated_governance_rel(rel: str) -> Path:
    try:
        nrel = _normalize_rel(rel)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if not nrel:
        raise ValueError("relative_path_required")
    parts = nrel.split("/")
    if len(parts) > _MAX_REL_PARTS:
        raise ValueError("relative_path_too_deep")
    top = parts[0]
    if top not in _GOVERNANCE_SUBDIRS:
        raise ValueError(f"governance_path_must_start_with:{','.join(_GOVERNANCE_SUBDIRS)}")
    for seg in parts[:-1]:
        if not _REL_SEGMENT_RE.match(seg):
            raise ValueError(f"invalid_path_segment:{seg}")
    if not _LEAF_NAME_RE.match(parts[-1]):
        raise ValueError("invalid_leaf_name")
    return Path(*parts)


def _safe_gov_target(rel_norm: str, gov: Path) -> Path:
    rel_p = _validated_governance_rel(rel_norm)
    out = (gov / rel_p).resolve()
    out.relative_to(gov)
    return out


def _extract_frontmatter_block(text: str) -> tuple[list[str], str] | None:
    raw = str(text or "")
    if not raw.lstrip().startswith("---"):
        return None
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end_idx: int | None = None
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None
    inner = lines[1:end_idx]
    rest = "\n".join(lines[end_idx + 1 :])
    return inner, rest


def _merge_fm_lines(inner_lines: list[str], patch: dict[str, str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in inner_lines:
        if ":" not in line:
            out.append(line)
            continue
        k = line.split(":", 1)[0].strip()
        if k in patch:
            out.append(f"{k}: {patch[k]}")
            seen.add(k)
        else:
            out.append(line)
    for k, v in patch.items():
        if k not in seen:
            out.append(f"{k}: {v}")
    return out


def _rebuild_file_with_fm(text: str, patch: dict[str, str]) -> str | None:
    got = _extract_frontmatter_block(text)
    if got is None:
        return None
    inner, rest = got
    new_inner = _merge_fm_lines(inner, patch)
    return "---\n" + "\n".join(new_inner) + "\n---\n" + rest.lstrip("\n")


def manifest_powerunits_tier4b_governance_scope(**_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    gov = _governance_root()
    from tools.powerunits_tier4a_skill_draft_proposals_tool import _proposals_root

    proposals = _proposals_root()
    return json.dumps(
        {
            "read_only": True,
            "tier": "4b_review_governance",
            "governance_root_relative": "governance",
            "governance_root_resolved": str(gov),
            "governance_subdirs": list(_GOVERNANCE_SUBDIRS),
            "proposals_root_for_status_patches_relative": "drafts/powerunits_skill_proposals",
            "proposals_root_resolved": str(proposals),
            "review_status_values": sorted(_REVIEW_STATUSES),
            "live_skills_directory_never_written": str(
                (Path(os.getenv("HERMES_HOME", "/opt/data")) / "skills").resolve()
            ),
            "requires_human_review_contract": True,
            "not_auto_applied_contract": True,
            "max_governance_write_chars": _MAX_GOVERNANCE_BODY,
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def ensure_powerunits_governance_workspace(**_: Any) -> str:
    """Create governance subdirs + README pointer (idempotent)."""

    from tools.registry import tool_error

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    ws = _workspace_root()
    ws.mkdir(parents=True, exist_ok=True)
    gov = _governance_root()
    gov.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for sub in _GOVERNANCE_SUBDIRS:
        d = (gov / sub).resolve()
        try:
            d.relative_to(gov)
        except ValueError:
            continue
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(sub)
    _write_tier4b_pointer_if_missing(gov)
    return json.dumps(
        {
            "read_only": False,
            "tier": "4b_review_governance",
            "governance_root": str(gov),
            "subdirs_ensured": list(_GOVERNANCE_SUBDIRS),
            "subdirs_created_this_call": created,
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def set_powerunits_skill_draft_review_status(
    relative_file_path: str,
    review_status: str,
    *,
    operator_note_one_line: str | None = None,
    **_: Any,
) -> str:
    """Patch YAML frontmatter on one Tier 4A proposal file (bounded path)."""

    from tools.registry import tool_error

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    st = str(review_status or "").strip()
    if st not in _REVIEW_STATUSES:
        return tool_error(
            f"review_status must be one of:{sorted(_REVIEW_STATUSES)}",
            error_code="invalid_review_status",
        )
    note = str(operator_note_one_line or "").strip().replace("\r", "").replace("\n", " ")
    if len(note) > 500:
        return tool_error("operator_note_one_line too long (max 500)", error_code="limit_exceeded")

    from tools.powerunits_tier4a_skill_draft_proposals_tool import (
        _ensure_proposals_tree,
        _normalize_rel,
    )

    proposals = _ensure_proposals_tree()
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _safe_proposal_target(nrel, proposals)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")

    if not target.is_file() or target.is_symlink():
        return tool_error("not_found", error_code="not_found")

    try:
        text = target.read_text(encoding="utf-8", errors="strict")
    except OSError as exc:
        return tool_error(str(exc), error_code="read_failed")
    except UnicodeDecodeError:
        return tool_error("non_utf8_file", error_code="read_failed")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    patch: dict[str, str] = {"review_status": st, "review_status_updated_at_utc": ts}
    if note:
        patch["review_status_operator_note"] = note.replace(":", " ")
    new_text = _rebuild_file_with_fm(text, patch)
    if new_text is None:
        return tool_error("no_valid_yaml_frontmatter", error_code="invalid_proposal_file")

    try:
        target.write_text(new_text, encoding="utf-8", newline="\n")
    except OSError as exc:
        return tool_error(str(exc), error_code="write_failed")

    return json.dumps(
        {
            "read_only": False,
            "tier": "4b_review_governance",
            "path_relative_to_proposals": target.relative_to(proposals).as_posix(),
            "review_status": st,
            "requires_human_review": True,
            "not_auto_applied": True,
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def append_powerunits_governance_note(
    relative_file_path: str,
    body: str,
    *,
    append_mode: str = "append",
    **_: Any,
) -> str:
    """Write or append a bounded note under governance/* (allowlisted prefixes)."""

    from tools.registry import tool_error

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    mode = str(append_mode or "append").strip().lower()
    if mode not in {"append", "create_only"}:
        return tool_error("append_mode must be append or create_only", error_code="invalid_mode")

    chunk = str(body if body is not None else "")
    if len(chunk) > _MAX_NOTE_APPEND:
        return tool_error("body_too_large", error_code="limit_exceeded")

    ensure_powerunits_governance_workspace()
    gov = _governance_root()
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _safe_gov_target(nrel, gov)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = f"\n\n<!-- tier4b_note {stamp} -->\n{chunk}\n"

    existed = target.exists()
    if existed and mode == "create_only":
        return tool_error("target_exists", error_code="exists")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if existed:
            prev = target.read_text(encoding="utf-8", errors="strict")
            target.write_text(prev + block, encoding="utf-8", newline="\n")
        else:
            hdr = (
                f"# Governance note\n\n"
                f"<!-- Tier 4B — bounded operator note ({target.relative_to(gov).as_posix()}) -->\n"
            )
            target.write_text(hdr + block.lstrip("\n"), encoding="utf-8", newline="\n")
    except OSError as exc:
        return tool_error(str(exc), error_code="write_failed")
    except UnicodeDecodeError:
        return tool_error("existing_file_non_utf8", error_code="read_failed")

    return json.dumps(
        {
            "read_only": False,
            "tier": "4b_review_governance",
            "path_relative_to_governance": target.relative_to(gov).as_posix(),
            "bytes_appended": len(block.encode("utf-8")),
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def read_powerunits_governance_note(relative_file_path: str, **_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    gov = _governance_root()
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _safe_gov_target(nrel, gov)
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
            "tier": "4b_review_governance",
            "path_relative_to_governance": target.relative_to(gov).as_posix(),
            "chars": len(body),
            "body": body,
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def list_powerunits_governance_workspace(
    subpath_prefix: str | None = None, **_: Any
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    gov = _governance_root()
    prefix = _normalize_rel(subpath_prefix or "")
    if prefix:
        try:
            base = (gov / prefix).resolve()
            base.relative_to(gov)
        except ValueError:
            return tool_error("invalid subpath_prefix", error_code="invalid_prefix")
    else:
        base = gov

    rows: list[dict[str, Any]] = []
    if base.is_dir():
        for fp in sorted(base.rglob("*")):
            if not fp.is_file() or fp.is_symlink():
                continue
            try:
                rel = fp.relative_to(gov).as_posix()
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
            if len(rows) >= _GOV_LIST_CAP:
                break

    return json.dumps(
        {
            "read_only": True,
            "tier": "4b_review_governance",
            "listing_truncated": len(rows) >= _GOV_LIST_CAP,
            "entries": rows,
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def summarize_powerunits_tier4b_governance_lane(**_: Any) -> str:
    """Rollups: proposal review_status + governance volume + soft cautions."""

    from tools.registry import tool_error
    from tools.powerunits_tier4a_skill_draft_proposals_tool import (
        _ensure_proposals_tree,
        _is_bootstrap_pointer,
        _iter_proposal_files,
        _split_tier4a_frontmatter,
    )

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    proposals = _ensure_proposals_tree()
    gov = _governance_root()

    status_counts: dict[str, int] = {s: 0 for s in _REVIEW_STATUSES}
    unresolved = 0
    stale_unresolved = 0
    contradictory = 0
    now = datetime.now(timezone.utc)

    files = _iter_proposal_files(proposals, exclude_bootstrap_pointer=True)
    for fp in files:
        if _is_bootstrap_pointer(fp):
            continue
        try:
            raw = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, _md = _split_tier4a_frontmatter(raw)
        rs_raw = str(fm.get("review_status") or "").strip()
        if not rs_raw or rs_raw not in _REVIEW_STATUSES:
            rs = "new"
        else:
            rs = rs_raw
        status_counts[rs] = status_counts.get(rs, 0) + 1
        if rs in _UNRESOLVED_STATUSES:
            unresolved += 1
            upd = str(fm.get("review_status_updated_at_utc") or "").strip()
            try:
                mdt = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
            except OSError:
                mdt = now
            ref = mdt
            if upd and "T" in upd:
                try:
                    ref = datetime.fromisoformat(upd.replace("Z", "+00:00"))
                except ValueError:
                    ref = mdt
            if now - ref > timedelta(days=_STALE_UNRESOLVED_DAYS):
                stale_unresolved += 1
        rh = str(fm.get("requires_human_review") or "").strip().lower()
        na = str(fm.get("not_auto_applied") or "").strip().lower()
        if rs == "accepted_for_promotion" and rh in ("false", "0", "no"):
            contradictory += 1
        if rs == "rejected" and na in ("false", "0", "no"):
            contradictory += 1

    gov_files = 0
    gov_bytes = 0
    if gov.is_dir():
        for gf in gov.rglob("*"):
            if gf.is_file() and not gf.is_symlink():
                try:
                    gf.relative_to(gov)
                except ValueError:
                    continue
                gov_files += 1
                try:
                    gov_bytes += gf.stat().st_size
                except OSError:
                    pass
                if gov_files >= _GOV_LIST_CAP:
                    break

    caution: list[str] = []
    if unresolved >= _CAUTION_UNRESOLVED:
        caution.append(f"tier4b_unresolved_draft_count_high:{unresolved}>={_CAUTION_UNRESOLVED}")
    if stale_unresolved >= _CAUTION_STALE_UNRESOLVED:
        caution.append(
            f"tier4b_stale_unresolved_reviews:{stale_unresolved}>={_CAUTION_STALE_UNRESOLVED}"
        )
    if gov_files >= _CAUTION_GOVERNANCE_FILES:
        caution.append(
            f"tier4b_governance_workspace_clutter:{gov_files}>={_CAUTION_GOVERNANCE_FILES}"
        )
    if contradictory:
        caution.append(f"tier4b_contradictory_review_metadata_files:{contradictory}")

    return json.dumps(
        {
            "read_only": True,
            "tier": "4b_review_governance",
            "proposal_review_status_counts": dict(sorted(status_counts.items())),
            "proposals_unresolved_active_count": unresolved,
            "proposals_unresolved_stale_est_count": stale_unresolved,
            "stale_unresolved_days_threshold": _STALE_UNRESOLVED_DAYS,
            "governance_file_count_sampled": gov_files,
            "governance_total_bytes_sampled": gov_bytes,
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def review_powerunits_tier4b_skill_drafts(
    *,
    max_entries: int = 100,
    review_status_filter: str | None = None,
    target_skill_substring: str | None = None,
    proposal_kind_filter: str | None = None,
    **_: Any,
) -> str:
    """Filtered proposal queue with explicit review_status (read-heavy, bounded)."""

    from tools.registry import tool_error
    from tools.powerunits_tier4a_skill_draft_proposals_tool import (
        _MAX_REVIEW_HEAD_BYTES,
        _ensure_proposals_tree,
        _is_bootstrap_pointer,
        _iter_proposal_files,
        _read_head_text,
        _split_tier4a_frontmatter,
    )

    if not check_powerunits_tier4b_review_governance():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=5 required for Tier 4B review/governance",
            error_code="tier_gate",
        )
    try:
        cap = max(1, min(int(max_entries), 400))
    except (TypeError, ValueError):
        cap = 100

    rs_f = str(review_status_filter or "").strip()
    if rs_f and rs_f not in _REVIEW_STATUSES:
        return tool_error("invalid review_status_filter", error_code="invalid_filter")
    tgt_sub = str(target_skill_substring or "").strip().casefold()
    kind_f = str(proposal_kind_filter or "").strip()

    proposals = _ensure_proposals_tree()
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for fp in _iter_proposal_files(proposals, exclude_bootstrap_pointer=True):
        if _is_bootstrap_pointer(fp):
            continue
        try:
            st = fp.stat()
        except OSError:
            continue
        head = _read_head_text(fp, _MAX_REVIEW_HEAD_BYTES)
        fm, md_rest = _split_tier4a_frontmatter(head)
        rs = str(fm.get("review_status") or "").strip() or "new"
        if rs_f and rs != rs_f:
            continue
        kind_meta = str(fm.get("proposal_kind") or "").strip()
        tgt_meta = str(fm.get("target_skill_name") or "").strip()
        if tgt_sub and tgt_sub not in tgt_meta.casefold():
            continue
        if kind_f and kind_meta != kind_f:
            continue
        mdt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        rows.append(
            {
                "relative_path": fp.relative_to(proposals).as_posix(),
                "mtime_utc": mdt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "review_status": rs,
                "review_status_updated_at_utc": fm.get("review_status_updated_at_utc"),
                "proposal_kind": kind_meta or None,
                "target_skill_name": tgt_meta or None,
                "requires_human_review": fm.get("requires_human_review"),
                "not_auto_applied": fm.get("not_auto_applied"),
                "body_preview": md_rest[:320],
            }
        )

    rows.sort(key=lambda r: str(r.get("review_status_updated_at_utc") or r["mtime_utc"]), reverse=True)
    total = len(rows)
    out = rows[:cap]
    caution: list[str] = []
    if total > cap:
        caution.append(f"tier4b_review_truncated:{total}>{cap}")
    if rs_f in _UNRESOLVED_STATUSES and total >= 40:
        caution.append(f"tier4b_review_status_filter_load:{total}_files")

    return json.dumps(
        {
            "read_only": True,
            "tier": "4b_review_governance",
            "filters": {
                "review_status": rs_f or None,
                "target_skill_substring": target_skill_substring or None,
                "proposal_kind": kind_f or None,
            },
            "matching_count": total,
            "max_entries": cap,
            "entries": out,
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier4b_review_governance_overlay_v1.md",
        },
        ensure_ascii=False,
    )


MANIFEST_SCHEMA = {
    "name": "manifest_powerunits_tier4b_governance_scope",
    "description": "Tier>=5: bounded Tier 4B roots, review statuses, caps.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
ENSURE_SCHEMA = {
    "name": "ensure_powerunits_governance_workspace",
    "description": "Tier>=5: create governance/ subdirs + README pointer (idempotent).",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
SET_STATUS_SCHEMA = {
    "name": "set_powerunits_skill_draft_review_status",
    "description": (
        "Tier>=5: patch review_status (+ timestamp, optional note) on one Tier 4A draft; "
        "never touches live skills."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "relative_file_path": {"type": "string"},
            "review_status": {"type": "string"},
            "operator_note_one_line": {"type": "string"},
        },
        "required": ["relative_file_path", "review_status"],
    },
}
APPEND_NOTE_SCHEMA = {
    "name": "append_powerunits_governance_note",
    "description": "Tier>=5: append/create bounded note under governance/* allowlisted tree.",
    "parameters": {
        "type": "object",
        "properties": {
            "relative_file_path": {"type": "string"},
            "body": {"type": "string"},
            "append_mode": {"type": "string", "enum": ["append", "create_only"]},
        },
        "required": ["relative_file_path", "body"],
    },
}
READ_GOV_SCHEMA = {
    "name": "read_powerunits_governance_note",
    "description": "Tier>=5: read one governance note file.",
    "parameters": {
        "type": "object",
        "properties": {"relative_file_path": {"type": "string"}},
        "required": ["relative_file_path"],
    },
}
LIST_GOV_SCHEMA = {
    "name": "list_powerunits_governance_workspace",
    "description": "Tier>=5: list governance subtree (bounded).",
    "parameters": {
        "type": "object",
        "properties": {"subpath_prefix": {"type": "string"}},
        "required": [],
    },
}
SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_tier4b_governance_lane",
    "description": "Tier>=5: review_status rollups + governance volume + caution flags.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
REVIEW_DRAFTS_SCHEMA = {
    "name": "review_powerunits_tier4b_skill_drafts",
    "description": (
        "Tier>=5: list proposal drafts with review_status / filters / previews (read-only board)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "max_entries": {"type": "integer"},
            "review_status_filter": {"type": "string"},
            "target_skill_substring": {"type": "string"},
            "proposal_kind_filter": {"type": "string"},
        },
        "required": [],
    },
}

registry.register(
    name="manifest_powerunits_tier4b_governance_scope",
    toolset="powerunits_tier4b_review_governance",
    schema=MANIFEST_SCHEMA,
    handler=lambda args, **kw: manifest_powerunits_tier4b_governance_scope(**kw),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="📋",
)
registry.register(
    name="ensure_powerunits_governance_workspace",
    toolset="powerunits_tier4b_review_governance",
    schema=ENSURE_SCHEMA,
    handler=lambda args, **kw: ensure_powerunits_governance_workspace(**kw),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="🧱",
)
registry.register(
    name="set_powerunits_skill_draft_review_status",
    toolset="powerunits_tier4b_review_governance",
    schema=SET_STATUS_SCHEMA,
    handler=lambda args, **kw: set_powerunits_skill_draft_review_status(
        relative_file_path=str(args.get("relative_file_path", "")),
        review_status=str(args.get("review_status", "")),
        operator_note_one_line=args.get("operator_note_one_line"),
        **kw,
    ),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="🏷️",
)
registry.register(
    name="append_powerunits_governance_note",
    toolset="powerunits_tier4b_review_governance",
    schema=APPEND_NOTE_SCHEMA,
    handler=lambda args, **kw: append_powerunits_governance_note(
        relative_file_path=str(args.get("relative_file_path", "")),
        body=str(args.get("body", "")),
        append_mode=str(args.get("append_mode") or "append"),
        **kw,
    ),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="📝",
)
registry.register(
    name="read_powerunits_governance_note",
    toolset="powerunits_tier4b_review_governance",
    schema=READ_GOV_SCHEMA,
    handler=lambda args, **kw: read_powerunits_governance_note(
        relative_file_path=str(args.get("relative_file_path", "")),
        **kw,
    ),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="📄",
)
registry.register(
    name="list_powerunits_governance_workspace",
    toolset="powerunits_tier4b_review_governance",
    schema=LIST_GOV_SCHEMA,
    handler=lambda args, **kw: list_powerunits_governance_workspace(
        subpath_prefix=args.get("subpath_prefix"),
        **kw,
    ),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="📂",
)
registry.register(
    name="summarize_powerunits_tier4b_governance_lane",
    toolset="powerunits_tier4b_review_governance",
    schema=SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_tier4b_governance_lane(**kw),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="📊",
)
registry.register(
    name="review_powerunits_tier4b_skill_drafts",
    toolset="powerunits_tier4b_review_governance",
    schema=REVIEW_DRAFTS_SCHEMA,
    handler=lambda args, **kw: review_powerunits_tier4b_skill_drafts(
        max_entries=args.get("max_entries", 100),
        review_status_filter=args.get("review_status_filter"),
        target_skill_substring=args.get("target_skill_substring"),
        proposal_kind_filter=args.get("proposal_kind_filter"),
        **kw,
    ),
    check_fn=check_powerunits_tier4b_review_governance,
    emoji="🗂️",
)
