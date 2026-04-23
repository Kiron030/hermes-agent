# Stage 2 activation — criteria & guardrails (Powerunits Hermes, Repo A)

**Purpose:** Explicit **gate** before **Controlled Implementer / Hermes-writer** is turned on anywhere (e.g. internal Railway). Until every mandatory item below is satisfied **and** documented owner sign-off exists, **Stage 1 — Trusted Analyst** remains the only live mode.

**This file does not activate anything.** It is a checklist for humans. No tool flags change by reading it.

---

## Required technical preconditions

- [ ] **Writer tool surface is defined in code** — exact tool names, handlers, and `check_fn`/env gates are merged in **Repo A** and reviewed (separate PR from “docs only”; not part of this checklist’s execution until that PR exists).
- [ ] **Runtime policy successor is named and implemented** — e.g. env + gateway/model_tools allowlists match the **narrow** writer surface (not a silent widening of `first_safe_v1` without a reviewed policy id).
- [ ] **Staging path exists** — Hermes can be exercised on a **non-prod** Telegram/webhook or isolated bot token with writer policy **before** production Telegram is switched.
- [ ] **Rollback is documented** — how to revert policy/env/image to Stage 1 in one controlled step (see `RUNBOOK.hermes-stage1-validation.md` for Stage 1 baseline).

---

## Required policy preconditions

- [ ] **Written owner** — one named maintainer/team accountable for Stage 2 Hermes behavior (not “the repo”).
- [ ] **Scope document** — single page or ticket: what writer **may** do (Repo A paths, max files, review rule) and what it **must never** do (below).
- [ ] **Human approval rule** — every apply path requires **explicit** human approval (e.g. PR merge by non-bot, or `/approve` equivalent); **no** auto-merge from Hermes to `main`/production.
- [ ] **Incident response** — who disables writer (env flip, deploy rollback) and within what SLA.

---

## Required repo / workflow preconditions

- [ ] **Repo A vs Repo B** — signed agreement: default writer target is **Repo A only**; **Repo B** changes stay human/CI unless a **separate** signed workflow exists (that workflow is out of scope for this checklist unless attached as addendum).
- [ ] **Branch protection** — target branch for Hermes-originated work cannot be written by bots without required checks/reviewers (Railway does not replace Git hosting rules).
- [ ] **Secrets** — no writer access to production secret stores; no `.env` or token commits in Hermes flows.

---

## Required validation / test expectations (before prod enable)

- [ ] Automated tests cover **new** writer paths at least at smoke level (happy path + one fail-closed rejection).
- [ ] Manual run: proposal → approved minimal patch → CI green on **Repo A** staging branch.
- [ ] **Negative test:** request Repo B apply, deploy, DB write, or infra change → Hermes **refuses** or has no tool to do it (document observed behavior).

---

## Must remain forbidden even after Stage 2 activation

*(Unless a future ADR explicitly extends scope — then replace this checklist, do not “interpret” loosely.)*

- DB **writes**, arbitrary SQL, schema migrations, production data repair from Hermes.
- Railway / DNS / TLS / scaling / env mutation for production from Hermes.
- Committing or rotating **secrets** via agent; editing tracked `.env` files.
- Broad Repo B writes, dependency or API-contract changes without the same human/CI bar as today’s product work.
- Disabling or bypassing **read-first** review gates “temporarily”.

---

## Activation sign-off (mandatory)

| Field | Value |
|-------|--------|
| Date | |
| Approver(s) | |
| Policy id / env names enabled | |
| Staging verification reference (link/ticket) | |

**Rule:** If this table is empty, Stage 2 is **not** activated.

---

**Related docs:** `SOUL.hermes-writer.md` (intent), `RUNBOOK.hermes-writer.md` (behavior **after** activation), `ACCESS_MATRIX.md` (Stage 2 rows + gate note).
