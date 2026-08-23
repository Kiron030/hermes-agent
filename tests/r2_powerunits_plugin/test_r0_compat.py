"""Semantic field compatibility against the R0 Golden contracts."""

from __future__ import annotations

import json

import pytest

from tests.powerunits_golden.contracts import (
    _PRE_HTTP_REFUSALS,
    args_for,
    contract_by_operation,
    happy_repo_b_payload,
)
from tests.powerunits_golden.env import FIXED_CORRELATION_ID, SYNTHETIC_EXECUTE_BASE_URL
from tests.powerunits_golden.http import RecordingPoster, correlation_from_headers
from tests.r2_powerunits_plugin.conftest import PLUGIN_TOOLS

SELECTED = tuple(PLUGIN_TOOLS)


def _patch_client(monkeypatch, poster: RecordingPoster):
    import hermes_plugins.powerunits.client as plugin_client

    monkeypatch.setattr(plugin_client, "http_post", poster)


@pytest.mark.parametrize("operation", SELECTED)
def test_plugin_happy_fields_match_r0(loaded_plugin, monkeypatch, operation) -> None:
    from model_tools import handle_function_call

    contract = contract_by_operation()[operation]
    poster = RecordingPoster(happy_repo_b_payload(contract))
    _patch_client(monkeypatch, poster)
    out = json.loads(handle_function_call(operation, args_for(contract)))

    assert poster.count == 1
    first = poster.calls[0]
    assert first["url"].startswith(SYNTHETIC_EXECUTE_BASE_URL)
    assert contract.route in first["url"]
    cid = correlation_from_headers(first["headers"]) or out.get("correlation_id")
    assert cid
    if out.get("correlation_id"):
        assert out["correlation_id"] in {FIXED_CORRELATION_ID, cid}
    assert out.get("error_code") not in _PRE_HTTP_REFUSALS
    for field in contract.happy_fields:
        assert field in out, f"{operation} missing R0 happy field {field}"
    for field in contract.provenance_fields:
        if field in happy_repo_b_payload(contract):
            assert field in out
    assert any(
        key in out
        for key in (
            "hermes_operator_note_v1",
            "hermes_statement",
            "http_status",
            "http_status_from_repo_b",
        )
    )
    assert not {"url", "host", "base_url", "path"} & set(first["json_body"])


@pytest.mark.parametrize("operation", SELECTED)
def test_plugin_feature_disabled_matches_r0(loaded_plugin, monkeypatch, operation) -> None:
    from model_tools import handle_function_call
    from tools.registry import invalidate_check_fn_cache

    contract = contract_by_operation()[operation]
    poster = RecordingPoster(happy_repo_b_payload(contract))
    _patch_client(monkeypatch, poster)
    for flag in contract.gate_envs:
        monkeypatch.delenv(flag, raising=False)
    invalidate_check_fn_cache()
    out = json.loads(handle_function_call(operation, args_for(contract)))
    assert poster.count == 0
    assert out.get("error_code") == "feature_disabled"


def test_schema_and_response_diffs_are_recorded() -> None:
    """Documented, expected non-regressions — not a frozen wrapper clone."""

    diffs = {
        "read_powerunits_coverage_snapshot_v1": {
            "old_wrapper": "tools.powerunits_bounded_coverage_snapshot_tool",
            "new_plugin_tool": "read_powerunits_coverage_snapshot_v1",
            "schema_diff": "additionalProperties=false; no transport fields (unchanged intent)",
            "response_field_diff": "adds effect_class=READ; chat_summary still present",
        },
        "inventory_powerunits_bounded_coverage_v1": {
            "old_wrapper": "tools.powerunits_bounded_coverage_inventory_tool",
            "new_plugin_tool": "inventory_powerunits_bounded_coverage_v1",
            "schema_diff": "removed export_format / workspace CSV persist (write-adjacent)",
            "response_field_diff": "keeps chat_summary + hermes_statement; no csv_export",
        },
        "read_powerunits_entsoe_bzn_price_readiness_v1": {
            "old_wrapper": "tools.powerunits_entsoe_bzn_price_readiness_tool",
            "new_plugin_tool": "read_powerunits_entsoe_bzn_price_readiness_v1",
            "schema_diff": "additionalProperties=false",
            "response_field_diff": "correlation_id + hermes_operator_note_v1 preserved",
        },
        "readiness_powerunits_option_d_bounded_window": {
            "old_wrapper": "tools.powerunits_option_d_readiness_tool",
            "new_plugin_tool": "readiness_powerunits_option_d_bounded_window",
            "schema_diff": "no local PL/24h domain authority; empty-field fail-early only",
            "response_field_diff": "correlation_id preserved; Repo B remains authoritative",
        },
    }
    assert set(diffs) == set(SELECTED)
    for row in diffs.values():
        assert "old_wrapper" in row
        assert "new_plugin_tool" in row
