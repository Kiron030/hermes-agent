"""Tests for staged Timescale read tool (mocked DB)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clear_timescale_env():
    with patch.dict(
        os.environ,
        {
            "HERMES_POWERUNITS_TIMESCALE_READ_ENABLED": "",
            "DATABASE_URL_TIMESCALE": "",
        },
        clear=False,
    ):
        yield


def _enabled_env():
    return {
        "HERMES_POWERUNITS_TIMESCALE_READ_ENABLED": "1",
        "DATABASE_URL_TIMESCALE": "postgresql://localhost/hermes_test",
    }


def test_success_recent_rows():
    from tools import powerunits_timescale_read_tool as mod

    sample_row = {
        "timestamp_utc": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        "price_eur_mwh": 80.0,
        "demand_mw": 60000.0,
        "renewable_share": 0.5,
        "residual_load_mw": 1000.0,
        "thermal_share": 0.2,
    }

    def fake_runner(db_url, sql, params, *, mode):
        assert "market_price_model_dataset_v" in sql
        assert mode == "all"
        assert params[0] == "DE"
        assert params[1] == "v1"
        assert params[4] == 10
        return [sample_row]

    with patch.dict(os.environ, _enabled_env(), clear=False):
        raw = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "recent_rows_by_country",
                "country_code": "de",
                "version": "v1",
                "window_id": "last_24h",
                "row_limit": 10,
            },
            _db_runner=fake_runner,
        )
    data = json.loads(raw)
    assert data["pattern_id"] == "recent_rows_by_country"
    assert data["row_count_returned"] == 1
    assert data["rows"][0]["price_eur_mwh"] == 80.0


def test_rejected_pattern():
    from tools import powerunits_timescale_read_tool as mod

    with patch.dict(os.environ, _enabled_env(), clear=False):
        raw = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "compact_metric_summary_by_country",
                "country_code": "DE",
                "version": "v1",
                "window_id": "last_24h",
            },
            _db_runner=lambda *a, **k: [],
        )
    err = json.loads(raw)
    assert "pattern" in err["error"].lower()


def test_rejected_country_version_window():
    from tools import powerunits_timescale_read_tool as mod

    with patch.dict(os.environ, _enabled_env(), clear=False):
        r1 = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "recent_rows_by_country",
                "country_code": "PL",
                "version": "v1",
                "window_id": "last_24h",
            },
            _db_runner=lambda *a, **k: [],
        )
        r2 = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "recent_rows_by_country",
                "country_code": "DE",
                "version": "v2",
                "window_id": "last_24h",
            },
            _db_runner=lambda *a, **k: [],
        )
        r3 = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "recent_rows_by_country",
                "country_code": "DE",
                "version": "v1",
                "window_id": "last_30d",
            },
            _db_runner=lambda *a, **k: [],
        )
    assert "country" in json.loads(r1)["error"].lower()
    assert "version" in json.loads(r2)["error"].lower()
    assert "window" in json.loads(r3)["error"].lower()


def test_row_cap_enforced():
    from tools import powerunits_timescale_read_tool as mod

    with patch.dict(os.environ, _enabled_env(), clear=False):
        raw = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "recent_rows_by_country",
                "country_code": "DE",
                "version": "v1",
                "window_id": "last_24h",
                "row_limit": 9999,
            },
            _db_runner=lambda *a, **k: [],
        )
    assert "row_limit" in json.loads(raw)["error"].lower()


def test_summary_rejects_row_limit():
    from tools import powerunits_timescale_read_tool as mod

    with patch.dict(os.environ, _enabled_env(), clear=False):
        raw = mod.read_powerunits_timescale_dataset(
            {
                "pattern_id": "recent_window_summary_by_country",
                "country_code": "DE",
                "version": "v1",
                "window_id": "last_7d",
                "row_limit": 5,
            },
            _db_runner=lambda *a, **k: {},
        )
    assert "row_limit" in json.loads(raw)["error"].lower()


def test_first_safe_includes_timescale_tool_when_env_gate_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """first_safe caps tools; powerunits_timescale_read must stay on that allowlist."""
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_TIMESCALE_READ_ENABLED", "1")
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", "postgresql://localhost/hermes_ts_test")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_timescale_read", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "read_powerunits_timescale_dataset" in names
    assert "web_search" not in names


def test_check_fn_requires_flag_and_url():
    from tools import powerunits_timescale_read_tool as mod

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HERMES_POWERUNITS_TIMESCALE_READ_ENABLED", None)
        os.environ.pop("DATABASE_URL_TIMESCALE", None)
        assert mod.check_powerunits_timescale_read_requirements() is False

    with patch.dict(os.environ, _enabled_env(), clear=False):
        assert mod.check_powerunits_timescale_read_requirements() is True
