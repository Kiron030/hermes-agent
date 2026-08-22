"""S0-C: single PowerUnits execute Base-URL resolver."""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest

import tools.approval as approval
from tests.tools.powerunits_s0b_approval_support import grant_powerunits_write_approvals
from tools.powerunits_execute_base_url_v1 import (
    ERROR_ALLOWLIST_REQUIRED,
    ERROR_HOST_REFUSED,
    ERROR_HTTPS_REQUIRED,
    ERROR_PIN_MODE_INVALID,
    ERROR_URL_INVALID,
    POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV,
    POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV,
    POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV,
    apply_powerunits_execute_base_url_refusal,
    powerunits_execute_base_url_is_configured,
    resolve_powerunits_execute_base_url,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
RESOLVER_NAME = "powerunits_execute_base_url_v1.py"
_BASE_READ_RE = re.compile(
    r"""os\.(?:getenv|environ\.get|environ\[)\(\s*(?:_BASE_ENV|['\"]POWERUNITS_INTERNAL_EXECUTE_BASE_URL['\"])"""
)


class _FakeHttpResp:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._data = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        return self._data


def _clear_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, raising=False)
    monkeypatch.delenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, raising=False)
    monkeypatch.delenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, raising=False)


def test_missing_base_url_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    assert powerunits_execute_base_url_is_configured() is False
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.configured is False
    assert resolved.refused is False
    assert resolved.base_url == ""
    payload = apply_powerunits_execute_base_url_refusal(
        {"error_code": "read_config_incomplete", "success": False}
    )
    assert payload["error_code"] == "read_config_incomplete"


def test_valid_allowed_host_enforce(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is False
    assert resolved.base_url == "https://api.example.test"
    assert resolved.hostname == "api.example.test"


def test_hostname_compare_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://API.Example.TEST/v1/")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is False
    assert resolved.base_url == "https://API.Example.TEST/v1"
    assert (resolved.hostname or "").lower() == "api.example.test"


def test_exact_host_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(
        POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV,
        "https://api.example.test.evil.invalid",
    )
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_HOST_REFUSED
    assert resolved.base_url == ""


def test_http_scheme_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "http://api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_HTTPS_REQUIRED
    assert resolved.base_url == ""


def test_userinfo_and_substring_do_not_authorize(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")

    monkeypatch.setenv(
        POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV,
        "https://api.example.test@evil.invalid",
    )
    userinfo = resolve_powerunits_execute_base_url()
    assert userinfo.refused is True
    assert userinfo.error_code == ERROR_URL_INVALID

    monkeypatch.setenv(
        POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV,
        "https://evil.invalid/api.example.test",
    )
    path_only = resolve_powerunits_execute_base_url()
    assert path_only.refused is True
    assert path_only.error_code == ERROR_HOST_REFUSED


def test_missing_hostname_and_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://")
    missing = resolve_powerunits_execute_base_url()
    assert missing.refused is True
    assert missing.error_code == ERROR_URL_INVALID
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "not a url")
    malformed = resolve_powerunits_execute_base_url()
    assert malformed.refused is True
    assert malformed.error_code in {ERROR_HTTPS_REQUIRED, ERROR_URL_INVALID}


def test_warn_foreign_host_preserves_url(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://foreign.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "warn")
    with caplog.at_level(logging.WARNING, logger="tools.powerunits_execute_base_url_v1"):
        resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is False
    assert resolved.warned is True
    assert resolved.base_url == "https://foreign.example.test"
    assert "not in" in caplog.text


def test_enforce_foreign_host_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://foreign.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_HOST_REFUSED


def test_missing_allowlist_warn_preserves(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "warn")
    with caplog.at_level(logging.WARNING, logger="tools.powerunits_execute_base_url_v1"):
        resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is False
    assert resolved.base_url == "https://api.example.test"
    assert POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV in caplog.text


def test_missing_allowlist_enforce_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_ALLOWLIST_REQUIRED
    assert resolved.base_url == ""


def test_invalid_pin_mode_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "maybe")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_PIN_MODE_INVALID


def test_default_pin_mode_is_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_pin(monkeypatch)
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://foreign.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.pin_mode == "warn"
    assert resolved.refused is False


def _snapshot_env(monkeypatch: pytest.MonkeyPatch, base: str) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, base)
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "secret")


POWERUNITS_HERMES_SECRET = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"


def test_read_wrapper_enforce_foreign_makes_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    _snapshot_env(monkeypatch, "https://api.example.test.evil.invalid")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("foreign host must not POST")

    out = json.loads(
        mod.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes=["DE"],
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["success"] is False
    assert out["error_code"] == ERROR_HOST_REFUSED
    assert out["read_attempted"] is False


def test_read_wrapper_warn_foreign_preserves_http(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    _snapshot_env(monkeypatch, "https://foreign.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "warn")
    posts = {"n": 0}
    ok_body = {
        "success": True,
        "correlation_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "baseline_ready": True,
        "baseline_readiness_reason": "ok",
        "time_window": {
            "start_utc": "2024-01-01T00:00:00+00:00",
            "end_utc_exclusive": "2024-01-08T00:00:00+00:00",
            "expected_hours": 168,
        },
        "baseline_readiness_detail": {},
        "latest_pipeline_runs": [],
    }

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        return _FakeHttpResp(200, ok_body)

    with caplog.at_level(logging.WARNING, logger="tools.powerunits_execute_base_url_v1"):
        out = json.loads(
            mod.read_powerunits_coverage_snapshot_v1(
                window_start_utc="2024-01-01T00:00:00Z",
                window_end_utc="2024-01-08T00:00:00Z",
                country_codes=["DE"],
                _http_post=fake_post,
            )
        )
    assert posts["n"] == 1
    assert out["success"] is True
    assert "not in" in caplog.text


def test_read_wrapper_http_scheme_makes_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    _snapshot_env(monkeypatch, "http://api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("http scheme must not POST")

    out = json.loads(
        mod.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes=["DE"],
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["error_code"] == ERROR_HTTPS_REQUIRED


def test_read_wrapper_missing_base_keeps_feature_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")
    monkeypatch.delenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, raising=False)
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "secret")
    out = json.loads(
        mod.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-08T00:00:00Z",
            country_codes=["DE"],
        )
    )
    assert out["error_code"] == "feature_disabled"


def test_read_with_side_effect_wrapper_enforce_foreign_makes_no_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import powerunits_option_d_validate_tool as mod

    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED", "1")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://foreign.example.test")
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "test-bearer-secret")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("foreign host must not POST")

    out = json.loads(
        mod.validate_powerunits_option_d_bounded_window(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["error_code"] == ERROR_HOST_REFUSED
    assert out["validation_attempted"] is False


def test_write_wrapper_enforce_allowed_still_posts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import powerunits_option_d_execute_tool as mod

    grant_powerunits_write_approvals(monkeypatch)
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "test-bearer-secret")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        return _FakeHttpResp(
            200,
            {"success": True, "pipeline_run_id": "rid-1", "correlation_id": "cid-1"},
        )

    out = json.loads(
        mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 1
    assert out["success"] is True


def test_s0b_deny_after_resolver_makes_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_option_d_execute_tool as exec_mod

    monkeypatch.setattr(
        approval, "get_current_session_key", lambda default="default": "test-session"
    )
    monkeypatch.setattr(approval, "is_approved", lambda sk, pk: False)
    monkeypatch.setattr(approval, "is_current_session_yolo_enabled", lambda: False)
    monkeypatch.setattr(approval, "_YOLO_MODE_FROZEN", False, raising=False)
    monkeypatch.setattr(approval, "_get_approval_mode", lambda: "manual")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "test-bearer-secret")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("denied write must not POST")

    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": False, "message": "denied by operator"},
    )
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["error_code"] == "approval_denied"
    assert out["execution_attempted"] is False


def test_s0b_yolo_without_allowlist_makes_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_option_d_execute_tool as exec_mod

    monkeypatch.setattr(
        approval, "get_current_session_key", lambda default="default": "test-session"
    )
    monkeypatch.setattr(approval, "is_approved", lambda sk, pk: False)
    monkeypatch.setattr(approval, "is_current_session_yolo_enabled", lambda: True)
    monkeypatch.setattr(approval, "is_approval_bypass_active", lambda: True)
    monkeypatch.setattr(approval, "_YOLO_MODE_FROZEN", False, raising=False)
    monkeypatch.setattr(approval, "_get_approval_mode", lambda: "manual")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "test-bearer-secret")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("YOLO must not POST")

    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["error_code"] == "approval_denied"


def test_s0b_cron_approve_without_allowlist_makes_no_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import powerunits_option_d_execute_tool as exec_mod

    monkeypatch.setattr(
        approval, "get_current_session_key", lambda default="default": "test-session"
    )
    monkeypatch.setattr(approval, "is_approved", lambda sk, pk: False)
    monkeypatch.setattr(approval, "is_current_session_yolo_enabled", lambda: False)
    monkeypatch.setattr(approval, "_YOLO_MODE_FROZEN", False, raising=False)
    monkeypatch.setattr(approval, "_get_approval_mode", lambda: "manual")
    monkeypatch.setattr(approval, "_is_interactive_cli", lambda: False)
    monkeypatch.setattr(approval, "_is_gateway_approval_context", lambda: False)
    monkeypatch.setattr(approval, "_get_cron_approval_mode", lambda: "approve")
    monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(POWERUNITS_HERMES_SECRET, "test-bearer-secret")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV, "api.example.test")
    monkeypatch.setenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV, "enforce")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("cron_mode=approve must not POST")

    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["error_code"] == "approval_denied"


def _runtime_modules() -> list[Path]:
    files = sorted(TOOLS_DIR.glob("powerunits_*.py"))
    files.append(TOOLS_DIR / "bounded_rollout_governance_projection_v1.py")
    return [p for p in files if p.is_file()]


def test_bounded_runtime_does_not_read_base_url_directly() -> None:
    offenders: list[str] = []
    for path in _runtime_modules():
        if path.name == RESOLVER_NAME:
            src = path.read_text(encoding="utf-8")
            assert POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV in src
            continue
        src = path.read_text(encoding="utf-8")
        if _BASE_READ_RE.search(src):
            offenders.append(path.name)
    assert offenders == []


def test_exactly_one_runtime_resolver_owns_getenv() -> None:
    owners: list[str] = []
    for path in _runtime_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute) and func.attr in {"getenv", "get"}:
                name = func.attr
            if name not in {"getenv", "get"} or not node.args:
                continue
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and arg0.value == POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV:
                owners.append(path.name)
            if isinstance(arg0, ast.Name) and arg0.id == "POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV":
                owners.append(path.name)
    assert owners == [RESOLVER_NAME]


def test_representative_schemas_have_no_host_path_or_url_params() -> None:
    from tools import powerunits_bounded_coverage_snapshot_tool as snap
    from tools import powerunits_option_d_execute_tool as exe
    from tools import powerunits_option_d_validate_tool as val

    forbidden = {"url", "host", "hostname", "base_url", "path", "route"}
    for schema in (
        snap.COVERAGE_SNAPSHOT_SCHEMA_V1,
        exe.EXECUTE_OPTION_D_SCHEMA,
        val.VALIDATE_OPTION_D_SCHEMA,
    ):
        props = set((schema.get("parameters") or {}).get("properties") or {})
        assert forbidden.isdisjoint(props)
