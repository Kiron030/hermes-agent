"""S0-B: every registered PowerUnits operation has exactly one effect class."""

from __future__ import annotations

import pytest

from tools.powerunits_bounded_effects_v1 import (
    EFFECT_CLASS_BY_OPERATION,
    EFFECT_CLASSES,
    READ,
    READ_WITH_SIDE_EFFECT,
    BOUNDED_WRITE,
    BOUNDED_WRITE_AMPLIFYING,
    DESTRUCTIVE,
    UnclassifiedPowerUnitsOperation,
    effect_class_for,
    registered_powerunits_operations,
    unclassified_registered_operations,
)


def test_every_registered_powerunits_operation_has_exactly_one_class() -> None:
    names = registered_powerunits_operations()
    assert names, "expected live PowerUnits registry discovery"
    missing = unclassified_registered_operations(names)
    extra = sorted(set(EFFECT_CLASS_BY_OPERATION) - set(names))
    assert missing == [], f"registered without classification: {missing}"
    assert extra == [], f"classified but not registered: {extra}"
    for name in names:
        classified = effect_class_for(name)
        assert classified in EFFECT_CLASSES
        assert list(EFFECT_CLASS_BY_OPERATION.keys()).count(name) == 1


def test_unknown_operation_fail_closed() -> None:
    with pytest.raises(UnclassifiedPowerUnitsOperation):
        effect_class_for("powerunits_totally_new_unclassified_op")
    with pytest.raises(UnclassifiedPowerUnitsOperation):
        effect_class_for("")


def test_write_families_match_roadmap() -> None:
    writes = {
        name
        for name, cls in EFFECT_CLASS_BY_OPERATION.items()
        if cls == BOUNDED_WRITE
    }
    amplifying = {
        name
        for name, cls in EFFECT_CLASS_BY_OPERATION.items()
        if cls == BOUNDED_WRITE_AMPLIFYING
    }
    assert writes == {
        "execute_powerunits_option_d_bounded_slice",
        "execute_powerunits_market_features_bounded_de_slice",
        "execute_powerunits_market_driver_features_bounded_de_slice",
        "execute_powerunits_entsoe_market_bounded_slice",
        "execute_powerunits_entsoe_forecast_bounded_slice",
        "execute_powerunits_era5_weather_bounded_slice",
        "execute_powerunits_outage_repair_bounded_slice",
        "save_hermes_workspace_note",
    }
    assert amplifying == {
        "campaign_powerunits_entsoe_market_bounded_de",
        "campaign_powerunits_era5_weather_bounded_de",
    }
    assert DESTRUCTIVE not in EFFECT_CLASS_BY_OPERATION.values()


def test_read_with_side_effect_is_classified_not_write() -> None:
    assert effect_class_for("validate_powerunits_option_d_bounded_window") == READ_WITH_SIDE_EFFECT
    assert effect_class_for("scan_powerunits_entsoe_market_bounded_coverage_de") == READ_WITH_SIDE_EFFECT
    assert effect_class_for("research_powerunits_energy_web_v1") == READ_WITH_SIDE_EFFECT
    assert effect_class_for("read_powerunits_coverage_snapshot_v1") == READ
