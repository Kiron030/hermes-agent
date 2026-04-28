# Option D Hermes preflight tool — operator note (v1)

## What this is

Hermes tool **`preflight_powerunits_option_d_bounded_slice`** (toolset **`powerunits_option_d_preflight`**) is **plan-only**.

- It **validates** the same first-release slice rules as the bounded wrapper: **country = PL**, **version = v1**, **UTC window** strictly **> 0** and **≤ 24 hours**, exclusive end semantics.
- It returns JSON with a **normalized slice**, **required environment variable names**, the **exact one-line** `python -m tools.powerunits_option_d_bounded_market_features …` command for **manual** operator use, and a **rollback SQL** template.
- Hermes **does not** run the wrapper, **does not** spawn shell jobs for this path, and **does not** perform database writes.

Gating: set **`HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED`** to a truthy value (`1`, `true`, etc.) on the Railway service **only** when you intentionally want this tool on the model surface.

## What this is not

The **operator-run bounded wrapper** (`python -m tools.powerunits_option_d_bounded_market_features`) performs env checks and delegates to the Powerunits product job (writes when you run it). That remains **operator-only** and is **not** invoked by the preflight tool.

See also: `docs/powerunits_option_d_bounded_wrapper_operator_v1.md`.
