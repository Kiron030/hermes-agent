# Bounded DE `market_driver_features_hourly` (Hermes + Repo B) — operator note v1

## Scope

- **Hermes:** **DE-only** tools with **dedicated** flags — separate from **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_*`** (market-features family) **and** from **Option D** (`HERMES_POWERUNITS_OPTION_D_*`).
- **Repo B:** **`POST /internal/hermes/bounded/v1/market-driver-features-hourly/{recompute,validate-window,readiness-window,summary-window}`** with **`country_code: "DE"`**, **`version: "v1"`**, **[`window_start_utc`, `window_end_utc`)** exclusive, duration **> 0** and **≤ 24 hours**.

## Tools (Hermes)

| Step | Tool | Toolset | Repo B path |
|------|------|---------|-------------|
| Execute | `execute_powerunits_market_driver_features_bounded_de_slice` | `powerunits_market_driver_features_bounded_de_execute` | `…/recompute` |
| Validate | `validate_powerunits_market_driver_features_bounded_de_window` | `powerunits_market_driver_features_bounded_de_validate` | `…/validate-window` |
| Readiness | `readiness_powerunits_market_driver_features_bounded_de_window` | `powerunits_market_driver_features_bounded_de_readiness` | `…/readiness-window` |
| Summary | `summarize_powerunits_market_driver_features_bounded_de_window` | `powerunits_market_driver_features_bounded_de_summary` | `…/summary-window` |

Parameters: **`window_start_utc`**, **`window_end_utc`**, optional **`version`** (default **`v1`**). Validate / readiness / summary accept optional **`pipeline_run_id`** for symmetry.

**Readiness:** Repo B evaluates **`market_features_hourly`** in the bounded window — the driver job’s required upstream layer.

## Feature flags (Hermes)

Always require **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`**.

**Recommended:**

- **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`** — gates **all four** driver bounded tools together.
- **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ALLOWED_COUNTRIES`** — same semantics as market-features (**DE** implicit if unset).

**Legacy (per-step):**

- **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_EXECUTE_ENABLED`**
- **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_VALIDATE_ENABLED`**
- **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_READINESS_ENABLED`**
- **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_SUMMARY_ENABLED`**

Primary falsy ⇒ each tool checks **only** its legacy flag (no accidental broadening).

See **`docs/powerunits_bounded_flags_consolidated_v1.md`**.

**Telegram / first_safe:** unchanged toolset plumbing (`gateway/run.py`, `model_tools.py`, `docker/apply_powerunits_runtime_policy.py`).

## Operator wording

- Execute runs Repo B **`market_driver_feature_job`** for the persisted window only — **no** chained **`market_feature_job`**, **no** **`market_input_prices_seed_job`**. Expect **`downstream_not_auto_triggered`** (and Repo B **`operator_note`**) when present.
- **720h rolling Z-score:** the job may read **`market_features_hourly`** roughly **30 days before** the window for context; bounded execution only limits what rows are **written** for `market_driver_features_hourly`.
- **Cost columns:** non-NULL only when Repo B **`MARKET_DRIVER_INCLUDE_COST_INPUTS`** and upstream commodity / carbon / FX data are present; otherwise success can still mean **NULL** cost fields.

## Telegram smoke sequence (staging)

1. Repo B deploy with internal Hermes routes + bearer; confirm four **`/market-driver-features-hourly/*`** paths accept **DE / v1**.
2. On Hermes: **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED=1`** or legacy **`HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_*`**; plus base URL + bearer; **`first_safe_v1`** includes the four **`powerunits_market_driver_features_bounded_de_*`** toolsets.
3. **Readiness** for a **≤24h** DE window → expect **`readiness_attempted: true`**; investigate **`readiness`** / **`dominant_blocker`** if not **`go`**.
4. **Execute** → capture **`pipeline_run_id`**; **validate** / **summary** with same window (and optional **`pipeline_run_id`**).
5. Primary **off** and all legacy **`…_DE_*`** **off** → **`feature_disabled`**; **market-features** and **Option D** unaffected.

## Multi-country scaling

New countries require Repo B allowlist / contract first, then **explicit** Hermes tools and flags per country — **no** silent reuse of DE flags or Option D.
