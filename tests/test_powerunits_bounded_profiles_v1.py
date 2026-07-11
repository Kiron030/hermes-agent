"""Tests for bounded env profile expansion (v1)."""

from __future__ import annotations

import os

import pytest

import powerunits_bounded_profiles_v1 as profiles


def test_apply_profile_fills_missing_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED", "1")

    out = profiles.apply_bounded_profile_to_process_env()
    assert out["profile"] == "stage1_read_health"
    assert out["unknown"] is False
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["applied"]
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED" in out["skipped_explicit"]
    assert os.getenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED") == "1"
    assert os.getenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED") == "1"


def test_evaluate_profile_alignment_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    out = profiles.evaluate_bounded_profile_alignment()
    assert out["aligned"] is False
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["missing_truthy"]
