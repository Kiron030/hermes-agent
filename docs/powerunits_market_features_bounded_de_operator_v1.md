# Bounded DE `market_features_hourly` (Hermes + Repo B) — operator note v1

## Scope

- **Hermes:** **DE-only** tools with **separate** feature flags — **not** **Option D** (`HERMES_POWERUNITS_OPTION_D_*` stays **PL-only**).
- **Repo B:** Canonical routes **`POST /internal/hermes/bounded/v1/market-features-hourly/{recompute,validate-window,readiness-window,summary-window}`** with **`country_code: "DE"`**, **`version: "v1"`**, **[`window_start_utc`, `window_end_utc`)** exclusive, duration **> 0** and **≤ 24 hours** (same bounds as PL bounded family).

## Tools (Hermes)

| Step | Tool | Toolset | Repo B path |
|------|------|---------|-------------|
| Execute | `execute_powerunits_market_features_bounded_de_slice` | `powerunits_market_features_bounded_de_execute` | `…/recompute` |
| Validate | `validate_powerunits_market_features_bounded_de_window` | `powerunits_market_features_bounded_de_validate` | `…/validate-window` |
| Readiness | `readiness_powerunits_market_features_bounded_de_window` | `powerunits_market_features_bounded_de_readiness` | `…/readiness-window` |
| Summary | `summarize_powerunits_market_features_bounded_de_window` | `powerunits_market_features_bounded_de_summary` | `…/summary-window` |

Parameters mirror Repo B: **`window_start_utc`**, **`window_end_utc`**, optional **`version`** (default **`v1`**). Validate/summary/readiness accept optional **`pipeline_run_id`** where applicable.

## Feature flags (Hermes)

Always require **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** and **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`**.

**Recommended (single switch for all four tools):**

- **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED`** — when truthy, **execute**, **validate**, **readiness**, and **summary** bounded tools all satisfy the Hermes gate (still **toolset-listed** separately in `first_safe_v1`).
- **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES`** (optional): comma-separated ISO2 (e.g. `DE`). If **unset**, Hermes behaves as **DE-only** for the current toolkit. If **set to empty**, the primary-flag path is **fail-closed**. **Legacy** per-step keys below **ignore** this allowlist (backward compatibility).

**Legacy (granular migration / rollback):**

- **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_EXECUTE_ENABLED`**
- **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_VALIDATE_ENABLED`**
- **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_READINESS_ENABLED`**
- **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_SUMMARY_ENABLED`**

If **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED`** is falsy, each tool falls back to **its own** legacy flag only (same narrow behavior as before this consolidation).

See **`docs/powerunits_bounded_flags_consolidated_v1.md`** for the full bounded-flag strategy and future families.

**Telegram / first_safe:** toolsets must appear in `gateway/run.py`, `model_tools.py`, and `docker/apply_powerunits_runtime_policy.py` as today.

## Operator wording

- This surface is **explicitly DE** bounded **`market_features_hourly`** Hermes tooling.
- **PL Option D** remains a **separate** gate; enabling DE tools does **not** enable Option D.
- **Same ≤24h UTC** rule as Repo B bounded market-features for PL/DE.

## Telegram smoke sequence (staging)

1. Confirm Repo B accepts **`country_code=DE`** on the four routes (deploy + secret on API).
2. On Hermes: set **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED=1`** (**recommended**) or toggle individual legacy **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_*`** keys; plus base URL + bearer.
3. Run **readiness** for a **≤24h** DE window → expect `readiness_attempted: true`, Repo B JSON.
4. Optionally **execute** → then **validate** / **summary** with returned **`pipeline_run_id`**.
5. With primary **off** and all legacy **`…_DE_*`** **off**, each tool returns **`feature_disabled`** (no widening of PL Option D).

## Multi-country scaling

Additional countries belong in Repo B **`ALLOWED_BOUNDED_MARKET_FEATURES_COUNTRIES`** first; add **explicit** Hermes tools/flags per country (avoid silent **`OPTION_D`** broadening).

