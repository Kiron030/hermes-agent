# Powerunits platform evolution backlog (Repo A slice)

**Audience:** operators and integrators of **Hermes** (Repo A: `hermes-agent`) for Powerunits.  
**Status:** **Backlog / when-ready** — not an active tier increase.  
**Not a second roadmap:** Hermes capability progression remains [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md).

**Canonical product/platform backlog (Repo B):** [`EU-PP-Database/docs/architecture/saas_ai_evolution_backlog_v1.md`](../../EU-PP-Database/docs/architecture/saas_ai_evolution_backlog_v1.md) — read that file for full **P/K** ratings and SaaS-wide quick wins.

---

## How Repo A relates to the five backlog themes

| # | Repo B theme | Repo A role (stay thin) |
|---|----------------|-------------------------|
| **1** | AI provenance & evaluation | Never treat Hermes chat/export as publish truth; optional **pointers** to Repo B `published` commentary IDs |
| **2** | Coverage & freshness product API | Keep using bounded **validate/summary** tools; later consume Repo B product API instead of ad-hoc CSV |
| **3** | Feature contracts | Tier 3 observer + Repo B read adapter must **track** contract version env or manifest key |
| **4** | Bounded orchestration in Repo B | Tier **5A** workflow artifacts **document** runs; **execute** stays Repo B bounded HTTP + env gates |
| **5** | Customer intelligence tier | **Do not** widen Telegram to customer-facing copilot; Stage 2–3 are Repo B + `app/` |

---

## Repo A — when-ready enhancements

### A1. Align workflow artifacts with Repo B run IDs (extends Tier 5A)

When Repo B exposes stable **run_id** on bounded families, store it in `operator_bounded_workflows/run_records/` frontmatter (`repo_b_run_id`). **K:** low once API exists.

### A2. Posture rollup includes product coverage API (when #2 lands)

Extend `summarize_powerunits_operator_posture` with optional read-only fetch of Repo B coverage snapshot — **additive JSON**, no new writes.

### A3. Contract version in operator manifest

`manifest_powerunits_*` tools echo **`REPO_B_DATASET_CONTRACT_VERSION`** (or read from allowlisted Repo B doc key) so operators see drift. **K:** low.

### A4. Dashboard plugin (optional, later)

Read-only tab: coverage + recent bounded run statuses via Repo B API — only after **observe** posture and network policy confirmed ([`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md)).

---

## Quick wins (Repo A — high leverage, low blast radius)

| Area | Quick win | Why |
|------|-----------|-----|
| **Deploy** | Run production from **`main` / `powerunits-internal-setup`**, not upstream-only branches missing Powerunits overlays | Avoids “docs say tier 6, runtime is tier 0” |
| **Dashboard** | Keep **`HERMES_POWERUNITS_DASHBOARD_MODE=observe`** + **`first_safe_v1`** on Railway | Prevents config/cron/skill drift from UI |
| **Railway** | Use **`docker/railway_gateway_with_dashboard.sh`** so **`PORT`** serves dashboard | Fixes 502 while keeping gateway |
| **Posture** | Weekly **`summarize_powerunits_operator_posture`** + non-empty `caution_flags` triage | Cheap health fingerprint |
| **Tiers** | Increase capability tier only after roadmap checklist + tag baseline ([`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md)) | Reversible liberation discipline |
| **Docs** | Update [`powerunits_hermes_dashboard_skills_atlas_v1.md`](powerunits_hermes_dashboard_skills_atlas_v1.md) tier env **`0…6`** when atlas next touched | Atlas is advisory; avoid stale tier cap |
| **Bounded tools** | One **smoke order** in RUNBOOK: preflight → execute → validate → summary for one DE window per family (flags on) | Catches env gate regressions |
| **Cache** | After env gate changes, confirm Telegram agent cache invalidation behavior (see recent `Invalidate Telegram agent cache` commits) | Prevents stale tool surfaces |
| **Upstream merge** | When merging Hermes upstream, re-verify **`observe`** middleware in `hermes_cli/web_server.py` and policy merge tests | Merge conflict hotspot |

---

## Explicit deferrals (unchanged)

- Full workflow engine / multi-agent control plane in Hermes.
- Curator autonomous writes without ops sign-off.
- Repo B semantics changes from Hermes tools alone.
- Customer-facing copilot on Telegram.

See Repo B backlog for SaaS Stages 2–3 and pgvector/Merit Order sequencing.

---

## Review cadence

- Review with Repo B [`saas_ai_evolution_backlog_v1.md`](../../EU-PP-Database/docs/architecture/saas_ai_evolution_backlog_v1.md) before tier uplift or major upstream Hermes merge.

**Last structured review:** 2026-07-10 (v1 initial).
