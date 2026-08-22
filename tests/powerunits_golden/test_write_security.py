"""Task D — S0-B write-security Golden negatives (behaviour, not internals)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.approval as approval
from tests.powerunits_golden.env import (
    SYNTHETIC_EXECUTE_BASE_URL,
    SYNTHETIC_EXECUTE_HOST,
    SYNTHETIC_EXECUTE_SECRET,
)
from tests.powerunits_golden.http import RecordingPoster
from tools import powerunits_entsoe_market_bounded_campaign_tool as camp_mod
from tools import powerunits_option_d_execute_tool as exec_mod
from tools import powerunits_workspace_tool as ws
from tools.powerunits_bounded_write_approval_v1 import (
    canonical_write_rule_key,
    require_powerunits_write_approval,
)


def _write_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)


def _deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": False, "message": "denied by operator"},
    )


def test_deny_bounded_http_write_posts_zero_times(monkeypatch: pytest.MonkeyPatch) -> None:
    _write_env(monkeypatch)
    _deny(monkeypatch)
    poster = RecordingPoster({"success": True})
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=poster,
        )
    )
    assert poster.count == 0
    assert out["error_code"] == "approval_denied"
    assert out["execution_attempted"] is False


def test_yolo_without_exact_authorization_does_not_write(monkeypatch: pytest.MonkeyPatch) -> None:
    _write_env(monkeypatch)
    poster = RecordingPoster({"success": True})
    monkeypatch.setattr(approval, "is_approval_bypass_active", lambda: True)
    monkeypatch.setattr(
        approval,
        "request_tool_approval",
        lambda *a, **k: {"approved": True, "message": None},
    )
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=poster,
        )
    )
    assert poster.count == 0
    assert out["error_code"] == "approval_denied"
    assert "yolo" in (out.get("message") or "").lower()


def test_cron_approve_without_exact_authorization_does_not_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_env(monkeypatch)
    poster = RecordingPoster({"success": True})
    monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    monkeypatch.setattr(approval, "_get_cron_approval_mode", lambda: "approve")
    monkeypatch.setattr(approval, "_is_interactive_cli", lambda: False)
    monkeypatch.setattr(approval, "_is_gateway_approval_context", lambda: False)
    out = json.loads(
        exec_mod.execute_powerunits_option_d_bounded_slice(
            country="PL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-02T00:00:00Z",
            version="v1",
            _http_post=poster,
        )
    )
    assert poster.count == 0
    assert out["error_code"] == "approval_denied"
    assert "cron_mode=approve" in (out.get("message") or "")


def test_deny_local_durable_writer_leaves_state_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _deny(monkeypatch)
    root = tmp_path / "hermes_workspace"
    out = json.loads(
        ws.save_hermes_workspace_note(
            kind="notes",
            name="denied.md",
            content="nope",
            overwrite_mode="forbid",
        )
    )
    assert out.get("error_code") == "approval_denied"
    assert not root.exists()
    assert not (root / "notes" / "denied.md").exists()


def test_campaign_approval_alone_does_not_authorize_slices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_env(monkeypatch)
    poster = RecordingPoster({"success": True, "http_status": 200, "pipeline_run_id": "x"})
    campaign_key = "plugin_rule:" + canonical_write_rule_key(
        "campaign_powerunits_entsoe_market_bounded_de",
        "DE",
        "2024-01-01T00:00:00Z/2024-01-08T00:00:00Z",
    )
    monkeypatch.setattr(approval, "is_approved", lambda sk, pk: pk == campaign_key)
    monkeypatch.setattr(approval, "_is_interactive_cli", lambda: False)
    monkeypatch.setattr(approval, "_is_gateway_approval_context", lambda: False)
    monkeypatch.setattr(approval, "env_var_enabled", lambda v: False)
    monkeypatch.setattr(approval, "is_current_session_yolo_enabled", lambda: False)
    monkeypatch.setattr(approval, "is_approval_bypass_active", lambda: False)
    out = json.loads(
        camp_mod.campaign_powerunits_entsoe_market_bounded_de(
            campaign_start_utc="2024-01-01T00:00:00Z",
            campaign_end_utc="2024-01-08T00:00:00Z",
            country="DE",
            _http_post=poster,
        )
    )
    assert poster.count == 0
    assert out.get("error_code") in {"approval_denied", "approval_required"} or out.get(
        "windows_succeeded", 1
    ) == 0


def test_distinct_identities_are_distinct_approvals() -> None:
    de = canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "DE",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    fr = canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "FR",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    other_window = canonical_write_rule_key(
        "execute_powerunits_entsoe_market_bounded_slice",
        "DE",
        "2026-02-01T00:00:00Z/2026-02-02T00:00:00Z",
    )
    other_op = canonical_write_rule_key(
        "execute_powerunits_era5_weather_bounded_slice",
        "DE",
        "2026-01-01T00:00:00Z/2026-01-02T00:00:00Z",
    )
    az = canonical_write_rule_key("save_hermes_workspace_note", "-", resource="notes/az.md")
    aZ = canonical_write_rule_key("save_hermes_workspace_note", "-", resource="notes/aZ.md")
    assert len({de, fr, other_window, other_op, az, aZ}) == 6

    ok = require_powerunits_write_approval(
        operation="validate_powerunits_option_d_bounded_window",
        country="PL",
        window="2024-01-01T00:00:00Z/2024-01-02T00:00:00Z",
    )
    assert ok["approved"] is True
    assert ok["effect_class"] == "READ_WITH_SIDE_EFFECT"
