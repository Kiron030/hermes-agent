# Powerunits — Progressive Liberation posture (single main Hermes)

**Audience:** operators of the **internal Powerunits** Hermes (Repo A: `hermes-agent`).  
**Canonical product truth:** **Repo B** — unchanged by this posture model.

**This file is the single canonical roadmap** for staged Hermes capability expansion. Deeper operational docs: workspace exports **1A**, operator diagnostics **1B**, Tier-1 workspace **2A**, Tier-2 allowlisted locals **2B**, **Tier 3** skills integration (**capability env `3`**) — cross-linked below.

**Phase 0 (established):** **rollback/tag contract**, **watcher checklist**, **`HERMES_POWERUNITS_CAPABILITY_TIER`** (**`0`** … **`3`** — **`≥ 1`** **2A**, **`≥ 2`** **2B**, **`= 3`** **Tier 3 skills overlay** — see **`powerunits_capability_tier.py`**).

**Phase 1A:** structured **`exports/`** posture + read-only summaries — § Phase 1A below.

**Phase 1B:** read-only **`summarize_powerunits_operator_posture`** — § Phase 1B below.

**Phase 2A (first controlled liberation on main agent):** **`powerunits_tier1_analysis`** toolset gated by **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 1`** — § Phase 2A below; detail [**`powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md`**](powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md).

**Phase 2B (broader bounded local read):** **`powerunits_tier2_allowlisted_read`** gated by **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 2`** — § Phase 2B below; detail [**`powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md`**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md).

**Tier 3 — skills integration (capability env `3`):** **`powerunits_tier3_skills_integration`** — bounded observe/diagnose/propose-only tooling over **`SKILL.md`** inventory — § Tier 3 below; detail [**`powerunits_tier3_skills_integration_overlay_v1.md`**](powerunits_tier3_skills_integration_overlay_v1.md).

---

## Related docs (cross-links)

| Doc | Role |
|-----|------|
| [**`powerunits_runtime_v0_12_integration.md`**](powerunits_runtime_v0_12_integration.md) | Docker/`HERMES_HOME`, `first_safe_v1`, staged deploy, bounded smoke order. |
| [**`hermes_v0_12_staged_upgrade_powerunits.md`**](hermes_v0_12_staged_upgrade_powerunits.md) | v0.12 Curator/self-improve posture; negative checklist. |
| [**`powerunits_hermes_upgrade_playbook.md`**](powerunits_hermes_upgrade_playbook.md) | Branches, tags, staging-first merges. |
| [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) | Executable bounded checks post-deploy. |
| [**`powerunits_workspace_v1.md`**](powerunits_workspace_v1.md) | Workspace tool contract (`analysis` / `notes` / `drafts` / `exports`). |
| [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md) | **Phase 1A detail:** export naming, overwrite semantics, hygiene thresholds, summary tool reference. |
| [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md) | Posture JSON (**1B** core + overlays **2A / 2B / Tier 3**). |
| [**`powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md`**](powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md) | **Phase 2A** gated workspace analytics + bounded search — thresholds/watchers/rollback only. |
| [**`powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md`**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md) | **Phase 2B** Tier-2 allowlisted locals — thresholds/watchers/rollback only. |
| [**`powerunits_tier3_skills_integration_overlay_v1.md`**](powerunits_tier3_skills_integration_overlay_v1.md) | **Tier 3** (**`HERMES_POWERUNITS_CAPABILITY_TIER = 3`**) bounded skills observer + proposal JSON — Curator posture, rollback. |

**Capability-tier env (**`HERMES_POWERUNITS_CAPABILITY_TIER`):** **`0`**–**`3`**. Policy merge (after **`powerunits_workspace`**): strip overlay toolsets not implied by tier; **`≥ 1`** inserts **2A**; **`≥ 2`** inserts **2B** after **2A**; **`= 3`** inserts **Tier 3** **`powerunits_tier3_skills_integration`** after **2B**. Tool **`check_fn`** gates align. **`powerunits_capability_tier.py`**.

**Naming:** **Capability env `3`** (Tier 3 skills tools) is **not** the same as the **conceptual** roadmap bucket **`tier3`** below (historic “curator product era” phrasing) — see § distinction there.

---

## Capability tiers (conceptual)

### `tier0` — Current approved baseline (mandatory starting point)

- **Means:** **`first_safe_v1`**, bounded Telegram tool surface, **`auxiliary.curator.enabled: false`** (policy + operator review), strict tool gating, Hermes as **thin operator** over Repo B HTTP.
- **May change:** Hotfixes that **preserve** bounded contracts; Hermes/runtime patch versions per upgrade playbook.

### `tier1` — internal assistive expansion (incremental)

- **Goal:** More **internal assistive** value with **low structural risk** on the **same** main Hermes.
- **Phase 1A (live experiment):** Stronger **`hermes_workspace/exports`** posture only — documented conventions, **read-only** **`summarize_powerunits_workspace_exports`**, non-destructive operator pointer file; see [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md). Does **not** widen bounded HTTP families from workspace-only scope.
- **Phase 1B (live experiment):** **Read-only aggregated posture view** via **`summarize_powerunits_operator_posture`** (`toolset` **`powerunits_operator_posture`**) — merges tier env readout, **`HERMES_POWERUNITS_RUNTIME_POLICY`**, curator **`config.yaml`** observation, Phase **1A** **`caution_flags`**, Telegram toolset drift checks for **`powerunits_tier1_analysis`** when **`tier ≥ 1`**, and tier-up checklist; [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md). **No** bounded family widen, Curator enablement, or Repo B weakening.
- **Phase 2A (live experiment; `HERMES_POWERUNITS_CAPABILITY_TIER ≥ 1`):** **`powerunits_tier1_analysis`** overlay — **read-only** **`summarize_powerunits_workspace_full`**, **`search_powerunits_workspace_text`** bounded to **`hermes_workspace`** [**detail**](powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md). Policy merge adds Telegram toolset; **`tier → 0`** removes it (**no migration**).
- **Phase 2B (live experiment; `HERMES_POWERUNITS_CAPABILITY_TIER ≥ 2`):** **`powerunits_tier2_allowlisted_read`** — allowlisted locals read/summarize/search + extended workspace text types [**detail**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md). **`tier → 1`** drops **2B** only; **`tier → 0`** drops **2A+2B** (and Tier 3 cannot apply).
- **Tier 3 skills integration (live experiment; `HERMES_POWERUNITS_CAPABILITY_TIER = 3`):** **`powerunits_tier3_skills_integration`** — observe/diagnose/propose JSON + bounded **`SKILL.md`** preview; **no** tool-level merges [**detail**](powerunits_tier3_skills_integration_overlay_v1.md). **`tier → 2`** drops **Tier 3** only.
- **Still deferred:** Unbounded skill hub exposure on Telegram, silent merge agents, Repo B–authoritative skill truth, any overlay **without** watcher bullets in **this** file.
- **Must not:** Weaken Repo B as source of truth; enable Curator writes; widen bounded family semantics without Repo B governance.

### `tier2` *(conceptual — alternate LLM / provider / transport; **not** “capability env = 2” / Phase 2B)*

- **Goal:** Controlled **model / provider / transport** experimentation on the **same** main deployment (env-driven), with budgets and golden checks. (**Phase 2B** is **Hermes-internal allowlisted read expansion** at **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 2`**, not alternate LLMs — see [**Phase 2B**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md).)
- **May change:** Non-default LLM routing for defined tasks; staged config flags documented in runbooks.
- **Must not:** Silent elevation of autonomous self-improvement; unbounded outbound tools.

### `tier3` *(conceptual — Curator/skills autonomy product era; **not** capability env ``3`` / Tier 3 overlay)*

- **Historical placeholder phrasing:** “Observed skill growth / Curator…” as a **future product class** requiring separate sign-off.
- **Today's capability env `3`:** Bounded **skills integration observer** tooling only ([**Tier 3 detail**](powerunits_tier3_skills_integration_overlay_v1.md)) — **does not** license silent merges or Repo B weakening.
- **May change:** Read-only/strawman Curator summaries when **explicitly enabled** upstream; staged flags per decision record.
- **Must not:** Treat autonomous skill deltas as Repo B evaluator truth; broaden bounded HTTP semantics from skills paths.

---

## Protected across all tiers

- **Repo B:** Canonical HTTP contracts, evaluator behavior, migrations, allowlists — Hermes does **not** replace or silently override this truth.
- **Bounded operator semantics:** Existing **family/tool gating** and **`gateway/run.py`** lockdown posture remain **explicit review** items; no “tier” bypasses them without the same review bar as any other production change.
- **Secrets:** No raw secrets in logs; same bar as [`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) smoke list.
- **Rollback discipline:** Tier increases run only after baseline tags/snapshots and checklist (below) where applicable.

---

## Rollback / baseline contract

### Git tag naming

Use **annotated tags** when a configuration + image combination is **known-good**:

| Pattern | When to use |
|---------|--------------|
| `powerunits-tier0-baseline-YYYYMMDD` | After bounded smokes succeed on staging/prod and you want a **Hermes-repo** rollback anchor for conservative posture. |
| `powerunits-hermes-<semver>-YYYYMMDD` | Optional: align with shipped **`pyproject.toml`** version after a runtime bump (e.g. post–v0.12.0). |
| Existing upstream Hermes tags (e.g. `v2026.4.30`) | Continue to pin **upstream merges** per upgrade playbook — orthogonal to tier labels. |

**When to create tags**

- Immediately **before** a **tier uplift** experiment (deploy/config change intended to widen capability).
- After any **successful** promotion where you want a **cheap git revert anchor** (`git checkout tag` → compare → redeploy).

**When to snapshot / backup `HERMES_HOME`**

- Before **`config.yaml`/`.env`/Railway variable** experiments that touch model, plugins, or tool-related flags.
- Before major Hermes image upgrades (often redundant with reproducible images, but cheap insurance for SQLite/session state).

Suggested minimal backup: tarball or volume snapshot of **`$HERMES_HOME`** excluding huge caches if needed — document where backups live in ops notes.

**Reverting config/runtime experiments**

1. Restore Railway env vars (or `.env`) to values recorded at **`powerunits-tier0-baseline-*`** tag or deploy checklist.
2. Restore `config.yaml` from backup **or** redeploy image + let `docker/apply_powerunits_runtime_policy.py` merge `first_safe_v1` again (verify Curator stays off unless intentionally set).
3. Redeploy previous **known-good container image digest** if the experiment touched code paths.
4. Re-run **`RUNBOOK.hermes-stage1-validation.md`** bounded subset.

Git-level rollback:

```bash
git fetch origin --tags
# Compare or cherry-pick; prefer revert commits on integration branch over force-push.
```

---

## Watcher foundation — checklist before raising tier

Keep this **manual or log-based** in Phase 0; automation can come later.

| Signal | Minimal check |
|--------|----------------|
| **Bounded governance recheck** | Governance read / bounded rollout sanity per runbook smoke order. |
| **Inventory recheck** | Coverage inventory tool still behaves (`feature_disabled` when flags off matches expectations). |
| **Config/runtime fingerprint** | Record: `HERMES_POWERUNITS_RUNTIME_POLICY`, image digest/semaphore, **`HERMES_POWERUNITS_CAPABILITY_TIER`**, model id in `config.yaml`, `auxiliary.curator.enabled`. |
| **Phase 2A analytics (when `tier ≥ 1`)** | Sample **`summarize_powerunits_workspace_full`** after major operator sessions; escalating **`high_*`** or depth-skip totals → reconcile sprawl (**[`powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md`](powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md)**). |
| **Phase 2B allowlisted-local analytics (when `tier ≥ 2`)** | Sample **`summarize_powerunits_allowlisted_locals`** after **`powerunits_local_reference`** drops or **`*.json`/`*.yaml`** growth; **`tier2_locals_full_scan_cap`** → prune or **`subdir`** work ([**`powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md`**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md)). |
| **Tier 3 skills observer (`tier = 3`)** | **`summarize_powerunits_skills_observer`** / **`diagnose_*`** / **`propose_*`** — duplicate/stale/proposal-volume signals; keep **`auxiliary.curator`** posture explicit ([**Tier 3 detail**](powerunits_tier3_skills_integration_overlay_v1.md)). |
| **Workspace / export hygiene** | Disk under `HERMES_HOME` / `hermes_workspace/exports` not growing without cause; no unexpected world-writable paths; **Phase 1A:** run **`summarize_powerunits_workspace_exports`** after material export work and archive or delete stale files per [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md). |
| **Posture snapshot (env + exports subset)** | **`summarize_powerunits_operator_posture`** (Phase 1B) — quick JSON fingerprint before tier uplift; see [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md). |
| **Curator** | **`enabled: false`** for `tier0`; any deviation is **explicit** and documented (not drift). |

**Caution triggers:** Passing smoke regressions, new HTTP 400/422 patterns on LLM routes, unexplained Telegram tool errors, curator directories appearing when supposed off.

**Phase 1B posture rollup:** Non-empty **`caution_flags`** → reconcile env, curator, Telegram overlays (**`phase_2a_*`**, **`phase_2b_*`**, **`tier3_skills_drift*`** / **`tier3_curator_*`**) (**[`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md)).

**Phase 2A rollback triggers:** Repeated **`workspace_full_scan_cap`** failures, unintended multi-gigabyte text drops into **`hermes_workspace`**, or unexplained spikes in **`search_powerunits_workspace_text`** scan caps → **set tier to `0`, restart gateway, re-run policy** (see [**Phase 2A detail**](powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md)).

**Phase 2B rollback triggers:** **`tier2_locals_full_scan_cap`**, unintended large secrets under **`powerunits_local_reference`** (never stage credentials intentionally), recurring **`phase_2b_drift*`** Telegram mismatches → **set capability tier to `1` or `0`**, re-run policy, restart ([**Phase 2B detail**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md)).

**Tier 3 rollback triggers:** recurring **`tier3_skills_drift*`**, runaway **`proposal_count`** churn without human triage, or **`tier3_curator_autonomous_path_enabled`** without staffed review → **`HERMES_POWERUNITS_CAPABILITY_TIER≤2`**, policy + restart ([**Tier 3 detail**](powerunits_tier3_skills_integration_overlay_v1.md)).

**Phase 1A export sprawl (lightweight):** use summary tool **`caution`** hints (file count / total bytes / large single file). **Suspicious** = growth with no correlated operator task, many tiny CSVs from retries, or disk pressure on the Railway volume — see [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md) § Watcher.

---

## Phase 1A — workspace / exports (roadmap slice)

**Intent:** Improve **internal reports and CSV snapshots** ergonomics **without** new write surfaces to Repo B or new bounded API families.

| Item | Contract |
|------|----------|
| **Conventions** | Documented naming + `overwrite_mode` semantics — detail: [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md). |
| **Read-only hygiene** | Tool **`summarize_powerunits_workspace_exports`** (same `powerunits_workspace` toolset): counts, bytes, largest files, soft **caution** flags (thresholds in detail doc). |
| **Operator pointer** | **`exports/EXPORTS_PHASE1_OPERATOR.txt`** created once if missing — points back to **this roadmap** + detail doc (**never overwrites** an existing file). |
| **Rollback** | Git revert Repo A deployment; optional volume cleanup unchanged from general posture § Rollback. |

**Frozen in Phase 1A:** No Curator, no new Telegram tool categories beyond documenting/using existing workspace helpers, no Repo B weakening.

---

## Phase 1B — operator diagnostics (roadmap slice)

**Intent:** Consolidated **read-only posture awareness** so operators answer “what tier label / policy snapshot / curator observation / exports hygiene rollup applies **right now**?” before raising freedom — **without** mutating **`HERMES_HOME`**.

| Item | Contract |
|------|----------|
| **Tool** | **`summarize_powerunits_operator_posture`** (`toolset` **`powerunits_operator_posture`**, Telegram allowlist aligned with **`first_safe_v1`** alongside other bounded toolsets). |
| **Reads** | Env + **`auxiliary.curator.enabled`** + Telegram observation (**2A/2B/Tier 3** drift) + Phase **1A** export subset. |
| **Watchers** | JSON **`caution_flags`** including **`tier3_*`** when **`tier ≥ 3`**, and Curator cautions when **`auxiliary.curator.enabled`** is **true** (**[`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md)). |
| **Rollback** | Remove tool via Repo A revert; **no persistent side effects** from invoking the tool itself. |

**Frozen in Phase 1B:** No bounded family widen; no curator or self-improvement **writes**; no Repo B authority shift.

---

## Phase 2A — Tier-1 workspace analysis overlay (controlled liberation)

**Intent:** First **meaningful** widening of **internal read-heavy** assistance **on the single main agent** while **`first_safe_v1`** bounded families + Repo B truth stay untouched.

| Item | Contract |
|------|----------|
| **Gate** | **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 1`** in the **gateway env** at **`apply_powerunits_runtime_policy.py`** run **and** subsequent gateway boot. **`tier = 0`** removes **`powerunits_tier1_analysis`** from merged Telegram allowlists (reversible env-only rollback). |
| **Toolset** | **`powerunits_tier1_analysis`** — **`summarize_powerunits_workspace_full`**, **`search_powerunits_workspace_text`**. Bounded to **`*.md`/`.txt`/`.csv`** under **`hermes_workspace`** (same subtree contract as **`powerunits_workspace`**). **`check_fn`** mirrors tier gate defensively. |
| **Observers** | Posture JSON **`phase_2a_overlay_read_only`** + tool-local **`caution_flags`** (**[`detail doc`](powerunits_phase2a_tier1_workspace_analysis_overlay_v1.md)**). |
| **Pre-flight** | Tag + **`HERMES_HOME`** snapshot (**§ Rollback**), bounded smokes green, curator still expected **false** absent explicit experiment. |

**Frozen:** No Repo B evaluator/HTTP widen, no curator. **Conceptual roadmap `tier2` (LLM routing)** experiments remain placeholders — orthogonal to Phase **2B** capability-tier read expansion.

---

## Phase 2B — Tier-2 allowlisted locals read overlay

**Intent:** Add **meaningful analytical leverage** beyond Phase **2A** — **`*.json`/`.yaml`/`.yml`**, **`powerunits_local_reference`**, aggregated navigation — **without** broad **`HERMES_HOME`** access or Repo B write expansion.

| Item | Contract |
|------|----------|
| **Gate** | **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 2`** when **`apply_powerunits_runtime_policy.py`** runs **and** on gateway boot. **`tier`** **`0`** or **`1`** omits **`powerunits_tier2_allowlisted_read`** from Telegram (**`1`** retains **2A** only). |
| **Toolset** | **`powerunits_tier2_allowlisted_read`** — [**detail doc**](powerunits_phase2b_tier2_allowlisted_locals_overlay_v1.md): **`manifest_*`**, **`summarize_*`**, **`search_*`**, **`read_powerunits_allowlisted_workspace_extended_file`**, **`read_powerunits_local_reference_file`**. **`check_fn`** requires **`≥ 2`**. |
| **Observers** | Posture **`phase_2b_overlay_read_only`** + **`phase_2b_drift*`** **`caution_flags`**. |
| **Pre-flight** | Tier **1** signals stable (**2A** posture clean); fresh baseline tag; curator policy-off unless deliberate. |

---

## Tier 3 — skills integration observer (capability env `3`)

**Intent:** **Meaningful skill maturity** for the **same** main Hermes — read/assess/report/propose **without** silent merges, **without** treating skills as Repo B truth, **without** weakening bounded operations.

| Item | Contract |
|------|----------|
| **Gate** | **`HERMES_POWERUNITS_CAPABILITY_TIER = 3`** at policy apply + gateway boot. **`tier ≤ 2`** omits **`powerunits_tier3_skills_integration`** from Telegram (**reversible** env + policy + restart). |
| **Toolset** | **`powerunits_tier3_skills_integration`** — inventory, diagnostics, **human-review proposal JSON**, bounded **`SKILL.md` preview** ([**detail**](powerunits_tier3_skills_integration_overlay_v1.md)). **Writes:** none from these tools. |
| **Curator** | Policy default **`auxiliary.curator.enabled: false`** (**unchanged**). Upstream Hermes Curator (**if ever enabled**) may still **observe/propose** per `agent/curator.py` — **explicit ops review** required; Tier 3 tools **never** imply approval to auto-merge **critical operator** skills. |
| **Observers** | Posture **`phase_tier3_skills_observer_read_only`**, **`tier3_skills_drift*`**, **`tier3_curator_autonomous_path_enabled`** (**[`operator posture doc`](powerunits_operator_posture_diagnostics_v1.md)**). |
| **Rollback** | Set **`HERMES_POWERUNITS_CAPABILITY_TIER`** to **`2`** or lower; **`apply_policy`**, restart. |

---

## Phase 0 outcome summary

Phase 0 **establishes:** tier vocabulary + placeholders (now **tier1** has first concrete slice), rollback/tag contract, watchlist, and **`HERMES_POWERUNITS_CAPABILITY_TIER`** log label.

Phase 1A **adds:** export posture documentation + non-invasive read-only summarization + pointer file (bounded-safe).

**Phase 1B adds:** read-only posture diagnostics + drift signals (**2A / 2B / Tier 3** Telegram alignment + Curator posture signals).

**Phase 2A adds:** gated **`powerunits_tier1_analysis`** read-heavy workspace summary + substring search (**no writes**, **no Repo B widen**).

**Phase 2B adds:** gated **`powerunits_tier2_allowlisted_read`** — structured extensions, optional **`powerunits_local_reference`**, bounded multi-root search (**still read-only**, no shell).

**Tier 3 adds:** gated **`powerunits_tier3_skills_integration`** — skills inventory/diagnostics/review-only proposals (**no auto merge from this overlay**).

**Fallback ladder:** **`3 → 2`** drops Tier 3 only; **`2 → 1`** drops **2B**; **`1 → 0`** drops **2A** (**policy re-apply + restart**).

## Next roadmap steps (after Tier 3 observer)

- **Later:** tighter integration with **`skill_manage`** behind **explicit** approvals (not Tier 3); broader skill hub tooling only with roadmap bullets here.
- **Conceptual LLM routing (`tier2`)** remains **deferred**.
- **Full autonomous skill product / silent merge narratives** remain **explicitly out of scope** for Powerunits staged Hermes absent separate governance.

**Intentionally unchanged:** Repo B canonicality, **`gateway/run.py`** bounded lockdown ethos, **`first_safe_v1`** default **Curator off** on fresh policy merges absent deliberate override.
