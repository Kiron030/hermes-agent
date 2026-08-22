"""Task A — effective callable first_safe_v1 surface, tiers 0–6."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.powerunits_golden.env import (
    ENV_PROFILE,
    UNSAFE_FREEDOMS_FIRST_SAFE_DENIES,
    apply_operator_ready_env,
)
from tests.powerunits_golden.surface import (
    absent_unsafe_freedoms,
    capture_tier_surface,
    explicit_request_cannot_restore,
)

FIXTURE = Path(__file__).parent / "fixtures" / "effective_surface.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("tier", range(7))
def test_effective_callable_surface_matches_frozen_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tier: int,
) -> None:
    apply_operator_ready_env(monkeypatch, tier=tier)
    captured = capture_tier_surface(tier)
    frozen = _load_fixture()["tiers"][str(tier)]

    assert captured["callable"] == frozen["callable"]
    assert captured["tool_count"] == frozen["tool_count"]
    assert captured["catalogued"] == frozen["catalogued"]
    assert captured["catalogued_not_callable"] == frozen["catalogued_not_callable"]
    assert captured["requested_not_callable"] == frozen["requested_not_callable"]
    assert captured["capability_groups"] == frozen["capability_groups"]
    assert "session_search" not in captured["catalogued"]
    assert "session_search" not in captured["callable"]
    assert "session_search" in captured["requested_not_callable"]


@pytest.mark.parametrize("tier", range(7))
def test_session_search_absent_even_when_explicitly_requested(
    monkeypatch: pytest.MonkeyPatch,
    tier: int,
) -> None:
    apply_operator_ready_env(monkeypatch, tier=tier)
    leaked = explicit_request_cannot_restore(["session_search"], ["session_search"])
    assert leaked == []


@pytest.mark.parametrize("tier", range(7))
def test_unsafe_freedoms_absent_from_callable_surface(
    monkeypatch: pytest.MonkeyPatch,
    tier: int,
) -> None:
    apply_operator_ready_env(monkeypatch, tier=tier)
    captured = capture_tier_surface(tier)
    assert absent_unsafe_freedoms(captured["callable"]) == []
    leaked = explicit_request_cannot_restore(
        UNSAFE_FREEDOMS_FIRST_SAFE_DENIES,
        ["session_search", "terminal", "web", "delegate", "cron", "browser", "file"],
    )
    assert leaked == []


def test_fixture_distinguishes_catalogued_requested_callable() -> None:
    frozen = _load_fixture()
    assert frozen["env_profile"] == ENV_PROFILE
    assert frozen["policy"] == "first_safe_v1"
    for tier in range(7):
        row = frozen["tiers"][str(tier)]
        assert "catalogued" in row
        assert "requested" in row
        assert "callable" in row
        assert isinstance(row["tool_count"], int)
