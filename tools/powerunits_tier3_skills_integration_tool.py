#!/usr/bin/env python3
"""
Tier 3 — bounded skills integration observer (Powerunits progressive posture).

Requires ``HERMES_POWERUNITS_CAPABILITY_TIER >= 3``. Read-only diagnostics, signals,
and structured **proposal** payloads only — **no** skill file writes, merges, or
silent Curator side effects from this toolset.

Canonical roadmap: ``docs/powerunits_hermes_progressive_posture_v1.md``.
Detail: ``docs/powerunits_tier3_skills_integration_overlay_v1.md``.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

from tools.registry import registry
from tools.skill_usage import (
    _find_skill_dir,
    _read_bundled_manifest_names,
    _read_hub_installed_names,
    _read_skill_name,
    activity_count,
    latest_activity_at,
    list_agent_created_skill_names,
    load_usage,
)

_NAME_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}$")
_MAX_SKILLS_SCAN = 450
_MAX_PREVIEW_CHARS_DEFAULT = 14_000
_MAX_PREVIEW_CHARS_CAP = 28_000
_STALE_HINT_DAYS = 30
_ARCHIVE_HINT_DAYS = 90

_INJECTION_NEEDLES = (
    "ignore previous instructions",
    "disregard your",
    "forget your instructions",
    "system prompt:",
)


def check_powerunits_tier3_skills_integration() -> bool:
    from powerunits_capability_tier import read_powerunits_capability_tier

    return read_powerunits_capability_tier() >= 3


def _skills_root() -> Path:
    return (get_hermes_home() / "skills").resolve()


def _safe_curator_state_slice() -> dict[str, Any]:
    out: dict[str, Any] = {"load_error": False}
    try:
        from agent import curator as cur

        st = cur.load_state()
        out["paused"] = bool(st.get("paused"))
        out["last_run_at"] = st.get("last_run_at")
        out["last_run_summary"] = (
            (st.get("last_run_summary") or "")[:800] if st.get("last_run_summary") else None
        )
        out["run_count"] = st.get("run_count")
    except Exception as exc:
        out["load_error"] = True
        out["error"] = str(exc)[:240]
    return out


def _iter_skill_md_paths(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for p in sorted(root.rglob("SKILL.md")):
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if not rel.parts or rel.parts[0].startswith(".") or rel.parts[0] in (
            ".git",
            ".github",
            ".hub",
            ".archive",
            "node_modules",
        ):
            continue
        paths.append(p)
        if len(paths) >= _MAX_SKILLS_SCAN:
            break
    return paths


def _frontmatter_snippet(skill_md: Path, limit: int = 480) -> str:
    try:
        return skill_md.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _provenance(name: str, bundled: set[str], hub: set[str]) -> str:
    if name in bundled:
        return "bundled"
    if name in hub:
        return "hub"
    return "agent_created_or_untracked"


def _parse_iso_days_ago(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, int(delta.total_seconds() // 86400))
    except (TypeError, ValueError):
        return None


def summarize_powerunits_skills_observer(**_: Any) -> str:
    """JSON summary: skill counts, usage slice, Curator state slice (read-only)."""

    from tools.registry import tool_error

    if not check_powerunits_tier3_skills_integration():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=3 required for Tier 3 skills integration overlay",
            error_code="tier_gate",
        )
    root = _skills_root()
    bundled = _read_bundled_manifest_names()
    hub = _read_hub_installed_names()
    skill_paths = _iter_skill_md_paths(root)
    caution: list[str] = []
    if len(skill_paths) >= _MAX_SKILLS_SCAN:
        caution.append(f"skills_scan_truncated_at_{_MAX_SKILLS_SCAN}")

    by_prov: dict[str, int] = defaultdict(int)
    names_seen: dict[str, list[str]] = defaultdict(list)

    for sp in skill_paths:
        fname = _read_skill_name(sp, fallback=sp.parent.name)
        prov = _provenance(fname, bundled, hub)
        by_prov[prov] += 1
        rel = sp.relative_to(root).as_posix()
        names_seen[fname].append(rel)

    dup_names = {k: v for k, v in names_seen.items() if len(v) > 1}

    usage = load_usage()
    agent_created = list_agent_created_skill_names()
    usage_states: dict[str, int] = defaultdict(int)
    for rec in usage.values():
        if isinstance(rec, dict):
            st = str(rec.get("state") or "unknown")
            usage_states[st] += 1

    return json.dumps(
        {
            "read_only": True,
            "tier": "3_skills_observer",
            "skills_directory_resolved": str(root),
            "skill_md_paths_scanned": len(skill_paths),
            "bundled_manifest_names_count": len(bundled),
            "hub_installed_names_count": len(hub),
            "agent_created_skill_names_count": len(agent_created),
            "counts_by_provenance": dict(by_prov),
            "duplicate_logical_names": {k: v for k, v in dup_names.items()},
            "usage_sidecar_skill_keys": len(usage),
            "usage_state_histogram": dict(usage_states),
            "curator_state_read_only": _safe_curator_state_slice(),
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier3_skills_integration_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def diagnose_powerunits_skills_signals(**_: Any) -> str:
    """Structured staleness / duplicate / content-hint signals (read-only)."""

    from tools.registry import tool_error

    if not check_powerunits_tier3_skills_integration():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=3 required for Tier 3 skills integration overlay",
            error_code="tier_gate",
        )
    root = _skills_root()
    bundled = _read_bundled_manifest_names()
    hub = _read_hub_installed_names()
    usage_map = load_usage()
    caution: list[str] = []

    stale_candidates: list[dict[str, Any]] = []
    idle_agent_skills: list[dict[str, Any]] = []
    duplicate_clusters: list[dict[str, Any]] = []
    injection_hits: list[dict[str, Any]] = []
    name_to_paths: dict[str, list[str]] = defaultdict(list)

    paths = _iter_skill_md_paths(root)
    if len(paths) >= _MAX_SKILLS_SCAN:
        caution.append(f"skills_scan_truncated_at_{_MAX_SKILLS_SCAN}")

    for sp in paths:
        name = _read_skill_name(sp, fallback=sp.parent.name)
        rel = sp.relative_to(root).as_posix()
        name_to_paths[name].append(rel)
        prov = _provenance(name, bundled, hub)
        snippet = _frontmatter_snippet(sp, 12000)
        low = snippet.lower()
        for needle in _INJECTION_NEEDLES:
            if needle in low:
                injection_hits.append(
                    {"skill_name": name, "path": rel, "needle": needle, "provenance": prov}
                )
                break

    for name, rels in name_to_paths.items():
        if len(rels) > 1:
            duplicate_clusters.append({"skill_name": name, "paths": sorted(rels)})

    for name in list_agent_created_skill_names():
        rec = usage_map.get(name)
        if not isinstance(rec, dict):
            rec = {}
        st = str(rec.get("state") or "active")
        act = activity_count(rec)
        last = latest_activity_at(rec)
        days_idle = _parse_iso_days_ago(last)
        if st in {"stale", "archived"}:
            stale_candidates.append(
                {
                    "skill_name": name,
                    "state": st,
                    "activity_total": act,
                    "latest_activity_at": last,
                    "provenance": "agent_created",
                }
            )
        elif act == 0 and days_idle is None:
            created = rec.get("created_at")
            d = _parse_iso_days_ago(str(created) if created else None)
            if d is not None and d >= _STALE_HINT_DAYS:
                idle_agent_skills.append(
                    {
                        "skill_name": name,
                        "reason": "zero_activity_and_old_created_at",
                        "created_days_ago": d,
                    }
                )
        elif act == 0 and days_idle is not None and days_idle >= _STALE_HINT_DAYS:
            idle_agent_skills.append(
                {
                    "skill_name": name,
                    "reason": "low_activity_window",
                    "days_since_latest_activity": days_idle,
                }
            )

    return json.dumps(
        {
            "read_only": True,
            "tier": "3_skills_observer",
            "threshold_hints_days": {
                "stale_like": _STALE_HINT_DAYS,
                "archive_like": _ARCHIVE_HINT_DAYS,
            },
            "duplicate_name_clusters": duplicate_clusters,
            "stale_or_archived_agent_skills": stale_candidates,
            "idle_agent_skill_hints": idle_agent_skills[:80],
            "injection_like_snippets_in_body_head": injection_hits[:40],
            "proposal_seed_count": len(duplicate_clusters)
            + len(stale_candidates)
            + len(injection_hits)
            + min(len(idle_agent_skills), 80),
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier3_skills_integration_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def propose_powerunits_skill_integration_actions(**_: Any) -> str:
    """Human-review proposals only — JSON; Hermes never applies these automatically."""

    from tools.registry import tool_error

    if not check_powerunits_tier3_skills_integration():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=3 required for Tier 3 skills integration overlay",
            error_code="tier_gate",
        )
    diag_raw = diagnose_powerunits_skills_signals()
    diag = json.loads(diag_raw)
    if diag.get("error_code") or isinstance(diag.get("error"), str):
        return diag_raw

    items: list[dict[str, Any]] = []

    for cl in diag.get("duplicate_name_clusters") or []:
        items.append(
            {
                "skill_name": cl.get("skill_name"),
                "proposal_type": "deduplicate_or_rename",
                "severity": "medium",
                "detail": {"paths": cl.get("paths")},
                "recommended_human_action": (
                    "Choose canonical path; archive or rename duplicate SKILL.md entries "
                    "(do not silently merge)."
                ),
            }
        )

    for row in diag.get("stale_or_archived_agent_skills") or []:
        items.append(
            {
                "skill_name": row.get("skill_name"),
                "proposal_type": "lifecycle_review",
                "severity": "low",
                "detail": row,
                "recommended_human_action": (
                    "Review usage + content; optionally pin, refresh, or restore from archive — "
                    "no autonomous apply."
                ),
            }
        )

    for row in diag.get("idle_agent_skill_hints") or []:
        items.append(
            {
                "skill_name": row.get("skill_name"),
                "proposal_type": "usage_or_archive_review",
                "severity": "low",
                "detail": row,
                "recommended_human_action": "Confirm still needed or archive via governed process.",
            }
        )

    for row in diag.get("injection_like_snippets_in_body_head") or []:
        items.append(
            {
                "skill_name": row.get("skill_name"),
                "proposal_type": "security_style_review",
                "severity": "high",
                "detail": row,
                "recommended_human_action": (
                    "Operator review SKILL.md body; verify trusted authorship — treat as heuristic only."
                ),
            }
        )

    return json.dumps(
        {
            "read_only": True,
            "tier": "3_skills_observer",
            "explicitly_not_auto_applied": True,
            "requires_human_review": True,
            "proposal_items": items,
            "proposal_count": len(items),
            "curator_autonomous_apply_contract": (
                "Powerunits Tier 3: no Hermes merges from this toolset; auxiliary Curator autonomous "
                "paths remain gated — keep Curator disabled on gateway unless deliberately reviewed."
            ),
            "doc_hint": "docs/powerunits_tier3_skills_integration_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def read_powerunits_skill_body_preview(skill_name: str, max_chars: int | None = None, **_: Any) -> str:
    """Bounded read of a single SKILL.md under ``HERMES_HOME/skills``."""

    from tools.registry import tool_error

    if not check_powerunits_tier3_skills_integration():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=3 required for Tier 3 skills integration overlay",
            error_code="tier_gate",
        )
    slug = str(skill_name or "").strip()
    if not _NAME_SLUG_RE.match(slug):
        return tool_error("invalid skill_name slug", error_code="invalid_skill_name")

    root = _skills_root()
    skill_dir = _find_skill_dir(slug)
    if skill_dir is None:
        return tool_error(f"skill not found: {slug}", error_code="not_found")

    md = skill_dir / "SKILL.md"
    md = md.resolve()
    md.relative_to(root)
    if not md.is_file():
        return tool_error("SKILL.md missing", error_code="not_found")

    try:
        text = md.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return tool_error(str(exc), error_code="read_failed")

    lim_i = int(max_chars) if max_chars is not None else _MAX_PREVIEW_CHARS_DEFAULT
    lim = max(2000, min(lim_i, _MAX_PREVIEW_CHARS_CAP))
    truncated = len(text) > lim
    out = text[:lim] + ("\n\n[truncated]" if truncated else "")
    canonical = _read_skill_name(md, fallback=slug)
    prov = _provenance(canonical, _read_bundled_manifest_names(), _read_hub_installed_names())

    return json.dumps(
        {
            "read_only": True,
            "tier": "3_skills_observer",
            "canonical_name_observed": canonical,
            "path_relative_to_skills": md.relative_to(root).as_posix(),
            "provenance_class": prov,
            "truncated": truncated,
            "chars_returned": len(out),
            "body": out,
            "doc_hint": "docs/powerunits_tier3_skills_integration_overlay_v1.md",
        },
        ensure_ascii=False,
    )


SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_skills_observer",
    "description": (
        "Tier>=3 Powerunits observe-only: inventory of Hermes HOME skills tree, provenance buckets, "
        "usage histogram, curator state slice."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

DIAGNOSE_SCHEMA = {
    "name": "diagnose_powerunits_skills_signals",
    "description": (
        "Tier>=3 bounded diagnostics: duplicates, staleness-ish hints, injection-like head markers."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

PROPOSE_SCHEMA = {
    "name": "propose_powerunits_skill_integration_actions",
    "description": (
        "Tier>=3 structured proposal list for human merge — NEVER auto-applied by Hermes tooling."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

PREVIEW_SCHEMA = {
    "name": "read_powerunits_skill_body_preview",
    "description": "Tier>=3 read bounded SKILL.md text for one skill slug under HERMES_HOME/skills.",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string"},
            "max_chars": {"type": "integer"},
        },
        "required": ["skill_name"],
    },
}

registry.register(
    name="summarize_powerunits_skills_observer",
    toolset="powerunits_tier3_skills_integration",
    schema=SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_skills_observer(**kw),
    check_fn=check_powerunits_tier3_skills_integration,
    emoji="🧠",
)

registry.register(
    name="diagnose_powerunits_skills_signals",
    toolset="powerunits_tier3_skills_integration",
    schema=DIAGNOSE_SCHEMA,
    handler=lambda args, **kw: diagnose_powerunits_skills_signals(**kw),
    check_fn=check_powerunits_tier3_skills_integration,
    emoji="🩺",
)

registry.register(
    name="propose_powerunits_skill_integration_actions",
    toolset="powerunits_tier3_skills_integration",
    schema=PROPOSE_SCHEMA,
    handler=lambda args, **kw: propose_powerunits_skill_integration_actions(**kw),
    check_fn=check_powerunits_tier3_skills_integration,
    emoji="📝",
)

registry.register(
    name="read_powerunits_skill_body_preview",
    toolset="powerunits_tier3_skills_integration",
    schema=PREVIEW_SCHEMA,
    handler=lambda args, **kw: read_powerunits_skill_body_preview(
        skill_name=str(args.get("skill_name", "")),
        max_chars=args.get("max_chars"),
        **kw,
    ),
    check_fn=check_powerunits_tier3_skills_integration,
    emoji="📖",
)
