# Option D bounded validate-window — Hermes operator note (v1)

## What this is

Tool **`validate_powerunits_option_d_bounded_window`** (toolset **`powerunits_option_d_validate`**) performs **exactly one** HTTP `POST` per call to:

`{POWERUNITS_INTERNAL_EXECUTE_BASE_URL}/internal/hermes/bounded/v1/market-features-hourly/validate-window`

Same **PL / v1 / ≤24h UTC** slice rules as execute/preflight (validated locally before the request). Optional **`pipeline_run_id`** (from execute response) is echoed from `data_pipeline_runs` when found; otherwise the API returns a **warning** (`run_not_found`) per ADR 039.

## Environment (Hermes Railway)

| Variable | Role |
|----------|------|
| `HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED` | Truthy to expose the tool. |
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | Same as execute (Powerunits API origin). |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | Same bearer secret as execute / Repo B internal routes. |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | Optional; defaults shorter than execute if unset in code (read-only path). |

## What this is not

- **Not** a generic analytics or SQL surface; no second HTTP hop; no writes.
- **Not** a substitute for full data QA pipelines — bounded counts + small sample only.

See **ADR 039** in Repo B (`docs/adr/039_internal_hermes_bounded_market_features_validate_window.md`) for server-side outcome semantics.
