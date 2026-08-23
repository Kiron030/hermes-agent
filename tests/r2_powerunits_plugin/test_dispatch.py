"""Dispatch through modern Hermes handle_function_call, not wrapper imports."""

from __future__ import annotations

import json

from tests.powerunits_golden.env import (
    FIXED_CORRELATION_ID,
    FIXED_WINDOW_END,
    FIXED_WINDOW_START,
    SYNTHETIC_EXECUTE_BASE_URL,
)
from tests.powerunits_golden.http import RecordingPoster, correlation_from_headers
from tests.r2_powerunits_plugin.conftest import PLUGIN_TOOLS


def _patch_client(monkeypatch, poster: RecordingPoster):
    import hermes_plugins.powerunits.client as plugin_client

    monkeypatch.setattr(plugin_client, "http_post", poster)


def test_handle_function_call_dispatches_all_plugin_tools(loaded_plugin, monkeypatch) -> None:
    from model_tools import handle_function_call

    poster = RecordingPoster(
        {
            "success": True,
            "correlation_id": FIXED_CORRELATION_ID,
            "baseline_ready": True,
            "time_window": {
                "start_utc": FIXED_WINDOW_START,
                "end_utc_exclusive": FIXED_WINDOW_END,
                "expected_hours": 24,
            },
            "rows": [],
            "readiness": "go",
        }
    )
    _patch_client(monkeypatch, poster)

    args_by_tool = {
        "read_powerunits_coverage_snapshot_v1": {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
        "inventory_powerunits_bounded_coverage_v1": {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
        "read_powerunits_entsoe_bzn_price_readiness_v1": {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
        "readiness_powerunits_option_d_bounded_window": {
            "country": "PL",
            "start": FIXED_WINDOW_START,
            "end": FIXED_WINDOW_END,
            "version": "v1",
        },
    }

    for name in PLUGIN_TOOLS:
        raw = handle_function_call(name, args_by_tool[name])
        out = json.loads(raw)
        assert out.get("error_code") not in {"unknown_operation_id", "unexpected_field"}
        assert out.get("success") is not False or out.get("readiness") == "go"

    assert poster.count == len(PLUGIN_TOOLS)
    for call in poster.calls:
        assert call["scheme"] == "https"
        assert call["url"].startswith(SYNTHETIC_EXECUTE_BASE_URL)
        assert correlation_from_headers(call["headers"])
        assert call["headers"]["Authorization"].startswith("Bearer ")
        body_keys = set(call["json_body"])
        assert not {"url", "host", "base_url", "path", "sql"} & body_keys
