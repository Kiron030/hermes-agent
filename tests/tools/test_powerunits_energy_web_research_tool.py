"""Tests for research_powerunits_energy_web_v1 (bounded, read-only Tavily wrapper).

No real Tavily API key/network calls are used — the Tavily search/extract
adapter is injected via ``_search_fn`` / ``_extract_fn``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import powerunits_energy_web_research_tool as mod
from tools.registry import registry


def test_gate_off_requires_feature_and_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod._FEATURE_ENV, raising=False)
    monkeypatch.delenv(mod._TAVILY_KEY_ENV, raising=False)
    out = json.loads(mod.research_powerunits_energy_web_v1(query="EU power prices"))
    assert out["success"] is False
    assert out["error_code"] == "feature_disabled"
    assert out["external_web_context"] is True
    note = out["hermes_operator_note_v1"].lower()
    assert "read-only" in note


def test_missing_api_key_fails_closed_even_if_feature_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.delenv(mod._TAVILY_KEY_ENV, raising=False)
    assert mod.check_powerunits_energy_web_research_requirements() is False


def test_empty_query_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")
    out = json.loads(mod.research_powerunits_energy_web_v1(query="   "))
    assert out["success"] is False
    assert out["error_code"] == "invalid_query"


def test_search_only_success_and_topic_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")

    def _search(query: str, max_results: int):
        assert query == "German day-ahead prices"
        assert max_results == 5
        return {
            "results": [
                {"title": "A", "url": "https://a.example.com", "content": "snippet a"},
                {"title": "B", "url": "https://b.example.com", "content": "snippet b"},
            ]
        }

    out = json.loads(
        mod.research_powerunits_energy_web_v1(
            query="German day-ahead prices",
            topic_type="market_news",
            _search_fn=_search,
        )
    )
    assert out["success"] is True
    assert out["external_web_context"] is True
    assert out["topic_type"] == "market_news"
    assert len(out["sources"]) == 2
    assert out["sources"][0]["url"] == "https://a.example.com"
    assert out["extracted"] == []
    assert any("market_features_hourly" in w for w in out["warnings"])
    assert out["caps_applied"]["effective_max_results"] == 5
    assert out["caps_applied"]["effective_extract_top_urls"] == 0

    # Always-present guardrails (independent of topic_type): GEM naming
    # collision + numeric cross-check reminder, in both warnings and the
    # consolidated operator_notice.
    assert any("gem_units" in w.lower() for w in out["warnings"])
    assert any("not authoritative" in w.lower() for w in out["warnings"])
    assert "gem_units" in out["operator_notice"].lower()
    assert "not authoritative" in out["operator_notice"].lower()

    # German Telegram-facing disclaimer is always present and non-empty.
    assert out["disclaimer_de"]
    assert "gem_units" in out["disclaimer_de"].lower()
    assert "tavily" in out["disclaimer_de"].lower()

    # sources_markdown renders each source as a clickable markdown link.
    assert out["sources_markdown"] == (
        "- [A](https://a.example.com)\n- [B](https://b.example.com)"
    )


def test_unknown_topic_type_falls_back_to_general(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")
    out = json.loads(
        mod.research_powerunits_energy_web_v1(
            query="x",
            topic_type="not_a_real_topic",
            _search_fn=lambda q, n: {"results": []},
        )
    )
    assert out["topic_type"] == "general_energy"


def test_max_results_and_extract_top_urls_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")
    captured: dict = {}

    def _search(query: str, max_results: int):
        captured["max_results"] = max_results
        return {"results": [{"title": f"r{i}", "url": f"https://x.example/{i}", "content": ""} for i in range(20)]}

    out = json.loads(
        mod.research_powerunits_energy_web_v1(
            query="x",
            max_results=999,
            extract_top_urls=999,
            _search_fn=_search,
            _extract_fn=lambda urls: {"results": []},
        )
    )
    assert captured["max_results"] == mod._MAX_RESULTS_CAP
    assert len(out["sources"]) == mod._MAX_RESULTS_CAP
    assert out["caps_applied"]["effective_extract_top_urls"] == mod._EXTRACT_TOP_URLS_CAP


def test_extract_top_urls_bounds_and_truncates_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")

    def _search(query: str, max_results: int):
        return {"results": [{"title": "A", "url": "https://a.example.com", "content": "snippet"}]}

    long_content = "x" * (mod._EXTRACT_CONTENT_CHAR_CAP + 500)

    def _extract(urls: list[str]):
        assert urls == ["https://a.example.com"]
        return {"results": [{"url": urls[0], "title": "A", "raw_content": long_content}]}

    out = json.loads(
        mod.research_powerunits_energy_web_v1(
            query="x",
            extract_top_urls=1,
            _search_fn=_search,
            _extract_fn=_extract,
        )
    )
    assert len(out["extracted"]) == 1
    entry = out["extracted"][0]
    assert entry["truncated"] is True
    assert len(entry["content"]) <= mod._EXTRACT_CONTENT_CHAR_CAP + 100


def test_extract_failure_is_reported_as_warning_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")

    def _search(query: str, max_results: int):
        return {"results": [{"title": "A", "url": "https://a.example.com", "content": "snippet"}]}

    def _extract(urls: list[str]):
        raise RuntimeError("boom")

    out = json.loads(
        mod.research_powerunits_energy_web_v1(
            query="x",
            extract_top_urls=1,
            _search_fn=_search,
            _extract_fn=_extract,
        )
    )
    assert out["success"] is True
    assert out["extracted"] == []
    assert any("extraction failed" in w.lower() for w in out["warnings"])


def test_search_backend_error_surfaces_as_typed_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")

    def _search(query: str, max_results: int):
        raise ValueError("TAVILY_API_KEY environment variable not set.")

    out = json.loads(
        mod.research_powerunits_energy_web_v1(query="x", _search_fn=_search)
    )
    assert out["success"] is False
    assert out["error_code"] == "tavily_config_error"


def test_no_results_adds_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")
    out = json.loads(
        mod.research_powerunits_energy_web_v1(query="x", _search_fn=lambda q, n: {"results": []})
    )
    assert out["success"] is True
    assert out["sources"] == []
    assert any("no web results" in w.lower() for w in out["warnings"])
    # Even with zero sources, the disclaimer/notice/markdown fields are present
    # and sources_markdown falls back to an explicit "no sources" placeholder.
    assert out["disclaimer_de"]
    assert out["operator_notice"]
    assert "no web sources" in out["sources_markdown"].lower()


def test_disclaimer_and_operator_notice_present_regardless_of_topic_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")
    for ttype in mod._TOPIC_TYPES:
        out = json.loads(
            mod.research_powerunits_energy_web_v1(
                query="x",
                topic_type=ttype,
                _search_fn=lambda q, n: {"results": []},
            )
        )
        assert out["disclaimer_de"], f"missing disclaimer_de for topic_type={ttype}"
        assert out["operator_notice"], f"missing operator_notice for topic_type={ttype}"
        assert "gem_units" in out["operator_notice"].lower()


def test_schema_declares_topic_type_enum_and_external_web_context() -> None:
    schema = mod.ENERGY_WEB_RESEARCH_SCHEMA_V1
    props = schema["parameters"]["properties"]
    assert set(props["topic_type"]["enum"]) == set(mod._TOPIC_TYPES)
    assert "external_web_context" in schema["description"]
    assert "query" in schema["parameters"]["required"]


def test_schema_description_carries_telegram_overlay_instructions() -> None:
    """The model must see the disclaimer/sources overlay instruction on every
    surface (Telegram included) that reads this tool's schema description —
    not only via a separate, possibly-unread overlay file."""
    from powerunits_telegram_overlays import (
        energy_web_research_telegram_overlay_instructions,
    )

    schema = mod.ENERGY_WEB_RESEARCH_SCHEMA_V1
    instructions = energy_web_research_telegram_overlay_instructions()
    assert instructions in schema["description"]
    assert "disclaimer_de" in instructions
    assert "sources_markdown" in instructions


def test_tool_source_has_no_repo_b_or_db_binding() -> None:
    """Implementation-only: this tool must not call Repo B's internal execute API or any DB."""
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "POWERUNITS_INTERNAL_EXECUTE_BASE_URL" not in src
    assert "DATABASE_URL" not in src
    assert "write_file" not in src
    assert "save_hermes_workspace" not in src


def test_registry_discovery_toolset() -> None:
    ts = registry.get_toolset_for_tool("research_powerunits_energy_web_v1")
    assert ts == "powerunits_energy_web_research"


def test_first_safe_includes_energy_web_research_when_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv(mod._FEATURE_ENV, "1")
    monkeypatch.setenv(mod._TAVILY_KEY_ENV, "tvly-test")

    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "powerunits_energy_web_research"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "research_powerunits_energy_web_v1" in names


def test_telegram_first_safe_base_toolsets_include_energy_web_research() -> None:
    from powerunits_telegram_overlays import TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1

    assert "powerunits_energy_web_research" in TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1


def test_energy_web_research_telegram_overlay_instructions_mention_required_fields() -> None:
    from powerunits_telegram_overlays import (
        ENERGY_WEB_RESEARCH_TELEGRAM_OVERLAY_INSTRUCTIONS_V1,
        energy_web_research_telegram_overlay_instructions,
    )

    text = energy_web_research_telegram_overlay_instructions()
    assert text == ENERGY_WEB_RESEARCH_TELEGRAM_OVERLAY_INSTRUCTIONS_V1
    for required in ("disclaimer_de", "sources_markdown", "operator_notice"):
        assert required in text
    assert "always" in text.lower()
