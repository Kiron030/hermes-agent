---
name: powerunits-data-health-triptychon
description: Use when the operator asks for national Tier-1 data health, coverage status, baseline readiness, or post-deploy freshness across Europe. Runs the read-only Repo B triptychon (snapshot, inventory, worker freshness) for all 11 national Tier-1 ISO2 countries and returns a concise ops summary. Never executes writes without explicit human confirmation.
version: 1.1.0
author: Powerunits
license: MIT
metadata:
  hermes:
    tags: [powerunits, data-health, bounded, operator, read-only, multi-country]
    related_skills: [powerunits-multi-country-analyst-read-v1, powerunits-de-outage-repair-playbook]
---

# Powerunits Data-Health Triptychon (read-only, national Tier-1)

## When to use

- Operator asks: „Data health“, „Coverage“, „National Tier-1 ready?“, „Post-deploy check“, „Alle Länder“
- After market expansion backfill or bounded repairs (verify before execute)
- Weekly ops fingerprint for Hermes Telegram

## Country scope (default)

**National Tier-1 (11 ISO2):** `DE`, `NL`, `BE`, `FR`, `AT`, `CZ`, `PL`, `FI`, `HU`, `SK`, `RO`

Operator may narrow to a subset (e.g. `DE`, `PL`) but **never assume DE-only** unless explicitly asked.

**Family scope notes (Repo B authoritative):**

- ENTSO-E market/forecast + worker freshness: national Tier-1 above
- ERA5 weather: Tier-1 bbox keys (19 ISO2) when ERA5 allowlist env is set in profile
- Market features execute: **DE, PL only**
- Market driver execute: **DE only**
- Outage repair: **DE only** — `skipped` for other countries in inventory is expected

## Preconditions

- `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
- Data-health gates on (or `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health` / `stage1_analyst_read`)
- `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` set

## Procedure (strict order)

**Preferred:** one call to **`read_powerunits_multi_country_data_health_v1`** (orchestrator) with default countries — use **`operator_summary_v1`** in the Telegram reply.

**Manual triptychon** (if orchestrator gate off):

**Do not** use `read_powerunits_doc`, roadmap markdown paths, or doc aliases — call API tools by **tool name**.

1. **Pick window** — default **7 UTC days** `[start,end)` ending at today 00:00Z unless operator specifies otherwise.
2. **Snapshot** — `read_powerunits_coverage_snapshot_v1` for national Tier-1 `country_codes` (11 ISO2 default).
3. **Inventory** — `inventory_powerunits_bounded_coverage_v1` same window/countries. Prefer `chat_summary`.
4. **Worker freshness** — `read_powerunits_worker_country_coverage_freshness_v1` with `national_country_codes` matching step 2, `rows_window_days=7`.
5. **Synthesize** — respond in **≤8 bullet points**:
   - **Grün:** countries with baseline_ready + inventory ok/skipped-only + freshness pass
   - **Ops-Aktion:** per-country warnings with **one** suggested bounded next step — **no execute** without explicit confirmation
6. **Record** — optional: `save_hermes_workspace_note` under `exports/` with correlation_ids.

## Completion criteria

- All three tools attempted (or orchestrator success) or gate-off reason stated
- Country-level baseline / outcome counts included
- No write/recompute tools invoked in this skill

## Safety

- **Read-only contract** — Repo B remains source of truth; rerun after repairs.
- **`skipped` in inventory** for non-DE outage = expected, not an error.
