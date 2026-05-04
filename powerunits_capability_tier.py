"""Powerunits progressive capability tier (Phase 0+) plus Phase 2A/2B gates.

Reads ``HERMES_POWERUNITS_CAPABILITY_TIER`` from the environment (integer ``0``–``3``).

- **0:** Baseline; Phase **1A/1B** only; Telegram does **not** include overlay toolsets.
- **≥ 1:** Enables **Phase 2A** (``powerunits_tier1_analysis``) when policy runs on the gateway.
- **≥ 2:** Additionally enables **Phase 2B** (``powerunits_tier2_allowlisted_read``) — broader allowlisted locals read.

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
    if tier >= 2:
        extra = "; Phase 2A+2B overlays eligible (tier>=2)"
    elif tier >= 1:
        extra = "; Phase 2A overlay eligible (tier>=1)"
    print(
        "[powerunits] HERMES_POWERUNITS_CAPABILITY_TIER="
        f"{tier}{extra} — see docs/powerunits_hermes_progressive_posture_v1.md",
        flush=True,
    )
