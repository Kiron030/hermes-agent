"""Tests for Hermes bounded DE market_driver_features_hourly tools (separate from market-features DE + Option D)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools import powerunits_market_driver_features_bounded_de_execute_tool as ex_mod
from tools import powerunits_market_driver_features_bounded_de_validate_tool as val_mod
from tools.powerunits_bounded_family_gates import (
    MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV,
    MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV,
)


def _clear_driver_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV, raising=False)
    for k in MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(k, raising=False)


def _prep_de_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def _prep_de_execute_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def _prep_de_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV["validate"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")


def test_de_driver_execute_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_driver_gates(monkeypatch)
    out = ex_mod.execute_powerunits_market_driver_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T12:00:00Z",
    )
    data = json.loads(out)
    assert data.get("error_code") == "feature_disabled"
    assert data.get("execution_attempted") is False


def test_de_driver_execute_local_validation_over_24h_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute(monkeypatch)
    called: list[bool] = []

    def boom(*a: Any, **k: Any) -> None:
        called.append(True)
        raise AssertionError("no http")

    out = ex_mod.execute_powerunits_market_driver_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-02T00:00:01Z",
        _http_post=boom,
    )
    assert not called
    data = json.loads(out)
    assert data.get("execution_attempted") is False


def test_de_driver_execute_http_posts_de_country_and_driver_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute(monkeypatch)

    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.content = (
                '{"success":true,"correlation_id":"c","pipeline_run_id":"p","rows_written":2,'
                '"downstream_not_auto_triggered":["market_feature_job"],'
                '"operator_note":"cost inputs optional"}'
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

    out = ex_mod.execute_powerunits_market_driver_features_bounded_de_slice(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T12:00:00Z",
        _http_post=fake_post,
    )
    data = json.loads(out)
    assert data.get("success") is True
    assert "/market-driver-features-hourly/recompute" in captured["url"]
    assert captured["body"]["country_code"] == "DE"
    assert data.get("downstream_not_auto_triggered") == ["market_feature_job"]
    assert "operator_note" in data


def test_de_driver_execute_primary_flag_same_http_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute_primary(monkeypatch)

    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.content = b'{"success":true}'

        def json(self) -> dict[str, Any]:
            return {"success": True}

        @property
        def text(self) -> str:
            return self.content.decode()

    captured: dict[str, Any] = {}

    def fake_post(url: str, headers: dict[str, str], json_body: dict[str, Any], timeout_s: float):
        captured["url"] = url
        return Resp()

    json.loads(
        ex_mod.execute_powerunits_market_driver_features_bounded_de_slice(
            window_start_utc="2024-01-01T00:00:00Z",
            window_end_utc="2024-01-01T12:00:00Z",
            _http_post=fake_post,
        )
    )
    assert "/market-driver-features-hourly/recompute" in captured["url"]


def test_de_driver_validate_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_driver_gates(monkeypatch)
    raw = val_mod.validate_powerunits_market_driver_features_bounded_de_window(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T06:00:00Z",
    )
    assert json.loads(raw)["error_code"] == "feature_disabled"


def test_driver_legacy_execute_only_does_not_enable_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_driver_gates(monkeypatch)
    monkeypatch.setenv(MARKET_DRIVER_FEATURES_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://pu.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "sec")
    raw = val_mod.validate_powerunits_market_driver_features_bounded_de_window(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T06:00:00Z",
    )
    assert json.loads(raw)["error_code"] == "feature_disabled"


def test_driver_primary_enables_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _prep_de_execute_primary(monkeypatch)

    class Resp:
        status_code = 200
        content = b'{"outcome":"passed"}'

        def json(self) -> dict[str, Any]:
            return {"outcome": "passed"}

        @property
        def text(self) -> str:
            return self.content.decode()

    raw = val_mod.validate_powerunits_market_driver_features_bounded_de_window(
        window_start_utc="2024-01-01T00:00:00Z",
        window_end_utc="2024-01-01T06:00:00Z",
        _http_post=lambda *_a, **_k: Resp(),
    )
    assert json.loads(raw).get("validation_attempted") is True


def test_execute_schema_mentions_market_features_separate_and_consolidated_gate() -> None:
    desc = ex_mod.EXEC_MDRIVER_DE_SCHEMA["description"]
    assert "MARKET_FEATURES_BOUNDED_DE" in desc or "market-features" in desc.lower()
    assert MARKET_DRIVER_FEATURES_BOUNDED_PRIMARY_ENV in desc
