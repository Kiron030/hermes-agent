# Powerunits Hermes — growth decisions & Option D intake (v1)

**Audience:** operators / architects maintaining Repo A (`hermes-agent`) alongside Powerunits Stage 1. **Not** a product roadmap for Repo B.

---

## What is live today (Stage 1 Trusted Analyst)

- **Runtime policy:** `first_safe_v1` — bounded tool surface (no opportunistic widen).
- **Primary knowledge:** GitHub-backed **doc key manifest** (`read_powerunits_doc` / manifest keys).
- **Row facts (gated):** Timescale read tool — env-gated, bounded patterns; see `docs/powerunits_timescale_read_operator_v1.md`.
- **Supplemental Repo B (gated):** Allowlisted **key-only** reads via GitHub Contents API (`read_powerunits_repo_b_allowlisted`); allowlist `config/powerunits_repo_b_read_allowlist.json` (**v5** = v4 plus Option D fact-gathering: Timescale DDL apply script, PL Wave-1 readiness doc, `011` `market_features_hourly` SQL); see `docs/powerunits_repo_b_read_operator_v1.md`.
- **UI smoke (human):** Manual preview checklist — `docs/hermes_stage1_preview_validation_v1.md` + `RUNBOOK.hermes-stage1-validation.md` (no Hermes URL fetch, no headless browser).
- **Explicitly not live:** writer / PR / generic SQL / broad repo traversal; Stage 2 remains documented and **off**.

---

## Decision: Repo B read **before** writer activation

**Rationale:** Ground the analyst on **implementation truth** (jobs, ADRs, `implementation_state`) with **fixed blast radius**: one allowlist key → one remote file, **fail-closed** unknown keys, same read-only GitHub credential class as docs. Adds **pipeline semantics** without opening mutation, deploy hooks, or unconstrained paths. Writer activation would multiply blast radius (credentials, reversibility, review load); bounded reads reduce wrong answers **without** new failure modes comparable to writes.

---

## Option D (minimal Timescale write experiment) — current direction

**Intent:** Very narrow first write path (**PL**, **one UTC day**, **`market_features_hourly`**) under **safety > speed**. **Stage 1 Hermes** remains read-only; writes stay **human-operated** until a separate capsule/wrapper + Stage-2 gate exists.

**Proven (experiment #1):** Human-run `market_feature_job` with **`MARKET_FEATURES_WRITE_TARGET=timescale`**, slice **PL / v1 / [2024-01-01Z, 2024-01-02Z)`**, **`rows_written=24`**, clean post-checks, rollback **not** applied. Recorded in **`docs/powerunits_option_d_pl_one_day_staging_gonogo_v1.md`**.

**Candidate write surface (unchanged):** `public.market_features_hourly` — same job semantics (delete window + upsert on **`(country_code, timestamp_utc, version)`**).

**Next design focus:** **Bounded wrapper** delegating to the existing job (then optional **DB capsule** if `EXECUTE`-only enforcement is required) — see **`docs/powerunits_option_d_next_write_capsule_step_v1.md`**. **Not** Hermes writer activation yet.

---

## Open questions (unresolved)

- **Per-slice repeat:** Each new day/country still needs its own preflight (inputs + schema + policy) — experiment #1 does not generalize automatically.
- **Environment / prod boundary:** Operators must still classify Railway URLs; Hermes docs do not assert prod vs staging.
- **Resolver discipline:** `auto` vs explicit timescale for scripts — Repo B `driver_db_resolver_verification_v1.md` (not allowlisted).
- **Downstream scope:** Whether a slice test **must** include `market_driver_feature_job` for org “done”.
- **Hermes coupling:** Wrapper vs eventual **`CALL`** capsule + DB role — see next-step doc.

---

## Next planned steps

1. **Allowlist v5 (Repo A):** **Done** — Option D read keys live (see `docs/powerunits_repo_b_read_operator_v1.md`).
2. **First human recompute (PL / v1 / one day):** **Done** — see **`docs/powerunits_option_d_pl_one_day_staging_gonogo_v1.md`** (experiment #1).
3. **Next:** **Design** smallest bounded wrapper / future capsule — **`docs/powerunits_option_d_next_write_capsule_step_v1.md`** and follow-up prompt therein; **no** Hermes writer until separate activation checklist.

---

## Related artifacts

| Artifact | Role |
|----------|------|
| `docs/powerunits_repo_b_read_operator_v1.md` | Allowlist contract + source precedence |
| `docs/hermes_stage1_preview_validation_v1.md` | Manual UI preview (read-only) |
| `RUNBOOK.hermes-stage1-validation.md` | Repeatable Stage 1 checks |
| `docs/powerunits_option_d_pl_one_day_staging_gonogo_v1.md` | PL one-day `market_features_hourly` — Go/No-Go + **executed experiment #1** record. |
| `docs/powerunits_option_d_next_write_capsule_step_v1.md` | **Next safe Option D step** — wrapper vs capsule design (no writer). |
| `docs/powerunits_option_d_bounded_wrapper_operator_v1.md` | **Operator** bounded wrapper (`python -m tools.powerunits_option_d_bounded_market_features`). |

*Version: v1 — amend in place when Stage 2 scope or Option D facts materially change.*
