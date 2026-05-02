# Bounded ENTSO-E market sync (Hermes + Repo B) — operator note v1

## Country

**Bounded v1 ISO2 set (Repo B authoritative):** **`DE`** and **`NL`**. Hermes mirrors this set in code; optional
`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES` intersects per request when the family **primary** flag is on (**unset ⇒ implicit `DE` only** for that intersection; **empty string ⇒ primary path fail-closed**). Legacy per-step flags ignore the allowlist.

## Live path (Hermes)

1. `preflight_powerunits_entsoe_market_bounded_slice` (local; **recommended:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`; **legacy:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED`)
2. `execute_powerunits_entsoe_market_bounded_slice` → `POST …/entsoe-market-sync/recompute`
3. `validate_powerunits_entsoe_market_bounded_window` → `POST …/entsoe-market-sync/validate-window`
4. `summarize_powerunits_entsoe_market_bounded_window` → `POST …/entsoe-market-sync/summary-window`

Same **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** as Option D bounded routes.

### Coverage-scan v1 (read-only, optional)

Tool: **`scan_powerunits_entsoe_market_bounded_coverage_de`** (toolset **`powerunits_entsoe_market_bounded_coverage_scan`**) → **`POST …/entsoe-market-sync/coverage-scan`**.

- **Repo B Tier v1 **`DE`** / **`NL`**, **v1**. Range `[scan_start_utc, scan_end_utc)` with **exclusive** end — same **≤ 31 d** span and **≤ 5** contiguous **≤ 7 d** sub-windows as the bounded campaign partitioning.
- **Read-only**: no `entsoe_market_job`, no bounded recompute path, no downstream feature jobs — response includes **`hermes_statement`: `read_only_scan_no_writes`** and per-sub-window checks on `market_demand_hourly`, `market_prices_day_ahead`, `market_generation_by_type_hourly`.
- Gated separately: **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED`** (plus same base URL and bearer as bounded validate/summary/campaign POSTs).

### Campaign v1 (optional, fail-fast)

Tool: **`campaign_powerunits_entsoe_market_bounded_de`** (requires toolset `powerunits_entsoe_market_bounded_campaign`).

- Chains the **existing** execute + summary bounded HTTP paths for each sub-window only (no Repo B orchestration changes).
- **Repo B Tier v1 **`DE`** / **`NL`**, **v1** only (per-slice `country_code`). Campaign range `[campaign_start_utc, campaign_end_utc)` with **exclusive end**; **total span ≤ 31 days**; split into **contiguous** sub-windows each **≤ 7 days** (**≤ 5** sub-windows).
- **Fail-fast:** stops on the first non-success execute (HTTP ≠ 200 or `success: false`) or on the first unsuccessful summary (same criteria as the single-slice summary tool).
- **Non-goals:** does **not** call `market_feature_job`, `market_driver_feature_job`, `expand_market_data`, or open countries outside the Repo B bounded v1 set.

## Slice rules (v1)

- `country_code` ∈ {**`DE`**, **`NL`**}, `version` = **v1**
- `window_start_utc` inclusive, `window_end_utc` exclusive, duration **≤ 7 days** UTC

## Railway / Hermes env

**Recommended (fewer Railway variables):** set **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED=1`**. Optionally **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`** (comma ISO2, subset of Repo B **`DE`**/**`NL`**; **unset ⇒ implicit `DE` only** for the Hermes intersection on the primary path; **explicitly empty ⇒ fail-closed**). When the primary flag is unset/falsy, each step still honors its **legacy** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_{PREFLIGHT,EXECUTE,VALIDATE,SUMMARY}_ENABLED` — legacy ignores the allowlist (**no broadening** vs pre-consolidation behavior).

| Variable | Execute | Validate | Summary | Coverage-scan | Preflight |
|----------|---------|----------|---------|---------------|-----------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ | ✓ | ✓ | ✓ | — |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ | ✓ | ✓ | ✓ | — |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED` | ✓ | ✓ | ✓ | | ✓ |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES` | optional † | optional † | optional † | | optional † |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED` (legacy) | ✓ | | | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED` (legacy) | | ✓ | | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED` (legacy) | | | ✓ | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED` (legacy) | | | | | ✓ |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED` | | | | ✓ | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED` | ✓‡ | | ✓‡ | | |

† Applies **only** when **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`** is truthy (primary path); ignored if you use legacy per-step flags only.

‡ **Campaign** (`campaign_powerunits_entsoe_market_bounded_de`) requires this flag **and** bounded **execute + summary** eligibility: either **primary** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED` (with allowlist not **explicitly empty**) **or** both legacy **`…_EXECUTE_ENABLED`** and **`…_SUMMARY_ENABLED`**, plus base URL and bearer. With primary + unset allowlist, effective Hermes narrowing is **`DE`** only until you add e.g. **`DE,NL`**.

Repo B API must have **`ENTSOE_API_KEY`** or **`ENTSOE_API_TOKEN`** for execute to succeed.

## Validate caveat (v1)

Validate counts run against **primary** `DATABASE_URL` only. If normalized ENTSO-E tables are written to Timescale per env, counts may look empty until a follow-up read-target alignment.

## Count semantics (validate / summary)

- **Raw ENTSO-E** load, prices, and generation can arrive **sub-hourly** (e.g. 15-minute).
- The bounded **`entsoe_market_job`** path still **writes UTC hour buckets** to `market_demand_hourly`, `market_prices_day_ahead`, and `market_generation_by_type_hourly` (see Repo B `entsoe_to_market` + ADR 042).
- **Generation** is **long-format** (one row per hour **per `technology_group`**), so **`row_count` ≫ `distinct_timestamps`** is expected.
- Repo B responses include **`checks.normalized_time_grain`** (`utc_hour_bucket`) and **`checks.semantics_notes`**. A large **`distinct_timestamps`** means many distinct hour starts in the filter window — **not** “quarter-hour rows persisted as the intended grain” of those hourly target tables.
