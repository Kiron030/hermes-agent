# Option D — next safe step: write capsule design (v1)

**Status:** Design-only. **Stage 1** Hermes remains read-only; **no** writer activation; **no** generic DB tool; **no** Repo B changes required for this design pass unless a capsule is later implemented **in** Repo B / DB migrations (explicit gate).

**Prerequisite proven:** First human-run `market_feature_job` recompute for **PL / v1 / one UTC day** to **`market_features_hourly`** on Timescale succeeded (`rows_written=24`, clean post-checks). See **`docs/powerunits_option_d_pl_one_day_staging_gonogo_v1.md`** § *Controlled write experiment #1*.

---

## Target design direction

Introduce a **single bounded execution surface** for Option D repeats that is **narrower than “run arbitrary job CLI”** but **reuses the same semantics** as `market_feature_job` (delete window + upsert, same conflict key). Goal: **Hermes Stage 2 later** can invoke **one** audited entrypoint with **hard-coded** or **strictly validated** parameters — not free-form SQL.

---

## Compare three shapes

| Shape | Blast radius | Audit / review | Coupling to product logic |
|-------|----------------|----------------|---------------------------|
| **A — Repeated human-run job** (current) | Low if operator discipline holds | Shell history + `data_pipeline_runs` on primary | **Zero** new code — full reuse of `market_feature_job` |
| **B — Tightly bounded wrapper** (Repo A or small Repo B CLI) | Low–medium: one script validates `country ∈ {PL}`, day length, `version`, then **delegates** to job module | Wrapper source + job | Thin layer; still Python process + DB creds on host |
| **C — DB stored procedure + `EXECUTE`-only role** | **Lowest** for automation: DB enforces slice bounds | SQL body in migration, reviewable | Must **duplicate or call** job logic — **risk of drift** vs Python job unless procedure is generated from one source of truth |

---

## Recommended next design target

**Prefer (B) first, then (C) if Hermes must not hold DB URLs:** a **tightly bounded wrapper command** (e.g. `hermes_option_d_recompute_features_slice` or Repo B `python -m …option_d_slice` with **no** extra flags — only env + fixed argparse) that:

1. Parses **exactly one** `country_code`, **one** `[start,end)`, **one** `version` (reject multi-country, reject window > 48h or > 1 calendar day per policy).
2. Sets or asserts `MARKET_FEATURES_WRITE_TARGET=timescale` and presence of `DATABASE_URL_TIMESCALE`.
3. Calls the **existing** `market_feature_job.run(...)` (or subprocess to the **same** module) — **no** duplicate SQL in the wrapper.
4. Emits a **structured summary** (rows_written, run_id, slice fingerprint) for operator logs.

**Why not jump straight to (C):** avoids maintaining **two** upsert implementations; the job is already the normative path used in production pipelines. A **procedure capsule** remains the **best long-term Hermes-facing** shape **if** the org requires DB-side enforcement (`EXECUTE` only); defer until wrapper path is reviewed and **one** slice policy is frozen.

---

## Still **not** allowed (until separate gates)

- **No** generic DB / arbitrary SQL writer for Hermes.
- **No** broad writer activation (`CHECKLIST.hermes-writer-activation.md` unchanged).
- **No** multi-country or multi-day expansion **by default** — each new slice = explicit allowlist / ticket / doc bump.
- **No** infra mutation (Railway/Vercel env surges, new production roles) as part of “Option D design”.

---

## Exact next prompt (design only — no writer, no Repo B unless agreed)

> **Repo A (`hermes-agent`) design-only:** Produce a **one-page** spec for a **bounded wrapper** (Option D step B above) that an operator could run from a controlled host: exact **argv** surface (fixed positional or required flags only), **validation rules** (PL-only first release, max window 24h UTC, `version` allowlist `{v1}`), **env dependencies**, **stdout JSON shape**, and **failure classes** (exit codes). Reference **`job_market_feature`** via import/delegate — **no** new SQL. Explicitly state **out of scope**: Hermes tool wiring, DB migration, new Postgres roles. **Do not** implement code in this task unless the user opens a separate implementation request.

**Bounded wrapper contract (argv, JSON, exit codes):** **`docs/powerunits_option_d_bounded_wrapper_spec_v1.md`**. **Implemented:** `python -m tools.powerunits_option_d_bounded_market_features` — **`docs/powerunits_option_d_bounded_wrapper_operator_v1.md`**.

*Version v1 — revise when capsule or wrapper is implemented or rejected.*
