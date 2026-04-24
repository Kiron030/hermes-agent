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

## Option D (future minimal Timescale write experiment) — current direction

**Intent:** Explore a **very narrow** first write test (e.g. **PL**, **one UTC day**, Timescale-related slice) under **safety > speed** — **design/intake first**, no writer, no new DB roles yet.

**Process decision:** **Facts before design** — confirm target DB URLs (primary vs Timescale), DDL parity, input coverage for the slice, rollback predicate, then choose mechanism.

**Likely candidate write surface:** `public.market_features_hourly` — product job already implements **DELETE window + `INSERT … ON CONFLICT (country_code, timestamp_utc, version) DO UPDATE`**; Timescale target via `MARKET_FEATURES_WRITE_TARGET=timescale` + `DATABASE_URL_TIMESCALE` while **reads** stay on `get_app_db_url()` (primary) in current code path.

**Execution preference (provisional):** **Operator-run `market_feature_job` once** on staging/pilot with explicit `--countries PL --start/--end` **before** any Hermes-invoked write capsule. Capsule / stored procedure + `EXECUTE`-only role remains the **longer-term** safest shape for Stage 2 if Hermes must trigger writes — not the first physical experiment.

---

## Open questions (unresolved)

- **Schema attestation:** Exact PK / hypertable / index state on the **specific** Timescale URL vs `backend/db/011_create_market_features_hourly.sql` (verify with `verify_timescale_worker_schema.py` or `\d+`, not assumed from chat).
- **Input completeness:** For chosen PL day + `version`, are **24** hours present on **primary** for demand, generation-by-type, and weather (job prerequisites)?
- **Environment proof:** Non-prod fingerprint for both `DATABASE_URL` and `DATABASE_URL_TIMESCALE`; resolver discipline (`auto` vs explicit timescale — see Repo B `driver_db_resolver_verification_v1.md`, not Hermes-allowlisted today).
- **Downstream scope:** Whether a one-day PL test **must** include `market_driver_feature_job` for the org’s definition of “done”.
- **Hermes coupling:** Whether first staging write stays **fully outside** Hermes forever vs later **single** `CALL` capsule behind separate gates.

---

## Next planned steps

1. **Allowlist v5 (Repo A):** **Done** — keys `apply_market_pipeline_schema_to_timescale`, `wave1_country_readiness_it_pl_se`, `ddl_011_create_market_features_hourly` (see `config/powerunits_repo_b_read_allowlist.json` and **Allowlist v5** in `docs/powerunits_repo_b_read_operator_v1.md`).
2. **Operator intake:** Run read-only counts / schema verify on **target** staging URLs; record **Go/No-Go** one-pager (still no `MARKET_FEATURES_WRITE_TARGET=timescale` until green).
3. **If Go:** first **mutating** attempt remains **human-operated job** + documented rollback `DELETE` matching job predicate; **then** specify DB capsule + role model for Hermes Stage 2 — separate checklist (`CHECKLIST.hermes-writer-activation.md` path in Repo A as already referenced elsewhere).

---

## Related artifacts

| Artifact | Role |
|----------|------|
| `docs/powerunits_repo_b_read_operator_v1.md` | Allowlist contract + source precedence |
| `docs/hermes_stage1_preview_validation_v1.md` | Manual UI preview (read-only) |
| `RUNBOOK.hermes-stage1-validation.md` | Repeatable Stage 1 checks |

*Version: v1 — amend in place when Stage 2 scope or Option D facts materially change.*
