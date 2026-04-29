# Bounded ENTSO-E market sync (Hermes + Repo B) — operator note v1

## Country

**DE** only in v1: matches `entsoe_market_job` defaults and the most exercised ingest path in this repo.

## Live path (Hermes)

1. `preflight_powerunits_entsoe_market_bounded_slice` (local; `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED`)
2. `execute_powerunits_entsoe_market_bounded_slice` → `POST …/entsoe-market-sync/recompute`
3. `validate_powerunits_entsoe_market_bounded_window` → `POST …/entsoe-market-sync/validate-window`
4. `summarize_powerunits_entsoe_market_bounded_window` → `POST …/entsoe-market-sync/summary-window`

Same **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** as Option D bounded routes.

## Slice rules (v1)

- `country_code` = **DE**, `version` = **v1**
- `window_start_utc` inclusive, `window_end_utc` exclusive, duration **≤ 24 h**

## Railway / Hermes env

| Variable | Execute | Validate | Summary | Preflight |
|----------|---------|----------|---------|-----------|
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | ✓ | ✓ | ✓ | — |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | ✓ | ✓ | ✓ | — |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED` | ✓ | | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED` | | ✓ | | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED` | | | ✓ | |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED` | | | | ✓ |

Repo B API must have **`ENTSOE_API_KEY`** or **`ENTSOE_API_TOKEN`** for execute to succeed.

## Validate caveat (v1)

Validate counts run against **primary** `DATABASE_URL` only. If normalized ENTSO-E tables are written to Timescale per env, counts may look empty until a follow-up read-target alignment.
