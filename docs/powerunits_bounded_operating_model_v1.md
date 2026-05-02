# Bounded Hermes + Repo B — operating model v1

**Companion (canonical product-side detail):** in **EU-PP-Database**, `docs/architecture/internal_hermes_bounded_operating_model_v1.md` (checkout path may differ locally).

This note is **Repo A–centric**: how Hermes should behave toward those routes. Full family tables and Repo B truths stay in EU-PP-Database.

---

## 1. Source of truth

- **Repo B** defines bounded **HTTP contracts**, **job execution**, and **country_code / window** validation.
- **Hermes** forwards **single structured POSTs** per tool call, applies **env gates** and optional **comma ISO2 allowlists**, and surfaces operator-safe JSON — **no** authoritative copy of pipeline or DB contents.

Repeat: **Hermes must not persist bounded outcomes as canonical state.** To “refresh”, call Repo B again (execute, validate, coverage-scan, or **coverage-inventory**).

---

## 2. Read-only vs write

| Bounded class | Illustrative Hermes tool families | Repo B characteristic |
|----------------|----------------------------------|----------------------|
| **Read-only** | validate, summary, readiness, coverage-scan, **coverage inventory**, baseline preview, **remediation planner** | Evaluators only; **`hermes_statement`** / rollup where applicable explicitly marks **no** job start on that route. |
| **Write / repair** | execute on recompute routes (ERA5, ENTSO-E market/forecast where applicable, market-features, outage **repair**, …) | Runs the declared in-process job; responses list **jobs not auto-run**. |

**Outage:** awareness paths are read-only on Repo B; **repair** execute is write — distinct Hermes gates.

---

## 3. Coverage inventory and `skipped`

- **Coverage-inventory** is a **Repo B aggregator**: each invocation recomputes the matrix Hermes asks for (`POST …/coverage-inventory`). Hermes may attach a **turn-local CSV** export only — **no** durable inventory DB in Repo A.
- Rows marked **`skipped`** mean “this evaluator was **not** run for `(country, family)` in this release” (e.g. family still **execute-limited** to **DE** on Repo B). That is **expected** during phased rollout — operators use skips to see **coverage of readiness**, not silent success.

Details: EU-PP-Database `docs/architecture/internal_hermes_bounded_operating_model_v1.md`.

---

## 4. Env model (no per-country primary flags)

- **One primary per bounded family** (where migrated) plus **one optional** `HERMES_POWERUNITS_<FAMILY>_BOUNDED_ALLOWED_COUNTRIES` — see **`docs/powerunits_bounded_flags_consolidated_v1.md`**.
- Prefer **never** introducing `HERMES_…BOUNDED_IE_ENABLED`-style primaries; **country stays in JSON + Repo B validators**; Hermes optional list only **narrows**.

**ERA5 Tier‑1 nuance:** allowlist omit ⇒ implicit **DE**-only narrowing; empty string ⇒ Hermes ERA5 bounded **fail-closed**; non-empty may omit **DE** (Repo B Tier‑1 ∩ list). ENTSO‑E and others differ — consolidated doc + EU-PP table.

---

## 5. Readiness terminology (Hermes wording)

Aligned with Repo B architecture note:

| Term | Meaning for operators |
|------|----------------------|
| **Execute-ready** | Repo B bounded **recompute** accepts that `country_code` for the family today. |
| **Inventory-ready** | Inventory POST returns a row (**ok**, **skipped**, or explicit outcome) — **skipped** ok. |
| **Planner-ready** | **Remediation planner** tool enabled; **DE-stack** aggregation, **read-only**, suggestions only — not blanket multi-country execute. |

**Multi-country today (Repo B bounded execute):** **ERA5** Tier‑1; **market-features** bounded **DE+PL**. Most other listed families remain **DE-only** (or **DE** for planner) until Repo B slices widen — see EU-PP table.

---

## 6. Step pattern (not every family has every step)

Conceptual order: **preflight** (Hermes-local, no Repo B HTTP) → **execute** (write) → **validate** / **readiness** → **summary** → optional **coverage-scan** (read-only multi-window) → optional **campaign** (Hermes orchestration) → **coverage-inventory** (matrix) → **planner** (read-only cross-family DE).

Per-family tool names, env keys, and ADR links: **`ACCESS_MATRIX.md`** documentation map and family `docs/powerunits_*_bounded_operator_v1.md` files.

---

## 7. Intentionally out of scope here

- Per-step SQL, ADR text, and Railway secret rotation — **runbooks** and ADRs.
- Telegram allowlists and `first_safe` policy — **`RUNBOOK.hermes-trusted-analyst.md`**, `docker/apply_powerunits_runtime_policy.py`.
- Option D PL-only flows — separate operator docs; still **Repo B** SoT for HTTP.
