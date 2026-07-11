---
name: powerunits-data-health-triptychon
description: Use when the operator asks for DE/PL data health, coverage status, baseline readiness, or post-deploy freshness. Runs the read-only Repo B triptychon (snapshot, inventory, worker freshness) and returns a concise ops summary with green vs action items. Never executes writes without explicit human confirmation.
version: 1.0.0
author: Powerunits
license: MIT
metadata:
  hermes:
    tags: [powerunits, data-health, bounded, operator, read-only]
    related_skills: [powerunits-de-outage-repair-playbook]
---

# Powerunits Data-Health Triptychon (read-only)

## When to use

- Operator asks: „Data health“, „Coverage“, „Ist DE/PL ready?“, „Post-deploy check“
- After market expansion backfill or bounded repairs (verify before execute)
- Weekly ops fingerprint for Hermes Telegram

## Preconditions

- `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
- Data-health gates on (or `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health`)
- `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` set

## Procedure (strict order)

1. **Pick window** — default **7 UTC days** `[start,end)` ending at today 00:00Z unless operator specifies otherwise.
2. **Snapshot** — call `read_powerunits_coverage_snapshot_v1` for requested `country_codes` (default `DE`, `PL`).
3. **Inventory** — call `inventory_powerunits_bounded_coverage_v1` same window/countries. Prefer `chat_summary`; avoid dumping full JSON to Telegram.
4. **Worker freshness** — call `read_powerunits_worker_country_coverage_freshness_v1` with `national_country_codes` matching step 2, `rows_window_days=7`.
5. **Synthesize** — respond in **≤5 bullet points**:
   - **Grün:** baseline_ready, passed freshness, inventory families `ok`
   - **Ops-Aktion:** any `warning`/`failed`/`gaps` with **one** suggested bounded next step (validate, repair, execute) — **do not run execute** unless operator explicitly confirms in a follow-up message
6. **Record** — optional: `save_hermes_workspace_note` under `exports/` with correlation_ids (operator audit).

## Completion criteria

- All three tools attempted or gate-off reason stated
- HTTP status and `baseline_ready` / outcome counts included
- No write/recompute tools invoked in this skill

## Safety

- **Read-only contract** — Repo B remains source of truth; rerun tools after repairs for fresh reads.
- **`skipped` in inventory** for PL outage = expected (DE-only family), not an error.
