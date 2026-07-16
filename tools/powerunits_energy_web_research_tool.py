#!/usr/bin/env python3
"""
Powerunits **energy-scoped Tavily web research** (read-only, bounded, `v1`).

Thin wrapper around the existing Tavily search/extract adapter
(``plugins.web.tavily.provider._tavily_request``) with a Powerunits-specific
envelope: an explicit ``external_web_context: true`` flag, a bounded
``sources`` list, a ``topic_type``-driven guardrail note in ``warnings``
(so the model does not confuse live web commentary with Repo B's own
ENTSO-E / ERA5 / GEM data), and hard caps on result count and optional
top-URL content extraction.

This is **not** a replacement for the generic ``web_search`` / ``web_extract``
tools (toolset ``web``) — those remain the right choice for general-purpose
browsing. Use this tool when the operator explicitly wants **energy-market /
Powerunits-relevant** external web context with the topic-aware guardrail
note attached, and does not need domain-agnostic scraping.

No Powerunits HTTP call, no Repo B access, no jobs, no ingestion, no writes.
Only outbound call is Tavily's own API (search, and optionally extract on a
handful of the search's own result URLs — never arbitrary caller-supplied
URLs).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED"
_TAVILY_KEY_ENV = "TAVILY_API_KEY"
_SURFACE = "powerunits_energy_web_research_v1"

_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_CAP = 10
_DEFAULT_EXTRACT_TOP_URLS = 0
_EXTRACT_TOP_URLS_CAP = 3
_MAX_QUERY_CHARS = 400
_EXTRACT_CONTENT_CHAR_CAP = 3000

_DEFAULT_TOPIC_TYPE = "general_energy"

# Powerunits-specific guardrail note per topic_type. This is the actual
# value-add over the generic web_search/web_extract tools: a short, explicit
# reminder of what this external web context is (and is not) relative to
# Repo B's own data layers, tailored to the kind of question being asked.
_TOPIC_GUARDRAILS: dict[str, str] = {
    "market_news": (
        "External web market commentary — not Repo B market_features_hourly / "
        "ENTSO-E data. Cross-check numeric price or demand claims against a "
        "bounded ENTSO-E/BZN tool before quoting figures to the operator."
    ),
    "regulatory_policy": (
        "Regulatory/policy content is jurisdiction- and date-sensitive. Treat "
        "as a starting point only; verify against primary official sources "
        "(EU/national regulator, TSO) before any operator-facing claim."
    ),
    "asset_project": (
        "Asset/project status from the web is not cross-checked against Repo "
        "B's GEM asset layer (gem_units). Treat as supplementary context, not "
        "a confirmed plant record."
    ),
    "technology_grid": (
        "General grid/technology web content — not validated against Repo "
        "B's own outage, weather, or market pipelines."
    ),
    "general_energy": (
        "General external web search context, not sourced from Powerunits' "
        "own data pipeline. Treat as background, not ground truth."
    ),
}

_TOPIC_TYPES: tuple[str, ...] = tuple(_TOPIC_GUARDRAILS.keys())

_HERMES_NOTE_V1 = (
    "Hermes: read-only Tavily web research, energy-scoped envelope only. No "
    "Powerunits HTTP call, no Repo B access, no jobs, no ingestion, no "
    "writes. external_web_context is always true on this tool's output."
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_energy_web_research_requirements() -> bool:
    if not _truthy_env(_FEATURE_ENV):
        return False
    if not (os.getenv(_TAVILY_KEY_ENV) or "").strip():
        return False
    return True


def _default_tavily_search(query: str, max_results: int) -> dict[str, Any]:
    from plugins.web.tavily.provider import _tavily_request

    return _tavily_request(
        "search",
        {
            "query": query,
            "max_results": max_results,
            "include_raw_content": False,
            "include_images": False,
        },
    )


def _default_tavily_extract(urls: list[str]) -> dict[str, Any]:
    from plugins.web.tavily.provider import _tavily_request

    return _tavily_request(
        "extract",
        {
            "urls": urls,
            "include_images": False,
        },
    )


def _clamp_int(raw: Any, *, default: int, cap: int, floor: int = 0) -> int:
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(floor, min(value, cap))


def _truncate(text: str, cap: int) -> tuple[str, bool]:
    if not text or len(text) <= cap:
        return text or "", False
    return text[:cap] + "\n\n[... truncated, see live source URL for full content ...]", True


def research_powerunits_energy_web_v1(
    *,
    query: str = "",
    topic_type: str = _DEFAULT_TOPIC_TYPE,
    max_results: Any = None,
    extract_top_urls: Any = None,
    _search_fn: Callable[[str, int], dict[str, Any]] | None = None,
    _extract_fn: Callable[[list[str]], dict[str, Any]] | None = None,
) -> str:
    """Return JSON string envelope. Always includes ``hermes_operator_note_v1``."""

    search_fn = _search_fn or _default_tavily_search
    extract_fn = _extract_fn or _default_tavily_extract

    if not check_powerunits_energy_web_research_requirements():
        return json.dumps(
            {
                "surface": _SURFACE,
                "external_web_context": True,
                "success": False,
                "error_code": "feature_disabled",
                "message": f"{_FEATURE_ENV} must be truthy and {_TAVILY_KEY_ENV} must be set.",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    q = (query or "").strip()
    if not q:
        return json.dumps(
            {
                "surface": _SURFACE,
                "external_web_context": True,
                "success": False,
                "error_code": "invalid_query",
                "message": "query must be a non-empty string.",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )
    if len(q) > _MAX_QUERY_CHARS:
        q = q[:_MAX_QUERY_CHARS]

    ttype = (topic_type or _DEFAULT_TOPIC_TYPE).strip().lower()
    if ttype not in _TOPIC_GUARDRAILS:
        ttype = _DEFAULT_TOPIC_TYPE

    effective_max_results = _clamp_int(
        max_results, default=_DEFAULT_MAX_RESULTS, cap=_MAX_RESULTS_CAP, floor=1
    )
    effective_extract_top_urls = _clamp_int(
        extract_top_urls, default=_DEFAULT_EXTRACT_TOP_URLS, cap=_EXTRACT_TOP_URLS_CAP, floor=0
    )

    warnings: list[str] = [_TOPIC_GUARDRAILS[ttype]]

    try:
        raw_search = search_fn(q, effective_max_results)
    except ValueError as exc:
        return json.dumps(
            {
                "surface": _SURFACE,
                "external_web_context": True,
                "success": False,
                "error_code": "tavily_config_error",
                "message": str(exc),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001 — including httpx errors
        logger.warning("energy_web_research: Tavily search failed: %s", exc)
        return json.dumps(
            {
                "surface": _SURFACE,
                "external_web_context": True,
                "success": False,
                "error_code": "tavily_search_failed",
                "message": f"Tavily search failed: {exc}",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    raw_results = raw_search.get("results", []) if isinstance(raw_search, dict) else []
    sources: list[dict[str, Any]] = []
    for i, r in enumerate(raw_results[:effective_max_results]):
        sources.append(
            {
                "position": i + 1,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "published_date": r.get("published_date") or None,
            }
        )

    if not sources:
        warnings.append("No web results were returned for this query.")

    extracted: list[dict[str, Any]] = []
    if effective_extract_top_urls > 0 and sources:
        target_urls = [
            s["url"] for s in sources[:effective_extract_top_urls] if s.get("url", "").startswith(("http://", "https://"))
        ]
        if target_urls:
            try:
                raw_extract = extract_fn(target_urls)
                extract_results = raw_extract.get("results", []) if isinstance(raw_extract, dict) else []
                by_url = {r.get("url", ""): r for r in extract_results}
                for url in target_urls:
                    r = by_url.get(url)
                    if r is None:
                        extracted.append({"url": url, "title": "", "content": "", "error": "not returned by extractor"})
                        continue
                    content, truncated = _truncate(
                        r.get("raw_content", "") or r.get("content", ""), _EXTRACT_CONTENT_CHAR_CAP
                    )
                    extracted.append(
                        {
                            "url": url,
                            "title": r.get("title", ""),
                            "content": content,
                            "truncated": truncated,
                        }
                    )
                failed = (raw_extract.get("failed_results", []) if isinstance(raw_extract, dict) else [])
                if failed:
                    warnings.append(f"{len(failed)} of {len(target_urls)} extract target(s) failed.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("energy_web_research: Tavily extract failed: %s", exc)
                warnings.append(f"Content extraction failed: {exc}")

    response = {
        "surface": _SURFACE,
        "external_web_context": True,
        "success": True,
        "query": q,
        "topic_type": ttype,
        "sources": sources,
        "extracted": extracted,
        "warnings": warnings,
        "caps_applied": {
            "max_results_cap": _MAX_RESULTS_CAP,
            "extract_top_urls_cap": _EXTRACT_TOP_URLS_CAP,
            "content_char_cap": _EXTRACT_CONTENT_CHAR_CAP,
            "effective_max_results": effective_max_results,
            "effective_extract_top_urls": effective_extract_top_urls,
        },
        "hermes_operator_note_v1": _HERMES_NOTE_V1,
    }
    return json.dumps(response, ensure_ascii=False)


ENERGY_WEB_RESEARCH_SCHEMA_V1 = {
    "name": "research_powerunits_energy_web_v1",
    "description": (
        "**Energy-scoped external web research (Tavily, read-only, bounded).** "
        "Not Repo B data — always returns `external_web_context: true`. Adds a "
        "`topic_type`-driven guardrail note to `warnings` so results are not "
        "confused with Repo B's own ENTSO-E/ERA5/GEM data. "
        "**Different tool:** use plain `web_search` / `web_extract` (toolset `web`) "
        "for general-purpose, non-energy-scoped browsing — this tool adds no value "
        "there. Use **this tool** when the operator wants energy/Powerunits-relevant "
        "web context with the topic guardrail attached. "
        "Optionally extracts bounded content from the top N of its own search results "
        "(never arbitrary caller-supplied URLs). "
        f"Gate **{_FEATURE_ENV}** plus **{_TAVILY_KEY_ENV}**. No jobs, no ingestion, no writes, "
        "no Repo B HTTP call."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": f"Search query (max {_MAX_QUERY_CHARS} chars; longer queries are truncated).",
            },
            "topic_type": {
                "type": "string",
                "enum": list(_TOPIC_TYPES),
                "description": (
                    "Energy-domain topic category — selects the guardrail note attached to "
                    "`warnings`. Defaults to 'general_energy' when omitted or unrecognized."
                ),
                "default": _DEFAULT_TOPIC_TYPE,
            },
            "max_results": {
                "type": "integer",
                "description": f"Max search results. Default {_DEFAULT_MAX_RESULTS}, capped at {_MAX_RESULTS_CAP}.",
                "minimum": 1,
                "maximum": _MAX_RESULTS_CAP,
                "default": _DEFAULT_MAX_RESULTS,
            },
            "extract_top_urls": {
                "type": "integer",
                "description": (
                    "Optional: extract bounded content (capped at "
                    f"{_EXTRACT_CONTENT_CHAR_CAP} chars each) from the top N of this call's own "
                    f"search results. Default 0 (search only), capped at {_EXTRACT_TOP_URLS_CAP}."
                ),
                "minimum": 0,
                "maximum": _EXTRACT_TOP_URLS_CAP,
                "default": _DEFAULT_EXTRACT_TOP_URLS,
            },
        },
        "required": ["query"],
    },
}


from tools.registry import registry

registry.register(
    name="research_powerunits_energy_web_v1",
    toolset="powerunits_energy_web_research",
    schema=ENERGY_WEB_RESEARCH_SCHEMA_V1,
    handler=lambda args, **kw: research_powerunits_energy_web_v1(
        query=str((args or {}).get("query", "") or ""),
        topic_type=str((args or {}).get("topic_type", "") or _DEFAULT_TOPIC_TYPE),
        max_results=(args or {}).get("max_results", _DEFAULT_MAX_RESULTS),
        extract_top_urls=(args or {}).get("extract_top_urls", _DEFAULT_EXTRACT_TOP_URLS),
    ),
    check_fn=check_powerunits_energy_web_research_requirements,
    requires_env=[_FEATURE_ENV, _TAVILY_KEY_ENV],
    emoji="🔎",
    max_result_size_chars=100_000,
)
