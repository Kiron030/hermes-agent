"""
Bounded env **profiles** for Powerunits Hermes (v1).

Operators set one profile on Railway instead of dozens of individual gates::

    HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health

At container start ``docker/apply_powerunits_runtime_policy.py`` calls
:func:`persist_bounded_profile_to_hermes_env` so the supervised gateway loads
profile gates from ``$HERMES_HOME/.env``. Explicit Railway env vars are **never
overwritten** (override wins).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Final

from utils import atomic_replace

PROFILE_ENV: Final[str] = "HERMES_POWERUNITS_BOUNDED_PROFILE"
ENV_MANAGED_BEGIN: Final[str] = (
    "# BEGIN powerunits_bounded_profile_v1 (managed by apply_powerunits_runtime_policy)"
)
ENV_MANAGED_END: Final[str] = "# END powerunits_bounded_profile_v1"
_ENV_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# Read-only data health + bounded reads (no primary execute families).
STAGE1_READ_HEALTH: Final[dict[str, str]] = {
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED": "1",
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED": "1",
    "HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED": "1",
    "HERMES_POWERUNITS_REPO_B_READ_ENABLED": "1",
    "HERMES_POWERUNITS_TIMESCALE_READ_ENABLED": "1",
    "HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED": "1",
    "HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED": "1",
    "HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED": "1",
    # Validate/summary/readiness via legacy per-step keys (no primary ⇒ no execute).
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_READINESS_ENABLED": "1",
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED": "1",
    "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED": "1",
    "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED": "1",
}

# Full Stage-1 operator: read_health + bounded execute families (DE/PL market features, ENTSO-E, ERA5, outage repair).
STAGE1_OPERATOR_EXECUTE: Final[dict[str, str]] = {
    **STAGE1_READ_HEALTH,
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED": "1",
    "HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED": "1",
    "HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED": "1",
}

PROFILE_ENV_EXPANSIONS_V1: Final[dict[str, dict[str, str]]] = {
    "stage1_read_health": STAGE1_READ_HEALTH,
    "stage1_operator_execute": STAGE1_OPERATOR_EXECUTE,
}

PROFILE_DESCRIPTIONS_V1: Final[dict[str, str]] = {
    "stage1_read_health": (
        "Data-health triptychon + bounded reads/validates; no primary execute families."
    ),
    "stage1_operator_execute": (
        "read_health plus bounded execute (market features, ENTSO-E, ERA5, outage repair)."
    ),
}


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def active_bounded_profile_id() -> str | None:
    raw = (os.getenv(PROFILE_ENV) or "").strip().lower()
    return raw or None


def _parse_env_keys_outside_managed_block(content: str) -> set[str]:
    keys: set[str] = set()
    in_managed = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == ENV_MANAGED_BEGIN:
            in_managed = True
            continue
        if stripped == ENV_MANAGED_END:
            in_managed = False
            continue
        if in_managed or not stripped or stripped.startswith("#"):
            continue
        match = _ENV_KEY_RE.match(stripped)
        if match:
            keys.add(match.group(1))
    return keys


def _strip_managed_block(content: str) -> str:
    lines = content.splitlines()
    out: list[str] = []
    in_managed = False
    for line in lines:
        stripped = line.strip()
        if stripped == ENV_MANAGED_BEGIN:
            in_managed = True
            continue
        if stripped == ENV_MANAGED_END:
            in_managed = False
            continue
        if not in_managed:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def _profile_expansion_for_active_profile() -> tuple[str | None, dict[str, str] | None, bool]:
    profile = active_bounded_profile_id()
    if not profile:
        return None, None, False
    expansion = PROFILE_ENV_EXPANSIONS_V1.get(profile)
    if expansion is None:
        return profile, None, True
    return profile, expansion, False


def persist_bounded_profile_to_hermes_env(env_path: Path) -> dict[str, Any]:
    """Write profile gates into ``$HERMES_HOME/.env`` for the gateway process.

    ``apply_powerunits_runtime_policy.py`` runs in a short-lived init subprocess;
    ``os.environ`` mutations there do not reach the supervised gateway. The gateway
    loads ``$HERMES_HOME/.env`` via ``load_hermes_dotenv()`` at import time.
    """
    profile, expansion, unknown = _profile_expansion_for_active_profile()
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    file_keys = _parse_env_keys_outside_managed_block(existing)
    base = _strip_managed_block(existing)

    if not profile:
        if base != existing.rstrip("\n"):
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(f"{base}\n" if base else "", encoding="utf-8")
        return {"profile": None, "persisted": [], "skipped_explicit": [], "env_path": str(env_path)}

    if unknown or expansion is None:
        return {
            "profile": profile,
            "unknown": True,
            "persisted": [],
            "skipped_explicit": [],
            "env_path": str(env_path),
            "known_profiles": sorted(PROFILE_ENV_EXPANSIONS_V1.keys()),
        }

    persisted: list[str] = []
    skipped_explicit: list[str] = []
    managed_lines: list[str] = [ENV_MANAGED_BEGIN, f"# profile={profile}"]
    for key, value in expansion.items():
        if (os.getenv(key) or "").strip() or key in file_keys:
            skipped_explicit.append(key)
            continue
        managed_lines.append(f"{key}={value}")
        persisted.append(key)
        os.environ[key] = value
    managed_lines.append(ENV_MANAGED_END)

    parts: list[str] = []
    if base:
        parts.append(base)
    if persisted:
        parts.append("\n".join(managed_lines))

    env_path.parent.mkdir(parents=True, exist_ok=True)
    new_content = "\n\n".join(parts)
    if new_content:
        new_content += "\n"

    tmp = env_path.with_suffix(".env.tmp")
    tmp.write_text(new_content, encoding="utf-8")
    atomic_replace(tmp, env_path)

    return {
        "profile": profile,
        "unknown": False,
        "description": PROFILE_DESCRIPTIONS_V1.get(profile),
        "persisted": persisted,
        "skipped_explicit": skipped_explicit,
        "total_keys_in_profile": len(expansion),
        "env_path": str(env_path),
    }


def apply_bounded_profile_to_process_env() -> dict[str, Any]:
    """Fill missing profile env keys; never override explicit Railway values."""
    profile = active_bounded_profile_id()
    if not profile:
        return {"profile": None, "applied": [], "skipped_explicit": [], "unknown": False}

    expansion = PROFILE_ENV_EXPANSIONS_V1.get(profile)
    if expansion is None:
        return {
            "profile": profile,
            "unknown": True,
            "applied": [],
            "skipped_explicit": [],
            "known_profiles": sorted(PROFILE_ENV_EXPANSIONS_V1.keys()),
        }

    applied: list[str] = []
    skipped_explicit: list[str] = []
    for key, value in expansion.items():
        if (os.getenv(key) or "").strip():
            skipped_explicit.append(key)
        else:
            os.environ[key] = value
            applied.append(key)

    return {
        "profile": profile,
        "unknown": False,
        "description": PROFILE_DESCRIPTIONS_V1.get(profile),
        "applied": applied,
        "skipped_explicit": skipped_explicit,
        "total_keys_in_profile": len(expansion),
    }


def evaluate_bounded_profile_alignment() -> dict[str, Any]:
    """Compare active profile (if any) against current process env."""
    profile = active_bounded_profile_id()
    if not profile:
        return {"profile": None, "aligned": None, "missing_truthy": [], "unknown_profile": False}

    expansion = PROFILE_ENV_EXPANSIONS_V1.get(profile)
    if expansion is None:
        return {
            "profile": profile,
            "aligned": False,
            "unknown_profile": True,
            "missing_truthy": [],
            "known_profiles": sorted(PROFILE_ENV_EXPANSIONS_V1.keys()),
        }

    missing: list[str] = []
    for key in expansion:
        if not _truthy(os.getenv(key)):
            missing.append(key)

    return {
        "profile": profile,
        "description": PROFILE_DESCRIPTIONS_V1.get(profile),
        "unknown_profile": False,
        "aligned": len(missing) == 0,
        "missing_truthy": missing,
        "missing_count": len(missing),
        "total_keys_in_profile": len(expansion),
    }
