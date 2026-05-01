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
| `docs/powerunits_bounded_flags_consolidated_v1.md` | Consolidated bounded env naming & migration table. |
| `docs/powerunits_entsoe_forecast_bounded_operator_v1.md` | Bounded ENTSO-E **forecast** Hermes tools (`entsoe_forecast_job` only; not market sync / features). |
| `docs/powerunits_de_stack_remediation_planner_operator_v1.md` | Read-only DE remediation planner (**one** Repo B POST; **no** job execution via this surface). |
| `docs/powerunits_outage_awareness_bounded_operator_v1.md` | Bounded DE outage awareness validate/summary (**read-only**; **no** ingest or feature recompute). |
| `docs/powerunits_outage_repair_bounded_operator_v1.md` | Bounded DE outage **repair** execute (Step A+B; **separate gate** from awareness). |
| `docs/powerunits_market_features_bounded_de_operator_v1.md` | Bounded DE `market_features_hourly` Hermes tools (separate from PL Option D). |
| `docs/powerunits_market_driver_features_bounded_de_operator_v1.md` | Bounded DE `market_driver_features_hourly` Hermes tools (separate from market-features DE + Option D). |
| `docs/powerunits_baseline_layer_preview_operator_v1.md` | Bounded baseline layer-coverage preview (Hermes POST to Repo B; read-only, DE). |
| `docs/hermes_stage1_preview_validation_v1.md` | Manual browser/preview smoke (read-only; no Hermes URL fetch). |
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

### Bounded ENTSO-E market (Hermes → Repo B)

- [ ] **Preflight — primary:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED=1` → `preflight_powerunits_entsoe_market_bounded_slice` with DE / v1 / ≤7d slice → JSON `syntactically_valid: true`, bounded HTTP hint names the execute tool.
- [ ] **Preflight — legacy:** same as above with primary off and `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED=1` only.
- [ ] **Primary + allowlist:** unset `…_ALLOWED_COUNTRIES` still allows DE-shaped tools; explicit `…_ALLOWED_COUNTRIES=` (empty) keeps primary on but fail-closed — execute tool returns **`feature_disabled`**.
- [ ] **Execute gate off:** primary falsy and all four legacy core flags falsy → execute returns **`feature_disabled`** — no Repo B HTTP from that path.
- [ ] **Campaign:** with `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED=1`, primary `=1` suffices for execute+summary gating (plus base URL/bearer); legacy configs still need execute+summary legacy flags.

### Bounded ERA5 weather (Hermes → Repo B)

- [ ] **Preflight — primary:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED=1` → `preflight_powerunits_era5_weather_bounded_slice` with DE / v1 / ≤7d slice → JSON `syntactically_valid: true`, `bounded_http_operator_hint` names the execute tool.
- [ ] **Preflight — legacy:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED=1` with primary off → same preflight behavior.
- [ ] **Execute gate off:** primary falsy and all four legacy core flags falsy → execute returns **`feature_disabled`** — no Repo B HTTP from that tool path.
- [ ] **Operator wording:** successful execute JSON includes explicit **no auto** `market_feature_job` / `market_driver_feature_job` reminder (`operator_statement` / Repo B `downstream_not_auto_triggered`).
- [ ] **Campaign:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED=1` + primary `=1` (or legacy execute+summary) + base URL/bearer.

### Bounded ENTSO-E forecast (Hermes → Repo B; forecast family only)

- [ ] **Orthogonal:** This path is **`…/entsoe-forecast/*`** → **`entsoe_forecast_job`** only — **not** **`…/entsoe-market-sync/*`**, **not** `market_feature_job`, **not** `market_driver_feature_job`.
- [ ] **Preflight — primary:** `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED=1` → `preflight_powerunits_entsoe_forecast_bounded_slice` (DE / v1 / ≤7d) → `syntactically_valid: true`, bounded hint names execute tool.
- [ ] **Preflight — legacy:** primary off + `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_PREFLIGHT_ENABLED=1` → same behavior.
- [ ] **Primary + empty allowlist:** `…_ALLOWED_COUNTRIES=` (empty) with primary truthy → **fail-closed** (`feature_disabled` or equivalent).
- [ ] **Execute gate off:** primary falsy **and** all four legacy falsy → execute **`feature_disabled`** — no Repo B HTTP.
- [ ] **Execute on:** bounded POST **`…/entsoe-forecast/recompute`**; response states **no downstream** features/market/auto-expand if Repo B echoes that field.

### Bounded DE market features hourly (Hermes → Repo B; optional)

- [ ] **Separate from Option D:** `HERMES_POWERUNITS_OPTION_D_*` unchanged; DE bounded market-features use **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED`** (**recommended**) or legacy **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*`** per tool.
- [ ] Optional Hermes-side allowlist: **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES`** (comma ISO2); unset → implicit **DE** for current tools; empty string → fail-closed for primary-flag path.
- [ ] **Primary off + all legacy off:** `execute_powerunits_market_features_bounded_de_slice` returns **`feature_disabled`** — no Repo B HTTP.
- [ ] **Primary on:** all four bounded market-features tools qualify (with base URL + bearer); **`≤24h`** execute POST body includes **`country_code: "DE"`**.
- [ ] **Legacy granular:** enabling only **`…_DE_EXECUTE_ENABLED`** still does **not** expose validate/readiness/summary until their legacy keys or **`MARKET_FEATURES_BOUNDED_ENABLED`** is set.

### Bounded DE market driver features hourly (Hermes → Repo B; optional)

- [ ] **Distinct family:** **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`** (**recommended**) or legacy **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_*`** — does **not** enable **`HERMES_POWERUNITS_MARKET_FEATURES_*`** or **`HERMES_POWERUNITS_OPTION_D_*`**.
- [ ] Optional: **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES`** — same semantics as market-features (`DE` implicit when unset).
- [ ] **Gate off:** all primary + legacy driver flags falsy → execute returns **`feature_disabled`**.
- [ ] **Primary on:** all four driver tools qualify; POST to **`…/market-driver-features-hourly/recompute`** with **`country_code: "DE"`**; expect **`downstream_not_auto_triggered`**.

### Bounded baseline layer-coverage preview (read-only; optional)

- [ ] **Feature gate:** with `HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED` falsy, `preview_powerunits_baseline_layer_coverage_de` absent or returns **`feature_disabled`** — no Repo B HTTP.
- [ ] **Gate on:** bounded base URL + bearer set; tool **`preview_powerunits_baseline_layer_coverage_de`** with DE / v1 / ≤31d `[preview_start_utc, preview_end_utc)` → JSON **`preview_attempted: true`**, Repo B **`rollup`**, **`hermes_statement`** reflects **no jobs / no campaigns / read-only preview** (`read_only_baseline_preview_no_jobs` on Repo B). **`rollup.suggested_next_bounded_action`** is Repo B-authored only — Hermes does not append local steps.

### Bounded DE outage awareness (read-only; Hermes → Repo B)

- [ ] **Feature gate:** with **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED`** falsy **and** both legacy **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED`** / **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED`** falsy, **`validate_powerunits_outage_awareness_bounded_window`** / **`summarize_powerunits_outage_awareness_bounded_window`** return **`feature_disabled`** — **no** Repo B HTTP.
- [ ] **Primary on:** **`validate_powerunits_outage_awareness_bounded_window`** with DE / v1 / ≤7 d **`[start, end)`** → **`validation_attempted: true`**, Repo B **`hermes_statement`** indicates **read-only** / **no writes**; response includes **`checks`**, **`warnings`**, **`semantics_notes`** as applicable; **Hermes does not start** outage ingestion, **`outage_country_hourly` recompute**, **`market_feature_job`**, or **`market_driver_feature_job`**.
- [ ] **Summary:** **`summarize_powerunits_outage_awareness_bounded_window`** same slice → **`summary_attempted: true`**, **`outcome_class`** set; still **no jobs** via this path.
- [ ] **Primary + empty allowlist:** **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES=`** (empty) with primary truthy → **fail-closed** (**`feature_disabled`**).
- [ ] **Legacy granular:** validate legacy only does **not** enable summary **`check_fn`** until summary legacy or primary is set.

### Bounded DE outage repair execute (Hermes → Repo B; separate gate from awareness)

- [ ] **Feature gate:** with **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED`** falsy **and** legacy **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED`** falsy → **`execute_powerunits_outage_repair_bounded_slice`** returns **`feature_disabled`** — **no** Repo B HTTP.
- [ ] **Primary on:** **`execute_powerunits_outage_repair_bounded_slice`** with DE / v1 / ≤7 d **`[start, end)`** → **`execution_attempted: true`**; response lists **`downstream_not_auto_triggered`** excluding **`market_feature_job`** automation; Repo B **`hermes_statement`** includes **`bounded_outage_repair_step_a_b_executed`** on nominal path.
- [ ] **`HERMES_POWERUNITS_OUTAGE_AWARENESS_*`** does **not** enable repair (**separate gate**).

### Bounded DE stack remediation planner (read-only only)

- [ ] **Feature gate:** with **`HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED`** falsy, **`plan_powerunits_de_stack_remediation`** returns **`feature_disabled`** — **no** Repo B HTTP from that path.
- [ ] **Gate on:** **`plan_powerunits_de_stack_remediation`** with DE / v1 / ≤31 d **`[window_start_utc, window_end_utc)`** → **`plan_attempted: true`**; Repo B **`hermes_statement`** includes **`read_only_remediation_plan_no_writes`**; response includes **`recommended_sequence`** and **`family_states`**; **Hermes executes no ingest / feature jobs** — **manual** bounded tools only (`tool_hint_hermes` hints).
- [ ] Wide windows (near 31 d) may be **slow** on Repo B (many internal sub-evaluations).

### Rollback (Repo B read only)

- [ ] Set `HERMES_POWERUNITS_REPO_B_READ_ENABLED` to **falsy** or remove it; redeploy or restart if your platform caches env — tool should disappear or return disabled without touching Repo B or GitHub.

---

## Fail-closed / negative checks

- [ ] Invalid `pattern_id` or `window_id` → error JSON, no raw SQL exposure.
- [ ] Unknown country or version → error, no query broadening.
- [ ] With Timescale gate **off**: tool absent from definitions or handler returns disabled message — **not** a connection leak stack to the client.
- [ ] **Repo B read:** unknown key and disabled gate — covered in **Bounded Repo B read** above (avoid duplicating full matrix here).

---

## Rollback basics

- [ ] **Webhook:** point Telegram webhook back to last-known-good Hermes URL (previous Railway service / project) if this service is bad.
- [ ] **Timescale:** set `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` to falsy / unset to drop DB reads without redeploying Hermes logic.
- [ ] **Repo B read:** unset or falsify `HERMES_POWERUNITS_REPO_B_READ_ENABLED` (see Repo B read subsection).
- [ ] **Bounded ENTSO-E / ERA5:** unset or falsify **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`** / **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED`** and legacy **`…_PREFLIGHT/_EXECUTE/_VALIDATE/_SUMMARY_ENABLED`** as needed to drop Hermes HTTP for those families without changing Repo B. **Forecast:** **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED`** and its four legacy **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_*_ENABLED`** are **separate** — drop them independently of market ERA5/market-sync flags. Campaign and coverage-scan modifiers remain separate.
- [ ] **Bounded DE market features:** unset or falsify `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*_ENABLED` (execute/validate/readiness/summary as needed) without touching PL Option D flags.
- [ ] **Bounded DE stack planner:** falsify **`HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED`** to drop **`plan_powerunits_de_stack_remediation`** Hermes POSTs independently of other bounded flags.
- [ ] **Bounded outage awareness (read-only):** falsify **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED`** and legacy **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED`** / **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED`** to drop outage-awareness Hermes POSTs — **no** Repo B job impact (read-only surface only).
- [ ] **Bounded outage repair:** falsify **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED`** and legacy **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED`** to drop outage-repair executes — does **not** stop Repo B ingestion when invoked elsewhere.

*Tick boxes in copy/paste or your ticket tracker; keep evidence (timestamp + operator) for production-impacting changes.*
