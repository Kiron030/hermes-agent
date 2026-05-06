#!/usr/bin/env python3
"""
Tier 5A — bounded operator workflow scaffolding (Powerunits progressive posture).

Requires ``HERMES_POWERUNITS_CAPABILITY_TIER >= 6``. Writes are **only** under:

``hermes_workspace/operator_bounded_workflows/**`` (run records, checkpoints, logs,
experiment / escalation notes — see manifest).

**Does not** call Repo B bounded HTTP APIs, **does not** execute Option D / other
bounded families, **does not** mutate live ``skills/`` or Tier 4A/4B trees outside
this subtree.

Canonical roadmap: ``docs/powerunits_hermes_progressive_posture_v1.md``.
Detail: ``docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md``.
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
_LEAF_MD_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,180}\.md$")
_MAX_REL_PARTS = 14
_MAX_LIST = 2000
_MAX_NOTE_APPEND = 32_000
_MAX_APPEND_MARKDOWN = 16_000
_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,119}$")

_WORKFLOW_REL_ROOT = "operator_bounded_workflows"
_NOTE_SUBDIRS = (
    "checkpoints",
    "bounded_logs",
    "escalation_notes",
    "experiment_records",
    "skill_integration_test_notes",
)
_RUN_SUBDIR = "run_records"

_WORKFLOW_STATUS_VALUES = frozenset(
    {
        "ready_to_run",
        "running",
        "validate_pending",
        "summary_pending",
        "retry_suggested",
        "escalation_suggested",
        "aborted",
        "paused",
        "completed",
    }
)
_WORKFLOW_STAGE_VALUES = frozenset(
    {
        "preflight",
        "execute",
        "validate",
        "summary",
        "idle",
    }
)

_STUCK_RUNNING_HOURS = 4
_CAUTION_RUN_FILES = 80
_CAUTION_VALIDATE_PENDING = 15
_CAUTION_SUMMARY_PENDING = 15
_CAUTION_RETRY_GE = 3
_CAUTION_ESCALATION_FILES = 12
_CAUTION_TOTAL_ESCALATION_SUM = 25
_REVIEW_BOARD_CAP = 50

_TIER5A_POINTER_NAME = "README_POWERUNITS_TIER5A.txt"
_TIER5A_POINTER_BODY = """Powerunits Hermes — Tier 5A bounded operator workflow scaffolding (pointer).

Canonical roadmap: docs/powerunits_hermes_progressive_posture_v1.md
Tier 5A detail: docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md

Subtree: hermes_workspace/operator_bounded_workflows/
- run_records/ — workflow run records (frontmatter state, operator-visible).
- checkpoints/, bounded_logs/, escalation_notes/, experiment_records/, skill_integration_test_notes/

Hermes records and assists only. Repo B remains canonical for bounded API semantics.
No automatic bounded HTTP execution from these tools.

Rollback: set HERMES_POWERUNITS_CAPABILITY_TIER=5 (drops this toolset; files stay on disk).
"""


def check_powerunits_tier5a_bounded_workflow_scaffolding() -> bool:
    from powerunits_capability_tier import read_powerunits_capability_tier

    return read_powerunits_capability_tier() >= 6


def _workspace_root() -> Path:
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    return (hermes_home / "hermes_workspace").resolve()


def _workflow_root() -> Path:
    return (_workspace_root() / _WORKFLOW_REL_ROOT).resolve()


def _write_pointer_if_missing(root: Path) -> None:
    try:
        marker = root / _TIER5A_POINTER_NAME
        marker.resolve().relative_to(_workflow_root().resolve())
        if marker.exists():
            return
        marker.write_text(_TIER5A_POINTER_BODY.strip() + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.warning("Tier 5A pointer skipped: %s", exc)


def _normalize_rel(rel: str) -> str:
    s = str(rel or "").strip().replace("\\", "/").lstrip("/")
    parts_raw = [p for p in s.split("/") if p]
    if any(p == ".." for p in parts_raw):
        raise ValueError("path_contains_parent_segment")
    parts = [p for p in parts_raw if p != "."]
    return "/".join(parts)


def _validated_under_workflow(rel_norm: str) -> Path:
    if not rel_norm:
        raise ValueError("relative_path_required")
    parts = rel_norm.split("/")
    if len(parts) > _MAX_REL_PARTS:
        raise ValueError("relative_path_too_deep")
    for seg in parts[:-1]:
        if not _REL_SEGMENT_RE.match(seg):
            raise ValueError(f"invalid_path_segment:{seg}")
    if not _LEAF_MD_RE.match(parts[-1]):
        raise ValueError("invalid_leaf_name_md_only")
    rel_p = Path(*parts)
    out = (_workflow_root() / rel_p).resolve()
    out.relative_to(_workflow_root().resolve())
    return out


def _validated_note_rel(rel_norm: str) -> Path:
    parts = rel_norm.split("/")
    if not parts or parts[0] not in _NOTE_SUBDIRS:
        raise ValueError(f"note_path_must_start_with:{','.join(_NOTE_SUBDIRS)}")
    return _validated_under_workflow(rel_norm)


def _extract_frontmatter_block(text: str) -> tuple[list[str], str] | None:
    raw = str(text or "")
    if not raw.lstrip().startswith("---"):
        return None
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end_idx: int | None = None
    for i in range(1, min(len(lines), 240)):
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


def _parse_fm_dict(text: str) -> dict[str, str]:
    got = _extract_frontmatter_block(text)
    if not got:
        return {}
    inner, _ = got
    fm: dict[str, str] = {}
    for line in inner:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm


def _validate_run_id(rid: str) -> str | None:
    s = str(rid or "").strip()
    if not s:
        return "workflow_run_id_required"
    if not _RUN_ID_RE.match(s):
        return "workflow_run_id_invalid_char_or_length"
    return None


def _normalize_frontmatter_patch(patch: dict[str, Any] | None) -> tuple[dict[str, str] | None, str | None]:
    if not patch:
        return {}, None
    allowed = {
        "workflow_status",
        "workflow_stage",
        "bounded_family_hint",
        "retry_count",
        "escalation_count",
        "requires_operator_checkpoint",
        "operator_state_note_one_line",
    }
    out: dict[str, str] = {}
    for k, v in patch.items():
        ks = str(k or "").strip()
        if ks not in allowed:
            return None, f"unknown_frontmatter_key:{ks}"
        if v is None:
            continue
        if ks == "workflow_status":
            st = str(v).strip()
            if st not in _WORKFLOW_STATUS_VALUES:
                return None, "invalid_workflow_status"
            out[ks] = st
        elif ks == "workflow_stage":
            sg = str(v).strip()
            if sg not in _WORKFLOW_STAGE_VALUES:
                return None, "invalid_workflow_stage"
            out[ks] = sg
        elif ks in ("retry_count", "escalation_count"):
            if isinstance(v, str) and not v.strip():
                continue
            if isinstance(v, bool):
                return None, f"{ks}_must_be_integer"
            try:
                n = int(v, 10) if isinstance(v, str) else int(v)
            except (TypeError, ValueError):
                return None, f"{ks}_not_integer"
            if n < 0 or n > 999_999:
                return None, f"{ks}_out_of_range"
            out[ks] = str(n)
        elif ks == "requires_operator_checkpoint":
            sl = str(v).strip().lower()
            if sl in ("true", "false", "1", "0", "yes", "no"):
                out[ks] = "true" if sl in ("true", "1", "yes") else "false"
            else:
                return None, "requires_operator_checkpoint_must_be_boolean_like"
        elif ks == "bounded_family_hint":
            hint = str(v).strip().replace("\n", " ")
            if len(hint) > 200:
                return None, "bounded_family_hint_too_long"
            out[ks] = hint
        elif ks == "operator_state_note_one_line":
            note = str(v).strip().replace("\r", "").replace("\n", " ")
            if len(note) > 500:
                return None, "operator_state_note_too_long"
            out[ks] = note
    return out, None


def manifest_powerunits_tier5a_bounded_workflow_scope(**_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    wf = _workflow_root()
    return json.dumps(
        {
            "read_only": True,
            "tier": "5a_bounded_workflow_scaffolding",
            "tool_surface": "workflow_artifacts_only_not_bounded_http",
            "distinct_from": [
                "preflight_powerunits_option_d_bounded_slice",
                "execute_powerunits_option_d_bounded_slice",
                "manifest_powerunits_tier4b_governance_scope",
            ],
            "workflow_root_relative": _WORKFLOW_REL_ROOT,
            "workflow_root_resolved": str(wf),
            "run_records_subdir": _RUN_SUBDIR,
            "note_subdirs": list(_NOTE_SUBDIRS),
            "workflow_status_values": sorted(_WORKFLOW_STATUS_VALUES),
            "workflow_stage_values": sorted(_WORKFLOW_STAGE_VALUES),
            "repo_b_canonical_truth": True,
            "not_auto_executed_contract": True,
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def ensure_powerunits_bounded_workflow_workspace(**_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    ws = _workspace_root()
    ws.mkdir(parents=True, exist_ok=True)
    root = _workflow_root()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for sub in (_RUN_SUBDIR, *_NOTE_SUBDIRS):
        d = (root / sub).resolve()
        d.relative_to(root)
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(sub)
    _write_pointer_if_missing(root)
    return json.dumps(
        {
            "read_only": False,
            "tier": "5a_bounded_workflow_scaffolding",
            "workflow_root": str(root),
            "subdirs_ensured": [_RUN_SUBDIR, *_NOTE_SUBDIRS],
            "subdirs_created_this_call": created,
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def upsert_powerunits_bounded_workflow_run(
    workflow_run_id: str,
    *,
    relative_run_record_path: str | None = None,
    frontmatter_patch: dict[str, Any] | None = None,
    append_markdown: str | None = None,
    **_: Any,
) -> str:
    """Create or patch one run record under run_records/ (frontmatter + optional body append)."""

    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    err_rid = _validate_run_id(workflow_run_id)
    if err_rid:
        return tool_error(err_rid, error_code="invalid_run_id")

    rid = str(workflow_run_id).strip()
    fm_patch, err_fm = _normalize_frontmatter_patch(frontmatter_patch)
    if err_fm:
        return tool_error(err_fm, error_code="invalid_frontmatter_patch")
    assert fm_patch is not None

    append_md = str(append_markdown or "")
    if len(append_md) > _MAX_APPEND_MARKDOWN:
        return tool_error("append_markdown_too_large", error_code="limit_exceeded")

    ensure_powerunits_bounded_workflow_workspace()
    wf_root = _workflow_root()

    if relative_run_record_path:
        try:
            nrel = _normalize_rel(relative_run_record_path)
        except ValueError as exc:
            return tool_error(str(exc), error_code="invalid_path")
        parts = nrel.split("/")
        if len(parts) < 2 or parts[0] != _RUN_SUBDIR:
            return tool_error("run_record_must_be_under_run_records", error_code="invalid_path")
        try:
            target = _validated_under_workflow(nrel)
        except ValueError as exc:
            return tool_error(str(exc), error_code="invalid_path")
    else:
        leaf = f"{rid}.md"
        try:
            target = _validated_under_workflow(f"{_RUN_SUBDIR}/{leaf}")
        except ValueError as exc:
            return tool_error(str(exc), error_code="invalid_path")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    core_patch: dict[str, str] = {
        "powerunits_tier_5a_workflow_run": "true",
        "workflow_run_id": rid,
        "not_auto_executed": "true",
        "repo_b_truth_canonical": "true",
        "updated_at_utc": ts,
    }
    for k, v in fm_patch.items():
        core_patch[k] = v

    created = False
    if not target.is_file():
        created = True
        body = (
            f"# Bounded workflow run — `{rid}`\n\n"
            "Operator-visible record for **preflight → execute → validate → summary**. "
            "Hermes scaffolds this file only; **Repo B** owns bounded HTTP semantics and outcomes.\n"
        )
        default_fm = {
            **core_patch,
            "workflow_status": core_patch.get("workflow_status", "ready_to_run"),
            "workflow_stage": core_patch.get("workflow_stage", "preflight"),
            "retry_count": core_patch.get("retry_count", "0"),
            "escalation_count": core_patch.get("escalation_count", "0"),
            "requires_operator_checkpoint": core_patch.get("requires_operator_checkpoint", "true"),
        }
        inner = [f"{k}: {v}" for k, v in default_fm.items()]
        text = "---\n" + "\n".join(sorted(inner)) + "\n---\n\n" + body
    else:
        try:
            text = target.read_text(encoding="utf-8", errors="strict")
        except OSError as exc:
            return tool_error(str(exc), error_code="read_failed")
        except UnicodeDecodeError:
            return tool_error("non_utf8_file", error_code="read_failed")
        # Preserve explicit status/stage defaults only when creating; on patch merge core_patch
        merged = {**core_patch}
        if "workflow_status" not in merged:
            existing = _parse_fm_dict(text).get("workflow_status")
            if not existing:
                merged["workflow_status"] = "ready_to_run"
        if "workflow_stage" not in merged:
            existing_g = _parse_fm_dict(text).get("workflow_stage")
            if not existing_g:
                merged["workflow_stage"] = "preflight"
        new_text = _rebuild_file_with_fm(text, merged)
        if new_text is None:
            return tool_error("no_valid_yaml_frontmatter", error_code="invalid_run_record")
        text = new_text

    if append_md.strip():
        text = text.rstrip() + "\n\n" + append_md.strip() + "\n"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        return tool_error(str(exc), error_code="write_failed")

    return json.dumps(
        {
            "read_only": False,
            "tier": "5a_bounded_workflow_scaffolding",
            "path_relative_to_workflow": target.relative_to(wf_root).as_posix(),
            "created_this_call": created,
            "workflow_run_id": rid,
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def read_powerunits_bounded_workflow_run(relative_file_path: str, **_: Any) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _validated_under_workflow(nrel)
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
            "tier": "5a_bounded_workflow_scaffolding",
            "path_relative_to_workflow": target.relative_to(_workflow_root()).as_posix(),
            "chars": len(body),
            "body": body,
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def list_powerunits_bounded_workflow_workspace(
    subpath_prefix: str | None = None, **_: Any
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    root = _workflow_root()
    prefix = _normalize_rel(subpath_prefix or "")
    if prefix:
        try:
            base = (root / prefix).resolve()
            base.relative_to(root)
        except ValueError:
            return tool_error("invalid subpath_prefix", error_code="invalid_prefix")
    else:
        base = root

    rows: list[dict[str, Any]] = []
    if base.is_dir():
        for fp in sorted(base.rglob("*")):
            if not fp.is_file() or fp.is_symlink():
                continue
            try:
                rel = fp.relative_to(root).as_posix()
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
            if len(rows) >= _MAX_LIST:
                break

    return json.dumps(
        {
            "read_only": True,
            "tier": "5a_bounded_workflow_scaffolding",
            "workflow_root_relative": _WORKFLOW_REL_ROOT,
            "workflow_root_resolved": str(root),
            "listing_truncated": len(rows) >= _MAX_LIST,
            "entries": rows,
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def append_powerunits_bounded_workflow_note(
    relative_file_path: str,
    body: str,
    *,
    append_mode: str = "append",
    **_: Any,
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    mode = str(append_mode or "append").strip().lower()
    if mode not in {"append", "create_only"}:
        return tool_error("append_mode must be append or create_only", error_code="invalid_mode")

    chunk = str(body if body is not None else "")
    if len(chunk) > _MAX_NOTE_APPEND:
        return tool_error("body_too_large", error_code="limit_exceeded")

    ensure_powerunits_bounded_workflow_workspace()
    try:
        nrel = _normalize_rel(relative_file_path)
        target = _validated_note_rel(nrel)
    except ValueError as exc:
        return tool_error(str(exc), error_code="invalid_path")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = f"\n\n<!-- tier5a_note {stamp} -->\n{chunk}\n"

    existed = target.exists()
    if existed and mode == "create_only":
        return tool_error("target_exists", error_code="exists")
    wf_root = _workflow_root()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if existed:
            prev = target.read_text(encoding="utf-8", errors="strict")
            target.write_text(prev + block, encoding="utf-8", newline="\n")
        else:
            hdr = (
                f"# Workflow note\n\n"
                f"<!-- Tier 5A — bounded operator note ({target.relative_to(wf_root).as_posix()}) -->\n"
            )
            target.write_text(hdr + block.lstrip("\n"), encoding="utf-8", newline="\n")
    except OSError as exc:
        return tool_error(str(exc), error_code="write_failed")
    except UnicodeDecodeError:
        return tool_error("existing_file_non_utf8", error_code="read_failed")

    return json.dumps(
        {
            "read_only": False,
            "tier": "5a_bounded_workflow_scaffolding",
            "path_relative_to_workflow": target.relative_to(wf_root).as_posix(),
            "bytes_appended": len(block.encode("utf-8")),
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def summarize_powerunits_tier5a_bounded_workflow_lane(**_: Any) -> str:
    """Histograms + soft cautions for bounded workflow run records (no HTTP)."""

    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    root = _workflow_root()
    runs_dir = root / _RUN_SUBDIR
    now = datetime.now(timezone.utc)
    status_counts: dict[str, int] = {s: 0 for s in sorted(_WORKFLOW_STATUS_VALUES)}
    stage_counts: dict[str, int] = {s: 0 for s in sorted(_WORKFLOW_STAGE_VALUES)}
    stuck_running = 0
    high_retry = 0
    high_escalation_files = 0
    validate_pending = 0
    summary_pending = 0
    run_files = 0
    invalid_status = 0
    total_escalation = 0

    if runs_dir.is_dir():
        for fp in sorted(runs_dir.glob("*.md")):
            if not fp.is_file() or fp.is_symlink():
                continue
            run_files += 1
            try:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _parse_fm_dict(raw)
            st = str(fm.get("workflow_status") or "").strip()
            if not st or st not in _WORKFLOW_STATUS_VALUES:
                invalid_status += 1
                st_e = "ready_to_run"
            else:
                st_e = st
            status_counts[st_e] = status_counts.get(st_e, 0) + 1

            sg = str(fm.get("workflow_stage") or "").strip()
            if sg in _WORKFLOW_STAGE_VALUES:
                stage_counts[sg] = stage_counts.get(sg, 0) + 1

            if st_e == "validate_pending":
                validate_pending += 1
            if st_e == "summary_pending":
                summary_pending += 1

            try:
                rc = int(str(fm.get("retry_count") or "0"), 10)
            except ValueError:
                rc = 0
            if rc >= _CAUTION_RETRY_GE:
                high_retry += 1

            try:
                ec = int(str(fm.get("escalation_count") or "0"), 10)
            except ValueError:
                ec = 0
            total_escalation += ec
            if ec >= 2:
                high_escalation_files += 1

            if st_e == "running":
                mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
                upd = str(fm.get("updated_at_utc") or "").strip()
                ref = mtime
                if upd and "T" in upd:
                    try:
                        ref = datetime.fromisoformat(upd.replace("Z", "+00:00"))
                    except ValueError:
                        ref = mtime
                if now - ref > timedelta(hours=_STUCK_RUNNING_HOURS):
                    stuck_running += 1

    esc_dir = root / "escalation_notes"
    esc_note_files = 0
    if esc_dir.is_dir():
        for ef in esc_dir.rglob("*.md"):
            if ef.is_file() and not ef.is_symlink():
                esc_note_files += 1

    caution: list[str] = []
    if run_files >= _CAUTION_RUN_FILES:
        caution.append(f"tier5a_workflow_run_records_clutter:{run_files}>={_CAUTION_RUN_FILES}")
    if stuck_running:
        caution.append(f"tier5a_workflow_stuck_running:{stuck_running}")
    if high_retry:
        caution.append(f"tier5a_high_retry_runs:{high_retry}")
    if high_escalation_files:
        caution.append(f"tier5a_escalation_count_signals:{high_escalation_files}")
    if esc_note_files >= _CAUTION_ESCALATION_FILES:
        caution.append(
            f"tier5a_escalation_notes_backlog:{esc_note_files}>={_CAUTION_ESCALATION_FILES}"
        )
    if total_escalation >= _CAUTION_TOTAL_ESCALATION_SUM:
        caution.append(
            f"tier5a_escalation_count_accumulation:{total_escalation}>={_CAUTION_TOTAL_ESCALATION_SUM}"
        )
    if validate_pending >= _CAUTION_VALIDATE_PENDING:
        caution.append(
            f"tier5a_operator_review_overload_validate_pending:{validate_pending}>={_CAUTION_VALIDATE_PENDING}"
        )
    if summary_pending >= _CAUTION_SUMMARY_PENDING:
        caution.append(
            f"tier5a_operator_review_overload_summary_pending:{summary_pending}>={_CAUTION_SUMMARY_PENDING}"
        )

    return json.dumps(
        {
            "read_only": True,
            "tier": "5a_bounded_workflow_scaffolding",
            "run_record_files_scanned": run_files,
            "workflow_status_counts": {k: status_counts.get(k, 0) for k in sorted(_WORKFLOW_STATUS_VALUES)},
            "workflow_stage_counts": {k: stage_counts.get(k, 0) for k in sorted(_WORKFLOW_STAGE_VALUES)},
            "validate_pending_count": validate_pending,
            "summary_pending_count": summary_pending,
            "stuck_running_estimate": stuck_running,
            "runs_with_retry_count_ge_3": high_retry,
            "runs_with_escalation_count_ge_2": high_escalation_files,
            "sum_escalation_count_across_runs": total_escalation,
            "escalation_note_files_md": esc_note_files,
            "invalid_workflow_status_in_run_files": invalid_status,
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


def review_powerunits_bounded_workflow_runs(
    *,
    workflow_status_filter: str | None = None,
    max_entries: int | None = None,
    **_: Any,
) -> str:
    from tools.registry import tool_error

    if not check_powerunits_tier5a_bounded_workflow_scaffolding():
        return tool_error(
            "HERMES_POWERUNITS_CAPABILITY_TIER>=6 required for Tier 5A workflow scaffolding",
            error_code="tier_gate",
        )
    st_f = str(workflow_status_filter or "").strip() or None
    if st_f and st_f not in _WORKFLOW_STATUS_VALUES:
        return tool_error("invalid_workflow_status_filter", error_code="invalid_filter")

    cap = int(max_entries) if max_entries is not None else _REVIEW_BOARD_CAP
    if cap < 1:
        cap = 1
    cap = min(cap, _REVIEW_BOARD_CAP)

    runs_dir = _workflow_root() / _RUN_SUBDIR
    rows: list[dict[str, Any]] = []
    if runs_dir.is_dir():
        for fp in sorted(runs_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if not fp.is_file() or fp.is_symlink():
                continue
            try:
                raw = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _parse_fm_dict(raw)
            st = str(fm.get("workflow_status") or "").strip()
            if st_f and st != st_f:
                continue
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            rows.append(
                {
                    "relative_path": fp.relative_to(_workflow_root()).as_posix(),
                    "workflow_run_id": fm.get("workflow_run_id"),
                    "workflow_status": st or None,
                    "workflow_stage": fm.get("workflow_stage"),
                    "retry_count": fm.get("retry_count"),
                    "escalation_count": fm.get("escalation_count"),
                    "updated_at_utc": fm.get("updated_at_utc"),
                    "mtime_utc": mtime,
                }
            )

    total = len(rows)
    out = rows[:cap]
    caution: list[str] = []
    if total > cap:
        caution.append(f"tier5a_review_board_truncated:{total}>{cap}")

    return json.dumps(
        {
            "read_only": True,
            "tier": "5a_bounded_workflow_scaffolding",
            "filters": {"workflow_status": st_f},
            "matching_count": total,
            "max_entries": cap,
            "entries": out,
            "caution_flags": sorted(set(caution)),
            "doc_hint": "docs/powerunits_tier5a_bounded_workflow_scaffolding_overlay_v1.md",
        },
        ensure_ascii=False,
    )


_MANIFEST_SCHEMA = {
    "name": "manifest_powerunits_tier5a_bounded_workflow_scope",
    "description": (
        "Tier 5A ONLY (tier>=6). Workflow artifact roots under operator_bounded_workflows/ — "
        "NOT bounded HTTP execute tools and NOT Tier 4B governance manifest."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_ENSURE_SCHEMA = {
    "name": "ensure_powerunits_bounded_workflow_workspace",
    "description": "Tier>=6: create operator_bounded_workflows/ subtree + README pointer (idempotent).",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_UPSERT_SCHEMA = {
    "name": "upsert_powerunits_bounded_workflow_run",
    "description": (
        "Tier 5A: create or patch YAML frontmatter on ONE run record under run_records/ "
        "(bounded workflow state only; does not execute bounded HTTP)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_run_id": {"type": "string"},
            "relative_run_record_path": {"type": "string"},
            "frontmatter_patch": {"type": "object"},
            "append_markdown": {"type": "string"},
        },
        "required": ["workflow_run_id"],
    },
}
_READ_SCHEMA = {
    "name": "read_powerunits_bounded_workflow_run",
    "description": "Tier 5A: read one markdown file under operator_bounded_workflows/**.",
    "parameters": {
        "type": "object",
        "properties": {"relative_file_path": {"type": "string"}},
        "required": ["relative_file_path"],
    },
}
_LIST_SCHEMA = {
    "name": "list_powerunits_bounded_workflow_workspace",
    "description": (
        "Tier 5A listing under hermes_workspace/operator_bounded_workflows/** only — "
        "NOT list_hermes_workspace."
    ),
    "parameters": {
        "type": "object",
        "properties": {"subpath_prefix": {"type": "string"}},
        "required": [],
    },
}
_APPEND_SCHEMA = {
    "name": "append_powerunits_bounded_workflow_note",
    "description": (
        "Tier 5A: append/create a note under checkpoints/, bounded_logs/, escalation_notes/, "
        "experiment_records/, or skill_integration_test_notes/ — NOT run_records/ (use upsert)."
    ),
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
_SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_tier5a_bounded_workflow_lane",
    "description": (
        "Tier 5A workflow lane: run/status histograms + stuck/retry/escalation soft flags — "
        "NOT summarize_powerunits_option_d_bounded_window."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_REVIEW_SCHEMA = {
    "name": "review_powerunits_bounded_workflow_runs",
    "description": (
        "Tier 5A operator review board for run_records/*.md (filter by workflow_status optional)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "workflow_status_filter": {"type": "string", "enum": sorted(_WORKFLOW_STATUS_VALUES)},
            "max_entries": {"type": "integer"},
        },
        "required": [],
    },
}

_TOOLSET = "powerunits_tier5a_bounded_workflow_scaffolding"

registry.register(
    name="manifest_powerunits_tier5a_bounded_workflow_scope",
    toolset=_TOOLSET,
    schema=_MANIFEST_SCHEMA,
    handler=lambda args, **kw: manifest_powerunits_tier5a_bounded_workflow_scope(**kw),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="🗂️",
)
registry.register(
    name="ensure_powerunits_bounded_workflow_workspace",
    toolset=_TOOLSET,
    schema=_ENSURE_SCHEMA,
    handler=lambda args, **kw: ensure_powerunits_bounded_workflow_workspace(**kw),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="🧱",
)
registry.register(
    name="upsert_powerunits_bounded_workflow_run",
    toolset=_TOOLSET,
    schema=_UPSERT_SCHEMA,
    handler=lambda args, **kw: upsert_powerunits_bounded_workflow_run(
        workflow_run_id=str(args.get("workflow_run_id", "")),
        relative_run_record_path=args.get("relative_run_record_path"),
        frontmatter_patch=args.get("frontmatter_patch"),
        append_markdown=args.get("append_markdown"),
        **kw,
    ),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="📌",
)
registry.register(
    name="read_powerunits_bounded_workflow_run",
    toolset=_TOOLSET,
    schema=_READ_SCHEMA,
    handler=lambda args, **kw: read_powerunits_bounded_workflow_run(
        relative_file_path=str(args.get("relative_file_path", "")),
        **kw,
    ),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="📄",
)
registry.register(
    name="list_powerunits_bounded_workflow_workspace",
    toolset=_TOOLSET,
    schema=_LIST_SCHEMA,
    handler=lambda args, **kw: list_powerunits_bounded_workflow_workspace(
        subpath_prefix=args.get("subpath_prefix"),
        **kw,
    ),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="📚",
)
registry.register(
    name="append_powerunits_bounded_workflow_note",
    toolset=_TOOLSET,
    schema=_APPEND_SCHEMA,
    handler=lambda args, **kw: append_powerunits_bounded_workflow_note(
        relative_file_path=str(args.get("relative_file_path", "")),
        body=str(args.get("body", "")),
        append_mode=str(args.get("append_mode") or "append"),
        **kw,
    ),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="📝",
)
registry.register(
    name="summarize_powerunits_tier5a_bounded_workflow_lane",
    toolset=_TOOLSET,
    schema=_SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_tier5a_bounded_workflow_lane(**kw),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="🧮",
)
registry.register(
    name="review_powerunits_bounded_workflow_runs",
    toolset=_TOOLSET,
    schema=_REVIEW_SCHEMA,
    handler=lambda args, **kw: review_powerunits_bounded_workflow_runs(
        workflow_status_filter=args.get("workflow_status_filter"),
        max_entries=args.get("max_entries"),
        **kw,
    ),
    check_fn=check_powerunits_tier5a_bounded_workflow_scaffolding,
    emoji="🧾",
)
