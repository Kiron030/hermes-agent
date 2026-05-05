# Bounded ENTSO-E forecast ingest (Hermes + Repo B) — operator note v1

This family is **forecast ingest only**. It is **not** realized ENTSO‑E market sync (`…/entsoe-market-sync/*`), **not** `market_features_hourly`, **not** `market_driver_features_hourly`, **not** `expand_market_data`.

## Country / version

**Repo B bounded v1:** Tier‑1 ISO2 **`DE`**, **`NL`**, **`BE`**, **`FR`**, **`AT`**, **`CZ`**, **`PL`**, **`FI`**; **`version=v1`** — matches Repo B `entsoe_forecast_job` slice contract (**Hermes mirrors** the same allowlist for local preflight + **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES`** narrowing when primary is on).

European expansion sequencing (paired with market; planning-only taxonomy) mirrors Repo B **ADR 045** and **`hermes_bounded_entsoe_candidate_readiness_matrix_v1`**.

## Live path (Hermes)

1. `preflight_powerunits_entsoe_forecast_bounded_slice` (local JSON; **recommended:** `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED`; **legacy:** `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_PREFLIGHT_ENABLED`)
2. `execute_powerunits_entsoe_forecast_bounded_slice` → **`POST`** `…/entsoe-forecast/recompute`
3. `validate_powerunits_entsoe_forecast_bounded_window` → **`POST`** `…/entsoe-forecast/validate-window`
4. `summarize_powerunits_entsoe_forecast_bounded_window` → **`POST`** `…/entsoe-forecast/summary-window`

Same **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** as other bounded Repo B Hermes POSTs.

There is **no** bounded `readiness-window` for forecasts in v1 — validate/summary are grounded in normalized forecast tables only.

## What was **executed** vs **not** executed

**After execute:** Repo B runs **`entsoe_forecast_job.run`** only (bounded slice Repo B Tier‑1 ISO2 **`DE`/`NL`/`BE`/`FR`/`AT`/`CZ`/`PL`/`FI`**, **v1**, `[window_start_utc, window_end_utc)` exclusive end, **≤ 7 days** UTC).

**Not executed** by this family (Hermes forwards **one POST** per step; **no hidden orchestration**):

- **`entsoe_market_job`**
- **`market_feature_job`**
- **`market_driver_feature_job`**
- **`expand_market_data`**
- **`era5_weather_job`**

Response bodies may echo **`downstream_not_auto_triggered`** and an **`operator_statement`** — treat those as authoritative for “what Repo B did not chain.”

## Slice rules (v1)

- `window_start_utc` **inclusive**, `window_end_utc` **exclusive**, duration **> 0** and **≤ 7 days** UTC
- Bounded HTTP body uses the same **`correlation_id`** / pipeline echo conventions as ENTSO‑E market bounded routes where Repo B emits them.

## Railway / Hermes env

**Recommended:** **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED=1`**.

Optional **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES`** (comma-separated ISO2). **Unset** ⇒ Hermes permits the **full mirrored Repo B Tier‑v1 bundle** (**`DE,NL,BE,FR,AT,CZ,PL`**) per-request; **empty string** ⇒ **fail-closed** when primary is truthy. Set a comma subset only when deliberately **narrowing** outbound traffic beneath that mirror (never beyond Repo B).

When primary is falsy/unset, per-step **legacy** flags still apply (no broadening vs pre-consolidation):

- `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_PREFLIGHT_ENABLED`
- `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_EXECUTE_ENABLED`
- `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED`
- `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_SUMMARY_ENABLED`

| Variable | Execute | Validate | Summary | Preflight |
|----------|---------|----------|---------|-----------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ | ✓ | ✓ | — |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ | ✓ | ✓ | — |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | optional | optional | optional | — |
| `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED` | ✓ | ✓ | ✓ | ✓ |
| `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES` | optional † | optional † | optional † | optional † |
| Legacy `…_EXECUTE_ENABLED` | ✓ | | | |
| Legacy `…_VALIDATE_ENABLED` | | ✓ | | |
| Legacy `…_SUMMARY_ENABLED` | | | ✓ | |
| Legacy `…_PREFLIGHT_ENABLED` | | | | ✓ |

† Applies when primary is truthy; ignored if you rely on legacy-only gating.

**Telegram / first_safe:** toolsets must be allowed in `gateway/run.py`, `model_tools.py`, and `docker/apply_powerunits_runtime_policy.py` (same pattern as ERA5 / ENTSO‑E market bounded).

## Repo B prerequisites (execute)

ENTSO‑E API credentials and DB settings live on Repo B (Hermes **does not** hold `ENTSOE_API_KEY`; it only POSTs with the Hermes-internal bearer).

## Validate / summary read targets

Read-only counts are against normalized tables on Repo B **primary** app DB:

- **`market_entsoe_load_forecast_hourly`**
- **`market_entsoe_wind_solar_forecast_hourly`**

Hermes **`validate_powerunits_entsoe_forecast_bounded_window`** (**not** **`validate_powerunits_entsoe_market_bounded_window`**) issues **`POST …/entsoe-forecast/validate-window`** only — not **`market_demand_hourly`**, **`market_prices_day_ahead`**, or **`market_generation_by_type_hourly`** (those belong to **`…/entsoe-market-sync/validate-window`**).

Responses include **`row_count`**, **`distinct_timestamps`** (delivery hour starts), **`min_timestamp`**, **`max_timestamp`**, duplicate-key style checks where applicable (`load`: `row_count == distinct` on PK implied keys; wind/solar: duplicates per **`(country_code, delivery_start_utc, technology, version)`** buckets), plus **`checks.normalized_time_grain`** and **`checks.semantics_notes`** (forecast vs realized metered, long-format generation, `forecast_issue_utc` caveats).

## Caveats

- **Grain:** Forecast rows are UTC **delivery hour buckets** (`delivery_start_utc`); ENTSO‑E may publish finer resolution upstream — ingest averages to hourly **`forecast_*_mw`** per Repo B job semantics.
- **Horizon / issue time:** `forecast_issue_utc` may be NULL in production; **`fetched_at_utc`** captures pull timing — see Repo B **`docs/operations/spike_entsoe_forecast_issue_time_xml.md`** (if present in that repo).
- **Upstream:** Bounded execute success still depends on ENTSO‑E API availability and entitlements on Repo B.
