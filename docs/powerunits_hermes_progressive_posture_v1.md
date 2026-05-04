# Powerunits — Progressive Liberation posture (single main Hermes, Phase 0)

**Audience:** operators of the **internal Powerunits** Hermes (Repo A: `hermes-agent`).  
**Canonical product truth:** **Repo B** — unchanged by this posture model.

**Purpose (Phase 0):** Establish a **documented capability-tier vocabulary**, **rollback/baseline contract**, and **minimal pre-tier watchlist**. **No broader runtime freedom yet** — `tier0` matches today’s conservative operator baseline (`HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`, Curator off by policy/docs).

---

## Related docs (cross-links)

| Doc | Role |
|-----|------|
| [**`powerunits_runtime_v0_12_integration.md`**](powerunits_runtime_v0_12_integration.md) | Docker/`HERMES_HOME`, `first_safe_v1`, staged deploy, bounded smoke order. |
| [**`hermes_v0_12_staged_upgrade_powerunits.md`**](hermes_v0_12_staged_upgrade_powerunits.md) | v0.12 Curator/self-improve posture; negative checklist. |
| [**`powerunits_hermes_upgrade_playbook.md`**](powerunits_hermes_upgrade_playbook.md) | Branches, tags, staging-first merges. |
| [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) | Executable bounded checks post-deploy. |

Optional env observability (Phase 0 **label only**, no behavior change for `tier>0` until explicitly wired):

- **`HERMES_POWERUNITS_CAPABILITY_TIER`** — integer `0`–`3`, default `0`. Logged at container start; implementation hook: **`powerunits_capability_tier.py`**.

---

## Capability tiers (conceptual)

### `tier0` — Current approved baseline (mandatory starting point)

- **Means:** **`first_safe_v1`**, bounded Telegram tool surface, **`auxiliary.curator.enabled: false`** (policy + operator review), strict tool gating, Hermes as **thin operator** over Repo B HTTP.
- **May change:** Hotfixes that **preserve** bounded contracts; Hermes/runtime patch versions per upgrade playbook.

### `tier1` *(placeholder — not enabled by this doc alone)*

- **Goal:** More **internal assistive** value with **low structural risk**.
- **May change (when approved):** Additional **read-heavy** helper tooling; clarified **workspace/export** roots under explicit allowlists; operational metrics from existing logs.
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
| **Workspace / export hygiene** | Disk under `HERMES_HOME` / `hermes_workspace/exports` not growing without cause; no unexpected world-writable paths. |
| **Curator** | **`enabled: false`** for `tier0`; any deviation is **explicit** and documented (not drift). |

**Caution triggers:** Passing smoke regressions, new HTTP 400/422 patterns on LLM routes, unexplained Telegram tool errors, curator directories appearing when supposed off.

---

## Phase 0 outcome summary

Phase 0 **establishes:** tier vocabulary + placeholders, rollback/tag contract, watchlist, and a **single env-controlled tier integer** surfaced in logs (**no extra tools, no Curator**, no weakening of Repo B).

**Intentionally unchanged:** `first_safe_v1` policy script behavior, bounded gateway lockdown, Repo B canonicality, Curator defaults for production/staging stance.

---

## Next step (Phase 1 experiment — strongest first candidate)

**Tier 1 pilot:** introduce **one** narrowly scoped capability under explicit allowlist (e.g. additional **read-only** helper or **single export subdirectory** convention) **after** a `powerunits-tier0-baseline-*` tag and `HERMES_HOME` backup — with fingerprints captured and bounded smokes re-run unchanged.
