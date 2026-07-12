---
name: powerunits-multi-country-analyst-read-v1
description: Read/analyze/synthesize operator view across national Tier-1 countries — cross-country data health, rollout governance, and bounded family scope without writes. Use for weekly ops reviews, expansion status, and M-track advisory prep.
version: 1.0.0
author: Powerunits
license: MIT
metadata:
  hermes:
    tags: [powerunits, analyst, read-only, multi-country, synthesize, bounded]
    related_skills: [powerunits-data-health-triptychon]
---

# Powerunits Multi-Country Analyst (read-only v1)

## When to use

- „Wie stehen alle Länder?“, „Cross-country health“, „Expansion status“, „Wo sind Lücken?“
- Before staged execute campaigns — confirm read-side health first
- M-track / F-track **advisory** prep (no modeling writes in this skill)

## Default country scope

National Tier-1 ENTSO-E / worker: **DE, NL, BE, FR, AT, CZ, PL, FI, HU, SK, RO** (11)

See **`read_powerunits_multi_country_data_health_v1`** → `country_scope_v1` for ERA5, market features, driver, outage subsets.

## Procedure

1. **Posture** (optional) — `summarize_powerunits_operator_posture` for tier/profile alignment + `data_health_fingerprint`.
2. **Orchestrator** — `read_powerunits_multi_country_data_health_v1` (default 7d window, all national Tier-1).
3. **Governance** (optional) — `governance_powerunits_bounded_rollout_read_v1` when operator asks what Hermes may execute per country/family now.
4. **Empirical deep dive (DK/NO/IE):** `validate_powerunits_entsoe_empirical_candidate_window_v1` — market + forecast families; **not** Tier-1 execute.
5. **Synthesize** for Telegram (structure):
   - **Headline:** green count / action count / window
   - **Top 3 action countries** with one line each (inventory or freshness driver)
   - **Scope reminder:** market features DE/PL, driver DE, outage DE-only
   - **Next bounded step:** validate or repair family X for country Y — **human confirms before execute**
5. **Deep dive** (on request): per-country triptychon via manual three-tool path in `powerunits-data-health-triptychon`.

## Tools (priority order)

| Priority | Tool | Purpose |
|----------|------|---------|
| 1 | `read_powerunits_multi_country_data_health_v1` | Cross-country rollup |
| 2 | `governance_powerunits_bounded_rollout_read_v1` | Hermes allowed-now matrix |
| 3 | `validate_powerunits_entsoe_empirical_candidate_window_v1` | DK/NO/IE empirical read-only (ADR 045) |
| 4 | `summarize_powerunits_operator_posture` | Env/tier/profile fingerprint |
| 5 | `plan_powerunits_de_stack_remediation` | Read-only DE-stack repair plan (no auto-run) |

**Never** in this skill without explicit operator write confirmation: `*_execute_*`, `*_repair_*`, outage repair.

## Completion criteria

- `operator_summary_v1` or equivalent synthesis delivered
- Country scope limitations stated when relevant (features/driver/outage)
- No bounded execute invoked

## Safety

- Hermes is thin client; Repo B JSON is canonical.
- Unset ENTSO-E allowlist = full national Tier-1; unset ERA5 allowlist = DE-only — profile `stage1_*` sets ERA5 Tier-1 CSV.
