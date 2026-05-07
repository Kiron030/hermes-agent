"""Tests for read_powerunits_entsoe_bzn_price_readiness_v1 (thin Repo B bounded read)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from tools import powerunits_entsoe_bzn_price_readiness_tool as mod
from tools.registry import registry


WINDOW = dict(
    window_start_utc="2024-01-01T00:00:00Z",
    window_end_utc="2024-01-02T00:00:00Z",
)


def test_gate_off_requires_feature_and_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod._FEATURE_ENV, raising=False)
    monkeypatch.delenv(mod._BASE_ENV, raising=False)
    monkeypatch.delenv(mod._SECRET_ENV, raising=False)
    raw = mod.read_powerunits_entsoe_bzn_price_readiness_v1(**WINDOW)
    body = json.loads(raw)
    assert body.get("success") is False
    assert body.get("error_code") == "feature_disabled"
    assert body.get("read_attempted") is False
    assert "read-only" in body.get("hermes_operator_note_v1", "").lower()


def test_missing_base_or_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.delenv(mod._BASE_ENV, raising=False)
    monkeypatch.delenv(mod._SECRET_ENV, raising=False)
    assert mod.check_powerunits_entsoe_bzn_price_readiness_requirements() is False


def test_http_200_repo_json_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._BASE_ENV, "https://powerunits-api.test")
    monkeypatch.setenv(mod._SECRET_ENV, "secret")

    repo = {
        "success": True,
        "bounded_internal_statement": "bzn_price_readiness_read_only",
        "countries": [{"country_code": "DK"}],
        "promotes_tier1": False,
    }

    def _post(url: str, headers: dict, body: dict, timeout_s: float) -> httpx.Response:
        assert url.endswith("/internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read")
        assert headers["Authorization"] == "Bearer secret"
        assert headers.get("X-Correlation-ID")
        assert body["country_codes"] == ["DK", "NO", "IE"]
        assert body["window_start_utc"].startswith("2024")
        assert body["table_version"] == mod._DEFAULT_TABLE_VERSION
        return httpx.Response(200, json=repo)

    out = json.loads(
        mod.read_powerunits_entsoe_bzn_price_readiness_v1(
            country_codes=["dk", "no", "ie"],
            window_start_utc=WINDOW["window_start_utc"],
            window_end_utc=WINDOW["window_end_utc"],
            table_version="bzn_advisory_v1",
            _http_post=_post,
        )
    )
    assert out["success"] is True
    assert out["countries"][0]["country_code"] == "DK"
    assert out["http_status_from_repo_b"] == 200
    assert out["read_attempted"] is True
    note = out.get("hermes_operator_note_v1", "")
    assert "no jobs" in note.lower()
    assert "tier-1" in note.lower() or "tier" in note.lower()


def test_default_country_codes_advisory_quintet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "true")
    monkeypatch.setenv(mod._BASE_ENV, "https://pu.test")
    monkeypatch.setenv(mod._SECRET_ENV, "x")
    captured: dict[str, object] = {}

    def _post(url: str, headers: dict, body: dict, timeout_s: float) -> httpx.Response:
        captured["country_codes"] = list(body["country_codes"])
        return httpx.Response(200, json={"success": True, "countries": []})

    mod.read_powerunits_entsoe_bzn_price_readiness_v1(
        country_codes=None,
        window_start_utc=WINDOW["window_start_utc"],
        window_end_utc=WINDOW["window_end_utc"],
        _http_post=_post,
    )
    assert captured["country_codes"] == ["DK", "NO", "SE", "IT", "IE"]


def test_repo_b_http_400_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._BASE_ENV, "https://pu.test")
    monkeypatch.setenv(mod._SECRET_ENV, "x")

    def _post(url: str, headers: dict, body: dict, timeout_s: float) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "success": False,
                "error_code": "invalid_country",
                "bounded_internal_statement": "bzn_price_readiness_read_only",
            },
        )

    out = json.loads(
        mod.read_powerunits_entsoe_bzn_price_readiness_v1(
            window_start_utc=WINDOW["window_start_utc"],
            window_end_utc=WINDOW["window_end_utc"],
            country_codes=["DE"],
            _http_post=_post,
        )
    )
    assert out.get("success") is False
    assert out.get("http_status_from_repo_b") == 400
    assert out.get("error_code") == "invalid_country"


def test_bad_country_codes_type_local_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._BASE_ENV, "https://pu.test")
    monkeypatch.setenv(mod._SECRET_ENV, "y")
    out = json.loads(
        mod.read_powerunits_entsoe_bzn_price_readiness_v1(
            country_codes={"not": "a list"},
            window_start_utc=WINDOW["window_start_utc"],
            window_end_utc=WINDOW["window_end_utc"],
        )
    )
    assert out.get("error_code") == "invalid_country_codes"


def test_schema_mentions_read_only_and_no_writes() -> None:
    desc = mod.BZN_PRICE_READINESS_SCHEMA_V1.get("description", "")
    dl = desc.lower()
    assert "read-only" in dl
    assert "no" in dl and ("job" in dl or "jobs" in dl)
    assert "tier" in dl


def test_tool_source_has_no_workspace_persistence() -> None:
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "save_hermes_workspace" not in src
    assert "write_file" not in src


def test_registry_discovery_toolset() -> None:
    ts = registry.get_toolset_for_tool("read_powerunits_entsoe_bzn_price_readiness_v1")
    assert ts == "powerunits_entsoe_bzn_price_readiness"


def test_first_safe_includes_readiness_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "tok")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_entsoe_bzn_price_readiness", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "read_powerunits_entsoe_bzn_price_readiness_v1" in names
    assert "web_search" not in names
