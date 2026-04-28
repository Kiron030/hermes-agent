"""Tests for Option D Hermes bounded execute tool (mocked subprocess)."""

from __future__ import annotations

import json
from subprocess import CompletedProcess

import pytest


def _exec(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    _run_wrapper=None,
) -> dict:
    from tools import powerunits_option_d_execute_tool as mod

    return json.loads(
        mod.execute_powerunits_option_d_bounded_slice(
            country=country,
            start=start,
            end=end,
            version=version,
            _run_wrapper=_run_wrapper,
        )
    )


def test_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", raising=False)
    out = _exec(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
    )
    assert out.get("error_code") == "feature_disabled"
    assert out["execution_attempted"] is False


def test_valid_execution_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")

    def _fake_run(cmd: list[str], *, cwd: str, env: dict, timeout_s: int = 3600):
        assert cmd[0]
        assert cmd[1] == "-m"
        assert cmd[2] == "tools.powerunits_option_d_bounded_market_features"
        assert cmd[cmd.index("--country") + 1] == "PL"
        assert cmd[cmd.index("--version") + 1] == "v1"
        return CompletedProcess(cmd, 0, stdout='{"ok":true}\n', stderr="")

    out = _exec(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _run_wrapper=_fake_run,
    )
    assert out["execution_attempted"] is True
    assert out["success"] is True
    assert out["delegated_wrapper_exit_code"] == 0
    assert out["slice"]["country"] == "PL"
    stmt = out["hermes_statement"].lower()
    assert "no direct sql" in stmt
    assert "single subprocess" in stmt


def test_invalid_country(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")

    def _boom(*a, **k):
        raise AssertionError("wrapper must not run")

    out = _exec(
        country="DE",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _run_wrapper=_boom,
    )
    assert out["execution_attempted"] is False
    assert out["success"] is False
    assert out["slice"] is None


def test_invalid_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")

    def _boom(*a, **k):
        raise AssertionError("wrapper must not run")

    out = _exec(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v2",
        _run_wrapper=_boom,
    )
    assert out["execution_attempted"] is False


def test_invalid_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")

    def _boom(*a, **k):
        raise AssertionError("wrapper must not run")

    out = _exec(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-02T00:00:01Z",
        version="v1",
        _run_wrapper=_boom,
    )
    assert out["execution_attempted"] is False


def test_wrapper_failure_propagation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")

    def _fake_run(cmd: list[str], *, cwd: str, env: dict, timeout_s: int = 3600):
        leak = "postgresql://secret:secret@db.example.com:5432/mydb"
        return CompletedProcess(cmd, 4, stdout="job failed", stderr=leak)

    out = _exec(
        country="PL",
        start="2024-01-01T00:00:00Z",
        end="2024-01-01T12:00:00Z",
        version="v1",
        _run_wrapper=_fake_run,
    )
    assert out["execution_attempted"] is True
    assert out["success"] is False
    assert out["delegated_wrapper_exit_code"] == 4
    assert "postgresql://" not in out["wrapper_stderr_summary"]
    assert "[REDACTED_URL]" in out["wrapper_stderr_summary"]


def test_first_safe_includes_execute_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_option_d_execute", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "execute_powerunits_option_d_bounded_slice" in names
    assert "web_search" not in names
