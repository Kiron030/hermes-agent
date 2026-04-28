# Option D bounded execute — Hermes operator note (v1)

## What this is

This is the **first real Hermes write test** for Powerunits: tool **`execute_powerunits_option_d_bounded_slice`** (toolset **`powerunits_option_d_execute`**), gated by **`HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED`**.

Hermes runs **exactly one** subprocess per invocation:

`python -m tools.powerunits_option_d_bounded_market_features --country … --start … --end … --version …`

(using the Hermes process interpreter). That module performs validation again and delegates to the product `market_feature_job` as already documented for the operator wrapper.

## What this is not

- **Not** a general-purpose DB or SQL writer: no ad-hoc queries, no other jobs, no extra shell commands from this tool.
- **Not** a replacement for operator discipline: Railway must still supply product root (`POWERUNITS_OPTION_D_PRODUCT_ROOT`), database URLs, `MARKET_FEATURES_WRITE_TARGET=timescale`, and a working `uv` + product checkout — same as manual wrapper runs.

## Pairing with preflight

**`preflight_powerunits_option_d_bounded_slice`** remains **plan-only** (separate gate). Use preflight to confirm slice and rollback SQL; enable execute only when you intentionally allow Hermes to trigger the bounded wrapper.

## Safety

Fail-closed on invalid **PL** / **v1** / **≤ 24 h UTC** window. No automatic rollback, no follow-up jobs, no multi-country. Stdout/stderr summaries returned to the model are **redacted** (e.g. database URLs) and length-capped.
