# Option D — PL / one UTC day / `market_features_hourly` staging write (Go/No-Go fact sheet v1)

**Status:** Combines **read-only synthesis** from Repo B sources with a **recorded** first controlled write experiment (human-run, not Hermes). **Hermes Stage 1** stays read-only; **no** Hermes writer in this path.

**Sources used:** `apply_market_pipeline_schema_to_timescale`, `wave1_country_readiness_it_pl_se`, `implementation_state`, `job_market_feature` (`market_feature_job.py`), ADR 013 hybrid, `runbook` § market feature job. **`ddl_011_create_market_features_hourly`** — use `read_repo_b_key` on deploy (file blocked in some local workspaces by ignore rules).

---

## Controlled write experiment #1 (executed — human, not Hermes)

| Field | Value |
|-------|--------|
| **Scope** | `country_code=PL`, `version=v1`, UTC window **`[2024-01-01T00:00:00Z, 2024-01-02T00:00:00Z)`** (end exclusive) — **one** calendar day only. |
| **Command class** | `uv run python -m services.data_ingestion.jobs.market_feature_job` from Repo B `backend/` with **`MARKET_FEATURES_WRITE_TARGET=timescale`** set in the shell (no code change). Args: `--version v1 --countries PL --start 2024-01-01T00:00:00Z --end 2024-01-02T00:00:00Z`. |
| **Target write path** | `public.market_features_hourly` on **`DATABASE_URL_TIMESCALE`** (delete-in-window + upsert per job implementation). |
| **Result summary** | `status=success`, **`rows_written=24`**, `write_target=timescale`, `error_count=0` (run id logged by job / pipeline). |
| **Post-check result** | Slice **`COUNT(*)=24`**, **24** distinct UTC hours, **0** duplicate groups on `(country_code, timestamp_utc, version)`; spot-check first hours showed plausible numeric columns. |
| **Rollback** | Predicate documented below; **not** executed after success. |
| **Conclusion** | For this **narrow slice**, the **technical path** (primary reads + Timescale writes via existing job) is **proven** once preflight inputs were complete. Next design step = **bounded wrapper or DB capsule** for repeatability and future Hermes gating — see **`docs/powerunits_option_d_next_write_capsule_step_v1.md`**. |

---

## Fact sheet (staging-only, human-run experiment design)

| Field | Fact |
|-------|------|
| **Target object** | `public.market_features_hourly` on the DB selected by **`MARKET_FEATURES_WRITE_TARGET`** when set to **`timescale`** (connection **`DATABASE_URL_TIMESCALE`**). |
| **Write mode** | Job path: **`delete_stale_feature_rows`** (DELETE for `version` + `country_code` list + `[ts_min, ts_max)` on write connection) then **`INSERT … ON CONFLICT … DO UPDATE`** (`upsert_features`). |
| **Conflict / upsert key** | **`(country_code, timestamp_utc, version)`** — explicit in `market_feature_job.py` SQL. |
| **Likely PL one-day row count** | **Up to 24** rows for `[start, end)` = one UTC calendar day **if** hourly inputs support a full grid (`runbook`: “24 Zeilen/Tag pro Land” for features). **Fewer** if normalized/weather inputs have gaps. |
| **Minimal prerequisite inputs** (read from **`get_app_db_url()`** / primary — **not** from Timescale in current `run()` code) | `market_demand_hourly`, `market_generation_by_type_hourly`, `weather_country_hourly` for `PL` + chosen `version` (+ optional `outage_country_hourly` / border flows per migrations — see `implementation_state` chain). |
| **Schema facts** | **Confirmed:** `011_create_market_features_hourly.sql` is **in** the canonical Timescale DDL list **after** `010`, before weather/driver/view stack; **`017`** indexes run **last** (`apply_market_pipeline_schema_to_timescale.py`). **Uncertain until live check:** relation exists on **your** staging Timescale URL, hypertable/PK matches repo DDL (read `ddl_011_*` via Repo B read or `\d+` / `verify_timescale_worker_schema.py`). |
| **PL-specific caveats** (`wave1_country_readiness_it_pl_se`) | Day-ahead: **ISO2 passthrough** (no `COUNTRY_TO_PRICE_AREA` map); reference area `10YPL-AREA-----S`. **DE↔PL** is in default cross-border flow scope; empty flow series can be OK. Operational truth for full soak = **env** (`ARCHIVE_COUNTRIES` includes PL), not repo defaults alone. |
| **Pre-write validation** | (1) Confirm URLs: staging **`DATABASE_URL`** and **`DATABASE_URL_TIMESCALE`** (non-prod fingerprint). (2) On **primary**: counts / min-max `timestamp_utc` for PL + `version` in `market_demand_hourly`, `market_generation_by_type_hourly`, `weather_country_hourly` over `[start,end)` — target **24** distinct hours if full day. (3) On **Timescale**: table exists; unique constraint compatible with upsert (verify via DDL read or `\d+`). (4) DDL apply script has been run on that Timescale URL **or** dry-run reviewed. |
| **Post-write validation** | (1) `COUNT(*)` on Timescale `market_features_hourly` for PL + `version` + window equals **expected** (≤24). (2) No duplicate `(country_code,timestamp_utc,version)`. (3) Spot-check non-null core columns vs inputs. |
| **Rollback shape** | Same predicate as job delete: `DELETE FROM public.market_features_hourly WHERE version = $v AND country_code = 'PL' AND timestamp_utc >= $start AND timestamp_utc < $end` (adjust `country_code` filter if multi-country run). |
| **Safest provisional execution path** | **Human** from repo root / `backend`: set **`MARKET_FEATURES_WRITE_TARGET=timescale`** + valid **`DATABASE_URL_TIMESCALE`**, then `uv run python -m services.data_ingestion.jobs.market_feature_job --version v1 --countries PL --start <day>T00:00:00Z --end <day+1>T00:00:00Z` (`runbook`). **Hermes stays read-only** until separate Stage-2 gates. |

---

## Confirmed vs uncertain

### Confirmed (from cited sources + job code)

- Feature table name and job ownership; job order relative to ENTSO-E / ERA5 in `implementation_state`.
- Upsert key and delete-before-upsert behavior in code.
- Reads always from **`get_app_db_url()`**; Timescale connection **only** for writes when target is `timescale`.
- Timescale DDL application order includes `011` and ends with `017`.
- PL Wave-1 operational notes (passthrough prices, DE–PL flows, env-first truth).
- ADR 013: additive Timescale, validation before route switches — aligns with **staging-first** posture.

### Uncertain / must be verified **outside** this synthesis (and outside Hermes if no DB access)

- **Live staging Timescale:** whether `market_features_hourly` + constraints actually match repo DDL (migration applied, drift absent).
- **Chosen calendar day:** whether primary inputs yield **24** computable hours for PL + `version`.
- **Org “done” definition:** whether `market_driver_feature_job` must run after the feature write for the experiment to count as success.

---

## Go / No-Go judgment (staging-only, human-run)

**Pre-execution (design-time):** **No-Go** until URL fingerprint, primary **24h** inputs, and Timescale schema/duplicate checks are green — see fact sheet above.

**Post experiment #1:** For the **executed** slice, preflight + post-checks were **green**; treat that run as **evidence** that the job path works for that day — **not** a blanket license for other days/countries without repeating checks.

---

## Rollback SQL (slice #1 — execute only if operator explicitly requests)

```sql
DELETE FROM public.market_features_hourly
WHERE version = 'v1'
  AND country_code = 'PL'
  AND timestamp_utc >= '2024-01-01T00:00:00+00:00'::timestamptz
  AND timestamp_utc <  '2024-01-02T00:00:00+00:00'::timestamptz;
```

---

## Related (next design step)

- **`docs/powerunits_option_d_next_write_capsule_step_v1.md`** — bounded wrapper vs procedure capsule; **still no** Hermes writer activation.

*Version v1 — experiment #1 appended 2026; amend when additional slices are recorded or policy changes.*
