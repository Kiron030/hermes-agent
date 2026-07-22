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

- [ ] **Safety tag** on the current deploy branch **before** merging the integration PR (rollback anchor). Example: `powerunits-hermes-pre-v0.19.0-20260722` on `powerunits-internal-setup` @ pre-merge SHA — annotated, pushed to `origin`.
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
- [ ] **Hermes Dashboard (optional Stage 1):** prefer observability-only; for HTTP-level hardening set `HERMES_POWERUNITS_DASHBOARD_MODE=observe` alongside `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` — see [`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) § *Hermes Dashboard*.

---

## Curator / self-improve — conservative defaults

Hermes ≥ v0.12 adds **Curator** and stronger self-improve paths upstream. For Powerunits **staging/production**: keep **Curator off** unless on a dedicated experiment; never treat auto-written skills/memories as truth for bounded allowlists. Policy + posture: **[`hermes_v0_12_staged_upgrade_powerunits.md`](hermes_v0_12_staged_upgrade_powerunits.md)**.

---

## Lesson: `Unrecognized request argument supplied: think` (custom + OpenAI)

**Cause:** Chat Completions transport injected **`extra_body["think"] = false`** for **any** `provider == "custom"` when reasoning was disabled (`effort: none` / `enabled: false`). That flag is **Ollama-specific**. **Official OpenAI** rejects **any** unknown `think` key (even `false`) → HTTP 400.

**Fix:** Only inject `think` for custom endpoints that accept Ollama’s extension — **omit** on `api.openai.com` / `*.openai.azure.com`. Implemented in **`agent/transports/chat_completions.py`** (`_custom_base_url_accepts_ollama_think_extra_body`).

**Related doc:** Responses vs Chat Completions / `include` issues: [`powerunits_openai_request_compatibility_v1.md`](powerunits_openai_request_compatibility_v1.md).

---

## Lesson: v0.19.0 merge — five recurring conflict patterns

**Context:** Upstream **v0.19.0** (`v2026.7.20`) had only **5** conflict files when merge ancestry was clean (contrast v0.17 ancestry bug → hundreds of spurious conflicts). Safety tag before merge: **`powerunits-hermes-pre-v0.19.0-20260722`**.

| File | Pattern | Resolution |
|------|---------|------------|
| `AGENTS.md` | Upstream injects large TUI/Desktop/dependency blocks into Hard Invariants | Keep **fork slim `AGENTS.md`**; upstream detail stays in `docs/agent_context/hermes_development_guide.md` (`git checkout --ours AGENTS.md` is valid) |
| `plugins/model-providers/custom/__init__.py` | Upstream adds top-level `reasoning_effort="none"` (Ollama #14820); fork had `_accepts_ollama_think_extra_body` gate | **Combine:** always emit `reasoning_effort`; gate `extra_body["think"]=False` behind host check |
| `hermes_cli/banner.py` | Upstream dynamic skills grid vs fork first-safe hide | Explicit `if _powerunits_lockdown: hidden … else: upstream grid` — auto-merge left a broken duplicate `else` branch |
| `providers/base.py` | Upstream adds `default_vision_model()`; may drop `base_url` on `get_max_tokens` | Keep **both** upstream hook and fork `get_max_tokens(..., base_url=…)` |
| `agent/transports/chat_completions.py` | Upstream simplifies `extra_body.reasoning` | Keep fork legacy fallback block until **all** call sites use `ProviderProfile` (summary/retry paths still bypass profile lookup) |

**Rollback:** `git checkout powerunits-hermes-pre-v0.19.0-20260722` (or redeploy Railway image pinned to that SHA) → re-run [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) post v0.19 smoke pack.

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
| [`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) § *Hermes Dashboard* | **Same-process** dashboard persistence matrix, boot reconcile vs drift, optional `HERMES_POWERUNITS_DASHBOARD_MODE=observe`. |
| [`powerunits_hermes_dashboard_skills_atlas_v1.md`](powerunits_hermes_dashboard_skills_atlas_v1.md) | **Capability atlas:** Railway 502/gateway+dashboard, `$HERMES_HOME` layout, bundled skills clusters, advisory tier hints (**not** a roadmap). |

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
