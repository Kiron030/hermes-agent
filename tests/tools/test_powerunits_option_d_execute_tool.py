"""Tests for Option D Hermes bounded execute tool (HTTP to Repo B internal API)."""

from __future__ import annotations

import json
from typing import Any

import pytest


def _exec(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    _http_post=None,
) -> dict:
    from tools import powerunits_option_d_execute_tool as mod

    return json.loads(
        mod.execute_powerunits_option_d_bounded_slice(
            country=country,
            start=start,
            end=end,
            version=version,
            _http_post=_http_post,
        )
    )


class _FakeHttpResp:
    def __init__(self, status_code: int, payload: dict[str, Any] | str) -> None:
        self.status_code = status_code
        if isinstance(payload, dict):
            self._data = payload
            self.text = json.dumps(payload)
        else:
            self._data = None
            self.text = str(payload)
        self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        if self._data is not None:
            return self._data
        return json.loads(self.text)


def _valid_pl_body() -> dict[str, str]:
    return {
        "country": "PL",
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-01-01T12:00:00Z",
        "version": "v1",
    }


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-bearer-secret")


def test_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", raising=False)
    out = _exec(**_valid_pl_body())
    assert out.get("error_code") == "feature_disabled"
    assert out["execution_attempted"] is False


def test_check_fn_requires_base_and_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_option_d_execute_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert mod.check_powerunits_option_d_execute_requirements() is True
    monkeypatch.delenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", raising=False)
    assert mod.check_powerunits_option_d_execute_requirements() is False


def test_http_200_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json_body
        return _FakeHttpResp(
            200,
            {
                "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "success": True,
                "pipeline_run_id": "rid-1",
                "rows_written": 24,
                "slice": {},
            },
        )

    out = _exec(**_valid_pl_body(), _http_post=fake_post)
    assert out["execution_attempted"] is True
    assert out["success"] is True
    assert out["http_status"] == 200
    assert out["error_class"] == "success"
    assert out["pipeline_run_id"] == "rid-1"
    assert out["correlation_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert "powerunits bounded internal api" in out["hermes_statement"].lower()
    assert captured["url"].endswith("/internal/hermes/bounded/v1/market-features-hourly/recompute")
    assert captured["json"]["country_code"] == "PL"
    assert captured["headers"]["Authorization"] == "Bearer test-bearer-secret"


def test_http_400_server_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)

    def fake_post(*a, **k):
        return _FakeHttpResp(
            400,
            {
                "correlation_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                "success": False,
                "error_code": "invalid_window",
                "message": "window too large",
            },
        )

    out = _exec(**_valid_pl_body(), _http_post=fake_post)
    assert out["execution_attempted"] is True
    assert out["success"] is False
    assert out["http_status"] == 400
    assert out["error_class"] == "server_validation"
    assert out["server_error_code"] == "invalid_window"


def test_http_401(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)

    def fake_post(*a, **k):
        return _FakeHttpResp(401, {"detail": "Unauthorized"})

    out = _exec(**_valid_pl_body(), _http_post=fake_post)
    assert out["success"] is False
    assert out["http_status"] == 401
    assert out["error_class"] == "auth_failed"


def test_http_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)

    def fake_post(*a, **k):
        return _FakeHttpResp(404, {"detail": "Not Found"})

    out = _exec(**_valid_pl_body(), _http_post=fake_post)
    assert out["success"] is False
    assert out["http_status"] == 404
    assert out["error_class"] == "not_found_or_disabled"


def test_http_502_job_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)

    def fake_post(*a, **k):
        return _FakeHttpResp(
            502,
            {
                "success": False,
                "pipeline_run_id": "p2",
                "correlation_id": "cccccccc-dddd-eeee-ffff-000000000001",
                "error_message": "postgresql://u:p@h/db oops",
            },
        )

    out = _exec(**_valid_pl_body(), _http_post=fake_post)
    assert out["success"] is False
    assert out["http_status"] == 502
    assert out["error_class"] == "job_failed"
    assert "postgresql://" not in out["response_body_summary"]


def test_client_validation_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)

    def boom(*a, **k):
        raise AssertionError("HTTP must not be called")

    out = _exec(
        country="DE",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _http_post=boom,
    )
    assert out["execution_attempted"] is False
    assert out["slice"] is None


def test_runtime_url_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    from tools import powerunits_option_d_execute_tool as mod

    monkeypatch.setattr(mod, "_internal_url", lambda: "")

    out = _exec(**_valid_pl_body())
    assert out.get("error_code") == "execute_config_incomplete"
    assert out["execution_attempted"] is False


def test_first_safe_includes_execute_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "tok")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_option_d_execute", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "execute_powerunits_option_d_bounded_slice" in names
    assert "web_search" not in names
