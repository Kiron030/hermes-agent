# Powerunits — Progressive Liberation posture (single main Hermes)

**Audience:** operators of the **internal Powerunits** Hermes (Repo A: `hermes-agent`).  
**Canonical product truth:** **Repo B** — unchanged by this posture model.

**This file is the single canonical roadmap** for staged Hermes capability expansion. Deeper operational docs are cross-linked below (workspace exports **1A**, operator diagnostics **1B**) — not duplicated here.

**Phase 0 (established):** **capability-tier vocabulary**, **rollback/baseline contract**, **minimal pre-tier watchlist**, optional **`HERMES_POWERUNITS_CAPABILITY_TIER`** log label (no extra runtime freedom by itself).

**Phase 1A (first concrete tier1 carve-out):** **structured `exports/` posture** — conventions, read-only export summary tool, one-time operator pointer file under `exports/`; see **§ Phase 1A — workspace / exports** below.

**Phase 1B:** **read-only operator posture diagnostics** — tool **`summarize_powerunits_operator_posture`** aggregates tier env, runtime policy snapshot, curator **observation**, Phase 1A export signals subset, bounded-assumption reminders, tier-up checklist; see **§ Phase 1B — operator diagnostics** below.

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
| [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md) | **Phase 1B:** read-only posture tool JSON semantics, watchers, rollup with Phase 1A signals. |

Optional env observability (Phase 0 **label only**, no behavior change for `tier>0` until explicitly wired):

- **`HERMES_POWERUNITS_CAPABILITY_TIER`** — integer `0`–`3`, default `0`. Logged at container start; implementation hook: **`powerunits_capability_tier.py`**.

---

## Capability tiers (conceptual)

### `tier0` — Current approved baseline (mandatory starting point)

- **Means:** **`first_safe_v1`**, bounded Telegram tool surface, **`auxiliary.curator.enabled: false`** (policy + operator review), strict tool gating, Hermes as **thin operator** over Repo B HTTP.
- **May change:** Hotfixes that **preserve** bounded contracts; Hermes/runtime patch versions per upgrade playbook.

### `tier1` — internal assistive expansion (incremental)

- **Goal:** More **internal assistive** value with **low structural risk** on the **same** main Hermes.
- **Phase 1A (live experiment):** Stronger **`hermes_workspace/exports`** posture only — documented conventions, **read-only** **`summarize_powerunits_workspace_exports`**, non-destructive operator pointer file; see [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md). Does **not** widen bounded HTTP families or Telegram tool allowlists beyond existing workspace tools.
- **Phase 1B (live experiment):** **Read-only aggregated posture view** via **`summarize_powerunits_operator_posture`** (`toolset` **`powerunits_operator_posture`** first_safe_v1 Telegram) — merges tier env readout, **`HERMES_POWERUNITS_RUNTIME_POLICY`**, best-effort **`auxiliary.curator.enabled`** observation from **`config.yaml`**, condensed Phase **1A** export **`caution_flags`**, roadmap-aligned operator checklist strings; [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md). **Still no** runtime mutations, bounded family widen, Curator enablement, or Repo B weakening.
- **Still deferred (later tier1 steps):** Additional helpers **beyond** diagnostics + exports hygiene — each small change plus watchlist bullet in **this roadmap**.
- **Must not:** Weaken Repo B as source of truth; enable Curator writes; widen bounded family semantics without Repo B governance.

### `tier2` *(placeholder)*

- **Goal:** Controlled **model / provider / transport** experimentation on the **same** main deployment (env-driven), with budgets and golden checks.
- **May change:** Non-default LLM routing for defined tasks; staged config flags documented in runbooks.
- **Must not:** Silent elevation of autonomous self-improvement; unbounded outbound tools.

### `tier3` *(placeholder)*

- **Goal:** **Observed** skill growth / curator / self-improvement paths — **proposal or human-gated** only until separately signed.
- **May change:** Read-only observation of Curator output; staged enablement policies documented per decision record.
- **Must not:** Treat auto-written artifacts as authoritative for Repo B schemas or bounded allowlists.

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
| **Workspace / export hygiene** | Disk under `HERMES_HOME` / `hermes_workspace/exports` not growing without cause; no unexpected world-writable paths; **Phase 1A:** run **`summarize_powerunits_workspace_exports`** after material export work and archive or delete stale files per [**`powerunits_workspace_phase1_exports_v1.md`**](powerunits_workspace_phase1_exports_v1.md). |
| **Posture snapshot (env + exports subset)** | **`summarize_powerunits_operator_posture`** (Phase 1B) — quick JSON fingerprint before tier uplift; see [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md). |
| **Curator** | **`enabled: false`** for `tier0`; any deviation is **explicit** and documented (not drift). |

**Caution triggers:** Passing smoke regressions, new HTTP 400/422 patterns on LLM routes, unexplained Telegram tool errors, curator directories appearing when supposed off.

**Phase 1B posture rollup:** Non-empty **`caution_flags`** from **`summarize_powerunits_operator_posture`** → reconcile env (`HERMES_POWERUNITS_RUNTIME_POLICY`, tier label), curator observation, failed export summarization (**[`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md)).

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
| **Reads** | Environment (`HERMES_HOME`, **`HERMES_POWERUNITS_CAPABILITY_TIER`**, **`HERMES_POWERUNITS_RUNTIME_POLICY`**) + best-effort YAML read of **`auxiliary.curator.enabled`** from **`config.yaml`** + condensed Phase **1A** **`summarize_powerunits_workspace_exports`** output; **never** emits secrets from config. |
| **Watchers** | JSON **`caution_flags`** (tier unset reminder, unset/non-default runtime policy, curator `true`, export hygiene echoes, summarized errors). Operational detail [**`powerunits_operator_posture_diagnostics_v1.md`**](powerunits_operator_posture_diagnostics_v1.md). |
| **Rollback** | Remove tool via Repo A revert; **no persistent side effects** from invoking the tool itself. |

**Frozen in Phase 1B:** No bounded family widen; no curator or self-improvement **writes**; no Repo B authority shift.

---

## Phase 0 outcome summary

Phase 0 **establishes:** tier vocabulary + placeholders (now **tier1** has first concrete slice), rollback/tag contract, watchlist, and **`HERMES_POWERUNITS_CAPABILITY_TIER`** log label.

Phase 1A **adds:** export posture documentation + non-invasive read-only summarization + pointer file (bounded-safe).

**Phase 1B adds:** read-only **`summarize_powerunits_operator_posture`** + diagnostics reference doc (**no state mutation**).

**Intentionally unchanged:** `first_safe_v1` policy script behavior **for bounded families**, bounded gateway lockdown, Repo B canonicality, Curator defaults for production/staging stance.

---

## Next roadmap steps (after Phase 1A / Phase 1B)

- **tier1 continuation:** additional **read-heavy** helpers beyond exports + diagnostics (each documented with rollback snippet in **this file**).
- **tier2 / tier3:** unchanged conceptual placeholders above — revisit only after tier1 learnings and fingerprint discipline.
