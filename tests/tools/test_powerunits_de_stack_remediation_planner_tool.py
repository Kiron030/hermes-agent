"""Tests for read-only DE stack remediation planner Hermes tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tools.powerunits_de_stack_remediation_planner_tool import (
    check_powerunits_de_stack_remediation_planner_requirements,
    plan_powerunits_de_stack_remediation,
)


def test_gate_requires_flag_and_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED", raising=False)
    assert check_powerunits_de_stack_remediation_planner_requirements() is False
    monkeypatch.setenv("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED", "1")
    monkeypatch.delenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", raising=False)
    assert check_powerunits_de_stack_remediation_planner_requirements() is False
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.delenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", raising=False)
    assert check_powerunits_de_stack_remediation_planner_requirements() is False
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "s")
    assert check_powerunits_de_stack_remediation_planner_requirements() is True


def test_disabled_returns_feature_disabled_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED", raising=False)
    out = json.loads(
        plan_powerunits_de_stack_remediation(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-02T00:00:00Z",
        )
    )
    assert out["error_code"] == "feature_disabled"


def test_happy_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sekret")

    class Resp:
        status_code = 200
        content = b"{}"
        text = "{}"

        def json(self) -> dict:
            return {
                "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "hermes_statement": "read_only_remediation_plan_no_writes",
                "planner": {"id": "de_bounded_stack_read_only_v1"},
                "slice": {"country_code": "DE"},
                "plan_outcome": "mixed_state",
                "family_states": [],
                "recommended_sequence": [],
                "notes": [],
            }

    out = json.loads(
        plan_powerunits_de_stack_remediation(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-03T00:00:00Z",
            _http_post=lambda *_a: Resp(),
        )
    )
    assert out["http_ok"] is True
    assert out["plan_outcome"] == "mixed_state"
    assert "read_only" in str(out["hermes_statement"]).lower()


def test_validation_span_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sekret")
    out = json.loads(
        plan_powerunits_de_stack_remediation(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-02-10T00:00:00Z",
            _http_post=MagicMock(),
        )
    )
    assert out.get("plan_attempted") is False
    assert "validation_messages" in out
