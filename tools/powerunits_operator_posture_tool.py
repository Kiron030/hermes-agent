#!/usr/bin/env python3
"""
Read-only operator posture snapshot for Powerunits Hermes (Phase 1B).

Does not mutate config, workspace, or runtime. See canonical roadmap:
docs/powerunits_hermes_progressive_posture_v1.md
"""

from __future__ import annotations

import json
import os
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from tools.registry import registry


def check_powerunits_operator_posture_requirements() -> bool:
    return True


def _installed_hermes_version() -> str | None:
    try:
        return str(pkg_version("hermes-agent"))
    except PackageNotFoundError:
        return None


def _safe_curator_snapshot(hermes_home: Path) -> dict[str, Any]:
    snap: dict[str, Any] = {
        "config_yaml_present": False,
        "auxiliary.curator.enabled": None,
        "parse_error": False,
    }
    cfg_path = hermes_home / "config.yaml"
    if not cfg_path.is_file():
        return snap
    snap["config_yaml_present"] = True
    if yaml is None:
        snap["parse_error"] = True
        return snap
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, dict):
            snap["parse_error"] = True
            return snap
        aux = data.get("auxiliary")
        if not isinstance(aux, dict):
            return snap
        curator = aux.get("curator")
        if isinstance(curator, dict) and "enabled" in curator:
            snap["auxiliary.curator.enabled"] = bool(curator["enabled"])
    except Exception:
        snap["parse_error"] = True
    return snap


def _exports_phase1_signals(hermes_home: Path) -> dict[str, Any]:
    """Subset of Phase 1A summarize; skips if workspace tooling fails."""

    workspace_root = (hermes_home / "hermes_workspace").resolve()
    pointer = workspace_root / "exports" / "EXPORTS_PHASE1_OPERATOR.txt"

    brief: dict[str, Any] = {
        "exports_pointer_present": pointer.is_file(),
        "summarize_attempted": False,
    }

    try:
        from tools.powerunits_workspace_tool import summarize_powerunits_workspace_exports

        raw = summarize_powerunits_workspace_exports()
        obj = json.loads(raw)
        if isinstance(obj.get("error"), str):
            brief["summarize_attempted"] = True
            brief["summarize_error"] = obj["error"]
            return brief

        brief["summarize_attempted"] = True
        brief["file_count"] = obj.get("file_count")
        brief["total_bytes"] = obj.get("total_bytes")
        brief["caution_flags"] = obj.get("caution_flags", [])
    except Exception as exc:
        brief["summarize_skipped_reason"] = str(exc)

    return brief


def summarize_powerunits_operator_posture(**_: Any) -> str:
    """Return JSON: capability tier, runtime policy hints, bounded posture, Phase 1A export signals."""

    try:
        from powerunits_capability_tier import read_powerunits_capability_tier

        hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))

        tier_effective = read_powerunits_capability_tier()
        raw_tier_env = os.getenv("HERMES_POWERUNITS_CAPABILITY_TIER")
        raw_tier_shown = (raw_tier_env or "").strip() or None

        policy = os.getenv("HERMES_POWERUNITS_RUNTIME_POLICY", "").strip()

        curator = _safe_curator_snapshot(hermes_home.resolve())
        exports_signals = _exports_phase1_signals(hermes_home)

        caution: list[str] = []

        if tier_effective > 0:
            caution.append(
                "tier_gt_zero_label_only:no extra runtime widen until roadmap wires tier (see roadmap)"
            )
        if not policy:
            caution.append(
                "runtime_policy_unset:expect HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1 for bounded Powerunits"
            )
        elif policy != "first_safe_v1":
            caution.append(f"runtime_policy_non_default:{policy}")

        if curator.get("auxiliary.curator.enabled") is True:
            caution.append("curator_enabled_true:confirm intentional before tier increases")

        if curator.get("parse_error"):
            caution.append(
                "config_yaml_curator_field_unparsed:inspect $HERMES_HOME/config.yaml manually"
            )

        for flag in exports_signals.get("caution_flags") or []:
            caution.append(f"exports_phase_1a:{flag}")

        if exports_signals.get("summarize_error"):
            caution.append(f"exports_summarize_failed:{exports_signals['summarize_error']}")

        bounded_assumptions = [
            "Repo B stays canonical HTTP/product truth — Hermes is thin operator.",
            "Telegram/tool surface remains gateway + first_safe_v1 allowlist unless explicitly redeployed otherwise.",
            "Workspace writes stay under hermes_workspace allowlisted dirs; exports Phase 1A uses summarize_powerunits_workspace_exports for hygiene hints.",
            "Hermes-derived CSV/files under exports are never authoritative over Repo B JSON.",
        ]

        operator_before_tier_up = [
            "Run bounded smokes per RUNBOOK.hermes-stage1-validation.md § post-deploy.",
            "Record fingerprint: image digest or release tag + HERMES_POWERUNITS_CAPABILITY_TIER + policy env + curator flag.",
            "Review caution_flags above; investigate exports summarize failures before expanding freedom.",
            "Prefer git tag powerunits-tier0-baseline-* and optional HERMES_HOMEbackup before uplift (roadmap § Rollback).",
        ]

        return json.dumps(
            {
                "read_only": True,
                "phase": "1B",
                "tool_name": "summarize_powerunits_operator_posture",
                "detail_doc": "docs/powerunits_operator_posture_diagnostics_v1.md",
                "canonical_roadmap": "docs/powerunits_hermes_progressive_posture_v1.md",
                "environment": {
                    "HERMES_HOME": str(hermes_home),
                    "HERMES_POWERUNITS_CAPABILITY_TIER_env": raw_tier_shown,
                    "tier_effective_integer": tier_effective,
                    "HERMES_POWERUNITS_RUNTIME_POLICY": policy or None,
                },
                "hermes_pkg_version_reported": _installed_hermes_version(),
                "config_curator_observation_read_only": curator,
                "phase_1a_exports_signals_read_only": exports_signals,
                "bounded_assumptions_summary": bounded_assumptions,
                "operator_next_checks_before_tier_increase": operator_before_tier_up,
                "caution_flags": sorted(set(caution)),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "read_only": True,
                "error": str(exc),
                "error_code": "operator_posture_summary_failed",
                "canonical_roadmap": "docs/powerunits_hermes_progressive_posture_v1.md",
            },
            ensure_ascii=False,
        )


POSTURE_SUMMARY_SCHEMA = {
    "name": "summarize_powerunits_operator_posture",
    "description": (
        "Read-only Powerunits operator posture (Phase 1B): tier label, runtime policy env, curator flag from "
        "config.yaml (observation only), Phase 1A export hygiene subset, bounded assumptions pointers, tier-up checklist. "
        "Does not mutate state. Canonical roadmap: docs/powerunits_hermes_progressive_posture_v1.md"
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


registry.register(
    name="summarize_powerunits_operator_posture",
    toolset="powerunits_operator_posture",
    schema=POSTURE_SUMMARY_SCHEMA,
    handler=lambda args, **kw: summarize_powerunits_operator_posture(**kw),
    check_fn=check_powerunits_operator_posture_requirements,
    emoji="🧭",
)
