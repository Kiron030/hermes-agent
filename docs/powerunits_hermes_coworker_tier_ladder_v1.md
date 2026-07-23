# Powerunits Hermes — Co-Worker Tier Ladder v1

**Audience:** Ron + future agents operating Repo A (`hermes-agent`).  
**Canonical capability roadmap (technical):** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md).  
**This file:** **operating plan** — how we climb tiers toward a strong, still-bounded co-worker without losing `first_safe_v1`.

**Status (2026-07-23):** Hermes **v0.19.0** live; profile `stage1_read_health`; **`HERMES_POWERUNITS_CAPABILITY_TIER=4`** (Tier 4A drafts) — **smoke green**, soak.  
Baseline tags: **`powerunits-tier0-baseline-20260723`**, **`powerunits-tier1-uplift-20260723`**, **`powerunits-tier2-uplift-20260723`**, **`powerunits-tier3-uplift-20260723`**, **`powerunits-tier4a-uplift-20260723`**.  
Curator **off**. Soft watch: older drafts / README may lack Tier‑4A frontmatter markers.

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

## Current recommended Railway env (Tier 4A soak)

```text
HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1
HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health
HERMES_POWERUNITS_CAPABILITY_TIER=4
```

Rollback to Tier 3: set `CAPABILITY_TIER=3`.

---

## Ladder (capability env → co-worker capability)

| Step | Env `CAPABILITY_TIER` | What Hermes gains | Human role | Soak / gate |
|------|----------------------|-------------------|------------|-------------|
| **T0** | `0` | Trusted Analyst: triptychon, posture, BZN/Repo-B/Timescale reads, empirical validate, first_safe | Daily driver; ask Hermes for health/posture | **Done** — tag `powerunits-tier0-baseline-20260723` |
| **T1** | `1` | Phase **2A**: workspace full summary + bounded text/path search under `hermes_workspace` | Use for session notes / export hygiene | **Done** — path-search smoke green; tag `powerunits-tier1-uplift-20260723` |
| **T2** | `2` | Phase **2B**: allowlisted locals + JSON/YAML workspace reads + optional `powerunits_local_reference` | Curate refs (no secrets); extended reads | **Done / soak** — smoke 2026-07-23; tag `powerunits-tier2-uplift-20260723` |
| **T3** | `3` | Skills **observer** (diagnose/propose JSON, SKILL preview) | Triage proposals; Curator still off | **Done / soak** — smoke 2026-07-23; tag `powerunits-tier3-uplift-20260723` |
| **T4** | `4` | Skill **drafts** under `hermes_workspace/drafts/...` only | Human review drafts; never auto-promote to live `skills/` | **Done / soak** — smoke 2026-07-23; tag `powerunits-tier4a-uplift-20260723` |
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

### Step 3 — Tier 2 (allowlisted locals) — **done (soak)**

Evidence (Telegram 2026-07-23, after `CAPABILITY_TIER=2`):

| Smoke | Result |
|-------|--------|
| Posture | `tier_effective_integer=2`, Tier‑2 overlay observed, `aligned=true`, no `phase_2b_drift*`, `caution_flags=[]` |
| Manifest | Roots `hermes_workspace` + optional `powerunits_local_reference`; 5 Tier‑2 tools listed |
| `summarize_powerunits_allowlisted_locals` | 9 files / ~8KB workspace; reference dir absent (`files=0`) — OK |
| `search_powerunits_allowlisted_local_text` EXPORTS | ≥1 content hit (`EXPORTS_PHASE1_OPERATOR.txt`); path-only CSV hits incomplete vs T1 → **path match parity** shipped in follow-up |
| Regression `summarize_powerunits_workspace_full` | Still works (Tier 1 retained) |
| Negatives | Path escape blocked; Tier‑3 tools unavailable; web search allowed under first_safe (expected) |

**Operator:** Tier‑2 path-search parity re-smoke **passed** (`EXPORTS` → 3 path hits). Optional seed `docker/powerunits_local_reference_example/` → `/opt/data/powerunits_local_reference/`.

**Expected log noise:** `check_fn … returned False` for **execute/campaign/preflight** under `stage1_read_health` is **normal**.

### What is a “Review-Fenster”?

Kein UI und kein Railway-Feature. Es ist eine **bewusste Operator-Phase** nach einem Tier‑Uplift:

1. Du setzt **nur** `CAPABILITY_TIER` (+ Redeploy).
2. Du läufst die RUNBOOK-Smokes (Posture + neue Tools + ein Negativ).
3. Du (oder Agent + du) **liest** die Outputs — bei Tier 3: Observer-/Diagnose-/Proposal-JSON — und entscheidet, was (nicht) weitergeht.
4. **Curator bleibt aus** (`auxiliary.curator.enabled: false`). Tier 3 schreibt **nichts** in live `skills/`.
5. Wenn Drift/Unruhe: Rollback = Tier wieder auf `2`.

Für Tier 0→2 war “Soak” oft “ein paar Tage ruhig laufen”. Für Tier 3 reicht ein **kurzes, besetztes Fenster** (30–60 Min Telegram), weil das Overlay read-only/propose-only ist — vorausgesetzt Posture bleibt `aligned` und Curator bleibt off.

### Step 4 — Tier 3 (skills observer) — **done (soak)**

Evidence (Telegram 2026-07-23, after `CAPABILITY_TIER=3`):

| Smoke | Result |
|-------|--------|
| Posture | `tier_effective_integer=3`, Tier‑3 observed, Tier 1+2 retained, `aligned=true`, `caution_flags=[]` |
| `summarize_powerunits_skills_observer` | ~99 `SKILL.md`; 12 bundled manifests; 11 active; no load errors |
| `diagnose_powerunits_skills_signals` | no duplicates / stale / injection-like; 0 proposals; clean |
| `propose_powerunits_skill_integration_actions` | `count=0`, `explicitly_not_auto_applied=true`, `requires_human_review=true` |
| Regression `summarize_powerunits_allowlisted_locals` | 9 files; Tier 2 OK |
| Negatives | Path escape / Terminal blocked; no live `skills/` write; Tier‑4 drafts not enabled |
| Optional browse/preview | `research/*` tree + `research/arxiv` preview OK |
| Decision | **Curator bleibt aus**; keine auffälligen Proposals |

**Operator:** soak on Tier 3; use observer weekly if useful; **do not** enable Curator; **do not** jump to Tier 4 until a second review window.

### Step 5 — Tier 4A (skill draft proposals) — **done (soak)**

Evidence (Telegram 2026-07-23, after `CAPABILITY_TIER=4`):

| Smoke | Result |
|-------|--------|
| Posture | `tier=4`, overlays 1–4A observed, `aligned=true`, Curator `false` |
| Soft caution | `tier4a_drafts_some_files_missing_marker_in_head` (legacy/README without Tier‑4A header) — expected hygiene, not fail |
| Manifest | Root `drafts/powerunits_skill_proposals`; live skills never written; human-review contract OK |
| Write smoke | `2026-07-23/tier4a_smoke_operator_note.md` (345 B) with full frontmatter |
| List / read / review | Smoke + legacy drafts visible; review board human-only |
| Boundaries | Path escape / Terminal blocked; **promote to live skills refused** with human path explained |
| Decision | Curator off; smoke not for promotion |

**Character read (ops):** Safety-first, structured, repeats governance contracts from tool JSON — good Stage‑1 Trusted Analyst voice. Soft UX: Telegram message drop occasionally (operator re-ask). Soft data hygiene: one nested legacy path under proposals (`…/drafts/powerunits_skill_proposals/improve_…`) and unmarked README/legacy files.

**Operator:** soak on Tier 4A; do **not** open Tier 4B (`=5`) until draft hygiene + triage feel quiet.

### Adaptation backlog (from Tier‑4A smoke; status)

1. **Done:** Exclude `README_POWERUNITS_TIER4A.txt` from marker caution (already in summarize; documented).
2. **Done (docs):** Telegram fenced-JSON habit + SOUL brevity / no invented promotion.
3. **Done:** Nested-path reject on write + summarize/review caution + `hygiene_hints`.
4. **Operator (manual):** prune legacy nested/unmarked drafts on volume — see overlay hygiene section.
5. **Deferred:** Model bump (`gpt-4.1`) — separate deploy; see OpenAI compatibility doc model table.
6. **Deferred:** Tier 4B (`=5`) after quiet soak.

### Step 6 — Tier 4B / later

Only after Tier‑4A soak. Detail: [`powerunits_tier4b_review_governance_overlay_v1.md`](powerunits_tier4b_review_governance_overlay_v1.md).

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
