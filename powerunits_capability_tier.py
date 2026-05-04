"""Powerunits progressive capability tier (Phase 0: observability only).

Reads ``HERMES_POWERUNITS_CAPABILITY_TIER`` from the environment. Values above
``0`` are not yet wired to runtime behavior; they exist for documentation and
future staged liberation. See ``docs/powerunits_hermes_progressive_posture_v1.md``.
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
    print(
        "[powerunits] HERMES_POWERUNITS_CAPABILITY_TIER="
        f"{tier} (tier>0: label only until wired per "
        "docs/powerunits_hermes_progressive_posture_v1.md)",
        flush=True,
    )
