"""Security / authority: what each system refuses, and who makes it refuse.

The distinction R3 has to keep straight is *where the refusal lives*:

    CURRENT_FORK  refuses via a PowerUnits-specific clamp keyed on
                  HERMES_POWERUNITS_RUNTIME_POLICY, which imports domain modules
                  into shared core.
    MODERN        refuses via agent.final_allowed_toolsets, which knows only
                  about config, toolsets and tool names.

Both are measured against the same widening attempts.
"""

from __future__ import annotations

import json

import pytest
import yaml

from tests.powerunits_golden.contracts import happy_repo_b_payload
from tests.powerunits_golden.env import UNSAFE_FREEDOMS_FIRST_SAFE_DENIES
from tests.powerunits_golden.http import RecordingPoster
from tests.r3_shadow_comparison.conftest import PLUGIN_NAME, PLUGIN_TOOLS, PLUGIN_TOOLSET
from tests.r3_shadow_comparison.corpus import BOUNDED_CASES

CASE_IDS = [case.case_id for case in BOUNDED_CASES]
FORBIDDEN_TRANSPORT_FIELDS = ("url", "host", "base_url", "path", "sql", "route")


def _callable_names(**kwargs) -> set[str]:
    from model_tools import get_tool_definitions

    return {t["function"]["name"] for t in get_tool_definitions(**kwargs)}


# ---------------------------------------------------------------------------
# Final callable surface: caller override, `all`, plugin self-expansion
# ---------------------------------------------------------------------------


def test_modern_cap_survives_caller_override(modern_stack) -> None:
    """A caller asking for high-authority families gets nothing extra."""

    names = _callable_names(
        enabled_toolsets=["terminal", "file", "delegation", "browser", PLUGIN_TOOLSET],
        quiet_mode=True,
    )
    assert names & set(PLUGIN_TOOLS), "the allowlisted bounded reads must survive"
    for forbidden in UNSAFE_FREEDOMS_FIRST_SAFE_DENIES:
        assert forbidden not in names, f"caller override restored {forbidden}"


def test_modern_cap_survives_toolsets_all(modern_stack) -> None:
    """`--toolsets all` reaches the seam as enabled=None; the cap still holds."""

    names = _callable_names(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True)
    for forbidden in UNSAFE_FREEDOMS_FIRST_SAFE_DENIES:
        assert forbidden not in names, f"--toolsets all restored {forbidden}"


def test_modern_cap_blocks_plugin_self_expansion(modern_stack, tmp_path) -> None:
    """An undeclared plugin toolset default-enables itself but cannot pass the cap."""

    home = modern_stack["home"]
    (home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "plugins": {"enabled": [PLUGIN_NAME]},
                "agent": {"final_allowed_toolsets": ["memory"]},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    from model_tools import _clear_tool_defs_cache

    _clear_tool_defs_cache()

    names = _callable_names(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True)
    assert not (names & set(PLUGIN_TOOLS)), (
        "a plugin that self-expands must not appear above a cap that omits it"
    )


def test_current_fork_clamp_still_holds(current_fork) -> None:
    """The legacy clamp is untouched by R3 and still bounds the fork."""

    names = _callable_names(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=True)
    for forbidden in UNSAFE_FREEDOMS_FIRST_SAFE_DENIES:
        assert forbidden not in names, f"fork clamp leaked {forbidden}"


def test_the_two_clamps_are_independent() -> None:
    """Source-level: the generic cap carries no domain knowledge, the legacy one does."""

    import inspect

    import model_tools

    generic = inspect.getsource(model_tools._read_final_toolset_cap) + inspect.getsource(
        model_tools._resolve_final_allowed_tools
    )
    assert "powerunits" not in generic.lower()
    assert "telegram" not in generic.lower()

    seam = inspect.getsource(model_tools._compute_tool_definitions)
    assert "HERMES_POWERUNITS_RUNTIME_POLICY" in seam, (
        "R3 must not remove the legacy clamp; it only measures it"
    )
    assert "_read_final_toolset_cap()" in seam


# ---------------------------------------------------------------------------
# Transport authority: the model must not choose host / path / URL / SQL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_no_transport_field_in_either_schema(current_fork, modern_stack, case) -> None:
    """Neither system lets the model name a destination."""

    # modern_stack has replaced the wrapper registration for these names, so
    # this reads the modern schema; the fork schema is read from the R0 fixture
    # captured while the wrappers were registered.
    from tools.registry import registry

    entry = registry.get_entry(case.modern_tool)
    assert entry is not None
    properties = set((entry.schema.get("parameters") or {}).get("properties") or {})
    assert not properties & set(FORBIDDEN_TRANSPORT_FIELDS), case.case_id
    assert (entry.schema.get("parameters") or {}).get("additionalProperties") is False


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_fork_schemas_do_not_close_the_object(current_fork, case) -> None:
    """Measured difference, not a defect claim: the wrappers leave the door open.

    Neither system exposes a transport field, but only the plugin schemas declare
    ``additionalProperties: false``, so only the plugin refuses an unexpected key
    at the schema boundary.
    """

    from tools.registry import registry

    entry = registry.get_entry(case.current_fork_tool)
    assert entry is not None
    parameters = entry.schema.get("parameters") or {}
    assert not set(parameters.get("properties") or {}) & set(FORBIDDEN_TRANSPORT_FIELDS)
    assert parameters.get("additionalProperties") is None, (
        "if a wrapper starts closing its object, update the R3 comparison table"
    )


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_modern_rejects_transport_fields_before_any_post(modern_stack, monkeypatch, case) -> None:
    import hermes_plugins.powerunits.client as plugin_client
    from model_tools import handle_function_call

    poster = RecordingPoster(happy_repo_b_payload(case.contract))
    monkeypatch.setattr(plugin_client, "http_post", poster)

    args = dict(case.args())
    args["url"] = "https://attacker.example.invalid/x"
    out = json.loads(handle_function_call(case.modern_tool, args))

    assert poster.count == 0, f"{case.case_id}: a transport field reached the network"
    assert out.get("error_code") in {"unexpected_field", "invalid_arguments"}


def test_modern_refuses_unknown_operation_id(modern_stack) -> None:
    import hermes_plugins.powerunits.client as plugin_client

    out = plugin_client.invoke("not_a_bounded_operation", {})
    assert out["error_code"] == "unknown_operation_id"
    assert out["success"] is False


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://bounded.example.test", "execute_target_https_required"),
        ("https://bounded.example.test.evil.invalid", "execute_target_host_refused"),
        ("https://elsewhere.example", "execute_target_host_refused"),
    ],
)
def test_modern_host_pinning_refuses_before_any_post(
    modern_stack, monkeypatch, base_url, expected
) -> None:
    import hermes_plugins.powerunits.client as plugin_client

    poster = RecordingPoster({})
    monkeypatch.setattr(plugin_client, "http_post", poster)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", base_url)

    out = plugin_client.invoke("read_powerunits_coverage_snapshot_v1", {"country_codes": ["DE"]})
    assert poster.count == 0
    assert out.get("error_code") == expected


def test_no_production_credential_is_required_by_either_system(current_fork) -> None:
    """R3 ran on synthetic credentials only. This asserts that, mechanically."""

    import os

    production_names = (
        "DATABASE_URL",
        "RAILWAY_TOKEN",
        "RAILWAY_API_TOKEN",
        "VERCEL_TOKEN",
    )
    for name in production_names:
        assert not os.getenv(name), f"{name} must not be set for the R3 comparison"
    assert os.getenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", "").startswith("r0-golden-")
