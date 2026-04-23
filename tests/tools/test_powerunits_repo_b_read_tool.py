"""Tests for allowlisted Repo B read tool (GitHub path mocked)."""

from __future__ import annotations

import json
import os

import pytest


@pytest.fixture(autouse=True)
def _clear_repo_b_feature_env():
    """Avoid leaking enabled flag across tests."""
    old = os.environ.get("HERMES_POWERUNITS_REPO_B_READ_ENABLED")
    try:
        os.environ.pop("HERMES_POWERUNITS_REPO_B_READ_ENABLED", None)
        yield
    finally:
        if old is not None:
            os.environ["HERMES_POWERUNITS_REPO_B_READ_ENABLED"] = old
        else:
            os.environ.pop("HERMES_POWERUNITS_REPO_B_READ_ENABLED", None)


def _enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "test-token-for-repo-b-read")


def test_read_allowed_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_repo_b_read_tool as mod

    _enabled_env(monkeypatch)

    def fake_fetch(repo: str, branch: str, api_path: str, token: str) -> str:
        assert "Kiron030" in repo
        assert api_path == "docs/implementation_state.md"
        assert token == "test-token-for-repo-b-read"
        return "implementation body"

    raw = mod.read_powerunits_repo_b_allowlisted(
        "read_repo_b_key",
        key="implementation_state",
        _fetch_raw=fake_fetch,
    )
    data = json.loads(raw)
    assert data["key"] == "implementation_state"
    assert data["content"] == "implementation body"
    assert data["truncated"] is False
    assert data["surface"] == "powerunits_repo_b_read"
    assert data["action"] == "read_repo_b_key"


def test_legacy_read_action_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """Old prompts using action=read still resolve."""
    from tools import powerunits_repo_b_read_tool as mod

    _enabled_env(monkeypatch)
    raw = mod.read_powerunits_repo_b_allowlisted(
        "read",
        key="implementation_state",
        _fetch_raw=lambda *a, **k: "body",
    )
    data = json.loads(raw)
    assert data["action"] == "read_repo_b_key"


def test_unknown_key_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_repo_b_read_tool as mod

    _enabled_env(monkeypatch)
    raw = mod.read_powerunits_repo_b_allowlisted(
        "read_repo_b_key",
        key="totally_unknown_key",
        _fetch_raw=lambda *a, **k: "",
    )
    err = json.loads(raw)
    assert "error" in err
    assert "unknown" in err["error"].lower()


def test_list_repo_b_keys_includes_job_market_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_repo_b_read_tool as mod

    _enabled_env(monkeypatch)
    raw = mod.read_powerunits_repo_b_allowlisted("list_repo_b_keys")
    data = json.loads(raw)
    assert data["surface"] == "powerunits_repo_b_read"
    assert data["key_namespace"] == "repo_b_allowlist_snake_case"
    assert data["action"] == "list_repo_b_keys"
    assert "implementation_state" in data["keys"]
    assert "job_market_feature" in data["keys"]
    assert "job_entsoe_market" in data["keys"]
    assert "adr_010_weather_ingestion_mvp" in data["keys"]
    assert "adr_014_entsoe_generation_outages" in data["keys"]
    assert len(data["keys"]) >= 13
    assert "disambiguation" in data
    assert ".md" in data["disambiguation"]


def test_legacy_list_keys_action_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_repo_b_read_tool as mod

    _enabled_env(monkeypatch)
    raw = mod.read_powerunits_repo_b_allowlisted("list_keys")
    data = json.loads(raw)
    assert data["action"] == "list_repo_b_keys"
    assert "job_market_feature" in data["keys"]


def test_schema_has_no_free_path_parameter() -> None:
    from tools.powerunits_repo_b_read_tool import READ_POWERUNITS_REPO_B_SCHEMA

    props = READ_POWERUNITS_REPO_B_SCHEMA["parameters"]["properties"]
    assert "path" not in props
    assert "repo" not in props
    enum = props["action"]["enum"]
    assert "list_keys" not in enum
    assert "read" not in enum


def test_repo_b_schema_distinct_from_doc_tool_description() -> None:
    from tools.powerunits_docs_tool import READ_POWERUNITS_DOC_SCHEMA
    from tools.powerunits_repo_b_read_tool import READ_POWERUNITS_REPO_B_SCHEMA

    doc_desc = READ_POWERUNITS_DOC_SCHEMA["description"].lower()
    repo_desc = READ_POWERUNITS_REPO_B_SCHEMA["description"].lower()
    assert "read_powerunits_repo_b_allowlisted" in doc_desc
    assert "manifest" in doc_desc
    assert "job_market_feature" in repo_desc
    assert "list_repo_b_keys" in repo_desc or "read_repo_b_key" in repo_desc


def test_first_safe_includes_repo_b_tool_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "tok")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_repo_b_read", "web_tools"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "read_powerunits_repo_b_allowlisted" in names
    assert "web_search" not in names


def test_feature_disabled_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_repo_b_read_tool as mod

    monkeypatch.delenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", raising=False)
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "tok")
    raw = mod.read_powerunits_repo_b_allowlisted(
        "read_repo_b_key",
        key="implementation_state",
        _fetch_raw=lambda *a, **k: "x",
    )
    err = json.loads(raw)
    assert err.get("error_code") == "feature_disabled"
