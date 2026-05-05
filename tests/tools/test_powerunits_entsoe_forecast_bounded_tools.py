"""Tests for bounded ENTSO-E forecast Hermes tools (HTTP to Repo B)."""

from __future__ import annotations

import json

import pytest

from tools import powerunits_entsoe_forecast_bounded_execute_tool as exec_mod
from tools import powerunits_entsoe_forecast_bounded_preflight_tool as pre_mod
from tools import powerunits_entsoe_forecast_bounded_validate_tool as val_mod
from tools.powerunits_bounded_family_gates import (
    ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ENTSOE_FORECAST_BOUNDED_LEGACY_ENV,
    ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV,
)
from tools.powerunits_entsoe_forecast_bounded_slice import validate_entsoe_forecast_bounded_slice


def _clear_fcst_bounded_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, raising=False)
    for env_name in ENTSOE_FORECAST_BOUNDED_LEGACY_ENV.values():
        monkeypatch.delenv(env_name, raising=False)


def _with_execute_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_execute_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_feature_disabled_primary_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "feature_disabled"


def test_execute_http_200_via_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "rid",
                "correlation_id": "cid",
                "rows_written": 12,
                "downstream_not_auto_triggered": ["market_feature_job"],
                "operator_statement": "forecast only",
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/recompute" in url
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True
    assert out["downstream_not_auto_triggered"] == ["market_feature_job"]
    assert out["operator_statement"] == "forecast only"


@pytest.mark.parametrize("country", ["BE", "FR", "AT", "CZ", "PL"])
def test_execute_http_be_fr_via_primary_allowlist_unset(
    monkeypatch: pytest.MonkeyPatch, country: str
) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.delenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "fcst-be-fr",
                "correlation_id": "cid",
                "rows_written": 7,
                "downstream_not_auto_triggered": ["market_feature_job"],
                "operator_statement": "forecast only",
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/recompute" in url
        assert json_body["country_code"] == country
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country=country,
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True


@pytest.mark.parametrize("country", ["BE", "FR", "AT", "CZ", "PL"])
def test_preflight_be_fr_via_primary_allowlist_unset(
    monkeypatch: pytest.MonkeyPatch, country: str
) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.delenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    out = json.loads(
        pre_mod.preflight_powerunits_entsoe_forecast_bounded_slice(
            country=country,
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert out.get("error_code") != "country_not_permitted"


def test_execute_http_nl_via_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    class R:
        status_code = 200
        content = b"{}"
        text = json.dumps(
            {
                "success": True,
                "status": "success",
                "pipeline_run_id": "nl-rid",
                "correlation_id": "cid",
                "rows_written": 24,
                "downstream_not_auto_triggered": ["market_feature_job"],
                "operator_statement": "forecast only",
            }
        )

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/recompute" in url
        assert json_body["country_code"] == "NL"
        return R()

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="NL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["success"] is True


def test_execute_country_not_permitted_when_allowlist_de_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    called: list[bool] = []

    def _should_not_call(*_args, **_kw) -> None:
        called.append(True)
        raise AssertionError("unexpected HTTP POST")

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="NL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=_should_not_call,
        )
    )
    assert not called
    assert out.get("error_code") == "country_not_permitted"
    assert out.get("execution_attempted") is False


def test_validate_wrong_country_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("no http")

    out = json.loads(
        val_mod.validate_powerunits_entsoe_forecast_bounded_window(
            country="PT",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=boom,
        )
    )
    assert out["validation_attempted"] is False


def test_legacy_execute_only_does_not_open_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_LEGACY_ENV["execute"], "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://x")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "y")
    assert val_mod.check_powerunits_entsoe_forecast_bounded_validate_requirements() is False


def _with_forecast_validate_primary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")


def test_validate_posts_only_entsoe_forecast_bounded_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_forecast_validate_primary_env(monkeypatch)

    captured: dict[str, str] = {}

    ok_body = json.dumps(
        {
            "outcome": "passed",
            "summary_code": "validation_passed",
            "warnings": [],
            "read_target": "primary",
            "checks": {
                "market_entsoe_load_forecast_hourly": {"row_count": 1},
                "market_entsoe_wind_solar_forecast_hourly": {"row_count": 0},
            },
        }
    )

    class R:
        status_code = 200
        text = ok_body
        content = ok_body.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        captured["url"] = url
        assert "entsoe-forecast/validate-window" in url
        assert "entsoe-market-sync" not in url
        return R()

    out = json.loads(
        val_mod.validate_powerunits_entsoe_forecast_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["validation_attempted"] is True
    assert out["bounded_internal_post_path"].endswith("/entsoe-forecast/validate-window")
    assert (
        out["bounded_internal_validator_family"] == val_mod._BOUNDED_REPO_B_VALIDATE_FAMILY_V1
    )
    assert "unexpected_contract_warnings" not in out
    assert "entsoe-forecast/validate-window" in captured["url"]


def test_validate_emits_warning_if_body_shape_is_market_sync_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guards against misrouted HTTP or wrong tool invocation echoing market-sync validate checks."""
    _with_forecast_validate_primary_env(monkeypatch)

    bad_body = json.dumps(
        {
            "outcome": "passed",
            "summary_code": "validation_passed",
            "warnings": [],
            "read_target": "primary",
            "checks": {
                "market_demand_hourly": {"row_count": 1},
            },
        }
    )

    class R:
        status_code = 200
        text = bad_body
        content = bad_body.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/validate-window" in url
        return R()

    out = json.loads(
        val_mod.validate_powerunits_entsoe_forecast_bounded_window(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out.get("unexpected_contract_warnings")
    assert any(
        "validate_powerunits_entsoe_market_bounded_window" in w
        for w in out["unexpected_contract_warnings"]
    )


def test_preflight_valid_de_via_primary_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    out = json.loads(
        pre_mod.preflight_powerunits_entsoe_forecast_bounded_slice(
            country="DE",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is True
    assert "execute_powerunits_entsoe_forecast_bounded_slice" in out["bounded_http_operator_hint"]


@pytest.mark.parametrize("country", ["BE", "FR"])
def test_execute_blocked_when_allowlist_de_nl_only_forecast(
    monkeypatch: pytest.MonkeyPatch, country: str
) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    called: list[bool] = []

    def _no_http(*_a: object, **_k: object) -> None:
        called.append(True)
        raise AssertionError("unexpected HTTP POST")

    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country=country,
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=_no_http,
        )
    )
    assert not called
    assert out.get("error_code") == "country_not_permitted"


@pytest.mark.parametrize("country", ["BE", "FR", "AT", "CZ", "PL"])
def test_validate_via_primary_be_fr_allowlist_unset_forecast(
    monkeypatch: pytest.MonkeyPatch, country: str
) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.delenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    ok_body = json.dumps(
        {
            "outcome": "passed",
            "summary_code": "validation_passed",
            "warnings": [],
            "read_target": "primary",
            "checks": {
                "market_entsoe_load_forecast_hourly": {"row_count": 1},
                "market_entsoe_wind_solar_forecast_hourly": {"row_count": 0},
            },
        }
    )

    class R:
        status_code = 200
        text = ok_body
        content = ok_body.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/validate-window" in url
        assert json_body["country_code"] == country
        return R()

    out = json.loads(
        val_mod.validate_powerunits_entsoe_forecast_bounded_window(
            country=country,
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["validation_attempted"] is True


@pytest.mark.parametrize("country", ["BE", "FR", "AT", "CZ", "PL"])
def test_summary_via_primary_be_fr_allowlist_unset_forecast(
    monkeypatch: pytest.MonkeyPatch, country: str
) -> None:
    from tools import powerunits_entsoe_forecast_bounded_summary_tool as sum_mod

    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.delenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, raising=False)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")

    ok_body = json.dumps(
        {
            "success": True,
            "outcome_class": "ok",
            "correlation_id": "cid",
            "operator_next": "ok",
        }
    )

    class R:
        status_code = 200
        text = ok_body
        content = ok_body.encode("utf-8")

        def json(self) -> dict:
            return json.loads(self.text)

    def fake_post(url: str, headers: dict, json_body: dict, timeout_s: float) -> R:
        assert "entsoe-forecast/summary-window" in url
        assert json_body["country_code"] == country
        return R()

    out = json.loads(
        sum_mod.summarize_powerunits_entsoe_forecast_bounded_window(
            country=country,
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=fake_post,
        )
    )
    assert out["summary_attempted"] is True


def test_execute_at_blocked_when_allowlist_core_four_only_forecast(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL,BE,FR")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    out = json.loads(
        exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
            country="AT",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
            _http_post=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
        )
    )
    assert out.get("error_code") == "country_not_permitted"


def test_execute_forecast_blocked_when_allowlist_explicit_de_through_at_blocks_cz_pl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE,NL,BE,FR,AT")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://powerunits-api.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "secret")
    for country in ("CZ", "PL"):
        out = json.loads(
            exec_mod.execute_powerunits_entsoe_forecast_bounded_slice(
                country=country,
                start="2024-01-01T00:00:00Z",
                end="2024-01-01T12:00:00Z",
                version="v1",
                _http_post=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
            )
        )
        assert out.get("error_code") == "country_not_permitted"


@pytest.mark.parametrize("iso2", ["ES", "IT", "SE"])
def test_preflight_es_it_rejected_slice_forecast(monkeypatch: pytest.MonkeyPatch, iso2: str) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    out = json.loads(
        pre_mod.preflight_powerunits_entsoe_forecast_bounded_slice(
            country=iso2,
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out["syntactically_valid"] is False


def test_forecast_slice_accepts_7d() -> None:
    cc, start, end = validate_entsoe_forecast_bounded_slice(
        "DE",
        "2024-01-01T00:00:00Z",
        "2024-01-08T00:00:00Z",
        "v1",
    )
    assert cc == "DE"
    assert (end - start).total_seconds() == 7 * 24 * 3600


def test_forecast_slice_accepts_nl() -> None:
    cc, *_ = validate_entsoe_forecast_bounded_slice(
        "NL",
        "2024-01-01T00:00:00Z",
        "2024-01-01T12:00:00Z",
        "v1",
    )
    assert cc == "NL"


def test_preflight_nl_blocked_when_allowlist_de_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_fcst_bounded_core(monkeypatch)
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV, "1")
    monkeypatch.setenv(ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV, "DE")
    out = json.loads(
        pre_mod.preflight_powerunits_entsoe_forecast_bounded_slice(
            country="NL",
            start="2024-01-01T00:00:00Z",
            end="2024-01-01T12:00:00Z",
            version="v1",
        )
    )
    assert out.get("error_code") == "country_not_permitted"
