---
name: powerunits-de-outage-repair-playbook
description: Use when coverage inventory reports DE outage_awareness warnings (missing hourly outage data) or operator asks to fix DE outage Step B gaps. Human-in-the-loop: diagnose read-only first, propose bounded repair, execute only after explicit operator confirmation.
version: 1.0.0
author: Powerunits
license: MIT
metadata:
  hermes:
    tags: [powerunits, outage, bounded, operator, human-in-the-loop]
    related_skills: [powerunits-data-health-triptychon]
---

# DE Outage Repair Playbook (human-in-the-loop)

## Trigger

- Inventory row: `bounded_outage_awareness` → `warning` / missing Step B for **DE**
- Triptychon flagged „Ausfall-Daten-Reparaturbedarf für DE“

## Phase A — Diagnose (read-only, always first)

**Do not** use `read_powerunits_doc` — call bounded tools by exact name below.

1. Run triptychon skill or at minimum:
   - `inventory_powerunits_bounded_coverage_v1` for `DE`, 7d window
   - Outage awareness **validate** + **summary** bounded tools for DE (24h slice)
2. State clearly: **symptom**, **affected surface**, **correlation_id**.

## Phase B — Plan (read-only)

3. Optional: `plan_powerunits_de_stack_remediation` (remediation planner) if gate enabled — **no jobs**.
4. Propose **one** bounded repair window (≤24h UTC) and expected post-check (re-inventory).

## Phase C — Execute (only after explicit confirmation)

**Stop here** unless operator message contains explicit approval, e.g. „Ja, outage repair ausführen für [window]“.

5. `execute_powerunits_outage_repair_bounded_slice` for approved DE window only.
6. Re-run **validate** + **inventory** for same window.
7. Summarize: before/after inventory status for `bounded_outage_awareness`.

## Completion criteria

- Without confirmation: ended at Phase B with clear ask
- With confirmation: repair + validate + inventory delta documented

## Safety

- **DE only** for outage repair v1
- No `market_feature_job` auto-run from this playbook
- Never chain execute into triptychon automatically
