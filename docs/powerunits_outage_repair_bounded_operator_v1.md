# DE bounded outage repair execute (Hermes + Repo B) — operator note v1

## What this is (vs. outage awareness)

| Concern | Hermes surface | Repo B routes |
|---------|----------------|----------------|
| **Read-only diagnostics** | `validate_powerunits_outage_awareness_bounded_window`, `summarize_powerunits_outage_awareness_bounded_window` | `…/outage-awareness/validate-window`, `…/summary-window` |
| **Bounded repair writes** | `execute_powerunits_outage_repair_bounded_slice` | **`POST`** `…/outage-repair/recompute` |

Repair runs **exactly**:

1. **Step A** — **`entsoe_generation_outage_sync`** → `market_generation_outage_events` (+ optional RAW / bucket per job config).
2. **Step B** — **`outage_country_hourly_compute`** → `outage_country_hourly`.

**Hermes performs no SQL** — one authenticated HTTP POST — same secret model as other bounded internal executes.

### Explicit non-goals on success

Repair **does not** run:

- **`market_feature_job`** (no refreshed nullable outage merge into `market_features_hourly`),
- **`market_driver_feature_job`**, **`expand_market_data`**, or **`entsoe_market_job`**.

Echo field **`downstream_not_auto_triggered`** on Repo B JSON lists **`market_feature_job`**, **`market_driver_feature_job`**, **`expand_market_data`** (see live response).

## Request contract (`POST …/outage-repair/recompute`)

| Field | Rule |
|--------|------|
| **`country_code`** | **DE** only |
| **`version`** | **v1** only |
| **`window_start_utc`** | inclusive, **Z** |
| **`window_end_utc`** | exclusive (**`[start, end)`**) |
| JSON | **`extra=forbid`** on Repo B |

Hermes mirrors `country`, `start`, `end`, `version` local validation (≤ **7 calendar days**, same as outage awareness bounded v1).

## Railway / Hermes env

| Variable | Role |
|---------|------|
| **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED`** | Recommended **primary** (execute-only family). |
| **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES`** | Optional; unset ⇒ implicit **DE**; empty ⇒ fail-closed with primary **on**. |
| **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED`** | Legacy execute-only gate (when primary falsy). |
| **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`**, **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** | Required for Repo B HTTPS + Bearer. |

**Awareness stays separate:** **`HERMES_POWERUNITS_OUTAGE_AWARENESS_*`** does **not** enable repair.

## Planner / remediation sequencing (read-only planner)

Repo B **`plan_powerunits_de_stack_remediation`** (`…/remediation/de-stack-plan`) includes **`generation_outages`** in **`family_states`**. When outage data appears **missing/stale** for bounded interpretation (aggregated outage-awareness summaries across ≤7 d chunks), **`recommended_sequence`** may list **`execute_powerunits_outage_repair_bounded_slice`** **before** **`execute_powerunits_market_features_bounded_de_slice`**. Duplicate hourly merge-keys instead suggest **`validate_powerunits_outage_awareness_bounded_window`** (repair does **not** deduplicate safely).

Market-features bounded execute still precedes driver bounded execute (**unchanged dependency**).

## Design note: one bounded action vs two

**v1 uses one composite POST (`recompute`):** sequential Step A→B mirrors production backfill **`ops/backfill_entsoe_outages`** for **`skip_features`**, minimizes partial states where events changed but **`outage_country_hourly`** was not rebuilt in the **same HTTP request**. Separate Step-A-only / Step-B-only routes would invite operator ordering mistakes; revisit only if ENTSO‑E rate limits mandate explicit split operations.

## Telegram smoke

1. **Awareness validate** (`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED`) — confirm gap/stale **summary_code**.
2. **Repair execute** (`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED=1`) — small **`[start, end)`** → **`success`**, **`step_a`** / **`step_b`** payloads, **`hermes_statement: bounded_outage_repair_step_a_b_executed`**.
3. Re-run awareness validate/summary → coverage moves toward **passed** where data allows (**not guaranteed** — ENTSO‑E API gaps, duplicates).
4. **Planner** unchanged read-only semantics — **`tool_hint_hermes`** hints only.

Rollback: falsify **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_*`** — Hermes drops execute; Repo B routes remain dormant without Railway secret exposure.
