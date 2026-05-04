"""Powerunits progressive capability tier (Phase 0+) plus progressive overlays.

Reads ``HERMES_POWERUNITS_CAPABILITY_TIER`` from the environment (integer ``0``–``3``).

- **0:** Baseline; overlays off in policy merge (except static allowlist).
- **≥ 1:** Phase **2A** — ``powerunits_tier1_analysis``.
- **≥ 2:** Adds Phase **2B** — ``powerunits_tier2_allowlisted_read``.
- **3:** Adds **Tier 3** — ``powerunits_tier3_skills_integration`` (bounded skills observe / propose-only tools).

Canonical roadmap: ``docs/powerunits_hermes_progressive_posture_v1.md``.
"""

from __future__ import annotations

import os


def read_powerunits_capability_tier() -> int:
    """Return an integer in ``0``..``3`` from ``HERMES_POWERUNITS_CAPABILITY_TIER``.

    Empty, missing, or non-numeric values default to ``0``. Out-of-range values
    are clamped (no exceptions).
    """
    raw = os.environ.get("HERMES_POWERUNITS_CAPABILITY_TIER", "0").strip()
    try:
        v = int(raw, 10)
    except ValueError:
        return 0
    return max(0, min(3, v))


def log_startup_capability_tier_notice() -> None:
    """Emit a single startup line for container logs (idempotent observation)."""
    tier = read_powerunits_capability_tier()
    extra = ""
    if tier >= 3:
        extra = "; Tier 3 skills-integration overlay eligible (tier>=3)"
    elif tier >= 2:
        extra = "; Phase 2A+2B overlays eligible (tier>=2)"
    elif tier >= 1:
        extra = "; Phase 2A overlay eligible (tier>=1)"
    print(
        "[powerunits] HERMES_POWERUNITS_CAPABILITY_TIER="
        f"{tier}{extra} — see docs/powerunits_hermes_progressive_posture_v1.md",
        flush=True,
    )
