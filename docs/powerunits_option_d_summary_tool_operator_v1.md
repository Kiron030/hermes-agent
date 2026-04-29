# Option D bounded summary-window — Hermes operator note (v1)

## What it does

Tool **`summarize_powerunits_option_d_bounded_window`** (toolset **`powerunits_option_d_summary`**) performs **exactly one** HTTP `POST` per call to:

`{POWERUNITS_INTERNAL_EXECUTE_BASE_URL}/internal/hermes/bounded/v1/market-features-hourly/summary-window`

Hermes performs **no** SQL. Repo B composes **readiness** (normalized inputs), **validation** (`market_features_hourly` for the slice), and an optional **execution** block from `data_pipeline_runs` when `pipeline_run_id` is supplied (same lookup as validate-window).

## Recommended loop

1. `readiness_powerunits_option_d_bounded_window`  
2. `preflight_powerunits_option_d_bounded_slice` (local)  
3. `execute_powerunits_option_d_bounded_slice`  
4. `validate_powerunits_option_d_bounded_window`  
5. **`summarize_powerunits_option_d_bounded_window`** (optional one-shot report; pass `pipeline_run_id` from execute when available)

## Railway / env (Hermes)

| Variable | Role |
|----------|------|
| `HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED` | Truthy to expose the tool. |
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | Repo B API base URL (same as execute/validate/readiness). |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | Bearer secret (same bounded internal secret). |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | Optional read timeout (same pattern as validate). |

## Response highlights (tool JSON)

Server-driven fields echoed in the tool output include: `outcome_class`, `flags`, `readiness`, `execution`, `validation`, `operator_next`, `caveats`, `correlation_id`. The tool sets `success` to true only when HTTP 200 and `outcome_class` is `ok` or `ok_with_warnings`.
