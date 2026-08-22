"""Task E — S0-C host-binding Golden negatives. Synthetic hosts only."""

from __future__ import annotations

import json

import pytest

from tests.powerunits_golden.env import SYNTHETIC_EXECUTE_SECRET
from tests.powerunits_golden.http import RecordingPoster
from tools import powerunits_bounded_coverage_snapshot_tool as snap
from tools.powerunits_execute_base_url_v1 import (
    ERROR_ALLOWLIST_REQUIRED,
    ERROR_HOST_REFUSED,
    ERROR_HTTPS_REQUIRED,
    resolve_powerunits_execute_base_url,
)


def _pin(monkeypatch: pytest.MonkeyPatch, base: str, allowed: str | None, mode: str) -> None:
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", base)
    if allowed is None:
        monkeypatch.delenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", raising=False)
    else:
        monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", allowed)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", mode)
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "1")


def test_https_required(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin(monkeypatch, "http://allowed.example", "allowed.example", "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_HTTPS_REQUIRED


def test_exact_host_matching_rejects_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin(
        monkeypatch,
        "https://allowed.example.evil.invalid",
        "allowed.example",
        "enforce",
    )
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_HOST_REFUSED
    assert resolved.hostname == "allowed.example.evil.invalid"


def test_foreign_host_enforce_refuses_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin(monkeypatch, "https://foreign.example", "allowed.example", "enforce")
    poster = RecordingPoster({"success": True})
    out = json.loads(
        snap.read_powerunits_coverage_snapshot_v1(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-02T00:00:00Z",
            country_codes=["DE"],
            _http_post=poster,
        )
    )
    assert poster.count == 0
    assert out["success"] is False
    assert out.get("error_code") == ERROR_HOST_REFUSED


def test_enforce_empty_allowlist_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    _pin(monkeypatch, "https://allowed.example", "", "enforce")
    resolved = resolve_powerunits_execute_base_url()
    assert resolved.refused is True
    assert resolved.error_code == ERROR_ALLOWLIST_REQUIRED


def test_model_schema_cannot_supply_host_url_or_route() -> None:
    schema = snap.COVERAGE_SNAPSHOT_SCHEMA_V1
    props = schema["parameters"]["properties"]
    forbidden = {
        "url",
        "base_url",
        "host",
        "hostname",
        "path",
        "route",
        "endpoint",
        "POWERUNITS_INTERNAL_EXECUTE_BASE_URL",
    }
    assert forbidden.isdisjoint(props)
    assert set(schema["parameters"]["required"]) == {
        "country_codes",
        "window_start_utc",
        "window_end_utc",
    }
