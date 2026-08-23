"""Correctness: same operator intent, both systems, one dispatch path.

Both sides go through ``model_tools.handle_function_call`` so the comparison is
of the answer the model would receive, not of internal call order. HTTP is
mocked on both sides with the same recorder and the same canned Repo-B payload.
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest

from tests.powerunits_golden.contracts import _PRE_HTTP_REFUSALS, happy_repo_b_payload
from tests.powerunits_golden.env import SYNTHETIC_EXECUTE_BASE_URL, SYNTHETIC_EXECUTE_HOST
from tests.powerunits_golden.http import RecordingPoster, correlation_from_headers
from tests.r3_shadow_comparison.corpus import BOUNDED_CASES, CORPUS_BY_ID, CorpusCase

CASE_IDS = [case.case_id for case in BOUNDED_CASES]


def _patch_fork_http(monkeypatch: pytest.MonkeyPatch, case: CorpusCase, poster: RecordingPoster) -> None:
    module = importlib.import_module(case.contract.module)
    monkeypatch.setattr(module, "_default_http_post", poster)


def _patch_modern_http(monkeypatch: pytest.MonkeyPatch, poster: RecordingPoster) -> None:
    import hermes_plugins.powerunits.client as plugin_client

    monkeypatch.setattr(plugin_client, "http_post", poster)


def _dispatch(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    from model_tools import handle_function_call

    return json.loads(handle_function_call(tool_name, args))


def _assert_answers_the_intent(case: CorpusCase, out: dict[str, Any], poster: RecordingPoster) -> None:
    assert poster.count == 1, f"{case.case_id}: expected exactly one bounded POST"
    call = poster.calls[0]
    assert call["scheme"] == "https"
    assert call["hostname"] == SYNTHETIC_EXECUTE_HOST
    assert call["url"].startswith(SYNTHETIC_EXECUTE_BASE_URL)
    assert case.contract.route in call["url"]
    assert correlation_from_headers(call["headers"])
    assert out.get("error_code") not in _PRE_HTTP_REFUSALS
    for field in case.contract.happy_fields:
        assert field in out, f"{case.case_id}: missing R0 happy field {field}"


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_current_fork_answers_the_corpus(current_fork, monkeypatch, case: CorpusCase) -> None:
    poster = RecordingPoster(happy_repo_b_payload(case.contract))
    _patch_fork_http(monkeypatch, case, poster)
    out = _dispatch(case.current_fork_tool, case.args())
    _assert_answers_the_intent(case, out, poster)


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_modern_answers_the_corpus(modern_stack, monkeypatch, case: CorpusCase) -> None:
    poster = RecordingPoster(happy_repo_b_payload(case.contract))
    _patch_modern_http(monkeypatch, poster)
    out = _dispatch(case.modern_tool, case.args())
    _assert_answers_the_intent(case, out, poster)


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_both_systems_post_the_same_route_and_body(
    monkeypatch, case: CorpusCase, tmp_path
) -> None:
    """The wire request is the comparable artifact; prose is not."""

    from tests.r3_shadow_comparison.wire import (
        capture_current_fork_request,
        capture_modern_request,
    )

    # One argument dict, two systems, so any divergence is the architecture.
    fork_call, _ = capture_current_fork_request(case, tmp_path / ".hermes-fork-wire", monkeypatch)
    modern_call = capture_modern_request(case, tmp_path, monkeypatch)

    assert modern_call["path"] == fork_call["path"], case.case_id
    assert modern_call["hostname"] == fork_call["hostname"]
    assert modern_call["scheme"] == fork_call["scheme"]
    assert set(modern_call["json_body"]) == set(fork_call["json_body"]), (
        f"{case.case_id}: request body keys diverge "
        f"(fork={sorted(fork_call['json_body'])}, modern={sorted(modern_call['json_body'])})"
    )
    assert modern_call["json_body"] == fork_call["json_body"], case.case_id


@pytest.mark.parametrize("case", BOUNDED_CASES, ids=CASE_IDS)
def test_gate_off_fails_identically_on_both(current_fork, monkeypatch, case: CorpusCase, tmp_path) -> None:
    from tools.registry import invalidate_check_fn_cache

    poster = RecordingPoster(happy_repo_b_payload(case.contract))
    _patch_fork_http(monkeypatch, case, poster)
    for flag in case.contract.gate_envs:
        monkeypatch.delenv(flag, raising=False)
    invalidate_check_fn_cache()
    fork_out = _dispatch(case.current_fork_tool, case.args())

    assert poster.count == 0
    assert fork_out.get("error_code") == "feature_disabled"


def test_methodology_case_has_no_modern_equivalent() -> None:
    """Recorded honestly: the modern proof does not cover every corpus intent."""

    case = CORPUS_BY_ID["methodology_doc"]
    assert case.modern_tool is None
    assert case.modern_gap

    from tools.registry import registry

    assert registry.get_entry(case.current_fork_tool) is not None, (
        "the current fork must still own the methodology path this case measures"
    )
