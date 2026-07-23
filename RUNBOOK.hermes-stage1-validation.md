# Stage 1 Trusted Analyst — validation pack (Powerunits internal Hermes)

**Use:** After deploy, env change, or incident triage — confirm Hermes is still **Stage 1 Trusted Analyst**, bounded and reviewable. Repo A only; product truth stays Repo B.

## Stage 1 documentation map

| Artifact | Role |
|----------|------|
| `SOUL.hermes.md` | Profile intent, knowledge order, roadmap stages (1 live; 2–3 placeholders). |
| `RUNBOOK.hermes-trusted-analyst.md` | Ongoing operator context, paths, “if something is wrong”. |
| `ACCESS_MATRIX.md` | What is allowed vs gated vs forbidden in Stage 1. |
| **This file** | Repeatable checks + post-change verification + rollback basics. |
| `docs/powerunits_timescale_read_operator_v1.md` | Timescale tool env gates and scope. |
| `docs/powerunits_repo_b_read_operator_v1.md` | Repo B allowlisted read (`read_powerunits_repo_b_allowlisted`); env-gated. |
| `docs/hermes_stage1_preview_validation_v1.md` | Manual browser/preview smoke (read-only; no Hermes URL fetch). |
| `docs/powerunits_tier4b_review_governance_overlay_v1.md` | Tier **4B** review-state + governance workspace ( **`tier ≥ 5`** ); rollback = **`tier = 4`**. |
| `docs/powerunits_hermes_growth_and_option_d_intake_v1.md` | Hermes growth decisions + Option D intake (read-only design path). |
| `config/powerunits_repo_b_read_allowlist.json` | Allowlist keys → Repo B paths (authoritative for that tool; **version** field drives v2–v5 expectations in checks below). |

---

## Post-change deploy verification (Trusted Analyst still on)

Run this block **first** after any Railway deploy or variable edit:

- [ ] `HERMES_POWERUNITS_RUNTIME_POLICY` is exactly `first_safe_v1` (Railway env for this service).
- [ ] `config.yaml` on the instance (under `HERMES_HOME`, e.g. `/opt/data`) shows Powerunits policy as expected: Telegram toolsets match the bounded set (see `docker/apply_powerunits_runtime_policy.py` / gateway lockdown behavior).
- [ ] Logs: gateway starts **telegram**; no stack trace loop; **no** full `DATABASE_URL*` or token strings in stdout/stderr.
- [ ] Telegram: bot answers; `/help` or equivalent shows only **bounded** tools (no web/terminal/MCP surge “for debugging”).
- [ ] **If Repo B read is supposed to be live:** `HERMES_POWERUNITS_REPO_B_READ_ENABLED` truthy **and** GitHub read token set; run the **Repo B read** subsection below.

If any item fails → treat as **not** Trusted Analyst until fixed; do not widen toolsets to “unblock”.

### Post v0.19.0 merge — Telegram smoke pack (copy/paste)

Run **after Railway redeploy** on `powerunits-internal-setup` (upstream **v0.19.0** / `v2026.7.20`). Rollback tag if needed: **`powerunits-hermes-pre-v0.19.0-20260722`**.

**Env sanity (Railway):**

- `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
- `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health` (recommended during backfill)
- `HERMES_POWERUNITS_CAPABILITY_TIER=0` or `1` (**not** `6`)
- If posture drift on ERA5: set/persist `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES` to national Tier-1 list

| # | Prompt (Telegram) | Pass criteria |
|---|-------------------|---------------|
| **0** | `Bitte führe summarize_powerunits_operator_posture aus und gib mir das JSON.` | `bounded_profile_v1` gesetzt, `aligned: true` (oder dokumentierte `missing_truthy` mit klarer Ursache — kein unerwarteter Tool-Surge) |
| **1** | `Nutze read_powerunits_multi_country_data_health_v1 für die Standard-11 national Tier-1 Länder (7-Tage-Fenster). Zeige operator_summary_v1.` | JSON mit `operator_summary_v1`; Länder DE/NL/BE/FR/AT/CZ/PL/FI/HU/SK/RO abgedeckt; kein HTTP-5xx-Loop |
| **2** | `Validiere validate_powerunits_entsoe_empirical_candidate_window_v1 für DK, Fenster 2024-01-01T00:00:00Z bis 2024-01-08T00:00:00Z, version v1.` | JSON zurück; `pre_backfill_gap` o.ä. ist **ok** wenn dokumentiert — kein Tool-Crash |
| **3** | `Lies ENTSO-E BZN Preise: read_powerunits_entsoe_bzn_prices_v1, window 2024-01-01T00:00:00Z bis 2024-01-02T00:00:00Z, country_codes DK NO SE, limit 20.` | `success=true`, `bounded_internal_statement=bzn_prices_read_only`, `http_status_from_repo_b=200` |
| **4** | `Liste Repo-B-Allowlist-Keys: read_powerunits_repo_b_allowlisted mit action list_repo_b_keys` | `surface: powerunits_repo_b_read`; snake_case keys (nicht Doc-Manifest) |
| **5** | Negative: bitte **web_search** oder Terminal ausführen | Abgelehnt / Tool nicht verfügbar — **first_safe** hält |

Evidence: Timestamp + Operator + Screenshot oder gekürztes JSON in eurem Ticket-Tracker.

### Co-worker ladder (after Tier-0 baseline)

Ops plan: **`docs/powerunits_hermes_coworker_tier_ladder_v1.md`**.  
Known-good tag after v0.19 smokes: **`powerunits-tier0-baseline-20260723`**.

**Next uplift (Tier 1 / Phase 2A):** Railway only change
`HERMES_POWERUNITS_CAPABILITY_TIER=0` → `1`, redeploy, then:

- [ ] Posture: `tier_effective_integer: 1`, `telegram_powerunits_tier1_analysis_observed: true`
- [ ] `summarize_powerunits_workspace_full`
- [ ] `search_powerunits_workspace_text` (known file under `hermes_workspace`)
- [ ] Soak ≥3 days before Tier 2

Keep `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health` during backfill.

---

## Startup checks

- [ ] Service reaches healthy / listening state within expected window.
- [ ] One log line confirms messaging platform init for **Telegram** (not a disabled platform).
- [ ] Disk/volume mount for `HERMES_HOME` present if workspace is required.

---

## Telegram checks

- [ ] Inbound message from an **allowlisted** operator identity gets a reply.
- [ ] `/new` or session reset still works if you rely on it for clean tests.
- [ ] Bot cannot invoke tools outside first_safe (e.g. no generic web search if not in allowlist).

---

## GitHub docs checks (primary knowledge)

- [ ] Ask Hermes to use the GitHub docs path for a **known allowlisted** file; content is non-empty and plausible.
- [ ] If GitHub is intentionally down: Hermes should **not** silently pretend live GitHub — expect error or explicit fallback messaging per tool behavior.

---

## Bundled docs (fallback only)

- [ ] If bundle is configured: a read returns explicit **bundled** / snapshot semantics when used.
- [ ] If bundle is absent: primary path remains GitHub; no crash.

---

## Manual browser/preview validation (read-only)

When a **frontend preview or staging URL** should be sanity-checked after a deploy or PR: follow **`docs/hermes_stage1_preview_validation_v1.md`** (placeholders for up to **3** HTTPS targets, short manual checklist). Hermes **must not** fetch those URLs or drive a headless browser — operator only.

---

## Bounded Timescale checks (optional but live when gated)

- [ ] `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` truthy **and** `DATABASE_URL_TIMESCALE` set **iff** you expect the tool.
- [ ] Valid call: `read_powerunits_timescale_dataset` with allowed `pattern_id`, `country_code`, `version`, `window_id` → JSON payload with `data_plane: timescale` / bounded fields.
- [ ] Row cap: request `row_limit` above max → **rejected** (fail closed), not truncated silently against policy.

---

## Bounded Repo B read (supplemental; live only when gated)

Tool: `read_powerunits_repo_b_allowlisted` — **GitHub API only**, **key-only** (allowlist: `config/powerunits_repo_b_read_allowlist.json`). Primary knowledge remains **GitHub docs reader**; this is extra surface for allowlisted implementation paths.

### Checklist

- [ ] **Feature gate:** With `HERMES_POWERUNITS_REPO_B_READ_ENABLED` unset/false, a `read_repo_b_key` call returns a clear **disabled** / missing-feature error (not a GitHub stack trace to the user).
- [ ] **Gate on:** With flag **true** and `POWERUNITS_GITHUB_TOKEN_READ` (or legacy docs token) set, tool appears in the bounded tool surface (same `first_safe_v1` set as other Powerunits tools).
- [ ] **`list_repo_b_keys`:** `action=list_repo_b_keys` returns JSON with `surface: powerunits_repo_b_read` and keys from `config/powerunits_repo_b_read_allowlist.json` only (must include `job_market_feature`, v2 samples such as `job_entsoe_market`, and v3 `frontend_product_ux_principles` when allowlist **version** ≥ 3 — see file `version` field).
- [ ] **Allowlist v4 (Option A):** When JSON **`version` ≥ 4**, `list_repo_b_keys` includes **at least one** Option A key (e.g. `adr_013_hybrid_postgis_timescale_strategy`, `job_entsoe_generation_outage`, or `agent_onboarding`).
- [ ] **Allowlist v5 (Option D support):** When JSON **`version` ≥ 5**, `list_repo_b_keys` includes **at least one** v5 key (e.g. `apply_market_pipeline_schema_to_timescale`, `wave1_country_readiness_it_pl_se`, or `ddl_011_create_market_features_hourly`).
- [ ] **Allowed read:** `action=read_repo_b_key`, `key=implementation_state` returns JSON with non-empty `content` and `path` matching allowlist (`docs/implementation_state.md`).
- [ ] **Unknown key (negative):** `action=read_repo_b_key`, `key=__nonexistent_key__` → error JSON (`unknown` / invalid key); no partial file body.
- [ ] **No free path:** Confirm tool schema / `/help` description has **no** `path` / `repo` / free-form file argument — only `action`, optional `key`, optional `max_output_chars` (see `docs/powerunits_repo_b_read_operator_v1.md`).

### Smoke prompts (copy for internal / Telegram test)

Use **`read_powerunits_repo_b_allowlisted`** (not `read_powerunits_doc`). Doc manifest keys use `*.md` names; Repo B allowlist uses **snake_case** keys (`job_market_feature`, …).

1. **List Repo B allowlist keys** — `{"action": "list_repo_b_keys"}` → JSON with `surface: powerunits_repo_b_read`, `key_namespace: repo_b_allowlist_snake_case`, keys include `job_market_feature`.
2. **Happy read** — `{"action": "read_repo_b_key", "key": "implementation_state"}` (expect markdown body in `content`).
3. **Reject** — `{"action": "read_repo_b_key", "key": "__nonexistent_key__"}` (expect JSON error, no secrets).
4. **Wrong-tool check** — `read_powerunits_doc` with `{"action": "list_keys"}` → keys look like `implementation_state.md` and `surface: powerunits_doc_key_manifest` — **different** from step 1.

### Bounded ERA5 weather (Hermes → Repo B)

- [ ] **Preflight:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED=1` → `preflight_powerunits_era5_weather_bounded_slice` with DE / v1 / ≤7d slice → JSON `syntactically_valid: true`, `bounded_http_operator_hint` names the execute tool.
- [ ] **Execute gate off:** with execute flag falsy, execute tool absent or returns `feature_disabled` — no Repo B HTTP from that tool path.
- [ ] **Operator wording:** successful execute JSON includes explicit **no auto** `market_feature_job` / `market_driver_feature_job` reminder (`operator_statement` / Repo B `downstream_not_auto_triggered`).

### ENTSO-E BZN day-ahead prices read (Hermes → Repo B; read-only)

Tool: **`read_powerunits_entsoe_bzn_prices_v1`** — **one** bounded **`POST …/entsoe-bzn-prices/read`**; Hermes does **not** read Timescale or run jobs. **Does not** imply national Tier‑v1 market readiness (bidding-zone rows only).

- [ ] **Gate + creds:** **`HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED`** truthy plus **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** (optional **`POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S`**).
- [ ] **Smoke:** call with a short UTC window (`window_start_utc` / `window_end_utc`), default or explicit **`country_codes` DK/NO/SE** (and optional zone labels) → JSON includes Repo B contract fields (`success`, `bounded_internal_statement`, pricing rows / summary as returned) plus Hermes fields `read_attempted`, `http_status_from_repo_b`, `hermes_operator_note_v1`.
- [ ] **Rollback:** set gate to falsy or unset — tool drops from definitions; no Repo B mutation.

#### Recorded Telegram smoke (production-style; evidence)

Hermes surfaced **`read_powerunits_entsoe_bzn_prices_v1`** in Telegram (**not** **`read_powerunits_entsoe_bzn_price_readiness_v1`**; **not** Timescale **`read_powerunits_timescale_dataset`**).

| Field | Recorded |
|-------|----------|
| Tool | **`read_powerunits_entsoe_bzn_prices_v1`** |
| `window_start_utc` | `2024-01-01T00:00:00Z` |
| `window_end_utc` | `2024-01-02T00:00:00Z` (exclusive end → one calendar day) |
| `table_version` | `bzn_advisory_v1` |
| `country_codes` | `["DK","NO","SE"]` |
| `limit` | `20` |

Observed payload highlights: **`success=true`**, **`bounded_internal_statement=bzn_prices_read_only`**, **`prices_contract=bounded_entsoe_bzn_prices_read_v1`**, **`summary.total_row_count=264`**, **`summary.distinct_timestamps=24`**, **`truncated=true`**, **`http_status_from_repo_b=200`**.

**Semantics for operators:** This is **timestamped BZN day-ahead price data** (EUR/MWh) from Repo B’s bounded read — **read-only**, **no** job execution, **no** ingestion side effects, **no** national Tier‑v1 promotion implied. Count **`total_row_count=264`** = **11 zones × 24 hours** for the window with these countries (**DK1/DK2**, **NO1–NO5**, **SE1–SE4**). The small **`limit`** affected **detail** rows returned in the tool/HTTP payload; **`summary`** remained a **full-window / full-zone** aggregate, hence **`truncated=true`** with a full-count summary.

**Cross-ref (Repo B API contract):** `docs/runbook.md` → *Internal Hermes bounded ENTSO‑E BZN day-ahead **prices***; `docs/operations/ACCESS_MATRIX.md` (ENTSO‑E BZN **prices** row).

### Rollback (Repo B read only)

- [ ] Set `HERMES_POWERUNITS_REPO_B_READ_ENABLED` to **falsy** or remove it; redeploy or restart if your platform caches env — tool should disappear or return disabled without touching Repo B or GitHub.

---

## Fail-closed / negative checks

- [ ] Invalid `pattern_id` or `window_id` → error JSON, no raw SQL exposure.
- [ ] Unknown country or version → error, no query broadening.
- [ ] With Timescale gate **off**: tool absent from definitions or handler returns disabled message — **not** a connection leak stack to the client.
- [ ] **Repo B read:** unknown key and disabled gate — covered in **Bounded Repo B read** above (avoid duplicating full matrix here).

---

## Tier 4B review governance (optional smoke; `HERMES_POWERUNITS_CAPABILITY_TIER ≥ 5`)

Only when Tier **4A** skill drafts are already enabled and operators want the **4B** review-state + governance scaffolding layer:

- [ ] **`HERMES_POWERUNITS_CAPABILITY_TIER=5`** (or set max tier per `powerunits_capability_tier` / roadmap) on the gateway process.
- [ ] Telegram merged toolsets include **`powerunits_tier4b_review_governance`** **after** **`powerunits_tier4a_skill_draft_proposals`** (policy: `docker/apply_powerunits_runtime_policy.py`).
- [ ] Positive: **`manifest_powerunits_tier4b_governance_scope`** → JSON with bounded paths and safety flags (**no** live **`skills/`** writes).
- [ ] **`ensure_powerunits_governance_workspace`** creates only the documented **`hermes_workspace/governance/*`** subtrees (see Tier 4B overlay doc).
- [ ] **`review_powerunits_tier4b_skill_drafts`** lists drafts with **`review_status`** rollups; **`set_powerunits_skill_draft_review_status`** updates **frontmatter only** on existing Tier 4A proposal files.
- [ ] **`summarize_powerunits_tier4b_governance_lane`** / posture **`tier4b_governance_watch_read_only`** — soft cautions only (unresolved queue, stale reviews, governance clutter); no auto-apply.

**Rollback (Tier 4B only):** set **`HERMES_POWERUNITS_CAPABILITY_TIER=4`** → policy drops **`powerunits_tier4b_review_governance`**; **4A** remains. No migration; governance notes and draft files stay on disk as inert artifacts.

---

## Bounded family smoke order (Tier-1 DE window; optional weekly)

When Repo B bounded HTTP is enabled and you want a **repeatable read-only health pass** (no execute/recompute):

1. **Market features** — `POST …/market-features-hourly/validate-window` for **`DE`** and **`PL`**, 24h UTC slice, `version=v1`.
2. **ENTSO-E market** — `POST …/entsoe-market-sync/validate-window` for **`DE`**, **`NL`**, **`BE`**, **`FR`** (same window).
3. **ERA5 weather** — `POST …/era5-weather/validate-window` for **`DE`**.
4. **Coverage snapshot** — `POST …/coverage-snapshot` with `country_codes: ["DE"]`, same window (layer + pipeline freshness rollup).

**Repo B in-process smoke (no Telegram):** from sibling repo `EU-PP-Database`:  
`cd backend && uv run python -m scripts.ops.smoke_bounded_validate_window_v1`  
(HTTP mode against Railway API: `--http` + `POWERUNITS_SMOKE_API_BASE` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`.)

**Interpretation:** `outcome=warning` may be normal on sparse windows; **`failed`** or HTTP 5xx → investigate before any execute. Full execute path remains **preflight → execute → validate → summary** per family (Tier 5A records only; Repo B owns truth).

---

## Rollback basics

- [ ] **Webhook:** point Telegram webhook back to last-known-good Hermes URL (previous Railway service / project) if this service is bad.
- [ ] **Timescale:** set `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` to falsy / unset to drop DB reads without redeploying Hermes logic.
- [ ] **Repo B read:** unset or falsify `HERMES_POWERUNITS_REPO_B_READ_ENABLED` (see Repo B read subsection).
- [ ] **Bounded ERA5:** unset or falsify `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_*_ENABLED` flags to drop the Hermes HTTP surface without changing Repo B.
- [ ] **Policy:** do not remove `first_safe_v1` casually; rollback to prior image/env snapshot per your Railway practice, then re-run this validation pack.
- [ ] **Tier 4B:** lower **`HERMES_POWERUNITS_CAPABILITY_TIER`** to **4** to disable governance toolset without removing Tier 4A (see section above).

---

*Tick boxes in copy/paste or your ticket tracker; keep evidence (timestamp + operator) for production-impacting changes.*
