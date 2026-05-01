"""Tests for bounded baseline layer-coverage preview (read-only Repo B POST)."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_baseline_layer_preview_tool as prev_mod


def _prep_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_baseline_preview_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED", raising=False)
    out = prev_mod.preview_powerunits_baseline_layer_coverage_de(
        preview_start_utc="2026-04-01T00:00:00Z",
        preview_end_utc="2026-04-08T00:00:00Z",
    )
    data = json.loads(out)
    assert data.get("error_code") == "feature_disabled"
    assert data.get("preview_attempted") is False


def test_baseline_preview_local_validation_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_env(monkeypatch)

    calls: list[bool] = []

    def boom(*a, **k):
        calls.append(True)
        raise AssertionError("HTTP must not run when slice invalid")

    out = prev_mod.preview_powerunits_baseline_layer_coverage_de(
        preview_start_utc="2026-04-01T00:00:00Z",
        preview_end_utc="2026-04-08T00:00:00Z",
        country_code="PL",
        _http_post=boom,
    )
    assert not calls
    data = json.loads(out)
    assert data.get("preview_attempted") is False
    assert data.get("preview_messages")


def test_baseline_preview_span_too_long(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_env(monkeypatch)
    out = prev_mod.preview_powerunits_baseline_layer_coverage_de(
        preview_start_utc="2026-04-01T00:00:00Z",
        preview_end_utc="2026-05-03T00:00:01Z",
    )
    data = json.loads(out)
    assert data.get("preview_attempted") is False
    assert any("31" in m for m in (data.get("preview_messages") or []))


class _Resp:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode()

    def json(self):
        return json.loads(self.text)


def test_baseline_preview_http_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_env(monkeypatch)

    def fake_post(url, headers, json_body, timeout_s):
        assert "/internal/hermes/bounded/v1/baseline/layer-coverage-preview" in url
        assert json_body["country_code"] == "DE"
        assert json_body["version"] == "v1"
        assert "preview_start_utc" in json_body and "preview_end_utc" in json_body
        assert headers["Authorization"].startswith("Bearer ")
        payload = {
            "correlation_id": "from-server",
            "scanner": "baseline_layer_preview_de_v1",
            "hermes_statement": "read_only_baseline_preview_no_jobs",
            "slice": {
                "country_code": "DE",
                "version": "v1",
                "preview_start_utc": json_body["preview_start_utc"],
                "preview_end_utc_exclusive": json_body["preview_end_utc"],
            },
            "expected_hours": 168,
            "baseline_ready_preview": True,
            "rollup": {"scan_outcome": "ok", "missing_layers": [], "weak_layers": []},
        }
        return _Resp(200, json.dumps(payload))

    raw = prev_mod.preview_powerunits_baseline_layer_coverage_de(
        preview_start_utc="2026-04-01T00:00:00Z",
        preview_end_utc="2026-04-08T00:00:00Z",
        _http_post=fake_post,
    )
    data = json.loads(raw)
    assert data["http_ok"] is True
    assert data["scanner"] == "baseline_layer_preview_de_v1"
    assert data["hermes_statement"] == "read_only_baseline_preview_no_jobs"
    assert data["rollup"]["scan_outcome"] == "ok"


def test_baseline_preview_schema_operator_wording() -> None:
    desc = prev_mod.BASELINE_PREVIEW_SCHEMA["description"]
    assert "HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED" in desc
    assert "read-only" in desc.lower()
    assert "Repo B" in desc


def test_baseline_preview_slice_validator_accepts_exactly_31_days() -> None:
    from tools.powerunits_baseline_layer_preview_slice import validate_baseline_preview_slice

    cc, ver, *_ = validate_baseline_preview_slice(
        "DE",
        "2026-04-01T00:00:00Z",
        "2026-05-02T00:00:00Z",
        "v1",
    )
    assert cc == "DE" and ver == "v1"
