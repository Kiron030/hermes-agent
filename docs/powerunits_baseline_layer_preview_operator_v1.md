# Bounded baseline layer-coverage preview (Hermes + Repo B) — operator note v1

## Country / version / window

- **DE** only, **`version=v1`** (matches Repo B bounded `baseline/layer-coverage-preview`).
- Single contiguous slice `[preview_start_utc, preview_end_utc)` with **exclusive** end — span **≤ 31 days** (**not** the ERA5/ENTSO-E campaign 5×7d partitioning).

## Live path (Hermes)

Tool: **`preview_powerunits_baseline_layer_coverage_de`** (toolset **`powerunits_baseline_layer_preview`**) → **`POST …/baseline/layer-coverage-preview`**.

### Read-only contract

- Hermes performs **no** SQL; **one** Repo B POST with Bearer auth.
- **No** ingestion jobs ran from this tool (no `entsoe_market_job`, `era5_weather_job`, `market_feature_job`, `market_driver_feature_job`, etc.).
- **No** campaigns started; **no** `expand_market_data` executed.
- Repo B **`hermes_statement`** is typically **`read_only_baseline_preview_no_jobs`**.
- **`rollup.suggested_next_bounded_action`** is produced **by Repo B only**; Hermes forwards JSON and adds no local remediation list.

### Response highlights (parsed from Repo B when HTTP 200)

`scanner`, `slice`, `expected_hours`, `baseline_gate_criteria`, `model_dataset_read_pilot`, `read_target_note`, `baseline_ready_preview`, `baseline_readiness_reason`, `baseline_readiness_detail`, `semantics_notes`, `layers_country`, and **`rollup`** (`scan_outcome`, `missing_layers`, `weak_layers`, `suggested_next_bounded_action`).

## Railway / Hermes env

| Variable | Baseline preview |
|----------|------------------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | optional |
| **`HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED`** | ✓ (must be truthy) |

**Telegram / first_safe:** ensure toolset appears in `gateway/run.py` `_POWERUNITS_ALLOWED_TELEGRAM_TOOLSETS`, `model_tools.py` `_POWERUNITS_ALLOWED_TOOLSETS`, and `docker/apply_powerunits_runtime_policy.py` `ALLOWED_TELEGRAM_TOOLSETS` when using policy apply.

## Telegram smoke sequence (staging)

After Repo B exposes the route and secrets match:

1. Set **`HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED=1`** (and bounded base URL + bearer on Hermes).
2. In Telegram, ask the analyst to invoke **`preview_powerunits_baseline_layer_coverage_de`** with a **≤31d** DE window, e.g. `preview_start_utc` / `preview_end_utc` = one week in ISO Z.
3. Expect JSON with **`preview_attempted: true`**, **`http_ok: true`**, **`baseline_ready_preview`** and **`rollup.scan_outcome`**, and Repo B **`hermes_statement`** echoing **read-only / no jobs** semantics.
4. Flip flag off → tool should fail closed with **`error_code`: `feature_disabled`** (no HTTP).

## Repo B prerequisites

Aggregation and pilot routing depend on Repo B **`DATABASE_URL`**, expand-aligned coverage helpers, and optional Timescale pilots — see Repo B **`docs/operations/ACCESS_MATRIX.md`** (baseline preview row).

## Scaling beyond DE (later)

Prefer a **suffix or country-parameter tool** gated per release (e.g. `_de` stays explicit) plus shared slice-validator modules on both repos; avoid reusing ERA5 campaign partition rules for baseline preview (`collection_enriched_coverage_layers` is one window).
