# DE bounded outage awareness — read-only Hermes tools (Repo B contract) — operator note v1

## What this is

Hermes tools issue **exactly one** authenticated POST each (**no chaining**, **no SQL**):

| Hermes tool | Repo B route |
|-------------|----------------|
| **`validate_powerunits_outage_awareness_bounded_window`** | **`POST /internal/hermes/bounded/v1/outage-awareness/validate-window`** |
| **`summarize_powerunits_outage_awareness_bounded_window`** | **`POST /internal/hermes/bounded/v1/outage-awareness/summary-window`** |

Repo B aggregates **existing** ingestion outputs (**`outage_country_hourly`**, overlapping **`market_generation_outage_events`**) using the same duplication / coverage ideas as bounded **market-features readiness** where applicable — **Hermes never runs jobs**.

## Explicit non-execution statement

These surfaces **do not**:

- start **outage event ingestion** (ENTSO‑E / Step A pipelines),
- run **`outage_country_hourly_compute`** (or equivalent hourly recompute jobs),
- run **`market_feature_job`**, **`market_driver_feature_job`**, **`expand_market_data`**, or any other Repo B orchestration Hermes exposes as bounded execute paths.

Structured **`checks.suggested_operator_followup`** / **`operator_next`** (if present) are **hints only** — no Hermes automation follows them automatically.

Validate responses should carry **`hermes_statement: read_only_outage_awareness_no_writes`** (or Repo B echoes an equivalent); summaries layer a classifier (`outcome_class`, flags) on top of the same validation envelope.

## Request contract (v1)

JSON body (**`extra=forbid`** on Repo B):

| Field | Rule |
|--------|------|
| **`country_code`** | **DE** only |
| **`version`** | **v1** only |
| **`window_start_utc`** | inclusive, **Z** |
| **`window_end_utc`** | exclusive, **Z** (`[start, end)`) |
| **`pipeline_run_id`** | optional UUID for **`data_pipeline_runs`** echo |

Hermes mirror: **`country`**, **`start`**, **`end`**, **`version`**; optional **`pipeline_run_id`**.

**Slice span:** **≤ 7 calendar days** UTC (same bounded window Hermes validates locally as other ≤7 d DE families).

## Railway / Hermes env

| Variable | Role |
|----------|------|
| **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED`** | **Recommended primary** — enables **both** validate and summary Hermes tools (with URL + bearer). |
| **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES`** | Optional comma ISO2 allowlist when primary is on; unset ⇒ implicit **DE**; empty ⇒ **fail-closed**. |
| **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED`** | Legacy granular validate-only gate (when primary is falsy). |
| **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED`** | Legacy granular summary-only gate (when primary is falsy). |
| **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** | Repo B HTTPS origin (**no** trailing path). |
| **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** | Bearer secret for internal bounded POSTs (**fail-closed** if missing). |
| **`POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S`** | Optional read timeout (**raise** if large windows lag). |

**Telegram (`first_safe_v1`):** toolsets **`powerunits_outage_awareness_bounded_validate`** and **`powerunits_outage_awareness_bounded_summary`** must remain in **`gateway/run.py`** / **`model_tools.py`** / **`docker/apply_powerunits_runtime_policy.py`** allowlists together with other bounded Repo B callers.

## Response shape — validate (operator-oriented)

Repo B authoritative. Expect at minimum:

| Field | Role |
|--------|------|
| **`correlation_id`** | Trace id (Hermes sends **`X-Correlation-ID`**; server may echo). |
| **`hermes_statement`** | e.g. **`read_only_outage_awareness_no_writes`**. |
| **`slice`** | DE / **`v1`** / UTC **`[start, end)`**. |
| **`outcome`** | e.g. **`passed`** / **`warning`** / **`failed`** (classification of data health vs window). |
| **`summary_code`** | Compact machine-stable tag for dashboards. |
| **`warnings`** | Human strings (gaps, partial coverage). |
| **`checks`** | Structured duplicates / hourly coverage / event overlap diagnostics. |
| **`semantics_notes`** | Caveats on revision, aggregation lag, downstream use. |

## Response shape — summary

Adds classifier fields (e.g. **`outcome_class`**, **`flags`**, **`validation`**, **`execution`**, **`caveats`**) aligned with Repo B **`hermes_bounded_entsoe_market_summary`**-style layering — **still read-only**.

## Caveats (read before interpreting features)

1. **Event revision semantics:** ENTSO‑E generation-outage **events can be revised, cancelled, or superseded**; **`market_generation_outage_events`** reflects “as ingested” history — bounded checks flag **overlaps** and **duplicates** but do **not** replay publisher business rules.
2. **Aggregation vs. events:** **`outage_country_hourly`** is a **derived hourly roll-up** (versioned). Gaps in hourly rows can mean “no outage signal” **or** “Step B not run / stale version” — use **`checks`** + **`sum_outage_events_used_count`**-style fields when present.
3. **Downstream features:** Market-feature columns that encode outage may **lag** derived hourly data; **readiness `outage_duplicate_keys`** in market-features bounded paths is a **separate** gate — use remediation planner or market-features validate when that blocks training.
4. **v1 scope:** **DE** + **`v1`** only; no multi-country; no generic SQL or bounded **execute** for outage in Hermes v1.

## Telegram smoke (staging)

1. Set **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED=1`**, base URL + bearer.
2. **`validate_powerunits_outage_awareness_bounded_window`** — `DE`, `v1`, small **`[start, end)`** (e.g. 24 h) → HTTP 200, **`outcome`**, **`checks`**, **`hermes_statement`** present.
3. **`summarize_powerunits_outage_awareness_bounded_window`** — same slice → **`outcome_class`**, nested **`validation`**.
4. Set primary **falsy** (and legacy off) → **`feature_disabled`** — **no** Repo B HTTP from that path.

Rollback: unset primary and legacy flags; no Repo B schema or job side effects.
