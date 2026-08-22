"""Generate frozen R0 fixtures from the live first_safe surface.

Run from repo root after applying no production env:

    .venv/Scripts/python -m tests.powerunits_golden.generate_fixtures
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.powerunits_golden.contracts import BOUNDED_HTTP_CONTRACTS
from tests.powerunits_golden.env import ENV_PROFILE, apply_operator_ready_env
from tests.powerunits_golden.surface import capture_tier_surface
from tools.powerunits_bounded_effects_v1 import (
    BOUNDED_WRITE,
    BOUNDED_WRITE_AMPLIFYING,
    DESTRUCTIVE,
    EFFECT_CLASS_BY_OPERATION,
    READ,
    READ_WITH_SIDE_EFFECT,
)

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"


def _write(name: str, payload: dict) -> None:
    path = FIXTURES / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    tiers = {}
    try:
        for tier in range(7):
            apply_operator_ready_env(monkeypatch, tier=tier)
            tiers[str(tier)] = capture_tier_surface(tier)
    finally:
        monkeypatch.undo()

    _write(
        "effective_surface.json",
        {
            "policy": "first_safe_v1",
            "env_profile": ENV_PROFILE,
            "tiers": tiers,
        },
    )

    live = {
        name: EFFECT_CLASS_BY_OPERATION[name]
        for name in sorted(EFFECT_CLASS_BY_OPERATION)
    }
    counts = {
        cls: sum(1 for found in live.values() if found == cls)
        for cls in (
            READ,
            READ_WITH_SIDE_EFFECT,
            BOUNDED_WRITE,
            BOUNDED_WRITE_AMPLIFYING,
            DESTRUCTIVE,
        )
    }
    _write(
        "effect_classes.json",
        {
            "operations": live,
            "counts": counts,
        },
    )

    _write(
        "manifest.json",
        {
            "slice": "R0",
            "gold_kind": "GOLDEN_BEHAVIOUR",
            "not": "GOLDEN_IMPLEMENTATION",
            "policy": "first_safe_v1",
            "env_profile": ENV_PROFILE,
            "effective_surface": "fixtures/effective_surface.json",
            "effect_classes": "fixtures/effect_classes.json",
            "bounded_operations": [item.operation for item in BOUNDED_HTTP_CONTRACTS],
            "bounded_operation_count": len(BOUNDED_HTTP_CONTRACTS),
            "happy_path_fixtures": len(BOUNDED_HTTP_CONTRACTS),
            "negative_path_fixtures": len(BOUNDED_HTTP_CONTRACTS),
            "security_negatives": {
                "session_search_absent_tiers_0_6": True,
                "unsafe_freedoms_absent": True,
                "write_deny_http_post_count_0": True,
                "yolo_without_exact_auth_no_write": True,
                "cron_approve_without_exact_auth_no_write": True,
                "local_durable_writer_deny_state_unchanged": True,
                "campaign_approval_does_not_authorize_slices": True,
                "distinct_identities": True,
                "https_required": True,
                "exact_host_matching": True,
                "foreign_host_enforce_no_http": True,
                "enforce_empty_allowlist_refuses": True,
                "model_cannot_supply_host_url_route": True,
            },
            "telegram_contracts": [
                "chat_summary_shape",
                "model_readable_tool_error",
                "powerunits_read_correlation_id",
                "energy_web_sources_disclaimer",
            ],
            "r3_consumption": {
                "compare_callable_names": "fixtures/effective_surface.json -> tiers.*.callable",
                "compare_effect_classes": "fixtures/effect_classes.json -> operations",
                "compare_bounded_fields": "tests.powerunits_golden.contracts.BOUNDED_HTTP_CONTRACTS",
                "compare_security_negatives": "security_negatives",
                "compare_telegram": "telegram_contracts",
            },
        },
    )


if __name__ == "__main__":
    main()
