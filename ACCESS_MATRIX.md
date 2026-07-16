# Access matrix — Powerunits Hermes (Stage 1: Trusted Analyst)

**Scope:** Internal Hermes on Railway with `first_safe_v1`. One row = one **class** of access (not every tool name).

| Surface | Stage 1 | Gating / notes |
|---------|---------|----------------|
| **Telegram → Hermes** | Allowed | Operator-facing; allowlisted users/env as configured. |
| **GitHub docs (allowlisted)** | Allowed (primary) | `POWERUNITS_GITHUB_TOKEN_READ` (or legacy docs token); paths/branches per `powerunits_github_knowledge` config. |
| **Bundled Powerunits docs** | Allowed (fallback) | Build-time / env-directed; not primary when GitHub is healthy. |
| **Workspace** (`hermes_workspace` allowlisted subdirs) | Allowed | Text notes / analysis under bounded paths; no delete/rename escapes. |
| **Memory / session search / todo** | Allowed | Part of first_safe bounded set for continuity and tasks. |
| **Timescale read** (`read_powerunits_timescale_dataset`) | Allowed **only** when gated | `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` + `DATABASE_URL_TIMESCALE`; single view `public.market_price_model_dataset_v`; fixed patterns only. |
| **Repo B file read** (`read_powerunits_repo_b_allowlisted`) | Allowed **only** when gated | `HERMES_POWERUNITS_REPO_B_READ_ENABLED` + GitHub read token; actions `list_repo_b_keys` / `read_repo_b_key` only (snake_case keys from `config/powerunits_repo_b_read_allowlist.json`); not the doc manifest tool. |
| **Option D preflight** (`preflight_powerunits_option_d_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED`; local PL / `v1` / ≤24h UTC slice check, rollback SQL, optional legacy wrapper CLI, bounded HTTP hint — **no** Powerunits HTTP, **no** wrapper execution, **no** DB writes from Hermes. |
| **Option D bounded execute** (`execute_powerunits_option_d_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED` + `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`; **one** HTTP POST to Powerunits internal bounded recompute API — **no** direct SQL from Hermes, **no** subprocess/product-root on this path; not a general writer. |
| **Option D bounded validate** (`validate_powerunits_option_d_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED` + same base URL and bearer as execute; **one** HTTP POST to internal **read-only** validate-window API — **no** SQL from Hermes; structured `passed` / `warning` / `failed` outcome only. |
| **Option D bounded readiness** (`readiness_powerunits_option_d_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED` + same base URL and bearer as execute; **one** HTTP POST to internal **read-only** readiness-window API — **no** SQL from Hermes; `readiness` `go` / `no_go` on normalized **inputs** for `market_feature_job` (not output rows). |
| **Option D bounded summary** (`summarize_powerunits_option_d_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED` + same base URL and bearer as execute; **one** HTTP POST to internal **read-only** summary-window (readiness + validation + optional pipeline echo); **no** SQL from Hermes. |
| **Bounded ENTSO-E market sync preflight** (`preflight_powerunits_entsoe_market_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED`; local DE / `v1` / ≤7d slice + bounded HTTP hint — **no** Powerunits HTTP, **no** job execution. |
| **Bounded ENTSO-E market sync execute** (`execute_powerunits_entsoe_market_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED` + same base URL and bearer; **one** HTTP POST to `…/entsoe-market-sync/recompute` — **no** SQL from Hermes; Repo B runs `entsoe_market_job.run` in-process. |
| **Bounded ENTSO-E market sync validate** (`validate_powerunits_entsoe_market_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED` + same base URL and bearer; **one** HTTP POST to read-only validate-window — **no** SQL from Hermes. |
| **Bounded ENTSO-E market sync summary** (`summarize_powerunits_entsoe_market_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED` + same base URL and bearer; **one** HTTP POST to read-only summary-window — **no** SQL from Hermes. |
| **Bounded ERA5 weather sync preflight** (`preflight_powerunits_era5_weather_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED`; local DE / `v1` / ≤7d slice + bounded HTTP hint — **no** Powerunits HTTP, **no** job execution. |
| **Bounded ERA5 weather sync execute** (`execute_powerunits_era5_weather_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED` + same base URL and bearer; **one** HTTP POST to `…/era5-weather/recompute` — **no** SQL from Hermes; Repo B runs `era5_weather_job.run` only (**does not** auto-run `market_feature_job` / `market_driver_feature_job`). |
| **Bounded ERA5 weather sync validate** (`validate_powerunits_era5_weather_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED` + same base URL and bearer; **one** HTTP POST to read-only validate-window on `weather_country_hourly` — **no** SQL from Hermes. |
| **Bounded ERA5 weather sync summary** (`summarize_powerunits_era5_weather_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED` + same base URL and bearer; **one** HTTP POST to read-only summary-window — **no** SQL from Hermes. |
| **Bounded ENTSO-E BZN price readiness read** (`read_powerunits_entsoe_bzn_price_readiness_v1`) | Allowed **only** when gated | **`HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED`** + **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** + **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** (+ optional **`POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S`**); **one** read-only **`POST …/entsoe-bzn-price-readiness/read`** — **no** jobs, ingestion, writes, Tier‑v1 promotion, or Hermes SQL. |
| **Bounded ENTSO-E BZN day-ahead prices read** (`read_powerunits_entsoe_bzn_prices_v1`) | Allowed **only** when gated | **`HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED`** + same execute base URL and bearer (**no** **`DATABASE_URL_TIMESCALE`** on this tool); **one** read-only **`POST …/entsoe-bzn-prices/read`** — **no** jobs, ingestion, writes, Tier‑v1 national promotion implied; bidding-zone scoped only. |
| **Energy-scoped web research** (`research_powerunits_energy_web_v1`) | Allowed **only** when gated | **`HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED`** + **`TAVILY_API_KEY`**; Tavily search (+ optional bounded extract of its **own** top result URLs, never caller-supplied URLs) — **no** Repo B HTTP call, **no** jobs, ingestion, or writes. Always returns `external_web_context: true`; not a substitute for the bounded ENTSO-E/ERA5/GEM read tools. |
| **General web / browser / terminal / file / code-exec / MCP / cron** | **Not** in first_safe Telegram surface | Fail-closed for Powerunits internal profile — do not “temporarily” widen without policy change. |
| **Broad DB / free SQL / schema writes** | Forbidden | Hermes has no such tool in this profile; Repo B owns schema. |
| **Repo B direct git writes from Hermes** | Forbidden | Product changes go through human/CI workflows, not agent. |
| **Infra mutation (Railway, DNS, secrets in git)** | Forbidden | Operators use consoles; agents document only. |

### Operator note — verified Telegram smoke (`read_powerunits_entsoe_bzn_prices_v1`)

A **successful** Telegram run used tool **`read_powerunits_entsoe_bzn_prices_v1`** (actual **EUR/MWh** day-ahead **rows** per BZN timestamp from Repo B **`POST …/internal/hermes/bounded/v1/entsoe-bzn-prices/read`**). That path is **read-only**, runs **no** jobs, triggers **no** ingestion, and **does not** represent national Tier‑v1 bounded market promotion (**`promotes_tier1: false`** on the bounded contract).

**Distinction:** **`read_powerunits_entsoe_bzn_price_readiness_v1`** hits **`…/entsoe-bzn-price-readiness/read`** (coverage/readiness aggregate). The prices tool is **not** that route and **not** `read_powerunits_timescale_dataset`.

Recorded parameters: `window_start_utc=2024-01-01T00:00:00Z`, `window_end_utc=2024-01-02T00:00:00Z`, `table_version=bzn_advisory_v1`, `country_codes=["DK","NO","SE"]`, **`limit=20`**. Observed: `success=true`, `bounded_internal_statement=bzn_prices_read_only`, `prices_contract=bounded_entsoe_bzn_prices_read_v1`, `summary.total_row_count=264`, `summary.distinct_timestamps=24`, `truncated=true`, `http_status_from_repo_b=200`.

**Interpretation:** `total_row_count=264` matches **11 bidding zones × 24 hourly buckets** for that window under the selected countries (**DK1/DK2**, **NO1–NO5**, **SE1–SE4**). **`limit`** applies to the returned **detail** price rows only; **`summary`** still reflects aggregates for the **full** requested zone/window (**truncated** flags when detail payload is shortened). Full checklist copy: **`RUNBOOK.hermes-stage1-validation.md`** (ENTSO-E BZN prices subsection).

## Stage 1 documentation map

| File | Use |
|------|-----|
| `SOUL.hermes.md` | Profile and intent. |
| `RUNBOOK.hermes-trusted-analyst.md` | Operator context and triage table. |
| `ACCESS_MATRIX.md` | This matrix — allowed / gated / forbidden. |
| `docs/powerunits_era5_weather_bounded_operator_v1.md` | Bounded ERA5 Hermes tools + env gates + no auto feature job reminder. |
| `RUNBOOK.hermes-stage1-validation.md` | Checklists, post-deploy verification, rollback basics. |
| `SOUL.hermes-writer.md` / `RUNBOOK.hermes-writer.md` | **Stage 2 scaffolding only** — not live until explicitly enabled. |
| `CHECKLIST.hermes-writer-activation.md` | **Gate** — all mandatory items + sign-off before Stage 2 is real on any environment. |

## Stage 2 — Controlled Implementer (**planned / not active by default**)

**Binding contract today:** only the **Stage 1** table above. The rows below describe **intended** behavior **only after** `CHECKLIST.hermes-writer-activation.md` is fully satisfied **and** maintainers record sign-off — not implicit availability, **not** the current Railway internal Hermes deployment.

| Surface | Stage 2 (when/if explicitly activated) | Still forbidden / unchanged |
|---------|----------------------------------------|----------------------------|
| **Repo A bounded code edits** | Planned: minimal patches only under agreed file list + plan; proposal-before-apply; human/CI gate as defined at rollout time. | No drive-by refactors; no scope expansion without re-approval. |
| **Repo B product repo** | **Not** default Hermes apply target; remains human/CI unless a separate approved workflow exists. | Same as Stage 1 unless explicitly documented elsewhere. |
| **DB / Timescale** | Read path may remain as today; **writes** stay **out of scope** for this Stage 2 doc. | No Hermes DB writer tool by default. |
| **Deploy / infra / secrets** | **Forbidden** from Hermes (same as Stage 1). | Railway, DNS, `.env`, secrets in git — operators only. |
| **Telegram → Hermes** | Would still be operator-facing; **tighter** review on any write-capable tool surface when introduced. | No “silent” broadening of `first_safe` without explicit policy change. |

**Docs:** `SOUL.hermes-writer.md`, `RUNBOOK.hermes-writer.md`, `CHECKLIST.hermes-writer-activation.md`.

## Stage 3 — Orchestrated Operator Read (**planned / not active**)

- Would add *orchestrated* read workflows; **no** default broader DB until defined and enabled separately.

---

**Summary:** Stage 1 rows are **live**. Stage 2/3 sections are **specification only** until runtime and access controls are deliberately changed — not this document alone.
