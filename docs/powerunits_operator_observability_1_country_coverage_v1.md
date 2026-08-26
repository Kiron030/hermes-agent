# Operator observability 1 — country coverage inspect

**Slice:** `OPERATOR_OBSERVABILITY_1_COUNTRY_COVERAGE`  
**Status:** implemented in Repo A + Repo B; **not deployed**. Human merge gate required.  
**Predecessor:** [`powerunits_operator_observability_0a_v1.md`](powerunits_operator_observability_0a_v1.md)

```text
Operator Hermes
  → inspect_powerunits_country_coverage_v1
  → POST /internal/hermes/bounded/v1/country-coverage/inspect
  → Repo B catalog + aggregates
  → Timescale / existing market surfaces
```

Hermes does **not** receive `DATABASE_URL_TIMESCALE` on this path and does **not** execute SQL.

## Tool contract

| Field | Value |
|-------|--------|
| Tool | `inspect_powerunits_country_coverage_v1` |
| Toolset | `powerunits_country_coverage_inspect` |
| Effect | `READ` |
| Gate | `HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED` |
| Credentials | existing `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` |
| Profile | added to `stage1_read_health` (fills missing keys only; explicit Railway values win) |
| Approval | none (read) |

Inputs: required `country` (ISO2); optional `dataset`, `start`, `end`. No SQL, table names, or URLs.

## Country semantics

Supported v1 = national Tier-1 (`AT BE CZ DE FI FR HU NL PL RO SK`) ∪ BZN advisory (`DK NO SE IT IE`).

- National datasets: Tier-1 only
- `bzn_price`: BZN advisory only
- Unknown / ineligible combination → typed fail-closed (`invalid_country`, `unsupported_country`, `dataset_not_applicable_for_country`)

Adding a country is an allowlist change. It does **not** require a new Hermes tool.

## Dataset catalog v1

`model_dataset`, `day_ahead_price`, `demand`, `generation_by_type`, `weather`, `cross_border`, `outage`, `bzn_price`.

Dataset omitted → bounded summary over datasets eligible for that country.

Adding a dataset is a Repo B catalog entry (+ Hermes schema mirror). It does **not** require a new public Operator capability.

## Coverage semantics

Per item: requested/observed/available range, expected_points, observed_points, coverage_ratio (hourly distinct timestamps / expected hours), missing_points, gap_count, largest_gap (single-dataset mode), latest_timestamp, age_hours, freshness, duplicate_count, status.

Status: `OK` | `THIN` (<80%) | `STALE` | `STALE_AND_THIN` | `NO_DATA`.

`NO_DATA` is a successful empty read, not a system error.

Weather stale floor is 168h (ERA5 publication lag). Other hourly surfaces use 48h.

## Defaults and performance

- Date range omitted → last 7 days, hour-aligned, exclusive end
- Max window: 31 days
- One country per call
- Aggregates only; no `SELECT *`; table names are compile-time literals
- Gap listing omitted in summary mode
- Whole-history option is **not** offered; `available_start` / `available_end` are `MIN`/`MAX` only

## Limitations

- Not a multi-country monitoring agent
- Forecast surfaces stay on the existing freshness tool
- Live Operator proof is deferred until a human deploys Repo B + Operator Hermes
- Developer Hermes does not receive this tool

## Extension

Repo B `DatasetSpec` + allowlist first; Hermes catalog/description stays a thin mirror.

**Next slice:** `OPERATOR_OBSERVABILITY_2_DB_HEALTH_READ`
