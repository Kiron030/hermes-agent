"""Tests for bounded outage awareness Hermes tools (read-only Repo B POSTs)."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_outage_awareness_bounded_summary_tool as sum_mod
from tools import powerunits_outage_awareness_bounded_validate_tool as val_mod
from tools.powerunits_bounded_family_gates import (
    OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV,
    OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV,
    OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV,
)


def _clear_outage_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV, raising=False)
    monkeypatch.delenv(OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    for env_name in OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)


@pytest.fixture(autouse=True)
def _fixture_clear_outage_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_outage_bounded(monkeypatch)


def test_validate_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    out = json.loads(
        val_mod.validate_powerunits_outage_awareness_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_validate_feature_disabled_primary_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    out = json.loads(
        val_mod.validate_powerunits_outage_awareness_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_validate_http_200_via_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "correlation_id": "cid-rb",
                "hermes_statement": "read_only_outage_awareness_no_writes",
                "slice": {},
                "outcome": "passed",
                "summary_code": "ok",
                "warnings": [],
                "checks": {},
                "semantics_notes": [],
                "operator_statement": {"no_jobs": True},
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "outage-awareness/validate-window" in url
        assert json_body.get("country_code") == "DE"
        assert json_body.get("version") == "v1"
        return R()

    out = json.loads(
        val_mod.validate_powerunits_outage_awareness_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out.get("validation_passed") is True
    assert out.get("success") is True
    assert out.get("correlation_id") == "cid-rb"


def test_legacy_validate_only_does_not_open_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OUTAGE_AWARENESS_BOUNDED_LEGACY_ENV["validate"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert sum_mod.check_powerunits_outage_awareness_bounded_summary_requirements() is False


def test_summary_http_ok_with_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OUTAGE_AWARENESS_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "outcome_class": "ok_with_warnings",
                "correlation_id": "s1",
                "hermes_statement": "read_only_outage_awareness_no_writes",
                "validation": {"outcome": "warning"},
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "outage-awareness/summary-window" in url
        return R()

    out = json.loads(
        sum_mod.summarize_powerunits_outage_awareness_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out.get("success") is True
    assert out.get("outcome_class") == "ok_with_warnings"
