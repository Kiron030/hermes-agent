"""Tests for Option D Hermes bounded validate-window tool (HTTP to Repo B)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_option_d_validate_tool as mod


def _call(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    pipeline_run_id: str | None = None,
    _http_post=None,
) -> dict:
    return json.loads(
        mod.validate_powerunits_option_d_bounded_window(
            country=country,
            start=start,
            end=end,
            version=version,
            pipeline_run_id=pipeline_run_id,
            _http_post=_http_post,
        )
    )


def _with_validate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-bearer-secret")


def test_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED", raising=False)
    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out.get("error_code") == "feature_disabled"
    assert out["validation_attempted"] is False


def test_check_fn_requires_base_and_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert mod.check_powerunits_option_d_validate_requirements() is True
    monkeypatch.delenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", raising=False)
    assert mod.check_powerunits_option_d_validate_requirements() is False


def test_client_validation_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_validate_env(monkeypatch)

    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("HTTP must not be called")

    out = _call(
        country="DE",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=boom,
    )
    assert out["validation_attempted"] is False
    assert out["slice"] is None


def test_http_200_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_validate_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "outcome": "passed",
                "summary_code": "validation_passed",
                "warnings": [],
                "checks": {"rows_present": 12},
                "read_target": "timescale",
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "validate-window" in url
        assert json_body["country_code"] == "PL"
        if "pipeline_run_id" in json_body:
            assert json_body["pipeline_run_id"] == "rid-1"
        return R()

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        pipeline_run_id="rid-1",
        _http_post=fake_post,
    )
    assert out["validation_attempted"] is True
    assert out["http_ok"] is True
    assert out["success"] is True
    assert out["outcome"] == "passed"
    assert "bounded internal validate-window" in out["hermes_statement"].lower()


def test_http_200_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_validate_env(monkeypatch)

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "outcome": "warning",
                "summary_code": "validation_warning_run_not_found",
                "warnings": ["run_not_found"],
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=lambda *a, **k: R(),
    )
    assert out["http_ok"] is True
    assert out["success"] is False
    assert out["validation_warning"] is True


def test_http_400(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_validate_env(monkeypatch)

    class R:
        status_code = 400
        content = b"{}"
        text = json.dumps({"message": "bad", "summary_code": "invalid_window"})

        def json(self) -> dict:
            return json.loads(self.text)

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=lambda *a, **k: R(),
    )
    assert out["http_status"] == 400
    assert out["error_class"] == "server_validation"


def test_http_401(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_validate_env(monkeypatch)

    class R:
        status_code = 401
        content = b"{}"
        text = "{}"

        def json(self) -> dict:
            return {}

    out = _call(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=lambda *a, **k: R(),
    )
    assert out["http_status"] == 401
    assert out["error_class"] == "http_error"


def test_pipeline_run_id_from_args() -> None:
    assert mod._pipeline_run_id_from_args({}) is None
    assert mod._pipeline_run_id_from_args({"pipeline_run_id": None}) is None
    assert mod._pipeline_run_id_from_args({"pipeline_run_id": "  abc  "}) == "abc"


def test_first_safe_includes_validate_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "tok")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_option_d_validate", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "validate_powerunits_option_d_bounded_window" in names
    assert "web_search" not in names
