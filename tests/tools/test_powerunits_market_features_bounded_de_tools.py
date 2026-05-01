"""Tests for Hermes bounded DE market_features_hourly tools (separate from PL Option D)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_market_features_bounded_de_execute_tool as ex_mod
from tools import powerunits_market_features_bounded_de_validate_tool as val_mod
from tools.powerunits_bounded_family_gates import (
    MARKET_FEATURES_BOUNDED_LEGACY_ENV,
    MARKET_FEATURES_BOUNDED_PRIMARY_ENV,
)


def _clear_market_features_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MARKET_FEATURES_BOUNDED_PRIMARY_ENV, raising=False)
    for k in MARKET_FEATURES_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(k, raising=False)


def _prep_de_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MARKET_FEATURES_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def _prep_de_execute_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MARKET_FEATURES_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def _prep_de_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MARKET_FEATURES_BOUNDED_LEGACY_ENV["validate"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def test_de_execute_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_market_features_gates(monkeypatch)
    out = ex_mod.execute_powerunits_market_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T12:00:00Z",
    )
    data = json.loads(out)
    assert data.get("error_code") == "feature_disabled"
    assert data.get("execution_attempted") is False


def test_de_execute_local_validation_over_24h_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute(monkeypatch)
    called: list[bool] = []

    def boom(*a: Any, **k: Any) -> None:
        called.append(True)
        raise AssertionError("no http")

    out = ex_mod.execute_powerunits_market_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-02T00:00:01Z",
        _http_post=boom,
    )
    assert not called
    data = json.loads(out)
    assert data.get("execution_attempted") is False


def test_de_execute_http_posts_de_country(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute(monkeypatch)

    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.content = (
                '{"success":true,"correlation_id":"c","pipeline_run_id":"p","rows_written":3}'
            ).encode()

        def json(self) -> dict[str, Any]:
            return json.loads(self.content.decode())

        @property
        def text(self) -> str:
            return self.content.decode()

    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], json_body: dict[str, Any], timeout_s: float):
        captured["url"] = url
        captured["body"] = json_body
        return Resp()

    out = ex_mod.execute_powerunits_market_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T12:00:00Z",
        _http_post=fake_post,
    )
    data = json.loads(out)
    assert data.get("success") is True
    assert "/market-features-hourly/recompute" in captured["url"]
    assert captured["body"]["country_code"] == "DE"


def test_de_execute_http_posts_de_country_via_primary_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute_primary(monkeypatch)

    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.content = (
                '{"success":true,"correlation_id":"c","pipeline_run_id":"p","rows_written":3}'
            ).encode()

        def json(self) -> dict[str, Any]:
            return json.loads(self.content.decode())

        @property
        def text(self) -> str:
            return self.content.decode()

    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], json_body: dict[str, Any], timeout_s: float):
        captured["url"] = url
        captured["body"] = json_body
        return Resp()

    out = ex_mod.execute_powerunits_market_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T12:00:00Z",
        _http_post=fake_post,
    )
    data = json.loads(out)
    assert data.get("success") is True
    assert captured["body"]["country_code"] == "DE"


def test_de_validate_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_market_features_gates(monkeypatch)
    raw = val_mod.validate_powerunits_market_features_bounded_de_window(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T06:00:00Z",
    )
    assert json.loads(raw)["error_code"] == "feature_disabled"


def test_slice_helpers_de_and_version() -> None:
    from tools.powerunits_market_features_bounded_de_slice import validate_de_market_features_bounded_window

    cc, ver, *_ = validate_de_market_features_bounded_window(
        "2024-01-01T00:00:00Z",
        "2024-01-01T01:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert ver == "v1"


def test_legacy_execute_only_does_not_enable_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_market_features_gates(monkeypatch)
    monkeypatch.setenv(MARKET_FEATURES_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")
    raw = val_mod.validate_powerunits_market_features_bounded_de_window(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T06:00:00Z",
    )
    assert json.loads(raw)["error_code"] == "feature_disabled"


def test_primary_flag_enables_validate_without_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute_primary(monkeypatch)

    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.content = b'{"outcome":"passed","correlation_id":"x"}'

        def json(self) -> dict[str, Any]:
            return json.loads(self.content.decode())

        @property
        def text(self) -> str:
            return self.content.decode()

    raw = val_mod.validate_powerunits_market_features_bounded_de_window(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T06:00:00Z",
        _http_post=lambda *_a, **_k: Resp(),
    )
    assert json.loads(raw).get("validation_attempted") is True


def test_execute_schema_mentions_option_d_and_consolidated_flag() -> None:
    desc = ex_mod.EXEC_MF_DE_SCHEMA["description"]
    assert "OPTION_D" in desc or "Option D" in desc
    assert MARKET_FEATURES_BOUNDED_PRIMARY_ENV in desc
