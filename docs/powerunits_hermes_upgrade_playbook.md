# Powerunits — Hermes upstream upgrade playbook (lightweight)

**Audience:** maintainers of Repo A (`hermes-agent` / Railway). **Repo B** stays **canonical** product truth; Hermes remains a **thin bounded operator**. Use this for **repeatable** merges (weekly-ish releases, major bumps, or hotfix syncs).

---

## Architecture guardrails (never “accidentally” widen)

- **Repo B:** HTTP contracts, evaluator model, allowlists — unchanged by a normal Hermes runtime bump.
- **Repo A:** Gateway lockdown, `model_tools` whitelist, `docker/apply_powerunits_runtime_policy.py` (`first_safe_v1`), Telegram toolsets — preserve during merge conflicts (see [`powerunits_fork_sync_strategy_v1.md`](powerunits_fork_sync_strategy_v1.md) § hotspots).
- **Do not** merge Repo B **feature** work in the same branch/PR as an upstream Hermes runtime bump — review surface and rollback story get messy.

---

## Branch strategy (hygiene)

| Branch role | Purpose |
|-------------|---------|
| **Long-lived** (`powerunits-internal-setup` or `main` on your fork) | Known-good Powerunits + Hermes overlay. |
| **Prep / docs** | Release-note alignment, policy comments, runbook tweaks — **no** upstream merge yet. |
| **Integration** (`integration/hermes-runtime-v0.12-bump`, `integration/upstream-sync-YYYYMMDD`) | **Only** upstream tag/SHA + conflict resolution + validation. |
| **Stash** | Prefer **small** WIP: finish or move to a named branch before merging upstream — fewer surprise conflicts. |

**Prefer:** prep PR → integration branch → staging → then merge integration into your integration line / `main`.

---

## Staging-first workflow (short)

1. **Pin target:** official **release tag** when available (see below) — not drifting `main`.
2. **Merge** tag into an **integration** branch; resolve conflicts preserving Powerunits layers.
3. Align **`pyproject.toml`** `[project].version` with the release you ship.
4. **Fresh Docker image** (avoid stale `uv`/lock layers).
5. Deploy **staging** Railway; **same** env pattern as prod (`HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`, `HERMES_HOME` volume).
6. **Logs + config** verification, then **bounded smokes** ([`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) order + [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md)).
7. Production only after explicit sign-off — repeat the same cutover checklist subset.

---

## Before merging upstream Hermes

- [ ] Target is a **tag** (e.g. `v2026.4.30` for v0.12.0) unless a **specific untagged fix** is justified — then **record the SHA** in deploy notes.
- [ ] `git fetch upstream --tags` — merge **`vX.Y.Z`**, not anonymous `main` tip, for reproducibility.
- [ ] Conflict hotspots mentally loaded: [`gateway/run.py`](../gateway/run.py), [`model_tools.py`](../model_tools.py), [`docker/apply_powerunits_runtime_policy.py`](../docker/apply_powerunits_runtime_policy.py), CLI/Docker/workflows.
- [ ] **Repo B:** no required change for runtime-only bumps — do not bundle product PRs here.

---

## After staging deploy (Railway — explicit)

- [ ] Gateway healthy; Telegram responds; **no** crash loop on first boot (allow extra time for SQLite/FTS migrations once).
- [ ] Logs: **no** repeating HTTP **400** on the LLM route; **no** raw secrets (`DATABASE_URL`, internal execute secret, bearer tokens).
- [ ] **`$HERMES_HOME/config.yaml`:** bounded Telegram toolsets; **`auxiliary.curator.enabled`** still **false** unless you **intentionally** test Curator ([`hermes_v0_12_staged_upgrade_powerunits.md`](hermes_v0_12_staged_upgrade_powerunits.md)).
- [ ] Bounded smokes passed (governance, inventory, ENTSO‑E market **and** forecast, ERA5, Repo B reads as applicable).

---

## Curator / self-improve — conservative defaults

Hermes ≥ v0.12 adds **Curator** and stronger self-improve paths upstream. For Powerunits **staging/production**: keep **Curator off** unless on a dedicated experiment; never treat auto-written skills/memories as truth for bounded allowlists. Policy + posture: **[`hermes_v0_12_staged_upgrade_powerunits.md`](hermes_v0_12_staged_upgrade_powerunits.md)**.

---

## Lesson: `Unrecognized request argument supplied: think` (custom + OpenAI)

**Cause:** Chat Completions transport injected **`extra_body["think"] = false`** for **any** `provider == "custom"` when reasoning was disabled (`effort: none` / `enabled: false`). That flag is **Ollama-specific**. **Official OpenAI** rejects **any** unknown `think` key (even `false`) → HTTP 400.

**Fix:** Only inject `think` for custom endpoints that accept Ollama’s extension — **omit** on `api.openai.com` / `*.openai.azure.com`. Implemented in **`agent/transports/chat_completions.py`** (`_custom_base_url_accepts_ollama_think_extra_body`).

**Related doc:** Responses vs Chat Completions / `include` issues: [`powerunits_openai_request_compatibility_v1.md`](powerunits_openai_request_compatibility_v1.md).

---

## Release tag vs upstream `main`

| Prefer | When |
|--------|------|
| **Annotated tag** matching the shipped semver | Staging-first, audit trail, predictable diff. |
| **`main` @ SHA** | Only when you need an **untagged** fix — pin SHA in ops notes; expect **larger** unknown delta. |

---

## Duplicate / layering (read this map, don’t fork content)

| Doc | Role |
|-----|------|
| **This file** | **Single entry:** branch discipline, staging order, pitfalls, pointers. |
| [`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) | Docker path, **`v2026.4.30`**, `HERMES_HOME`, staging sequence, **bounded smoke order**. |
| [`hermes_v0_12_staged_upgrade_powerunits.md`](hermes_v0_12_staged_upgrade_powerunits.md) | **v0.12 feature** posture (Curator, redaction, pinning), negative checklist. |
| [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) | **Executable** checks post-deploy + v0.12 cutover subsection. |
| [`powerunits_fork_sync_strategy_v1.md`](powerunits_fork_sync_strategy_v1.md) | **Ongoing** sync mechanics; prefers tags for major bumps (see playbook). |
| [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) | **Single main Hermes:** `tier0` baseline, placeholders `tier1`–`tier3`, **rollback/tag contract**, pre-tier watcher checklist (Phase 0). |

**Do not prune** the v0.12-specific docs; **cross-link** from here instead of repeating long checklists.

---

## Weekly / frequent Hermes releases — practical do / don’t

**Do**

- One integration branch per bump; merge **tag** when possible.
- Staging Railway first; skim logs for **new** HTTP 400/422 patterns before declaring success.
- Keep **`first_safe_v1`** unless a formal decision expands surface.

**Don’t**

- Mix Repo B releases with Hermes runtime merges in one PR.
- “Accept theirs” wholesale on **`gateway/run.py`** / **`model_tools.py`** — re-apply Powerunits lockdown.
- Enable Curator, optional plugins, or broad toolsets to “try the new Hermes” on the production operator gateway without a signed decision trail.
