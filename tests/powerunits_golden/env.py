"""Operator-ready first_safe_v1 env for Golden surface capture.

Synthetic hosts/secrets only. Does not read or write production configuration.
"""

from __future__ import annotations

from typing import Mapping

# Synthetic pin target. Not a production architecture constant.
SYNTHETIC_EXECUTE_HOST = "bounded.example.test"
SYNTHETIC_EXECUTE_BASE_URL = f"https://{SYNTHETIC_EXECUTE_HOST}"
SYNTHETIC_EXECUTE_SECRET = "r0-golden-synthetic-secret"
SYNTHETIC_TAVILY_KEY = "tvly-r0-golden"
SYNTHETIC_GITHUB_TOKEN = "ghs-r0-golden-read"
SYNTHETIC_TIMESCALE_DSN = "postgresql://golden:golden@timescale.example.test:5432/golden"

FIXED_CORRELATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FIXED_WINDOW_START = "2024-01-01T00:00:00Z"
FIXED_WINDOW_END = "2024-01-02T00:00:00Z"
FIXED_CAMPAIGN_END = "2024-01-08T00:00:00Z"

# All first_safe family / leaf gates that exist today. Enabling them in tests
# records the surface WHEN those gates are on. It does not change deployment.
OPERATOR_READY_ENABLED_FLAGS: tuple[str, ...] = (
    "HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED",
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED",
    "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED",
    "HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED",
    "HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED",
    "HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_ENABLED",
    "HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED",
    "HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED",
    "HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED",
    "HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED",
    "HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED",
    "HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED",
    "HERMES_POWERUNITS_TIMESCALE_READ_ENABLED",
    "HERMES_POWERUNITS_REPO_B_READ_ENABLED",
    "HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED",
    "HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED",
    "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED",
    "HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED",
)

UNSAFE_FREEDOMS_FIRST_SAFE_DENIES: tuple[str, ...] = (
    "session_search",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "terminal",
    "execute_code",
    "process",
    "delegate_task",
    "browser",
    "computer",
    "cron",
    "routine",
    "web_browser",
)

ENV_PROFILE = "operator_ready_gates_on_synthetic"


def invalidate_tool_surface_caches() -> None:
    from model_tools import _clear_tool_defs_cache
    from tools.registry import invalidate_check_fn_cache

    invalidate_check_fn_cache()
    _clear_tool_defs_cache()


def apply_operator_ready_env(monkeypatch, *, tier: int) -> None:
    """Apply a realistic first_safe_v1 gate combination with synthetic credentials."""

    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", str(tier))
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    monkeypatch.setenv("TAVILY_API_KEY", SYNTHETIC_TAVILY_KEY)
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", SYNTHETIC_GITHUB_TOKEN)
    monkeypatch.setenv("DATABASE_URL_TIMESCALE", SYNTHETIC_TIMESCALE_DSN)
    for flag in OPERATOR_READY_ENABLED_FLAGS:
        monkeypatch.setenv(flag, "1")
    invalidate_tool_surface_caches()


def apply_execute_pin(
    monkeypatch,
    *,
    base_url: str,
    allowed_hosts: str | None,
    pin_mode: str,
    extra: Mapping[str, str] | None = None,
) -> None:
    if allowed_hosts is None:
        monkeypatch.delenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", raising=False)
    else:
        monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", allowed_hosts)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", base_url)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", pin_mode)
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    if extra:
        for key, value in extra.items():
            monkeypatch.setenv(key, value)
