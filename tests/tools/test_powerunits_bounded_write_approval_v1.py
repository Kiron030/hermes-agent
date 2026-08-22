"""S0-B: PowerUnits write gate — deny / YOLO / rule-key / gateway / no-human."""

from __future__ import annotations

import json
from typing import Any

import pytest

import tools.approval as approval
import tools.powerunits_bounded_write_approval_v1 as pu_write_approval
from tools import powerunits_option_d_execute_tool as exec_mod
from tools.powerunits_bounded_write_approval_v1 import (
    canonical_write_rule_key,
    require_powerunits_write_approval,
)


@pytest.fixture(autouse=True)
def _isolate_approval_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        approval, "get_current_session_key", lambda default="default": "test-session"
    )
    monkeypatch.setattr(approval, "is_approved", lambda sk, pk: False)
    monkeypatch.setattr(approval, "is_current_session_yolo_enabled", lambda: False)
    monkeypatch.setattr(approval, "_YOLO_MODE_FROZEN", False, raising=False)
    monkeypatch.setattr(approval, "_get_approval_mode", lambda: "manual")
    monkeypatch.setattr(
        "tools.terminal_tool._get_approval_callback", lambda: None, raising=False
    )


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-bearer-secret")


def _valid_pl() -> dict[str, str]:
    return {
        "country": "PL",
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-01-01T12:00:00Z",
        "version": "v1",
    }


class _FakeHttpResp:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._data = payload
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        return self._data


def test_rule_key_distinguishes_country_window_and_operation() -> None:
    de_jan = canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "DE",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    fr_jan = canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "FR",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    de_feb = canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "DE",
        "2026-02-01T00:00:00Z/2026-02-02T00:00:00Z",
    )
    other_op = canonical_write_rule_key(
        "execute_powerunits_era5_weather_bounded_slice",
        "DE",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    assert de_jan != fr_jan
    assert de_jan != de_feb
    assert de_jan != other_op
    assert de_jan == canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "de",
        "2026-01-01T00:00:00z/2026-01-02T00:00:00z",
    )


def test_always_approval_does_not_leak_across_identities(monkeypatch: pytest.MonkeyPatch) -> None:
    de_key = "plugin_rule:" + canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "DE",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    monkeypatch.setattr(approval, "is_approved", lambda sk, pk: pk == de_key)
    monkeypatch.setattr(approval, "_is_interactive_cli", lambda: False)
    monkeypatch.setattr(approval, "_is_gateway_approval_context", lambda: False)
    monkeypatch.setattr(approval, "env_var_enabled", lambda v: False)

    ok = require_powerunits_write_approval(
        operation="execute_powerunits_entsoe_market_bounded_slice",
        country="DE",
        window="2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    assert ok["approved"] is True

    other_country = require_powerunits_write_approval(
        operation="execute_powerunits_entsoe_market_bounded_slice",
        country="FR",
        window="2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    other_window = require_powerunits_write_approval(
        operation="execute_powerunits_entsoe_market_bounded_slice",
        country="DE",
        window="2026-02-01T00:00:00Z/2026-02-02T00:00:00Z",
    )
    other_op = require_powerunits_write_approval(
        operation="execute_powerunits_era5_weather_bounded_slice",
        country="DE",
        window="2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    assert other_country["approved"] is False
    assert other_window["approved"] is False
    assert other_op["approved"] is False


def test_deny_blocks_http_post(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        return _FakeHttpResp(200, {"success": True, "pipeline_run_id": "x"})

    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": False, "message": "denied by operator"},
    )
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            **_valid_pl(),
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["execution_attempted"] is False
    assert out["success"] is False
    assert out["error_code"] == "approval_denied"
    assert "denied" in (out.get("message") or "").lower()


def test_approval_success_posts_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    order: list[str] = []

    def _approve(*_a: Any, **_k: Any) -> dict[str, Any]:
        order.append("approval")
        return {"approved": True, "message": None}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        order.append("post")
        return _FakeHttpResp(
            200,
            {
                "success": True,
                "pipeline_run_id": "rid-1",
                "correlation_id": "cid-1",
                "rows_written": 12,
            },
        )

    monkeypatch.setattr(approval, "request_tool_approval", _approve)
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            **_valid_pl(),
            _http_post=fake_post,
        )
    )
    assert order == ["approval", "post"]
    assert out["success"] is True
    assert out["execution_attempted"] is True
    assert out["pipeline_run_id"] == "rid-1"


def test_gateway_approval_required_does_not_post(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("gateway pending must not POST")

    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {
            "approved": False,
            "status": "approval_required",
            "message": "awaiting operator",
        },
    )
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            **_valid_pl(),
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["status"] == "approval_required"
    assert out["error_code"] == "approval_required"
    assert out["execution_attempted"] is False


def test_no_human_context_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("no-human context must not POST")

    monkeypatch.setattr(approval, "_is_interactive_cli", lambda: False)
    monkeypatch.setattr(approval, "_is_gateway_approval_context", lambda: False)
    monkeypatch.setattr(approval, "env_var_enabled", lambda v: False)
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            **_valid_pl(),
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["success"] is False
    assert out["execution_attempted"] is False
    assert out["error_code"] == "approval_denied"


def test_yolo_cannot_bypass_write_hardline(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_execute_env(monkeypatch)
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> _FakeHttpResp:
        posts["n"] += 1
        raise AssertionError("YOLO must not POST")

    monkeypatch.setattr(approval, "is_approval_bypass_active", lambda: True)
    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": True, "message": None},
    )
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            **_valid_pl(),
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["error_code"] == "approval_denied"
    assert out["execution_attempted"] is False
    assert "yolo" in (out.get("message") or "").lower()


def test_read_with_side_effect_is_not_gated_by_helper() -> None:
    decision = require_powerunits_write_approval(
        operation="validate_powerunits_option_d_bounded_window",
        country="PL",
        window="2024-01-01T00:00:00Z/2024-01-01T12:00:00Z",
    )
    assert decision["approved"] is True
    assert decision["effect_class"] == "READ_WITH_SIDE_EFFECT"


def test_validate_read_with_side_effect_is_not_write_gated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import powerunits_option_d_validate_tool as val_mod

    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-bearer-secret")
    posts = {"n": 0}

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

        def json(self) -> dict[str, Any]:
            return json.loads(self.text)

    def fake_post(*_a: Any, **_k: Any) -> R:
        posts["n"] += 1
        return R()

    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: pytest.fail("READ_WITH_SIDE_EFFECT must not request write approval"),
    )
    out = json.loads(
        val_mod.validate_powerunits_option_d_bounded_window(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 1
    assert out.get("error_code") != "approval_denied"
    assert "approval" not in json.dumps(out).lower()


def test_campaign_deny_blocks_iteration(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_entsoe_market_bounded_campaign_tool as camp_mod
    from tools.powerunits_bounded_family_gates import ENTSOE_MARKET_BOUNDED_PRIMARY_ENV

    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv(ENTSOE_MARKET_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    posts = {"n": 0}

    def fake_post(*_a: Any, **_k: Any) -> Any:
        posts["n"] += 1
        raise AssertionError("campaign deny must not POST")

    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": False, "message": "denied by operator"},
    )
    out = json.loads(
        camp_mod.campaign_powerunits_entsoe_market_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-08T00:00:00Z",
            country="DE",
            _http_post=fake_post,
        )
    )
    assert posts["n"] == 0
    assert out["windows_attempted"] == 0
    assert out["error_code"] == "approval_denied"
    assert out["stopped_reason"] == "approval_denied"


def test_unclassified_write_fails_closed() -> None:
    decision = require_powerunits_write_approval(
        operation="powerunits_totally_new_unclassified_op",
        country="DE",
        window="2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    assert decision["approved"] is False
    assert decision["error_code"] == "effect_unclassified"
