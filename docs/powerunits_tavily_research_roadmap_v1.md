# Powerunits Tavily research roadmap v1

**Status: implemented (core slice), Stage 1 (Trusted Analyst) — read-only.** This doc records the assessment of the proposed Tavily-integration prompt and the resulting Stage 2 implementation slice: tool `research_powerunits_energy_web_v1` in toolset `powerunits_energy_web_research`.

---

## Part A — Assessment: existing web/Tavily surface before this change

**Repo A already has a full, working Tavily backend** — this was not a greenfield integration.

| Surface | What exists today |
|---|---|
| `tools/web_tools.py` | `web_search_tool` / `web_extract_tool` — generic multi-backend dispatcher (Exa, Firecrawl, Parallel, Tavily, SearXNG, Brave-free, ddgs, xAI). Backend selected via `web.backend` / `web.search_backend` / `web.extract_backend` in `config.yaml`, or auto-detected from whichever API key is set. |
| `plugins/web/tavily/provider.py` | `TavilyWebSearchProvider` — the actual Tavily HTTP client (`_tavily_request`, `_normalize_tavily_search_results`, `_normalize_tavily_documents`). Registered via `agent.web_search_registry`. This is the adapter this roadmap's new tool reuses directly. |
| Toolsets `web` / `search` | `web_search` + `web_extract` (`web`), `web_search` only (`search`). Both already included in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` (`powerunits_telegram_overlays.py`) — i.e. **generic Tavily-backed web search is already live on the Trusted Analyst / Telegram surface today**, gated only by whichever backend env var is set (`TAVILY_API_KEY` among them). |
| `TAVILY_API_KEY` usage | Already read in `plugins/web/tavily/provider.py`, re-exported through `tools/web_tools.py` for backward compat, and listed in `_web_requires_env()` tool metadata. No new secret is introduced by this roadmap. |
| Tests | `tests/tools/test_web_tools_tavily.py`, `tests/tools/test_web_providers.py`, `tests/plugins/web/test_web_search_provider_plugins.py` already cover the Tavily adapter's request/normalize paths with mocks — no real network calls in CI today, and this pattern is preserved for the new tool. |
| Powerunits bounded-tool pattern | ~40 `powerunits_*` tools in `tools/`, each a single bounded HTTP POST to Repo B's internal execute API (`POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`), gated by a per-tool `HERMES_POWERUNITS_<X>_ENABLED` flag, registered in `toolsets.py`, and (for Telegram) listed in `powerunits_telegram_overlays.TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`. |

### Overlap verdict

`research_powerunits_energy_web_v1` (this roadmap's tool) **does not duplicate** `web_search` / `web_extract`. It **reuses** the same underlying Tavily adapter (`plugins.web.tavily.provider._tavily_request`) rather than reimplementing an HTTP client, and adds a **Powerunits-specific envelope** on top:

- `external_web_context: true` — an explicit, always-present flag distinguishing this tool's output from Repo B's own data.
- `topic_type` enum (`market_news`, `regulatory_policy`, `asset_project`, `technology_grid`, `general_energy`) — attaches a guardrail note to `warnings` reminding the model what this external content is (and is not) relative to Repo B's ENTSO-E/ERA5/GEM layers.
- Hard caps (`max_results` ≤ 10, `extract_top_urls` ≤ 3, extracted content ≤ 3000 chars/URL) tighter than the generic `web_search`/`web_extract` defaults, and a bounded `caps_applied` block in every response.
- `extract_top_urls` only ever extracts from the **tool's own search results**, never arbitrary caller-supplied URLs — narrower attack surface than `web_extract`.
- Its own feature gate (`HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED`), independent of whether the generic `web`/`search` toolsets are enabled, so Powerunits-scoped research can be toggled without touching the general-purpose web toolset.

**Conclusion: complementary, not redundant.** The generic `web`/`search` toolsets remain the right choice for non-energy-scoped browsing (and stay unchanged). This tool is a narrow, opt-in overlay for when the operator explicitly wants energy/Powerunits-relevant web context with the topic guardrail attached. If, after live use, the guardrail note turns out to add negligible value over prompting the model directly, the recommendation would be to **retire this tool and rely on `web_search`/`web_extract` plus a system-prompt reminder** rather than keep two near-identical surfaces — that reassessment is listed under Deferred below.

### AGENTS.md file-limit note

This implementation touches **6 files**, one over the 3–5 guideline in `AGENTS.md`. Rationale recorded here per that rule's own escape hatch ("if more needed, implement core slice and list deferred"): a new bounded tool inherently needs (1) the tool implementation, (2) mocked tests, (3) `toolsets.py` registration, (4) `powerunits_telegram_overlays.py` first_safe wiring (so it's actually reachable on the live Telegram surface, not just registered), (5) `ACCESS_MATRIX.md` (per AGENTS.md's own documentation discipline for new Powerunits surfaces), and (6) this roadmap doc. No files outside this list were touched; no unrelated refactors were made.

---

## Part B — Tool contract (`research_powerunits_energy_web_v1`)

| Item | Value |
|---|---|
| Tool name | `research_powerunits_energy_web_v1` |
| Toolset | `powerunits_energy_web_research` |
| File | `tools/powerunits_energy_web_research_tool.py` |
| Feature gate | `HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED` (truthy) |
| Credential | `TAVILY_API_KEY` (existing var — reused, not new) |
| Outbound call | Tavily `/search`, optionally Tavily `/extract` on the search's own top-N result URLs |
| Repo B / DB | None. No HTTP to `POWERUNITS_INTERNAL_EXECUTE_BASE_URL`, no SQL, no Timescale. |
| Jobs / writes | None. Read-only, stateless, no workspace persistence. |

### Parameters

| Param | Type | Default | Cap | Notes |
|---|---|---|---|---|
| `query` | string | — (required) | 400 chars | Truncated, not rejected, if longer. |
| `topic_type` | enum | `general_energy` | — | `market_news`, `regulatory_policy`, `asset_project`, `technology_grid`, `general_energy`. Unknown values fall back to `general_energy`. |
| `max_results` | integer | 5 | 10 | Clamped, not rejected. |
| `extract_top_urls` | integer | 0 | 3 | Clamped. Extracts from this call's own top search results only. |

### Response envelope (always present)

`surface`, `external_web_context` (always `true`), `success`, `hermes_operator_note_v1`. On success additionally: `query`, `topic_type`, `sources[]` (`position`, `title`, `url`, `snippet`, `published_date`), `extracted[]` (`url`, `title`, `content`, `truncated`), `warnings[]` (always includes the topic guardrail note), `caps_applied`. On failure: `error_code` (`feature_disabled`, `invalid_query`, `tavily_config_error`, `tavily_search_failed`) and `message`.

---

## Part C — Guardrails and boundaries (explicit)

- **Read-only.** No DB writes, no Repo B mutation, no job triggers, no execute paths — matches every other Powerunits bounded tool's contract.
- **No secrets in git.** `TAVILY_API_KEY` is read from env only, same as the existing `web_tools.py` path; nothing new is written to `.env.example` beyond what already documents Tavily.
- **Bounded egress.** `extract_top_urls` never accepts caller-supplied URLs — only URLs the tool's own Tavily search call just returned — so it cannot be used as a generic SSRF-adjacent fetch primitive the way `web_extract` (by design) can for arbitrary URLs.
- **Fail-closed.** Missing feature flag or missing `TAVILY_API_KEY` → `feature_disabled`, no outbound call attempted.
- **No API contract freeze concerns.** This tool is internal (Telegram/Trusted-Analyst tool-calling surface), not part of the public Mapbox-facing FastAPI contract governed by API Contract Freeze Mode — that constraint does not apply here.

---

## Part D — Rollout / gating

1. **Off by default.** `HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED` unset ⇒ tool unavailable even if `TAVILY_API_KEY` is set for the generic web toolset.
2. **Toolset registered** in `toolsets.py` (`powerunits_energy_web_research`) and added to `powerunits_telegram_overlays.TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` (immediately after `vision`, alongside the other Hermes-core read toolsets) — this is the single source of truth consumed by `gateway/run.py::_powerunits_allowed_telegram_toolsets()`, `model_tools.py`'s hard-cap allowlist sync, and `docker/apply_powerunits_runtime_policy.py`'s `ALLOWED_TELEGRAM_TOOLSETS`. No separate edits were needed in those three files — confirmed by reading their source before editing.
3. **`ACCESS_MATRIX.md`** updated with one row describing the gate and boundaries, next to the other "Allowed only when gated" bounded-tool rows.
4. Enabling on Railway: set both `HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED=1` and `TAVILY_API_KEY=...` on the Hermes service; no other infra change required.

---

## Part E — Testing

`tests/tools/test_powerunits_energy_web_research_tool.py` — fully mocked (`_search_fn` / `_extract_fn` injection points on the tool function itself, mirroring the `_http_post` injection pattern used by `tools/powerunits_entsoe_bzn_prices_tool.py`). No real Tavily network calls, no real API key, safe for CI. Covers: gate-off, missing-key, empty query, happy path + topic guardrail text, unknown topic fallback, cap clamping (both `max_results` and `extract_top_urls`), content truncation, extractor failure (non-fatal, surfaces as a warning), search backend failure (typed error), empty-results warning, schema shape, absence of any Repo B/DB binding in the implementation, registry discovery, and presence in the Telegram first_safe base toolset list.

Run: `pytest tests/tools/test_powerunits_energy_web_research_tool.py -v`

---

## Changelog — smoke-test refinements (post-#55)

Live Telegram smoke-testing of the Stage 2 slice surfaced four gaps, all addressed in this follow-up pass (no behavioral change to `success`/`error_code`/`sources`/`extracted`/`caps_applied` — additive only):

- **Disclaimer visibility.** The external-web disclaimer lived only in `hermes_operator_note_v1` (Hermes-internal, English) and was easy for the model to drop from the Telegram reply. Added `operator_notice` (consolidated, always present on success) and `disclaimer_de` (short, German, Telegram-facing, meant to be shown verbatim) to the response envelope, plus a new `energy_web_research_telegram_overlay_instructions()` constant in `powerunits_telegram_overlays.py` that is folded into `ENERGY_WEB_RESEARCH_SCHEMA_V1`'s own description, so the "always surface the disclaimer + sources" instruction reaches the model on every surface the tool is registered on, Telegram included.
- **Clickable sources.** Added `sources_markdown` — a ready-to-paste `- [Title](url)` block (falls back to an explicit "no sources" placeholder when `sources` is empty) — so the model does not have to hand-format Telegram markdown from the `sources` array itself.
- **GEM naming confusion.** Operators conflated web-branded "GEM" tools (e.g. Global Energy Monitor's "GEM Energy Analytics") with Repo B's own GEM asset layer (`gem_units`). Added an always-present (not just `asset_project`-scoped) warning plus matching text in `operator_notice` and `disclaimer_de`.
- **Numeric cross-check.** The cross-check reminder previously only fired for `topic_type="market_news"`. It is now an always-present `warnings` entry (any topic can surface a number) reinforced in `operator_notice`.

No parameter, `error_code`, or cap changed. Existing consumers reading only `sources`/`extracted`/`warnings[0]` remain unaffected; `warnings` now has two additional fixed entries appended after the topic guardrail.

---

## Part F — Deferred / not done in this pass

- **Live Telegram smoke test** (recorded parameters + observed response, in the style of the BZN-prices "Operator note — verified Telegram smoke" section in `ACCESS_MATRIX.md`). Requires an operator with `TAVILY_API_KEY` + the feature flag set on the actual Railway service; not something this pass can execute from Repo A alone.
- **`docs/powerunits_setup_v2_sustainable_v1.md`** still states the old count ("**54**") for `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`; it is now 55. Left unedited to keep this pass's blast radius to 6 files — flag for a follow-up doc-sync pass.
- **Re-assessment after live use:** if operator feedback shows the `topic_type` guardrail note adds negligible value over the generic `web_search`/`web_extract` tools plus a system-prompt reminder, consider retiring this tool rather than maintaining two overlapping web-research surfaces (see overlap verdict in Part A).
- **Domain allowlisting / trusted-source weighting** (e.g. preferring ENTSO-E, national TSOs, Eurostat, official regulator domains for `market_news`/`regulatory_policy`) was intentionally left out of this slice — Tavily's `include_domains` parameter could support it later if operators want stronger source curation than the guardrail-note approach.
- **`ACCESS_MATRIX.md`'s pre-existing "General web … Not in first_safe Telegram surface" row** is already stale independent of this change (the `web`/`search` toolsets have been in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` since an earlier change per `docs/powerunits_setup_v2_sustainable_v1.md` line 361) — noted here, not fixed, to avoid unrelated scope creep in this pass.
