"""Tests for bounded outage repair execute tool (Hermes → Repo B)."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_outage_repair_bounded_execute_tool as exec_mod
from tools.powerunits_bounded_family_gates import (
    OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV,
    OUTAGE_REPAIR_BOUNDED_LEGACY_ENV,
    OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV,
)


def _clear_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV, raising=False)
    monkeypatch.delenv(OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    for env_name in OUTAGE_REPAIR_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)


@pytest.fixture(autouse=True)
def _clear_repair_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_repair(monkeypatch)


def test_execute_gate_off() -> None:
    out = json.loads(
        exec_mod.execute_powerunits_outage_repair_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_http_200_via_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OUTAGE_REPAIR_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "rid-b",
                "correlation_id": "cid",
                "step_a": {"run_id": "a"},
                "step_b": {"run_id": "b", "rows_written": 10},
                "downstream_not_auto_triggered": ["market_feature_job"],
                "operator_statement": "Repo B ok.",
                "hermes_statement": "bounded_outage_repair_step_a_b_executed",
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "outage-repair/recompute" in url
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_outage_repair_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
