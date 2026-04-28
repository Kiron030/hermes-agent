# Option D bounded execute — Hermes operator note (v1)

## What this is

**Live Railway path:** tool **`execute_powerunits_option_d_bounded_slice`** (toolset **`powerunits_option_d_execute`**) calls the Powerunits backend **once per invocation**:

`POST {POWERUNITS_INTERNAL_EXECUTE_BASE_URL}/internal/hermes/bounded/v1/market-features-hourly/recompute`

with JSON `country_code` / `version` / `window_start_utc` / `window_end_utc` (same PL / `v1` / ≤24h UTC rules as preflight). Auth: **`Authorization: Bearer`** using the same shared secret the API expects: **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`**.

**Gates / env (Hermes Railway):**

| Variable | Role |
|----------|------|
| `HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED` | Truthy to expose the tool. |
| `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` | HTTPS origin of the Powerunits API (no trailing slash). |
| `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` | Bearer token (must match the value set on the Powerunits API service). |
| `POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S` | Optional read timeout seconds (default 3600). |

Hermes performs **no** direct SQL; execution is delegated to Repo B’s bounded internal route and existing `market_feature_job` there.

## What this is not

- **Not** a general-purpose DB writer.
- **Not** the local subprocess path: `python -m tools.powerunits_option_d_bounded_market_features` remains **operator-only / fallback** (needs `POWERUNITS_OPTION_D_PRODUCT_ROOT` and product checkout). See `docs/powerunits_option_d_bounded_wrapper_operator_v1.md`.

## Pairing with preflight

**`preflight_powerunits_option_d_bounded_slice`** stays **plan-only** (separate gate). Use it to validate slice and rollback SQL before enabling execute.

## Post-execute validation

**`validate_powerunits_option_d_bounded_window`** (separate gate) calls the read-only validate-window API — see `docs/powerunits_option_d_validate_tool_operator_v1.md`.

## Safety

Fail-closed client validation before any HTTP call. Responses are summarized with URL redaction. No automatic rollback.
