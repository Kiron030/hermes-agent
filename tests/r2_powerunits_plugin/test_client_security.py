"""Host / transport negatives. All HTTP mocked. No live network."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import pytest

from tests.powerunits_golden.env import (
    FIXED_WINDOW_END,
    FIXED_WINDOW_START,
    SYNTHETIC_EXECUTE_HOST,
    SYNTHETIC_EXECUTE_SECRET,
)
from tests.powerunits_golden.http import RecordingPoster
from tests.r2_powerunits_plugin.conftest import PLUGIN_TOOLS


def _client(loaded_plugin):
    import hermes_plugins.powerunits.client as plugin_client

    return plugin_client


def test_foreign_host_rejected(loaded_plugin, monkeypatch) -> None:
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://evil.example")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    poster = RecordingPoster({"success": True})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    out = client.invoke(
        "read_powerunits_coverage_snapshot_v1",
        {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
    )
    assert poster.count == 0
    assert out["success"] is False
    assert out["error_code"] == "execute_target_host_refused"


def test_evil_suffix_host_rejected(loaded_plugin, monkeypatch) -> None:
    monkeypatch.setenv(
        "POWERUNITS_INTERNAL_EXECUTE_BASE_URL",
        f"https://{SYNTHETIC_EXECUTE_HOST}.evil.com",
    )
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    poster = RecordingPoster({"success": True})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    out = client.invoke(
        "read_powerunits_coverage_snapshot_v1",
        {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
    )
    assert poster.count == 0
    assert out["error_code"] == "execute_target_host_refused"
    assert urlparse(f"https://{SYNTHETIC_EXECUTE_HOST}.evil.com").hostname != SYNTHETIC_EXECUTE_HOST


def test_http_scheme_rejected(loaded_plugin, monkeypatch) -> None:
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", f"http://{SYNTHETIC_EXECUTE_HOST}")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    poster = RecordingPoster({"success": True})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    out = client.invoke(
        "read_powerunits_coverage_snapshot_v1",
        {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
    )
    assert poster.count == 0
    assert out["error_code"] == "execute_target_https_required"


def test_unknown_operation_id_rejected(loaded_plugin, monkeypatch) -> None:
    poster = RecordingPoster({"success": True})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    out = client.invoke("not_a_real_operation", {"country_codes": ["DE"]})
    assert poster.count == 0
    assert out["error_code"] == "unknown_operation_id"


def test_arbitrary_path_impossible_from_body(loaded_plugin, monkeypatch) -> None:
    poster = RecordingPoster({"success": True, "correlation_id": "cid"})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    out = client.invoke(
        "read_powerunits_coverage_snapshot_v1",
        {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
            "path": "/internal/hermes/bounded/v1/market-features-hourly/recompute",
        },
    )
    assert poster.count == 0
    assert out["error_code"] == "unexpected_field"
    assert "path" in out["rejected_fields"]


@pytest.mark.parametrize("tool_name", PLUGIN_TOOLS)
def test_handler_rejects_url_sql_and_unknown_fields(loaded_plugin, monkeypatch, tool_name) -> None:
    from model_tools import handle_function_call

    poster = RecordingPoster({"success": True})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    raw = handle_function_call(
        tool_name,
        {
            "url": "https://evil.example/x",
            "sql": "SELECT 1",
            "host": "evil.example",
            "path": "/etc/passwd",
        },
    )
    out = json.loads(raw)
    assert poster.count == 0
    assert out["error_code"] == "unexpected_field"


def test_bearer_stays_inside_client(loaded_plugin, monkeypatch) -> None:
    poster = RecordingPoster({"success": True, "correlation_id": "cid"})
    client = _client(loaded_plugin)
    monkeypatch.setattr(client, "http_post", poster)
    out = client.invoke(
        "read_powerunits_coverage_snapshot_v1",
        {
            "country_codes": ["DE"],
            "window_start_utc": FIXED_WINDOW_START,
            "window_end_utc": FIXED_WINDOW_END,
        },
    )
    assert poster.count == 1
    assert poster.calls[0]["headers"]["Authorization"] == f"Bearer {SYNTHETIC_EXECUTE_SECRET}"
    dumped = json.dumps(out)
    assert SYNTHETIC_EXECUTE_SECRET not in dumped
