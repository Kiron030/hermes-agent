# Option D bounded readiness-window — Hermes operator note (v1)

## What it does

Tool **`readiness_powerunits_option_d_bounded_window`** (toolset **`powerunits_option_d_readiness`**) performs **exactly one** HTTP `POST` per call to:

`{POWERUNITS_INTERNAL_EXECUTE_BASE_URL}/internal/hermes/bounded/v1/market-features-hourly/readiness-window`

Hermes performs **no** SQL. The API checks **normalized hourly inputs** that `market_feature_job.compute_features` reads (`market_demand_hourly`, `market_generation_by_type_hourly`, `weather_country_hourly`, `market_border_flow_hourly` for scheduled day-ahead exchange, `outage_country_hourly`) for the same **PL / v1 / ≤24h UTC** slice rules as preflight / execute / validate.

## When to use which surface

| Step | Surface | Purpose |
|------|---------|---------|
| Local only | **Preflight** | Validate slice + operator CLI / rollback text; **no** Repo B HTTP. |
| Before execute | **Readiness** | **Go/no-go** on **input** tables and hour coverage; catches demand gaps and merge-blocking duplicate keys (weather/outage) before a write. |
| After execute | **Validate** | Quality check on **`market_features_hourly` output** rows (`passed` / `warning` / `failed`). |

Readiness **go** does **not** guarantee validate **passed** (outputs may still be absent or stale).

## Railway / env (Hermes)

| Variable | Role |
|----------|------|
| `HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED` | Truthy to expose the tool. |
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | Repo B API base URL (same as execute/validate). |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | Bearer secret (same as execute/validate). |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | Optional; seconds (same pattern as validate). |

## Machine-friendly JSON (tool return)

Top-level keys include: `readiness` (`go` \| `no_go`), `readiness_go` (bool), `dominant_blocker`, `reason_codes`, `warnings`, `checks`, `explanation`, `http_status`, `readiness_attempted`, `correlation_id`, `slice`, `success` (true only when HTTP 200 and `readiness` is `go`).
