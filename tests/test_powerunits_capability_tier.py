"""Sanity checks for Phase 0 capability tier scaffolding."""

from __future__ import annotations

import pytest

from powerunits_capability_tier import read_powerunits_capability_tier


@pytest.fixture(autouse=True)
def clear_tier_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_CAPABILITY_TIER", raising=False)


def test_default_is_zero() -> None:
    assert read_powerunits_capability_tier() == 0


def test_parses_valid_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "2")
    assert read_powerunits_capability_tier() == 2


def test_invalid_string_defaults_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "nope")
    assert read_powerunits_capability_tier() == 0


def test_clamps_high(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "99")
    assert read_powerunits_capability_tier() == 3


def test_clamps_low(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "-5")
    assert read_powerunits_capability_tier() == 0
