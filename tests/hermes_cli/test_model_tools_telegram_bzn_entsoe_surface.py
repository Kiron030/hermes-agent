"""model_tools × Telegram first_safe_v1 surface for ENTSO‑E BZN tools.

Pinned contract: merging policy + gated ``check_fn`` must expose **both**
readiness **and** prices tools when Railway-like env gates are truthy —
regressions manifest as silently missing schemas in Telegram runtime.
"""

from __future__ import annotations

import pytest


def test_model_tools_final_names_include_entsoe_bzn_prices_and_readiness_railway_like_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: ``_get_platform_tools`` ∪ ``get_tool_definitions`` ≡ gateway tool list."""

    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    assert (
        "powerunits_entsoe_bzn_price_readiness" in enabled
    ), "telegram merge missing readiness leaf toolset"
    assert "powerunits_entsoe_bzn_prices" in enabled, (
        "telegram merge missing **powerunits_entsoe_bzn_prices** leaf toolset "
        "(check powerunits_telegram_overlays + apply_powerunits_runtime_policy + "
        "`agent.disabled_toolsets` in persisted config)."
    )

    defs = get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    names = {d["function"]["name"] for d in defs}

    bzn_hints = sorted(n for n in names if "bzn" in n.casefold() or "entsoe_bzn" in n)

    assert "read_powerunits_entsoe_bzn_price_readiness_v1" in names, (
        "missing readiness tool despite gate; schema_names_with_bzn_like="
        + str(bzn_hints)
    )

    assert "read_powerunits_entsoe_bzn_prices_v1" in names, (
        "Telegram runtime miss: **read_powerunits_entsoe_bzn_prices_v1** not in "
        "``get_tool_definitions`` after merge + gates. "
        "Check Railway `HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED=1`, cached "
        "gateway agent eviction (requires_env_binding signature), stale image, "
        "or YAML `agent.disabled_toolsets` dropping `powerunits_entsoe_bzn_prices`. "
        "bzn_like_tools_in_defs=" + str(bzn_hints)
    )


def test_model_tools_entsoe_bzn_prices_absent_when_prices_gate_unset_readiness_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.delenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED", raising=False)
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    names = {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }
    assert "read_powerunits_entsoe_bzn_prices_v1" not in names
    assert "read_powerunits_entsoe_bzn_price_readiness_v1" in names


def test_model_tools_entsoe_bzn_prices_absent_when_prices_gate_explicit_falsy_readiness_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED", "0")
    monkeypatch.setenv("HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", "https://example.test")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "test-secret")

    from hermes_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions

    enabled = _get_platform_tools({}, "telegram")
    names = {
        d["function"]["name"]
        for d in get_tool_definitions(enabled_toolsets=sorted(enabled), quiet_mode=True)
    }
    assert "read_powerunits_entsoe_bzn_prices_v1" not in names
    assert "read_powerunits_entsoe_bzn_price_readiness_v1" in names
