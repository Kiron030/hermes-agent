"""Task B + H — effect-class inventory and READ_WITH_SIDE_EFFECT assumptions."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from tools.powerunits_bounded_effects_v1 import (
    BOUNDED_WRITE,
    BOUNDED_WRITE_AMPLIFYING,
    DESTRUCTIVE,
    EFFECT_CLASS_BY_OPERATION,
    READ,
    READ_WITH_SIDE_EFFECT,
    effect_class_for,
    registered_powerunits_operations,
    unclassified_registered_operations,
)

FIXTURE = Path(__file__).parent / "fixtures" / "effect_classes.json"

_SCAFFOLDING = (
    "ensure_powerunits_governance_workspace",
    "ensure_powerunits_bounded_workflow_workspace",
)


def test_every_registered_operation_has_exactly_one_class() -> None:
    names = registered_powerunits_operations()
    assert names
    assert unclassified_registered_operations(names) == []
    extra = sorted(set(EFFECT_CLASS_BY_OPERATION) - set(names))
    assert extra == []
    for name in names:
        assert effect_class_for(name) in {
            READ,
            READ_WITH_SIDE_EFFECT,
            BOUNDED_WRITE,
            BOUNDED_WRITE_AMPLIFYING,
            DESTRUCTIVE,
        }


def test_effect_class_snapshot_matches_registry() -> None:
    frozen = json.loads(FIXTURE.read_text(encoding="utf-8"))
    live = {
        name: EFFECT_CLASS_BY_OPERATION[name]
        for name in sorted(EFFECT_CLASS_BY_OPERATION)
    }
    assert live == frozen["operations"]
    counts = {
        cls: sorted(name for name, found in live.items() if found == cls)
        for cls in (
            READ,
            READ_WITH_SIDE_EFFECT,
            BOUNDED_WRITE,
            BOUNDED_WRITE_AMPLIFYING,
            DESTRUCTIVE,
        )
    }
    assert {key: len(value) for key, value in counts.items()} == frozen["counts"]
    assert frozen["counts"][DESTRUCTIVE] == 0


def test_read_with_side_effect_assumptions_hold() -> None:
    from tools import powerunits_tier4b_review_governance_tool as t4b
    from tools import powerunits_tier5a_bounded_workflow_tool as t5

    for name in _SCAFFOLDING:
        assert effect_class_for(name) == READ_WITH_SIDE_EFFECT

    gov_src = inspect.getsource(t4b.ensure_powerunits_governance_workspace)
    wf_src = inspect.getsource(t5.ensure_powerunits_bounded_workflow_workspace)
    assert "Create governance subdirs" in (t4b.ensure_powerunits_governance_workspace.__doc__ or "")
    assert "mkdir" in gov_src
    assert "mkdir" in wf_src
    assert "require_powerunits_write_approval" not in gov_src
    assert "require_powerunits_write_approval" not in wf_src
    assert "_http_post" not in gov_src
    assert "_http_post" not in wf_src

    assert effect_class_for("validate_powerunits_option_d_bounded_window") == READ_WITH_SIDE_EFFECT
    assert effect_class_for("scan_powerunits_entsoe_market_bounded_coverage_de") == READ_WITH_SIDE_EFFECT
    assert effect_class_for("research_powerunits_energy_web_v1") == READ_WITH_SIDE_EFFECT
    assert effect_class_for("read_powerunits_coverage_snapshot_v1") == READ
