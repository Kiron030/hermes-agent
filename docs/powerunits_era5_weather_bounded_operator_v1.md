# Bounded ERA5 weather sync (Hermes + Repo B) — operator note v1

## Country / version

**DE** and **`version=v1`** only — matches Repo B bounded `era5_weather_job` contract (ADR 043).

## Live path (Hermes)

1. `preflight_powerunits_era5_weather_bounded_slice` (local; **recommended:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED`; **legacy:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED`)
2. `execute_powerunits_era5_weather_bounded_slice` → `POST …/era5-weather/recompute`
3. `validate_powerunits_era5_weather_bounded_window` → `POST …/era5-weather/validate-window`
4. `summarize_powerunits_era5_weather_bounded_window` → `POST …/era5-weather/summary-window`

Same **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** as Option D and ENTSO-E bounded routes.

### Coverage-scan v1 (read-only, optional)

Tool: **`scan_powerunits_era5_weather_bounded_coverage_de`** (toolset **`powerunits_era5_weather_bounded_coverage_scan`**) → **`POST …/era5-weather/coverage-scan`**.

- **DE** / **v1**. Range `[scan_start_utc, scan_end_utc)` with **exclusive** end — same **≤ 31 d** span and **≤ 5** contiguous **≤ 7 d** sub-windows as the bounded ERA5 campaign partitioning.
- **Read-only:** **no** `era5_weather_job` / bounded recompute, **no** `market_feature_job`, **no** `market_driver_feature_job`. Response includes **`hermes_statement`: `read_only_scan_no_writes`** and per-sub-window checks on **`weather_country_hourly`** (same semantics as validate-window).
- **`rollup.suggested_next_bounded_action`** is produced by **Repo B only**; Hermes forwards the JSON and does **not** add local remediation suggestions (see tool `hermes_statement` in outputs on parse errors as well).
- Gated separately: **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED`** (plus same base URL and bearer as other bounded ERA5 POSTs).

### Campaign v1 (optional, fail-fast)

Tool: **`campaign_powerunits_era5_weather_bounded_de`** (toolset **`powerunits_era5_weather_bounded_campaign`**).

- Chains **only** bounded `recompute` + `summary-window` per sub-window (same contract as single-slice tools).
- **DE** / **v1**. Range `[campaign_start_utc, campaign_end_utc)` **exclusive end**; span **≤ 31 days**; **≤ 5** contiguous sub-windows each **≤ 7 days**.
- **Fail-fast** on first failed execute (HTTP ≠ 200 or `success: false`) or first unsuccessful summary (`ok` / `ok_with_warnings` rule matches the single-slice summary tool).
- **Does not** invoke `market_feature_job`, `market_driver_feature_job`, or `expand_market_data`.

## What was **not** auto-triggered

After a **successful** bounded ERA5 execute, Repo B runs **`era5_weather_job` only**.

- **`market_feature_job`** was **NOT** auto-run.
- **`market_driver_feature_job`** was **NOT** auto-run.

**Next manual step** if weather-dependent **`market_features_hourly`** should be updated for **DE**: use bounded Hermes **`execute_powerunits_market_features_bounded_de_slice`** (toolsets + **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*`** — **not** PL Option D) pointing at the same Repo B **`/market-features-hourly/recompute`** with **`country_code=DE`**, or run **`market_feature_job`** via Repo B worker/runbook/CLI. Bounded **Option D execute** remains **PL-only** and does **not** cover DE.

## Slice rules (v1)

- `country_code` = **DE**, `version` = **v1**
- `window_start_utc` inclusive, `window_end_utc` exclusive, duration **> 0** and **≤ 7 days** UTC

## Railway / Hermes env

**Recommended:** **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED=1`**. Optionally **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES`** (same semantics as ENTSO‑E primary allowlist above). Primary unset ⇒ **legacy** per-step `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_{PREFLIGHT,EXECUTE,VALIDATE,SUMMARY}_ENABLED` unchanged.

| Variable | Execute | Validate | Summary | Coverage-scan | Preflight |
|----------|---------|----------|---------|---------------|-----------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ | ✓ | ✓ | ✓ | — |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ | ✓ | ✓ | ✓ | — |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | optional | optional | optional | optional | — |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED` | ✓ | ✓ | ✓ | | ✓ |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES` | optional † | optional † | optional † | | optional † |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED` (legacy) | ✓ | | | | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED` (legacy) | | ✓ | | | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED` (legacy) | | | ✓ | | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED` (legacy) | | | | | ✓ |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED` | | | | ✓ | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED` | ✓‡ | | ✓‡ | | |

† Primary path only; ignored on legacy-only configs.

‡ **Campaign** requires this flag **and** **execute + summary** eligibility via **primary** or both legacy execute+summary flags, plus base URL and bearer.

**Telegram / first_safe:** toolsets must appear in `gateway/run.py` `_POWERUNITS_ALLOWED_TELEGRAM_TOOLSETS`, `model_tools.py` `_POWERUNITS_ALLOWED_TOOLSETS`, and `docker/apply_powerunits_runtime_policy.py` `ALLOWED_TELEGRAM_TOOLSETS` (policy apply).

## Repo B prerequisites (execute)

CDS credentials and object storage / DB settings live on **Repo B** (API service). See Repo B ADR 010/011/043 and `era5_weather_job` — Hermes only forwards the bounded HTTP request.

## Validate read target

Repo B validate may read **`weather_country_hourly`** from **primary** or **Timescale** depending on **`ERA5_WEATHER_WRITE_TARGET`** and **`DATABASE_URL_TIMESCALE`** on the API — Hermes surfaces Repo B’s `read_target` field in the JSON response.
