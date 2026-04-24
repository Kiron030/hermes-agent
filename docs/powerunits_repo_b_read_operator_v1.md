# Powerunits Repo B read — operator (Stage 1 Trusted Analyst)

**Status:** **Live tool (Repo A)** — `read_powerunits_repo_b_allowlisted` in toolset `powerunits_repo_b_read`, included under `first_safe_v1` **together with** an explicit env gate (see below). Repo B is still **not** modified from Hermes; reads go through the **GitHub Contents API** only (same principle as the primary GitHub docs reader).

## Tool

| Item | Value |
|------|--------|
| Tool name | `read_powerunits_repo_b_allowlisted` |
| Toolset | `powerunits_repo_b_read` |
| Actions | `list_repo_b_keys` (no `key`), `read_repo_b_key` (requires allowlist `key`) — distinct from `read_powerunits_doc`’s `list_keys` / `read` (manifest `*.md` keys). Legacy `list_keys` / `read` are still accepted by the handler but omitted from the schema. |
| Allowlist file | `config/powerunits_repo_b_read_allowlist.json` (override: `HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST`) |
| Feature gate | `HERMES_POWERUNITS_REPO_B_READ_ENABLED` must be truthy (`1`, `true`, `yes`, `on`) |
| GitHub auth | Same as docs: `POWERUNITS_GITHUB_TOKEN_READ` or legacy `POWERUNITS_GITHUB_DOCS_TOKEN` |

There is **no** parameter for a free repo path — unknown keys **fail closed**.

## Smoke / validation (live)

Operator checklist and JSON-style smoke steps: **`RUNBOOK.hermes-stage1-validation.md`** → section **“Bounded Repo B read”** (gate, `list_repo_b_keys`, one allowed `read_repo_b_key`, unknown-key negative, no free `path`, rollback).

## Purpose

Supplemental **read-only** access to a **fixed allowlist** of high-signal Repo B paths (see **Allowlist v2**, **v3**, **v4 (Option A)**, and **v5 (Option D support)** below) for **Trusted Analyst** grounding. Still **one GitHub file per key**, **no** free paths, **fail-closed** on unknown keys. Growth / Option D decisions: **`docs/powerunits_hermes_growth_and_option_d_intake_v1.md`**.

## Source precedence (Repo B read keys — quality)

Use this when **several allowlist keys** could answer the same topic. Prefer **one primary key** per question type; pull a **second** key only to disambiguate.

| Kind of question | Prefer first | Then (if needed) |
|------------------|--------------|-------------------|
| **What is implemented / live today?** | `implementation_state` | `architecture_overview`; job files (`job_market_feature`, `job_entsoe_market`, `job_era5_weather`, `job_market_driver_feature`) for **how** a pipeline is wired in code. |
| **Normative design / storage / semantics** | Matching **ADR** (`adr_013_*`, `adr_010_*`, `adr_014_*`) | `repo_boundaries` if scope/monorepo rules matter. |
| **Future / target direction (may lag prod)** | `target_architecture_v04` | `implementation_state` to contrast plan vs shipped reality. |
| **How to run checks, migrate, operate** | `runbook` | `implementation_state` for whether a capability exists. |
| **Where things live in the repo** | `agent_repo_overview` | `repo_boundaries`, then `implementation_state`. |
| **Product / UX / UI boundaries (no component crawl)** | `frontend_product_ux_principles` | `frontend_ui_architecture`, then `feature_policy`; use **`adr_0008_monorepo_frontend_backend`** when the question is explicitly **frontend vs backend** responsibility in the monorepo. |
| **ENTSO-E generation outages (pipeline order)** | **`adr_014_entsoe_generation_outages`** | **`job_entsoe_generation_outage`** → **`job_outage_country_hourly`** (ADR = semantics; jobs = wiring; optional **`ops_backfill_entsoe_outages`** for chunked backfill ops). |
| **PostGIS vs Timescale / where geo vs time series live** | **`adr_013_hybrid_postgis_timescale_strategy`** | `architecture_overview`, `implementation_state` if deployment reality matters. |
| **Option D — Timescale DDL order / `market_features_hourly` schema text** | **`apply_market_pipeline_schema_to_timescale`** + **`ddl_011_create_market_features_hourly`** | `job_market_feature` (runtime upsert/delete behavior), `runbook` (CLI windows). |
| **Option D — PL country readiness (ENTSO-E / archive context)** | **`wave1_country_readiness_it_pl_se`** | `implementation_state` (chain table), `job_entsoe_market` if fetch wiring needed. |

**Cross-surface (outside this tool):** narrative roadmap doc keys → **`read_powerunits_doc`** first; row facts → **Timescale** tool; Repo B read for **allowlisted** implementation/ADR/job files only.

### Ambiguity and recency

- If **ADR vs job code vs `implementation_state`** appear to disagree, say so **explicitly**: quote or paraphrase each source and its **key**; treat **ADRs as normative for designed semantics**, **`implementation_state` as normative for “exists in platform today”**, **job files as “how the job is coded”** (may lag ADR until refactors land).  
- If **`target_architecture_v04` vs `implementation_state`** conflict, state that target-arch may be **ahead or behind** deployment — default to **`implementation_state`** for “what we run now” unless the question is explicitly about target vision.

## Allowlist v2 (controlled expansion)

**Historical slice (still in the same file at `version` ≥ 3):** the **v2** batch retains all **v1** keys and adds **eight** entries for architecture / pipeline / ADR depth:

| Key | Why added |
|-----|-----------|
| `job_entsoe_market` | ENTSO-E market ingestion orchestration — complements `job_market_feature`. |
| `adr_013_entsoe_raw_object_store` | Normative raw object-store path for ENTSO-E archive questions. |
| `job_era5_weather` | Weather ingestion job entrypoint; pairs with weather ADR and Timescale. |
| `adr_010_weather_ingestion_mvp` | Weather MVP semantics (indices, windows) at ADR level. |
| `job_market_driver_feature` | Driver-feature job — links hourly features to modeling drivers. |
| `agent_repo_overview` | Repo layout for agents/operators; orients Hermes work across Repo A/B. |
| `target_architecture_v04` | Target architecture doc; use with `implementation_state` for plan vs reality. |
| `adr_014_entsoe_generation_outages` | Outage pipeline ADR — high value next to market/outage analyst threads. |

**Unchanged rules:** only **`list_repo_b_keys`** / **`read_repo_b_key`**; keys are **snake_case** from this JSON only; **GitHub remote only**; **Stage 1** stays read-only (no writer, no new tool classes).

## Allowlist v3 (frontend / product slice)

**Config version 3** adds **five** keys for **product, UX, and frontend-architecture** questions — still one file per key, no `src/` component trees:

| Key | Role |
|-----|------|
| `frontend_product_ux_principles` | UX/product principles — default first stop for “how should the product behave?”. |
| `frontend_ui_architecture` | UI shell / layering blueprint. |
| `frontend_punkt4_risiken` | Documented UX/product risks — use for explicit caveats. |
| `feature_policy` | Feature gating and surface constraints. |
| `adr_0008_monorepo_frontend_backend` | Normative **frontend vs backend** boundary in the monorepo. |

## Allowlist v4 (Option A — arch / data / ops slice)

**Config version 4** adds **six** keys — still one file per key, GitHub read-only, **Stage 1** (no writer):

| Key | Role |
|-----|------|
| `adr_013_hybrid_postgis_timescale_strategy` | Hybrid **PostGIS vs Timescale** strategy — prefer this for placement and scaling questions. |
| `job_outage_country_hourly` | **Step B** country-hourly outage aggregation into feature-layer join semantics (with ADR014). |
| `job_entsoe_generation_outage` | **Step A** outage raw ingest / sync job entrypoint (with ADR014). |
| `adr_011_era5_raw_storage_object_store` | ERA5 **raw** artifacts in **object storage** — complements `job_era5_weather` and `adr_010_weather_ingestion_mvp`. |
| `agent_onboarding` | **Agent/operator** onboarding — workflow, boundaries, how to work the repo safely. |
| `ops_backfill_entsoe_outages` | **Ops** chunked backfill for outages — read alongside outage ADR/jobs, not as a second generic `ops/` tree. |

## Allowlist v5 (Option D support — fact-gathering only)

**Config version 5** adds **three** keys for **Option D** intake: confirming how **`market_features_hourly`** lands on Timescale (DDL apply order + `011` definition), and **PL** Wave-1 operational context. These keys **do not** enable writes, jobs, or Hermes-side mutation — they only ground **read-only** answers before any staging-only write experiment is designed or operator-run outside Hermes.

| Key | Role |
|-----|------|
| `apply_market_pipeline_schema_to_timescale` | Ordered list of `backend/db/*.sql` applied to `DATABASE_URL_TIMESCALE` (includes `011` … `017` last). |
| `wave1_country_readiness_it_pl_se` | PL day-ahead passthrough, DE↔PL flow scope notes, soak lessons. |
| `ddl_011_create_market_features_hourly` | Authoritative SQL for the `market_features_hourly` relation (constraints / hypertable as defined in repo). |

## Why this is separate from GitHub docs (primary)

The primary GitHub docs reader uses the **doc-key manifest** under curated `docs/` surfaces. This tool reads the **Repo B implementation allowlist** (including **non-manifest** paths such as selected `backend/...` jobs). Use **docs reader first** for narrative roadmap content; use **Repo B read** for allowlisted implementation files when needed — and use the **source precedence** table above when choosing among overlapping Repo B keys.

## Why this is separate from Timescale

Timescale answers **row-level factual** queries on one view. Repo B read answers **source layout / job wiring** questions. Different credentials and contracts.

## Why this is not writer capability (Stage 2)

Read-only; no commits, no PR tool, no Repo B writes. Stage 2 remains gated by `CHECKLIST.hermes-writer-activation.md`.

## Explicit prohibitions (unchanged contract)

- **No free paths** — only allowlist keys.
- **No broad repo traversal** — no directory walk APIs beyond `list_repo_b_keys` over the **frozen** key set.
- **No secret-oriented keys** in the allowlist (operators must not add them).
- **No writes** — GitHub read-only API.
- **No local clone** — no filesystem path to a mounted Repo B clone in this design.

## Allowlist authority

Changes to scope = **edit JSON + review**; Hermes does not infer new paths from chat.
