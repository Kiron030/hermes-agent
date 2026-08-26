# Operator Hermes observability — architecture 0A

**Slice:** `OPERATOR_OBSERVABILITY_0A`  
**Status:** discovery + architecture only — no production authority, no credentials created, no Railway/Vercel/DB mutation, no deploy.  
**Follow-on:** slice 1 is implemented in [`powerunits_operator_observability_1_country_coverage_v1.md`](powerunits_operator_observability_1_country_coverage_v1.md) (`inspect_powerunits_country_coverage_v1`; live Operator PASS). Slice 2 is implemented in [`powerunits_operator_observability_2_db_health_v1.md`](powerunits_operator_observability_2_db_health_v1.md). **Not deployed.**  
**Audience:** operators deciding how Operator Hermes becomes a safe PowerUnits operational-intelligence agent.  
**Runtimes:** this initiative belongs to **Operator Hermes** (Railway). It must **not** be given to Developer Hermes.

Companion contracts (do not replace):

| Doc | Role |
|-----|------|
| [`powerunits_bounded_operating_model_v1.md`](powerunits_bounded_operating_model_v1.md) | Hermes as thin client over Repo B bounded HTTP |
| [`powerunits_hermes_integration_pattern_v1.md`](powerunits_hermes_integration_pattern_v1.md) | Repeatable bounded-tool recipe |
| [`ACCESS_MATRIX.md`](../ACCESS_MATRIX.md) | Live Stage-1 allow / gate / forbid |
| Repo B `docs/architecture/internal_hermes_bounded_operating_model_v1.md` | Product-side HTTP SoT |
| Repo B `docs/operations/database_routing_timescale_sot_v1.md` | Production DB routing |
| [`hermes_r5_developer_hermes_v1.md`](architecture/hermes_r5_developer_hermes_v1.md) | Developer Hermes isolation — no production authority |

```text
THIS_SLICE_DOES_NOT
  create tokens
  connect to production
  enable extensions
  schedule routines
  implement write authority
```

---

## 1. Goal and non-goals

Long-term Operator Hermes should answer operational questions about PowerUnits **services, deployments, data coverage, and database health**, then later propose — and only after a separate trust-boundary review, perhaps execute — tightly bounded actions.

This 0A slice designs the control plane. It does **not** implement production reads or writes.

**Preserve:**

```text
Operator Hermes
→ standalone PowerUnits integration/client
→ fixed bounded API
→ validator / effect policy
→ deterministic read / job / data operation
```

**Reject:**

```text
Operator Hermes → arbitrary Railway CLI / Vercel CLI / psql
```

Developer Hermes stays local Docker/WSL2 with **no** Railway, Vercel, or production-DB credentials. That isolation is already proven in R5 and must not be weakened.

---

## 2. Current Operator inventory (factual)

Effect classes come from `tools/powerunits_bounded_effects_v1.py`. Writes go through `tools/powerunits_bounded_write_approval_v1.py` (explicit human approval; YOLO / `approvals.mode=off` / cron auto-approve cannot authorize a PowerUnits write). Credentials are **never** values in this document.

Documented production posture (last written 2026-07-23, **not live-probed in 0A**): Operator Hermes **v0.19.0**, profile `stage1_read_health`, capability tier recorded as `1` in the progressive-posture doc and `4` in the coworker ladder. Profile ≠ tier. `stage1_read_health` fills missing env keys only; explicit Railway values win.

### 2.1 Read tools (Repo B HTTP or local)

| Tool / family | Target | Credential source | Effect | Approval | Typical prod gate |
|---------------|--------|-------------------|--------|----------|-------------------|
| Coverage snapshot / inventory / worker freshness / multi-country health | Repo B `POST /internal/hermes/bounded/v1/{coverage-snapshot,coverage-inventory,worker-country-coverage/freshness/read}` | `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | `READ` | none | `stage1_read_health` |
| ENTSO-E / ERA5 / market-features / driver / outage **validate / readiness / summary** | same bearer, family routes | same | `READ` or `READ_WITH_SIDE_EFFECT` (validate) | none | profile legacy per-step flags |
| BZN price readiness + prices | `…/entsoe-bzn-price-readiness/read`, `…/entsoe-bzn-prices/read` | same | `READ` | none | profile |
| Baseline preview, remediation planner, rollout governance | Repo B read routes | same | `READ` | none | profile |
| `read_powerunits_timescale_dataset` | Timescale view `public.market_price_model_dataset_v` only; patterns `recent_rows_by_country` / `recent_window_summary_by_country`; ISO2 `DE,FR,NL,BE,ES` | `DATABASE_URL_TIMESCALE` | `READ` | none | profile + `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` |
| `read_powerunits_repo_b_allowlisted` | GitHub API, key-only allowlist | `POWERUNITS_GITHUB_TOKEN_READ` | `READ` | none | profile |
| Docs / GitHub docs / workspace list+read / posture | local bundle / GitHub / `$HERMES_HOME` workspace | read token or none | `READ` | none | `first_safe_v1` |
| Energy web research | Tavily | `TAVILY_API_KEY` | `READ_WITH_SIDE_EFFECT` | none | separate flag |

### 2.2 Bounded execute / job tools (write)

| Family | Target | Effect | Approval | Typical prod |
|--------|--------|--------|----------|--------------|
| Option D / market-features / market-driver / ENTSO-E market / ENTSO-E forecast / ERA5 / outage **repair** execute | one `POST …/recompute` per call | `BOUNDED_WRITE` | human rule-key | **off** under `stage1_read_health`; on only in `stage1_operator_execute` |
| ENTSO-E / ERA5 **campaign** | sequential execute+summary | `BOUNDED_WRITE_AMPLIFYING` | human | modifier flags, not in read-health |
| Workspace note / skill-draft / governance / workflow-run writes | local `hermes_workspace` only | `BOUNDED_WRITE` | human | capability-tier overlays |

Hermes never issues SQL writes. Repo B runs the declared in-process job.

### 2.3 Coverage / readiness already present

Country scope (Hermes **mirror** of Repo B; Repo B remains authoritative):

- National Tier-1: `AT, BE, CZ, DE, FI, FR, HU, NL, PL, RO, SK`
- Market-features execute: `DE, PL`
- Market-driver / outage repair: `DE`
- BZN advisory reads: `DK, NO, SE, IT, IE`
- Empirical ENTSO-E candidate validate: `DK, NO, IE`

Existing country-coverage **intelligence** is a **triptychon** (snapshot + inventory + worker freshness) plus family validate/summary windows. It is **not** a year-gap / missing-interval / NULL-coverage / duplicate-key inspector. Repo B already has the operator CLI `market_coverage_gap_report` over `market_price_model_dataset_v` (month/week buckets, expected vs actual hours). That CLI is **not** a Hermes tool.

### 2.4 Platform and DB internals — current state

| Surface | Operator Hermes today |
|---------|----------------------|
| Railway observability tools | **NONE** (bootstrap/runbook docs only) |
| Vercel observability tools | **NONE** |
| Deployment/status tools | **NONE** |
| DB catalog / vacuum / index / `pg_stat_*` tools | **NONE** |
| Timescale job/policy/CAGG tools | **NONE** |
| Backup/restore tools | **NONE** |
| Arbitrary SQL / CLI | **FORBIDDEN** (`ACCESS_MATRIX.md`) |

Repo B has **human/operator scripts**, not Hermes tools: `scripts/maintenance/report_postgres_disk_usage.py`, `generate_db_catalog_report.py`, `verify_timescale_worker_schema.py`, `market_coverage_gap_report`. These require a local `.env` DB URL and must not be wired into Developer Hermes.

---

## 3. Production database architecture (Repo B truth)

**Do not treat this file as live inventory.** Schema/pipeline SoT is Repo B `docs/implementation_state.md` and numbered migrations.

| Fact | Evidence |
|------|----------|
| Unified SoT | Railway service **TimescaleDB** (`timescaledb`); public proxy host documented as `ballast.proxy.rlwy.net`. Prefer `DATABASE_URL_TIMESCALE`; production `DATABASE_URL` may point at the same instance. |
| Extensions | `timescaledb` + `postgis` on one URL. ADR 013 hybrid strategy is **accepted**; cutover to unified SoT is operational fact in `database_routing_timescale_sot_v1.md`. |
| PostgreSQL version | Production documented as **16.1** with Timescale/PostGIS in RG-X2-C readiness notes. An isolated restore rehearsal used PG **18.4 without** those extensions. **Not re-probed in 0A.** |
| Catalog snapshot (2026-03-21, **stale**) | PostGIS 3.4.1, Timescale 2.13.1, toolkit 1.18.0. Public object counts from that day are obsolete (market hypertables then nearly empty). Use only as “extensions existed.” |
| Legacy Postgres | Former trolley Railway PostgreSQL **human-deleted**. `.env.pgurl` retired. |
| Test DB | Dedicated Railway Postgres (`TEST_DATABASE_URL`); must not resolve to SoT host:port. |
| Frontend | Vercel project **`analytics-app-powerunits`** (app.powerunits.io). Marketing landing is a **separate** Vercel project. |
| API / workers / Martin / Hermes | Railway project documented as `prolific-victory` for Production API; Martin `tiles.powerunits.io`; Operator Hermes is a **separate** Railway runtime. |

### 3.1 Major data objects

**Asset / geo (PostGIS + Martin):** `gem_units` + views (`gem_units_tiles`, `gem_units_spatial_eligible`, …); grid registry / L1 / licence-clear line routes; isolated `map_context` HVLSP; G9 Elia ODS124 PT15M hypertable.

**Market / weather chain:**

```text
raw → normalized hourly → market_features_hourly
  → market_driver_features_hourly
  → view market_price_model_dataset_v
  → view market_price_explainability_v
```

Normalized cores: `market_demand_hourly`, `market_prices_day_ahead`, `market_generation_by_type_hourly`, `weather_country_hourly`, `market_border_flow_hourly`, `outage_country_hourly`, commodity/carbon/FX hourlies. Jobs log to `data_pipeline_runs`.

**Hypertables (from stale catalog + later migrations):** the market/weather hourlies above; G9 operational series. **Continuous aggregates, compression/retention policies, and Timescale background jobs are not present in Repo B SQL/code search.** Refresh and ingest are **Railway cron workers** (`WORKER_JOB=…`), not `add_job` / CAGG policies.

**Materialized views:** product modeling layers are **views**, not matviews. Martin tile sources are functions/views.

**Access patterns already authorized for Operator:**

1. Bounded Repo B HTTP (preferred).
2. Single Timescale view, two fixed patterns (`read_powerunits_timescale_dataset`).
3. Public/product APIs (`/api/v1/…`, trust-snapshot) — not Hermes-internal, not a substitute for operator diagnostics.

**Read-only DB role:** not documented as an existing production credential. Creating one is a future human action, Operator-only.

**`pg_stat_statements`:** no enablement or usage in Repo B. Status for production: **UNKNOWN**. Do not enable in this program until a later explicit slice.

---

## 4. Country / data-coverage design

Reuse Repo B evaluators. Do **not** hard-code Austria.

```text
inspect_country_coverage(country, dataset?, start?, end?)
```

**Hermes role:** one typed tool, env-gated, single POST (or a documented fan-in of existing snapshot/inventory/freshness + a new gap-report route).  
**Repo B role:** authoritative SQL against allowlisted views/tables.

### 4.1 Dataset catalog (generic)

| `dataset` id | Backing object | Expected grain | Notes |
|--------------|----------------|----------------|-------|
| `model_dataset` | `market_price_model_dataset_v` | 1h | Strictest join (prices ∩ features ∩ drivers). AT 2026-07-20 snapshot: 73.9% in `[2016-01-02, 2026-07-10)` — empty `2016-01→2018-09`, complete from `2018-10`. **Point-in-time; re-read Repo B.** |
| `day_ahead_price` | `market_prices_day_ahead` | 1h | AT/CZ Wave-2: ISO2 passthrough sufficient in tested window |
| `demand` | `market_demand_hourly` | 1h | |
| `generation_by_type` | `market_generation_by_type_hourly` | 1h UTC bucket | sub-hourly raw ≠ persisted grain |
| `weather` | `weather_country_hourly` | 1h | ERA5 publication lag 6–13d |
| `cross_border` | `market_border_flow_hourly` | 1h | NULL outside configured borders is by design |
| `outage` | `outage_country_hourly` | 1h | awareness/repair still DE-scoped on bounded execute |
| `bzn_price` | `market_prices_day_ahead_bzn_v1` | 1h | advisory BZNs; not national Tier-1 |

Unknown `dataset` / `country` fail closed. Default `dataset` = `model_dataset`. Window exclusive-end, cap (suggest ≤ 31d for live HTTP; longer history via Repo B gap-report batching, already OOM-aware).

### 4.2 Checks (deterministic, no LLM)

| Check | Source idea |
|-------|-------------|
| earliest / latest timestamp | `MIN/MAX(timestamp_utc)` |
| row count vs expected interval hours | same math as `market_coverage_gap_report` |
| missing days/months/years | month/week buckets → `ok` / `thin` / `empty` |
| stale / lag | `now - max_ts`; ERA5 uses documented lag floor |
| NULL coverage | named nullable columns only (weather/cost) |
| duplicate natural keys | already in bounded validate-window |
| generation-type / forecast horizon | only if Repo B expose a fixed evaluator |

Return structured:

```text
country, dataset, window, coverage_ratio, missing_periods[],
lag_hours, null_rates{}, duplicate_keys, caveats[],
bounded_internal_statement, hermes_called_powerunits_http
```

AT is one ISO2 in the national Tier-1 set — no special case.

**Implementation home:** extend Repo B with `POST /internal/hermes/bounded/v1/country-coverage/inspect` that wraps `market_coverage_gap_report` + existing layer helpers. Hermes tool `inspect_powerunits_country_coverage_v1` stays a thin client. This is **MATERIAL** (same bearer, new named route), not a new credential class.

---

## 5. Database health design (read-only)

All diagnostics are **Repo B bounded HTTP** (or a later read-only DB role used **only** by Repo B). Hermes never sees a connection string in tool output and never sends SQL.

Proposed Repo B routes (names illustrative):

| Route idea | Reads |
|------------|-------|
| `…/db-health/storage` | `pg_database_size`, `pg_total_relation_size`, hypertable/chunk counts from `timescaledb_information` — already prototyped in `report_postgres_disk_usage.py` |
| `…/db-health/planner` | `last_analyze` / `last_autoanalyze`, `n_live_tup` vs `n_dead_tup` from `pg_stat_user_tables` |
| `…/db-health/indexes` | `pg_stat_user_indexes` (idx_scan), sequential-scan heavy tables, duplicate-index **candidates as recommendations only** |
| `…/db-health/vacuum` | last vacuum/autovacuum, dead tuples |
| `…/db-health/sessions` | `pg_stat_activity` summary (count, wait, backend_type, **query text redacted or fingerprinted**), blocking locks, connection saturation vs `max_connections` |
| `…/db-health/statements` | `pg_stat_statements` **if** present; else `{available: false}` — **do not CREATE EXTENSION** |
| `…/db-health/timescale` | hypertables, chunks, jobs (`timescaledb_information.jobs` / job stats) if relations exist; otherwise explicit `not_configured` |

**Timescale observability expected today:** hypertables + chunks + compression flag **if column exists**. CAGG / refresh / retention / compression **policies** and Timescale jobs: design for absence (`not_configured`). Ingest health stays on `data_pipeline_runs` + worker freshness (already built).

**Query text:** never return raw SQL that could embed literals. Fingerprint + normalized statement only.

---

## 6. DB advisor (design only)

A later tool `advise_powerunits_db_health_v1` consumes **only** structured health payloads (no raw SQL). Output envelope:

```text
FINDING            = QUERY_PERFORMANCE | STORAGE | VACUUM | INDEX | TIMESCALE | COVERAGE
EVIDENCE           = fingerprint, calls, mean/total time, plan characteristic, table/index stats
RECOMMENDATION     = bounded proposal (no executable SQL unless ACTION_CLASS allows a named op)
EXPECTED_BENEFIT   = LOW | MEDIUM | HIGH
RISK               = LOW | MEDIUM | HIGH
ACTION_CLASS       = OBSERVE_ONLY | PROPOSE_CHANGE | SAFE_MAINTENANCE | HIGH_RISK_DDL
HUMAN_APPROVAL_REQUIRED = YES | NO
```

`HUMAN_APPROVAL_REQUIRED = NO` only for `OBSERVE_ONLY`. Advisor never executes.

Model split (future routing, not implemented): collection = code; rollup = cheap model; diagnosis = Terra; hard planner/index reasoning = Sol. Security gates stay independent of model.

---

## 7. Future safe actions (not authorized)

Classification only. A later trust-boundary review decides the real allowlist.

### Lower risk / potentially bounded (`EXECUTE_SAFE` candidates)

| Action | Rollback |
|--------|----------|
| `ANALYZE` allowlisted table | n/a (stats) |
| Refresh a **named** CAGG **if one exists later** | re-refresh |
| Retry a **named** failed Timescale job **if jobs exist later** | job retry |
| Trigger a **known** PowerUnits bounded recompute (already exists) | re-run / upsert window |
| Restart a **named** Railway worker | platform restart; no DB rollback |
| Cancel a clearly identified runaway **read** backend | session gone |

### Medium / high risk (`EXECUTE_HIGH_RISK`, disabled by default)

`VACUUM` (not FULL), index create/drop, Timescale policy/retention/compression changes, schema migration.

### Forbidden by default

Arbitrary SQL; `DROP` / `TRUNCATE`; arbitrary `UPDATE`/`DELETE`/`ALTER`; `VACUUM FULL`; extension changes; role/credential changes; database delete/restore; model-generated DDL; Railway/Vercel mutations; secret value reads.

Existing bounded execute families remain the **only** live write path and stay behind `stage1_operator_execute` + human approval.

---

## 8. Backup / rollback contract

**Reality (documented, not triggered):**

- No Operator-visible automated “backup freshness” API.
- Railway volume backup GraphQL exists (list/create/restore/schedules) but **project tokens are write-capable**; G9 activation notes Railway CLI was **not** logged in and **`postgres pitr` was unused**.
- Production mutations use **manual `pg_dump` custom format** stored **outside Git**, with `pg_restore --list` verification and SHA-256 recorded in ops docs (RG-X2-C, G9, MAP-CONTEXT-3B, ODS121). Frequency: **ad-hoc per migration**, not daily.
- GEM path: JSONL table backup before native upsert (table-scoped, not cluster).
- Grid registry: identity-preserving restore is mandatory; empty-registry rebuild is a **new bootstrap**, not DR.
- Isolated restore rehearsals exist (PG16/18). Full production Timescale+PostGIS restore **drill as a scheduled control** is not documented as routine.

**Future invariant for DB mutation (except already-bounded window upserts):**

```text
DB_MUTATION
requires
  BACKUP_RECENCY_PASS
+ ROLLBACK_PLAN_PRESENT
+ HUMAN_APPROVAL
```

| Action class | Rollback mechanism |
|--------------|--------------------|
| Bounded window upsert / recompute | re-run same window (idempotent keys) |
| `ANALYZE` | none required |
| Index create | `DROP INDEX` named object |
| Index drop | recreate from recorded DDL; **requires backup or recorded definition** |
| Migration | new numbered migration + pre-apply `pg_dump`; never re-run applied files |
| Timescale policy | restore previous policy settings (record before change) |
| Railway worker restart | n/a (process) |
| Volume/PITR restore | **human-only**, sibling service; never an agent tool |

`BACKUP_RECENCY_PASS` should later read Railway volume-backup metadata (timestamp, lock, size) **without** creating/restoring, plus an ops ledger of the last verified `pg_dump`. That check does not exist today.

---

## 9. Control-plane options

| | A DIRECT | B BOUNDED_SERVICE | C EXTEND_EXISTING_API |
|--|----------|-------------------|------------------------|
| What | Railway/Vercel/DB creds on Hermes tools | Credentials behind a deterministic client; Hermes gets named tools only | New `/internal/hermes/bounded/v1/…` routes on Repo B |
| Security | Weak — model-adjacent write-capable tokens | Strong | Strong for DB; weaker if Railway tokens land on the **product** API |
| Least privilege | Poor | Good if adapter allowlists queries | Good for DB (SQL never leaves Repo B) |
| Complexity | Lowest | Medium (client module, not a new deployable) | Low–medium (pattern already exists) |
| Maintenance | Drift to CLI | One query allowlist | Same as other bounded families |
| Audit / approval | Must be bolted on | Reuse S0-B effects + approval | Reuse S0-B |
| Credential exposure | High | Low (redact in adapter) | Low for DB; Railway token on API service expands Repo B blast radius |
| Incremental add | Easy, unsafe | Railway/Vercel first-class | DB/coverage natural; platform awkward |

**Recommendation:** do **not** introduce a new deployed microservice.

```text
RECOMMENDED_SHAPE = EXISTING_BOUNDED_PATTERN

DB + coverage + advisor
  → C  extend Repo B bounded HTTP
      (SQL, catalog, gap report already live as scripts)

Railway + Vercel
  → B  standalone Operator-only client
      (same recipe as Tavily / GitHub docs)
      credentials only on Operator Hermes Railway
      allowlisted GraphQL/REST
      strip all secret values before model context

NEVER A
  Railway and Vercel tokens are not read-only
```

`RECOMMENDED_CONTROL_PLANE` in the slice report is **`BOUNDED_SERVICE`**: the existing thin-client + validator + effect policy, with Repo B remaining SoT for data/DB and a new platform client for Railway/Vercel. That is option B as the **shape**, implemented by C where the control plane already exists.

---

## 10. Read / write separation

Keep it small. Do **not** invent a second gateway.

| Layer | Mechanism |
|-------|-----------|
| **OBSERVE** | New toolsets `powerunits_platform_observe`, `powerunits_db_observe` + existing coverage tools. Effect `READ`. Profile `stage1_read_health`. |
| **ADVISE** | Same observe credentials. Effect `READ`. No execute path in the tool. |
| **EXECUTE_SAFE** | Existing bounded execute families + (later) named maintenance ops. Effect `BOUNDED_WRITE`. Profile `stage1_operator_execute` **or** a future `stage1_observe_plus_safe_maint`. Human rule-key approval. |
| **EXECUTE_HIGH_RISK** | No tools registered. Missing `check_fn` → fail closed. |

Prefer **combination**:

1. Separate toolsets (prompt-cache: add only via policy merge / new conversation — do not swap mid-chat).
2. Separate Operator **profiles** (already the live switch).
3. Separate credentials where the provider allows (DB: read-role vs job-role; Railway/Vercel: **cannot** — see §11).
4. Separate Repo B path prefixes (`…/observe/…` vs `…/recompute`) so logs and host-pin stay obvious.

Developer Hermes: none of these credentials.

---

## 11. Secret design (no secrets in this slice)

| Provider | Least-privilege placement | Read-only token? |
|----------|---------------------------|------------------|
| **Railway** | Operator Hermes Railway env only. Narrowest official scope: **project token** for the PowerUnits production environment (`Project-Access-Token`). Not account, not workspace. | **No.** Same token can deploy, mutate variables, create/restore volume backups. **Adapter must allowlist Query fields and refuse all Mutation/Subscription except future approved named ops.** |
| **Vercel** | Operator Hermes env only. Narrowest: **project-scoped access token** for `analytics-app-powerunits` (and a **second** token if landing is in another project). REST, not CLI. | **No.** Project tokens read **and write** that project. Adapter: `GET` allowlist only; never `decrypt=true` on env; return key / target / type / updatedAt. |
| **Production DB** | **Not** in Hermes if Repo B observe routes exist. If a direct Timescale path is ever added beyond the existing one-view tool: dedicated `hermes_observe` role (`SELECT` on allowlisted views/catalog + `pg_stat_*`), separate from job/API writers. | **Yes, Postgres can.** Use it. |

Common rules: not in Git; not in model context; not in tool results; not in logs (existing URL redaction stays). Rotation: replace Operator env vars; no code change. Never copy these into Developer Hermes or R5 pin files (already denylisted).

---

## 12. Audit envelope

Reuse S0-B (`effect_class_for`, `require_powerunits_write_approval`) plus a small durable record for mutations. Do **not** build a new audit product.

```text
timestamp
actor/profile          (Operator Hermes profile + capability tier)
source_session         (gateway session key, not user PII beyond Telegram id policy)
requested_operation    (tool name)
target                 (service / country / table / deployment id)
effect_class
approval_state         (n/a | required | approved | denied)
precondition_results   (host pin, backup recency, window bounds)
result                 (success | refused | error_class)
rollback_reference     (dump SHA / window key / none)
```

Reads: lightweight (existing tool-call log, no secret bodies).  
Mutations: durable (append-only workspace or Repo B ledger row). Never log secret values or full `DATABASE_URL`.

Unclassified operations already fail closed.

---

## 13. Routines (not enabled)

Hermes already has cron, but PowerUnits writes **cannot** be authorized by `cron_mode=approve`. Natural homes:

| Routine | Home | Layer |
|---------|------|-------|
| Daily ingestion / country-coverage anomaly | Operator Hermes cron → existing/new **OBSERVE** tools → workspace export | OBSERVE |
| Weekly DB health + slow-query report | same, after `db-health` routes exist | OBSERVE + ADVISE |
| Deployment regression | platform-observe client | OBSERVE |
| Backup freshness | platform-observe volume-backup **list** only | OBSERVE |

Do not enable cron in 0A. When enabled, cron may **collect and file**, never execute.

---

## 14. Model-routing compatibility

Outputs are already JSON with provenance flags (`bounded_internal_statement`, `hermes_statement`, `external_web_context`). Keep that.

| Work | Future model |
|------|----------------|
| HTTP/SQL collection, redaction, gap arithmetic | code only |
| Daily “3 bullets” | Luna / local |
| “Why is AT thin in 2017?” | Terra |
| Index/planner/architecture | Sol |

Security (gates, allowlists, redaction) does not depend on the model. Do not require Sol for telemetry.

---

## 15. Recommended implementation slices

Three to five slices after this document. No 30-mission roadmap.

1. **`OPERATOR_OBSERVABILITY_1_COUNTRY_COVERAGE`** — Repo B `country-coverage/inspect` + Hermes thin tool. Reuse gap-report + triptychon. No new credentials.
2. **`OPERATOR_OBSERVABILITY_2_DB_HEALTH_READ`** — Repo B observe routes wrapping existing maintenance scripts. Fail closed if `pg_stat_statements` missing. No extension create. Optional later: dedicated `hermes_observe` DB role (human).
3. **`OPERATOR_OBSERVABILITY_3_PLATFORM_OBSERVE`** — Operator-only Railway GraphQL + Vercel REST adapters. Keys/presence only. Human creates **project-scoped** tokens on Operator Hermes only. Trust-boundary review **before** this slice.
4. **`OPERATOR_OBSERVABILITY_4_DB_ADVISOR`** — structured recommendations from (2). `OBSERVE_ONLY` / `PROPOSE_CHANGE` only.
5. **`OPERATOR_OBSERVABILITY_5_WRITE_BOUNDARY`** *(later)* — allowlist of `EXECUTE_SAFE` ops + `BACKUP_RECENCY_PASS`. **Opus review of the write boundary before implementation.**

---

## 16. Trust-boundary call

| Move | Class |
|------|--------|
| Country-coverage + DB-health via **existing** Repo B bearer and new named read routes | **MATERIAL** |
| Railway or Vercel token on Operator Hermes, even query-only | **TRUST_BOUNDARY_CHANGE** (tokens are write-capable) |
| Any new DB write, extension, or platform mutation | **TRUST_BOUNDARY_CHANGE** |
| Giving Developer Hermes any of the above | **Forbidden** |

---

## 17. Human actions after 0A

1. Read this document. Do not create tokens yet.
2. Confirm documented Operator profile (`stage1_read_health`) is still intended.
3. Authorize **slice 1** (country coverage via Repo B) when ready.
4. Defer Railway/Vercel tokens until slice 3’s trust-boundary review.
5. Optional later: create a Postgres `hermes_observe` role; never put it in Developer Hermes.

```text
DEPLOYMENT_PERFORMED = NO
OPUS_REQUIRED_BEFORE = OPERATOR_OBSERVABILITY_5_WRITE_BOUNDARY
```
