# Bounded ENTSO-E market sync (Hermes + Repo B) — operator note v1

## Country

**DE** only in v1: matches `entsoe_market_job` defaults and the most exercised ingest path in this repo.

## Live path (Hermes)

1. `preflight_powerunits_entsoe_market_bounded_slice` (local; `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED`)
2. `execute_powerunits_entsoe_market_bounded_slice` → `POST …/entsoe-market-sync/recompute`
3. `validate_powerunits_entsoe_market_bounded_window` → `POST …/entsoe-market-sync/validate-window`
4. `summarize_powerunits_entsoe_market_bounded_window` → `POST …/entsoe-market-sync/summary-window`

Same **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** as Option D bounded routes.

### Campaign v1 (optional, fail-fast)

Tool: **`campaign_powerunits_entsoe_market_bounded_de`** (requires toolset `powerunits_entsoe_market_bounded_campaign`).

- Chains the **existing** execute + summary bounded HTTP paths for each sub-window only (no Repo B orchestration changes).
- **DE** / **v1** only. Campaign range `[campaign_start_utc, campaign_end_utc)` with **exclusive end**; **total span ≤ 31 days**; split into **contiguous** sub-windows each **≤ 7 days** (**≤ 5** sub-windows).
- **Fail-fast:** stops on the first non-success execute (HTTP ≠ 200 or `success: false`) or on the first unsuccessful summary (same criteria as the single-slice summary tool).
- **Non-goals:** does **not** call `market_feature_job`, `market_driver_feature_job`, `expand_market_data`, or multi-country logic.

## Slice rules (v1)

- `country_code` = **DE**, `version` = **v1**
- `window_start_utc` inclusive, `window_end_utc` exclusive, duration **≤ 7 days** UTC

## Railway / Hermes env

| Variable | Execute | Validate | Summary | Preflight |
|----------|---------|----------|---------|-----------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ | ✓ | ✓ | — |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ | ✓ | ✓ | — |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED` | ✓ | | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED` | | ✓ | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED` | | | ✓ | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED` | | | | ✓ |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED` | ✓† | | ✓† | |

† **Campaign** (`campaign_powerunits_entsoe_market_bounded_de`) requires this flag **and** both `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED` and `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED` truthy, with the same base URL and bearer.

Repo B API must have **`ENTSOE_API_KEY`** or **`ENTSOE_API_TOKEN`** for execute to succeed.

## Validate caveat (v1)

Validate counts run against **primary** `DATABASE_URL` only. If normalized ENTSO-E tables are written to Timescale per env, counts may look empty until a follow-up read-target alignment.

## Count semantics (validate / summary)

- **Raw ENTSO-E** load, prices, and generation can arrive **sub-hourly** (e.g. 15-minute).
- The bounded **`entsoe_market_job`** path still **writes UTC hour buckets** to `market_demand_hourly`, `market_prices_day_ahead`, and `market_generation_by_type_hourly` (see Repo B `entsoe_to_market` + ADR 042).
- **Generation** is **long-format** (one row per hour **per `technology_group`**), so **`row_count` ≫ `distinct_timestamps`** is expected.
- Repo B responses include **`checks.normalized_time_grain`** (`utc_hour_bucket`) and **`checks.semantics_notes`**. A large **`distinct_timestamps`** means many distinct hour starts in the filter window — **not** “quarter-hour rows persisted as the intended grain” of those hourly target tables.
