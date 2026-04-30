# Bounded ERA5 weather sync (Hermes + Repo B) — operator note v1

## Country / version

**DE** and **`version=v1`** only — matches Repo B bounded `era5_weather_job` contract (ADR 043).

## Live path (Hermes)

1. `preflight_powerunits_era5_weather_bounded_slice` (local; `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED`)
2. `execute_powerunits_era5_weather_bounded_slice` → `POST …/era5-weather/recompute`
3. `validate_powerunits_era5_weather_bounded_window` → `POST …/era5-weather/validate-window`
4. `summarize_powerunits_era5_weather_bounded_window` → `POST …/era5-weather/summary-window`

Same **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** as Option D and ENTSO-E bounded routes.

## What was **not** auto-triggered

After a **successful** bounded ERA5 execute, Repo B runs **`era5_weather_job` only**.

- **`market_feature_job`** was **NOT** auto-run.
- **`market_driver_feature_job`** was **NOT** auto-run.

**Next manual step** if weather-dependent **`market_features_hourly`** should be updated: use **bounded Option D** Hermes tools (`preflight_powerunits_option_d_bounded_slice` → execute → validate → summary) for the same slice, or the Repo B runbook path for `market_feature_job`.

## Slice rules (v1)

- `country_code` = **DE**, `version` = **v1**
- `window_start_utc` inclusive, `window_end_utc` exclusive, duration **> 0** and **≤ 7 days** UTC

## Railway / Hermes env

| Variable | Execute | Validate | Summary | Preflight |
|----------|---------|----------|---------|-----------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ | ✓ | ✓ | — |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ | ✓ | ✓ | — |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | optional | optional | optional | — |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED` | ✓ | | | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED` | | ✓ | | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED` | | | ✓ | |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED` | | | | ✓ |

**Telegram / first_safe:** toolsets must appear in `gateway/run.py` `_POWERUNITS_ALLOWED_TELEGRAM_TOOLSETS`, `model_tools.py` `_POWERUNITS_ALLOWED_TOOLSETS`, and `docker/apply_powerunits_runtime_policy.py` `ALLOWED_TELEGRAM_TOOLSETS` (policy apply).

## Repo B prerequisites (execute)

CDS credentials and object storage / DB settings live on **Repo B** (API service). See Repo B ADR 010/011/043 and `era5_weather_job` — Hermes only forwards the bounded HTTP request.

## Validate read target

Repo B validate may read **`weather_country_hourly`** from **primary** or **Timescale** depending on **`ERA5_WEATHER_WRITE_TARGET`** and **`DATABASE_URL_TIMESCALE`** on the API — Hermes surfaces Repo B’s `read_target` field in the JSON response.
