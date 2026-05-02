# Bounded Hermes env flags — consolidated model & migration v1

## 0. Operating model (cross-repo)

Hermes gates and allowlists attach to **Repo B bounded HTTP** contracts — see **`docs/powerunits_bounded_operating_model_v1.md`**. Canonical **product-side** semantics (thin Hermes vs SoT, read/write split, inventory + **`skipped`**, readiness snapshot): **EU-PP-Database** repo, **`docs/architecture/internal_hermes_bounded_operating_model_v1.md`**.

## 1. Current inventory (Hermes codebase)

These are **`HERMES_POWERUNITS_*_ENABLED`**-style gates as of **2026** refactor prep.

| Surface | Vars today | Role |
|---------|-------------|------|
| **Option D PL** | `OPTION_D_PREFLIGHT`, `EXECUTE`, `VALIDATE`, `READINESS`, `SUMMARY` | Bounded PL **`market-features-hourly`** Hermes POSTs (**not** consolidating here). |
| **Market features bounded (DE tooling)** | **Primary:** `MARKET_FEATURES_BOUNDED_ENABLED`; **legacy:** `_DE_EXECUTE`, `_VALIDATE`, `_READINESS`, `_SUMMARY`; **optional:** `MARKET_FEATURES_BOUNDED_ALLOWED_COUNTRIES` | **Implemented.** |
| **Market driver bounded** | **Primary:** `MARKET_DRIVER_FEATURES_BOUNDED_ENABLED`; **legacy:** `_DE_*` same pattern; optional `*_ALLOWED_COUNTRIES` | **Implemented.** |
| **ENTSO‑E bounded** | **Primary:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`; **legacy:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_{PREFLIGHT,EXECUTE,VALIDATE,SUMMARY}_ENABLED`; optional `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`; **modifiers:** `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_{COVERAGE_SCAN,CAMPAIGN}_ENABLED` | **Implemented** (campaign / coverage-scan stay separate modifiers). |
| **ERA5 bounded** | **Primary:** `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED`; same legacy + allowlist + modifier pattern as ENTSO‑E | **Implemented.** |
| **ENTSO‑E forecast bounded** | **Primary:** `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED`; **legacy:** four `*_PREFLIGHT/EXECUTE/VALIDATE/SUMMARY_*`; optional `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES`; **no** separate campaign modifier in Hermes v1 | **Implemented** (forecast F3b+F4 only; orthogonal to ENTSO‑E **market** family). |
| **Baseline preview** | `BASELINE_LAYER_PREVIEW_ENABLED` | Already **single** gate; fits target model as-is. |
| **Bounded coverage inventory** | **`HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED`** | **Read-only** aggregator — Repo B **`…/coverage-inventory`**; default inventory v1 aggregates **four** Repo B evaluator families (**ERA5**, ENTSO‑E **market**, **outage awareness**, ENTSO‑E **forecast**). Hermes persists **no** inventory matrix (`csv_export` is turn-local only). Requires same bounded execute **base URL** + bearer as other **`internal/hermes/bounded`** tools. |
| **DE stack remediation planner** | **`HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED`** | **Read-only** cross-family aggregator (**one** Repo B planner POST; starts **no** jobs). |
| **Outage awareness bounded (DE)** | **Primary:** `HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED`; **legacy:** `HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_{VALIDATE,SUMMARY}_ENABLED`; optional `HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES` | **Read-only** Hermes POSTs to **`…/outage-awareness/*`** — **no** outage ingest, **no** hourly outage recompute, **no** market-feature or driver jobs. |
| **Outage repair bounded (DE)** | **Primary:** `HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED`; optional `HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES`; **legacy:** `HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED` | **Write** bounded path (**Step A + Step B**) via **`…/outage-repair/recompute`**; **no auto** **`market_feature_job`** / **`market_driver_feature_job`**. Separate family from awareness. |
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

Same rules as §4 (**primary wins**, **legacy when primary falsy**, **allowlist ignored on legacy-only**) for steps **preflight**, **execute**, **validate**, **summary**. Per-request narrowing: **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES` unset ⇒ implicit `{DE}`**; **explicit `""` ⇒ fail-closed when primary is on.** Intersection always includes Repo B **`{DE,NL}`** Tier v1 (**FR** etc. rejected regardless of Railway). **ENTSO‑E forecast bounded** mirrors **ENTSO‑E market** primaries: **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES`** **unset ⇒ `{DE}`** at permit time; **explicit `""` ⇒ fail-closed**; Tier v1 Repo B codes **`{DE,NL}`**.

**Exception — bounded ERA5 weather Tier‑1:** bounded ERA5 tools stay unlocked on primary whenever **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES`** is **non-empty**, even if **`DE`** is omitted; **explicit empty** still fail-closes. Per-request narrowing still intersects Repo B **`ERA5_COUNTRY_BBOXES`** Tier‑1 with that allowlist (**env var omitted ⇒ `{DE}`** at permit time).

**Modifiers unchanged:** **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED`** / **`…_COVERAGE_SCAN_ENABLED`** and **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED`** / **`…_COVERAGE_SCAN_ENABLED`** remain **separate** — they imply multi-window orchestration or read-only scan semantics beyond a single bounded slice.

### Migration — ENTSO‑E / ERA5

1. Set **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED=1`** and/or **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED=1`**.
2. Optionally set **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`**, comma ISO2 subset of Repo B **`DE`**/**`NL`** (**omit ⇒ Hermes narrowing still implicit `DE` only**). **ERA5 Tier‑1:** set **`HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES`** to a **non-empty comma list** subset of Repo B **`ERA5_COUNTRY_BBOXES`** keys (**omit unset ⇒ implicit `{DE}`** at request narrowing; **`""` ⇒ Hermes ERA5 bounded tools disable**).
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

**ENTSO‑E forecast bounded** — deprecated per-step Hermes gates (still read when primary is falsy):

```text
HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_PREFLIGHT_ENABLED
HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_EXECUTE_ENABLED
HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED
HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_SUMMARY_ENABLED
```

### ENTSO‑E forecast bounded

Core steps align with **bounded ENTSO‑E market** (**primary** + optional allowlist; **unset ⇒ implicit `DE` narrowing**; **explicit empty ⇒ fail-closed**); per-request permit intersects Repo B Tier v1 **`DE`/`NL`**. **Orthogonal** to **`ENTSOE_MARKET_BOUNDED_*`** — routes `…/entsoe-forecast/*` invoke **`entsoe_forecast_job`** only (no **`entsoe_market_job`**, no market-features auto-run).

Recommended primary:

- **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED=1`**
- Optional **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES`** (comma ISO2 subset of Repo B **`DE`/`NL`**; omit ⇒ implicit **`DE`** at Hermes narrowing; empty ⇒ fail-closed with primary).

### DE bounded coverage inventory v1 (read-only)

Hermes **`inventory_powerunits_bounded_coverage_v1`** is a **thin** POST to Repo B **`POST /internal/hermes/bounded/v1/coverage-inventory`** (same credentials as **`POWERUNITS_INTERNAL_EXECUTE_*`**). **Separate gate:** **`HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED`**. Turning it **off** disables only this tool — it does **not** disable outage awareness reads, outage repair, ENTSO‑E forecast executes, etc. Turning it **on** still performs **zero** writes and stores **no** canonical matrix in Hermes (JSON **`repo_b_inventory`** in the reply is ephemeral). **`export_format=csv`** derives UTF-8 **`csv_export`** inline from embedded **`rows`**; optional **`exports_csv_workspace_filename`** writes the same CSV to **`exports/*.csv`** on the bounded workspace volume, or use **`save_hermes_workspace_note`** with a **`.csv`** name — **no** Repo B CSV endpoint.

### DE bounded stack remediation planner (read-only)

Single Hermes gate: **`HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED`**. Enables **`plan_powerunits_de_stack_remediation`** (**one** HTTP POST to Repo B **`…/remediation/de-stack-plan`**). Independent of ENTSO‑E / ERA5 / forecast / market‑features execute primaries; still requires **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** + **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`**. **No job execution** on this surface — JSON **`tool_hint_hermes`** values are manual operator hints only.

### Outage repair bounded (execute-only family)

Hermes **`execute_powerunits_outage_repair_bounded_slice`** is gated separately from **outage awareness** (validate/summary are read-only; repair runs Step A+B on Repo B).

- **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED=1`** unlocks bounded outage repair execute (with base URL + bearer).
- Optional **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ALLOWED_COUNTRIES`** — unset ⇒ implicit **DE**; empty ⇒ fail-closed when primary is on.
- **Legacy** when primary is falsy: **`HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED`**.

**Deprecated (still read when primary is falsy):**

```text
HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED
```

### Outage awareness bounded (read-only)

Same §6 semantics as other primary+legacy bounded families for **validate** and **summary** only (**no execute** in Hermes v1).

- **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ENABLED=1`** unlocks **`validate_powerunits_outage_awareness_bounded_window`** and **`summarize_powerunits_outage_awareness_bounded_window`** together (with base URL + bearer).
- Optional **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_ALLOWED_COUNTRIES`** — unset ⇒ implicit **DE**; empty ⇒ fail-closed when primary is on.
- **Legacy** when primary is falsy: **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED`** / **`HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED`** (granular).

**Deprecated (still read when primary is falsy):**

```text
HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED
HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED
```

---

**Canonical code:** `tools/powerunits_bounded_family_gates.py`
