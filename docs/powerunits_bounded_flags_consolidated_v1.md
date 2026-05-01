# Bounded Hermes env flags — consolidated model & migration v1

## 1. Current inventory (Hermes codebase)

These are **`HERMES_POWERUNITS_*_ENABLED`**-style gates as of **2026** refactor prep.

| Surface | Vars today | Role |
|---------|-------------|------|
| **Option D PL** | `OPTION_D_PREFLIGHT`, `EXECUTE`, `VALIDATE`, `READINESS`, `SUMMARY` | Bounded PL **`market-features-hourly`** Hermes POSTs (**not** consolidating here). |
| **Market features bounded (DE tooling)** | **Primary:** `MARKET_FEATURES_BOUNDED_ENABLED`; **legacy:** `_DE_EXECUTE`, `_VALIDATE`, `_READINESS`, `_SUMMARY`; **optional:** `MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES` | **Implemented.** |
| **Market driver bounded** | **Primary:** `MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`; **legacy:** `_DE_*` same pattern; optional `*_ALLOWED_COUNTRIES` | **Implemented.** |
| **ENTSO‑E bounded** | **Primary:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`; **legacy:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_{PREFLIGHT,EXECUTE,VALIDATE,SUMMARY}_ENABLED`; optional `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`; **modifiers:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_{COVERAGE_SCAN,CAMPAIGN}_ENABLED` | **Implemented** (campaign / coverage-scan stay separate modifiers). |
| **ERA5 bounded** | **Primary:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED`; same legacy + allowlist + modifier pattern as ENTSO‑E | **Implemented.** |
| **Baseline preview** | `BASELINE_LAYER_PREVIEW_ENABLED` | Already **single** gate; fits target model as-is. |
| **Timescale read / Repo B read** | One primary each | Fits model. |

## 2. Design target principles

1. **One primary flag per Repo B bounded *family*** (writes + read-only mates that share credentials and route prefix): turns on Hermes tooling for **all** sibling steps (**execute**, **validate**, **readiness**, **summary**) where those tools exist — **consistent with `first_safe_v1`** still requiring each toolset to be enumerated in gateway policy.
2. **No `_DE_` / `_PL_` in primary names.** Country/version/window stay **Repo B** authority; Hermes **`…_ALLOWED_COUNTRIES`** is an **extra** narrowing layer for future multi-country tooling (comma ISO2).
3. **Preserve conservative legacy path:** Primary **unset** ⇒ fall back **only** to the **old per-step env vars** unchanged so existing Railway configs do **not** widen unintentionally.
4. **Primary set** ⇒ **all steps** unlocked together (narrower Railway config for teams that want parity across execute/readiness/validate/summary); **granular revoke** ⇒ clear primary **or** set **`ALLOWED_COUNTRIES`** to exclude **`DE`** (fail-closed for current DE-focused tools).

## 3. Naming scheme (recommended)

General pattern:

- **`HERMES_POWERUNITS_<FAMILY>_BOUNDED_ENABLED`** — primary Hermes gate.
- **`HERMES_POWERUNITS_<FAMILY>_BOUNDED_ALLOWED_COUNTRIES`** — optional Hermes-side allowlist.
- **`HERMES_POWERUNITS_<FAMILY>_BOUNDED_<MODIFIER>_ENABLED`** — reserve **modifiers** for **true** composites (e.g. **campaign**, **coverage_scan**) with different blast radius or orchestration. For **ENTSO‑E** and **ERA5**, **preflight** is part of the **primary** family gate (same as execute/validate/summary), not a separate modifier env.

Families not yet migrated keep their existing names until refactor PRs align them.

## 4. Implemented behavior (market features & market driver)

- **Primary wins when truthy:** all four sibling tools satisfy `check_fn` (given base URL + bearer).
- **Primary falsy:** each tool accepts **only** its historical **`HERMES_*_BOUNDED_DE_*_<STEP>_ENABLED`** (no broadening vs pre-refactor semantics).
- **Allowlist ignored on legacy-only path:** avoiding accidental regressions where operators still use four separate DE keys.
- **Allowlist semantics (primary-only):**
  - **Unset** ⇒ implicit **`DE`** (current tools only POST **DE**).
  - **`DE` or multi like `DE,FR`** ⇒ allowed if **`DE`** present.
  - **Empty string** ⇒ fail-closed for primary-enabled path.

## 5. Migration from old `_DE_*_EXECUTE`-style Railway vars

1. Set **`HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED=1`** (same for **`MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`**).
2. **Remove** legacy **`*_DE_VALIDATE_ENABLED`** etc. when you intend **parity** across all four tools — **otherwise** clearing legacy before confirming primary triggers **feature_disabled**.
3. After validation in staging (`RUNBOOK.hermes-stage1-validation.md`), delete duplicated legacy keys from Railway to shrink variable count.

**Deprecated names (Hermes-side only)** — superseded **when primary is adopted** but **still read** alongside primary **only** via legacy branch:

```text
HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_EXECUTE_ENABLED
HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_VALIDATE_ENABLED
HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_READINESS_ENABLED
HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_SUMMARY_ENABLED
HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_EXECUTE_ENABLED
HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_VALIDATE_ENABLED
HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_READINESS_ENABLED
HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_SUMMARY_ENABLED
```

## 6. Implemented behavior — ENTSO‑E & ERA5 bounded (symmetric)

Same rules as §4 (**primary wins**, **legacy when primary falsy**, **allowlist ignored on legacy-only**, **unset allowlist ⇒ implicit DE**, **empty allowlist ⇒ fail-closed**) for steps **preflight**, **execute**, **validate**, **summary**.

**Modifiers unchanged:** **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED`** / **`…_COVERAGE_SCAN_ENABLED`** and **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED`** / **`…_COVERAGE_SCAN_ENABLED`** remain **separate** — they imply multi-window orchestration or read-only scan semantics beyond a single bounded slice.

### Migration — ENTSO‑E / ERA5

1. Set **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED=1`** and/or **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED=1`**.
2. Optionally set **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES=DE`** (same for ERA5) for explicitness; unset still defaults to **DE** for current Hermes tools.
3. After staging validation, remove redundant legacy **`…_PREFLIGHT_ENABLED`**, **`…_EXECUTE_ENABLED`**, **`…_VALIDATE_ENABLED`**, **`…_SUMMARY_ENABLED`** keys if you want fewer Railway variables — **do not** remove **`…_CAMPAIGN_ENABLED`** / **`…_COVERAGE_SCAN_ENABLED`** where those tools are used.

**Deprecated (still read when primary is falsy):**

```text
HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED
HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED
HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED
HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED
HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED
HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED
HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED
HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED
```

---

**Canonical code:** `tools/powerunits_bounded_family_gates.py`
