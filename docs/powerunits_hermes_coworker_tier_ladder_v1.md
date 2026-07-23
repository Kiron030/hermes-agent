# Powerunits Hermes — Co-Worker Tier Ladder v1

**Audience:** Ron + future agents operating Repo A (`hermes-agent`).  
**Canonical capability roadmap (technical):** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md).  
**This file:** **operating plan** — how we climb tiers toward a strong, still-bounded co-worker without losing `first_safe_v1`.

**Status (2026-07-23):** Hermes **v0.19.0** live; profile `stage1_read_health`; **`HERMES_POWERUNITS_CAPABILITY_TIER=1`** (Phase 2A).  
Baseline tags: **`powerunits-tier0-baseline-20260723`**, **`powerunits-tier1-uplift-20260723`**.  
**Soak:** stay on Tier 1 ≥3 days before Tier 2.

---

## Goal (what “strong co-worker” means here)

Hermes should become an **increasingly capable internal analyst / operator assistant** that:

1. **Reads & synthesizes** multi-country data health (Repo B HTTP, allowlisted).
2. **Diagnoses** posture / drift / gaps before humans dig into Railway/Logs.
3. **Prepares** reviewable drafts and workflow records (later tiers).
4. **Never** silently becomes source of truth for product data, migrations, or unbounded writes.

**Repo B stays canonical.** Hermes is thin, gated, and reversible.

---

## North-star principles

| Principle | Practice |
|-----------|----------|
| **One lever per step** | Change either **capability tier** *or* **bounded profile** *or* **model** — never all three in one deploy. |
| **Evidence before uplift** | Posture JSON + RUNBOOK smokes green on current tier. |
| **Rollback is env-only** | Lower `HERMES_POWERUNITS_CAPABILITY_TIER` + redeploy/restart; no volume migration. |
| **Profile ≠ Tier** | `stage1_read_health` / `stage1_operator_execute` gate **bounded HTTP families**. Capability tier gates **workspace/skills overlays**. |
| **Backfill first** | Prefer `stage1_read_health` while national backfills run; execute profile only for short, deliberate repair windows. |
| **Curator stays off** | Until a signed decision; Tier 3+ observer ≠ autonomous skill merge. |

---

## Current recommended Railway env (Tier 1 soak)

```text
HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1
HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health
HERMES_POWERUNITS_CAPABILITY_TIER=1
```

Tier 0 (conservative rollback) uses `CAPABILITY_TIER=0` instead.

---

## Ladder (capability env → co-worker capability)

| Step | Env `CAPABILITY_TIER` | What Hermes gains | Human role | Soak / gate |
|------|----------------------|-------------------|------------|-------------|
| **T0** | `0` | Trusted Analyst: triptychon, posture, BZN/Repo-B/Timescale reads, empirical validate, first_safe | Daily driver; ask Hermes for health/posture | **Done** — tag `powerunits-tier0-baseline-20260723` |
| **T1** | `1` | Phase **2A**: workspace full summary + bounded text/path search under `hermes_workspace` | Use for session notes / export hygiene | **Live soak** — uplift evidence 2026-07-23; tag `powerunits-tier1-uplift-20260723` |
| **T2** | `2` | Phase **2B**: allowlisted local reference reads | Drop curated local refs; Hermes searches them | ≥1 week on T1; no secrets under local_reference |
| **T3** | `3` | Skills **observer** (diagnose/propose JSON, SKILL preview) | Triage proposals; Curator still off | Explicit staffed review window |
| **T4** | `4` | Skill **drafts** under `hermes_workspace/drafts/...` only | Human review drafts; never auto-promote to live `skills/` | Draft volume watchers green |
| **T5** | `5` | Review **governance** + `governance/` notes | Accept/reject drafts via review_status | Clear promotion ritual |
| **T6** | `6` | Bounded **workflow scaffolding** (run records) | Operator still triggers Repo B execute | Records ≠ HTTP truth |

**Parallel track (not capability tier):** bounded **execute** profile  
`HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_operator_execute` — only for short repair campaigns after backfill maturity. Rollback = switch back to `stage1_read_health`.

**Deferred / separate decision:** model upgrade (`gpt-4.1`), Curator on, public dashboard, multi-region (blocked by volume).

---

## Weekly co-worker rhythm (Tier 0 → T1)

| When | Action |
|------|--------|
| After every Railway deploy | `summarize_powerunits_operator_posture` → expect `aligned: true`, Curator false, version matches |
| 1× / week | `read_powerunits_multi_country_data_health_v1` → archive `operator_summary_v1` into workspace exports if useful |
| As needed | Empirical validate / BZN / Repo-B key reads |
| Before any tier uplift | Full watcher checklist in progressive posture + this ladder § Gate checklist |

---

## Gate checklist (copy before each uplift)

- [ ] Baseline tag exists for current known-good (`powerunits-tier0-baseline-*` or newer).
- [ ] `summarize_powerunits_operator_posture`: `aligned: true`, no unexplained `caution_flags`.
- [ ] Stage-1 Telegram smokes (posture + multi-country + one negative first_safe check).
- [ ] `HERMES_POWERUNITS_BOUNDED_PROFILE` still intentional (`stage1_read_health` during backfill).
- [ ] One change only: set `HERMES_POWERUNITS_CAPABILITY_TIER` to next integer.
- [ ] Redeploy / restart; confirm posture overlay for new tier (`phase_2a_*` / `phase_2b_*` / …).
- [ ] Soak period from table above before next step.

**Rollback:** set tier to previous integer → Redeploy → re-run posture.

---

## Immediate next steps (ordered)

### Step 1 — Close Tier 0 (repo + ops) — **done**

1. Keep image on **v0.19** with hotfixes (`reasoning_effort` OpenAI gate, CSV allowlist alignment).
2. Confirm Railway redeploy of latest `powerunits-internal-setup` HEAD.
3. Posture smoke: **`aligned: true`** (ERA5 CSV no longer false-missing).
4. Annotated tag **`powerunits-tier0-baseline-20260723`** on known-good SHA.

### Step 2 — Tier 1 uplift (Phase 2A) — **done (soak)**

Evidence (Telegram 2026-07-23):

| Smoke | Result |
|-------|--------|
| Posture | `tier_effective_integer=1`, `powerunits_tier1_analysis_listed=true`, `telegram_powerunits_tier1_analysis_observed=true`, `aligned=true`, `caution_flags=[]` |
| `summarize_powerunits_workspace_full` | 8 files / ~8KB; `caution_flags=[]` |
| `search_powerunits_workspace_text` | Content search OK after note write; path-only queries initially empty → **fixed** (path/basename match) |
| Exports summary | 3 files, clean |
| Multi-country regression | Read-only triptychon OK |
| Negatives | Path escape / Tier-2 tool expected unavailable; note: **`web`/`search` are allowed** in first_safe (not a fail) |

**Operator:** soak ≥3 days on Tier 1; use workspace notes for ops diary; optional `/sethome` in the one Telegram chat.

### Step 3 — Tier 2 (allowlisted locals) — next after soak

Only after T1 soak. Prepare `powerunits_local_reference` content deliberately (no secrets).

### Step 4+ — Skills / drafts / governance / workflow

Follow progressive posture overlay docs; never skip soak; never enable Curator as a shortcut.

### Repo B track (parallel, not Hermes tier)

Continue market-expansion / Tier-2 product slices in **EU-PP-Database** with stop-gates. Hermes remains read/analyze until execute profile is explicitly opened.

---

## What not to do

- Jump `CAPABILITY_TIER` from `0` to `6`.
- Open `stage1_operator_execute` + raise tier in the same deploy.
- Click Railway “Fix region identifier” into multi-region while a volume is attached.
- Treat `pre_backfill_gap` as Hermes failure.
- Switch primary model during a tier uplift.

---

## Related

| Doc | Role |
|-----|------|
| [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) | Technical tier/overlay contract |
| [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) | Executable smokes |
| [`powerunits_setup_v2_sustainable_v1.md`](powerunits_setup_v2_sustainable_v1.md) | Bounded profiles RH vs OE |
| [`powerunits_fork_sync_preflight_checklist.md`](powerunits_fork_sync_preflight_checklist.md) | Upstream sync lessons |
| [`upstream_sync_log.md`](upstream_sync_log.md) | Chronological sync evidence |
