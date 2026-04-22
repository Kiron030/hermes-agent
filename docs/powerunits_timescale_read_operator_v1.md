# Powerunits Timescale read (operator / staged)

Hermes can expose a **single** bounded read-only tool, `read_powerunits_timescale_dataset`, backed only by `public.market_price_model_dataset_v` on the database reached via `DATABASE_URL_TIMESCALE`.

## Status

- **Operator-oriented, staged capability** — under Powerunits `first_safe_v1`, the toolset `powerunits_timescale_read` is **explicitly** allowlisted for Telegram/runtime together with the other bounded Powerunits toolsets (see `gateway/run.py`, `model_tools.py`, `docker/apply_powerunits_runtime_policy.py`). The tool still appears only when its env gate passes.
- **Feature-gated** — set `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` to a truthy value (`1`, `true`, `yes`, `on`) **and** provide `DATABASE_URL_TIMESCALE`. If either is missing, the tool does not register as available.
- **Supplemental factual access** — primary Powerunits knowledge for Hermes remains **GitHub docs** (and bundled docs where applicable). Timescale reads are optional, read-only, and pattern-fixed (no ad-hoc SQL, no arbitrary tables).

## Enabling

1. Configure `DATABASE_URL_TIMESCALE` (connection string is never logged in full).
2. Set `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED=1`.
3. Ensure enabled toolsets for the session include `powerunits_timescale_read` (first_safe `config.yaml` already lists it when the Docker policy script has been applied).

## GitHub documentation

Repository and branch policies for public docs are unchanged; this file only describes the **Hermes-side** gate and scope.
