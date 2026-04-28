# Runbook — Hermes Controlled Implementer / writer (Powerunits, **future**)

**Status:** **Not active.** The live internal Hermes on Railway stays **Stage 1 — Trusted Analyst** (`RUNBOOK.hermes-trusted-analyst.md`, `RUNBOOK.hermes-stage1-validation.md`). This runbook defines how a **future** Hermes-writer mode **should** behave once maintainers enable it **explicitly** (policy + tool surface + review path — not documented here as implemented).

**Before any activation:** complete **`CHECKLIST.hermes-writer-activation.md`** (technical, policy, repo, validation, forbidden list) **and** fill the sign-off table. That checklist is the **prerequisite gate**; **this runbook** is the **operating contract after** the gate is passed.

## Repo A vs Repo B

| Repo | Future writer scope |
|------|---------------------|
| **Repo A** (`hermes-agent`) | Only where an explicit, minimal scope is agreed — patches, tests, docs **in this repo** per plan. |
| **Repo B** (Powerunits product) | **Out of scope** for autonomous Hermes apply from Telegram unless a **separate** human-approved workflow exists; default remains human/CI in Repo B. |

## Required plan before any edit (when Stage 2 is on)

1. **Goal** — one sentence tied to a ticket or ADR reference if available.  
2. **Affected files** — exact list (paths); if the list grows, **stop and ask**.  
3. **Non-goals** — what will not be touched (deps, unrelated modules, refactors).  
4. **Risk** — blast radius (max files, contract sensitivity).

No plan → no edits.

## Affected-files listing

- Every change series must end with the **same** file list as approved (plus only if unavoidable: build/lint fix in the same file).  
- **Drift rule:** if implementation discovers a need to touch extra files, **pause** and get approval for the new list.

## Minimal-diff expectation

- Prefer the smallest patch that satisfies the agreed goal.  
- No formatting-only sweeps; no “while we’re here” cleanup.  
- Tests: add or adjust **only** what proves the change; no unrelated test expansion.

## Required validation steps (when Stage 2 is on)

- Targeted tests or checks defined in the plan (e.g. `pytest` path scoped to touched code).  
- Lint/typecheck only if already part of the agreed workflow for that change.  
- Re-read diff before hand-off: no secrets, no `.env`, no surprise files.

## When to stop and ask

- Scope creep, unclear ownership (Repo A vs B), security-sensitive paths, dependency bumps, API contract changes, or anything that would **broaden** runtime or production behavior.  
- Any request that implies **deploy**, **DB migration**, or **infra** — document and hand off to humans; do not execute from Hermes.

## What remains forbidden (even in Stage 2 as specified here)

- DB **writes**, arbitrary SQL, schema changes, production data fixes from Hermes.  
- Railway / DNS / secret store / production env mutation from the agent.  
- Broad repo writes, Repo B apply without the dedicated human workflow, new toolsets or capability flags **not** explicitly approved for that rollout.  
- Enabling writer behavior **by documentation alone** — this file does **not** turn anything on.

## Cross-reference

- **Live today:** `SOUL.hermes.md`, `ACCESS_MATRIX.md` (Stage 1 rows), `RUNBOOK.hermes-trusted-analyst.md`.  
- **Writer intent (future):** `SOUL.hermes-writer.md`.  
- **Activation gate (before enable):** `CHECKLIST.hermes-writer-activation.md`.
