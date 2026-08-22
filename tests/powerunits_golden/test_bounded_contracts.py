"""Task C — deterministic happy/negative contracts for every bounded HTTP operation."""

from __future__ import annotations

import importlib
import json

import pytest

from tests.powerunits_golden.contracts import (
    BOUNDED_HTTP_CONTRACTS,
    _PRE_HTTP_REFUSALS,
    BoundedHttpContract,
    args_for,
    happy_repo_b_payload,
    negative_args,
)
from tests.powerunits_golden.env import (
    FIXED_CORRELATION_ID,
    SYNTHETIC_EXECUTE_BASE_URL,
    SYNTHETIC_EXECUTE_HOST,
    SYNTHETIC_EXECUTE_SECRET,
    apply_operator_ready_env,
)
from tests.powerunits_golden.http import RecordingPoster, correlation_from_headers
from tests.tools.powerunits_s0b_approval_support import grant_powerunits_write_approvals


def _enable_contract(monkeypatch: pytest.MonkeyPatch, contract: BoundedHttpContract) -> None:
    apply_operator_ready_env(monkeypatch, tier=0)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_BASE_URL", SYNTHETIC_EXECUTE_BASE_URL)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS", SYNTHETIC_EXECUTE_HOST)
    monkeypatch.setenv("POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE", "enforce")
    monkeypatch.setenv("POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET", SYNTHETIC_EXECUTE_SECRET)
    for flag in contract.gate_envs:
        monkeypatch.setenv(flag, "1")
    if contract.is_write:
        grant_powerunits_write_approvals(monkeypatch)


def _call(contract: BoundedHttpContract, kwargs: dict, poster: RecordingPoster | None) -> dict:
    mod = importlib.import_module(contract.module)
    fn = getattr(mod, contract.function)
    if poster is None:
        raw = fn(**kwargs)
    else:
        raw = fn(**kwargs, _http_post=poster)
    return json.loads(raw)


@pytest.mark.parametrize("contract", BOUNDED_HTTP_CONTRACTS, ids=lambda c: c.operation)
def test_bounded_happy_path_contract(
    monkeypatch: pytest.MonkeyPatch,
    contract: BoundedHttpContract,
) -> None:
    _enable_contract(monkeypatch, contract)
    poster = RecordingPoster(happy_repo_b_payload(contract))
    out = _call(contract, args_for(contract), poster)

    assert poster.count >= 1
    first = poster.calls[0]
    assert first["scheme"] == "https"
    assert first["hostname"] == SYNTHETIC_EXECUTE_HOST
    assert first["path"] == contract.route or first["path"].endswith(contract.route.split("/")[-1])
    assert first["url"].startswith(SYNTHETIC_EXECUTE_BASE_URL)
    assert contract.route in first["url"]
    cid = correlation_from_headers(first["headers"]) or out.get("correlation_id")
    assert cid
    if out.get("correlation_id"):
        assert out["correlation_id"] in {FIXED_CORRELATION_ID, cid}
    assert out.get("error_code") not in _PRE_HTTP_REFUSALS
    for field in contract.happy_fields:
        assert field in out, f"{contract.operation} missing happy field {field}"
    for field in contract.provenance_fields:
        if field in out:
            assert out[field] not in (None, "")
    assert any(
        key in out
        for key in (
            "hermes_operator_note_v1",
            "hermes_statement",
            "http_status",
            "http_status_from_repo_b",
            "http_ok",
            "windows_attempted",
        )
    )
    body_keys = sorted(first["json_body"])
    assert body_keys, f"{contract.operation} posted an empty JSON body"
    assert not {"url", "host", "base_url", "path"} & set(body_keys)


@pytest.mark.parametrize("contract", BOUNDED_HTTP_CONTRACTS, ids=lambda c: c.operation)
def test_bounded_negative_path_contract(
    monkeypatch: pytest.MonkeyPatch,
    contract: BoundedHttpContract,
) -> None:
    _enable_contract(monkeypatch, contract)
    poster = RecordingPoster(happy_repo_b_payload(contract))
    if contract.negative == "feature_disabled":
        for flag in contract.gate_envs:
            monkeypatch.delenv(flag, raising=False)
    out = _call(contract, negative_args(contract), poster)
    assert poster.count == 0
    assert out.get("success") is False or out.get("error_code")
    if contract.negative == "feature_disabled":
        assert out.get("error_code") == "feature_disabled"
    else:
        assert out.get("error_code") == contract.negative


def test_inventory_covers_every_http_post_wrapper() -> None:
    names = {item.operation for item in BOUNDED_HTTP_CONTRACTS}
    assert len(names) == len(BOUNDED_HTTP_CONTRACTS)
    assert "read_powerunits_coverage_snapshot_v1" in names
    assert "campaign_powerunits_entsoe_market_bounded_de" in names
