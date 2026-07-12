---
name: powerunits-stage1-de-bounded-repair-sequence
description: Use when operator Ron asks to repair or backfill DE data for yesterday or a bounded UTC window. Staged bounded executes only — one family per operator turn unless explicitly told to continue. Never use read_powerunits_doc for tool names.
version: 1.0.0
author: Powerunits
license: MIT
metadata:
  hermes:
    tags: [powerunits, bounded, operator, execute, de, staged]
    related_skills: [powerunits-data-health-triptychon, powerunits-de-outage-repair-playbook]
---

# Stage-1 DE bounded repair sequence (staged)

## When to use

- Operator says „Repair-Sequenz“, „Lücken schließen“, „Backfill DE gestern“
- After triptychon shows ENTSO-E / ERA5 / market warnings for DE

## Hard rules

- **One execute family per operator message** unless they say „weiter mit Schritt N“.
- **Never** `read_powerunits_doc` — call bounded API tools by exact name.
- **Market driver** only after market features validate is acceptable (warning may be ok; failed is not).
- **Outage repair execute** only after explicit confirmation (see outage playbook).

## Stages (DE, default 24h yesterday UTC)

| Step | Tool | Write? |
|------|------|--------|
| 1 | `execute_powerunits_entsoe_market_bounded_slice` | yes |
| 2 | `execute_powerunits_era5_weather_bounded_slice` (skip if CDS unavailable / 502) | yes |
| 3 | `validate_powerunits_market_features_bounded_de_window` → if ok/warning acceptable to operator: `execute_powerunits_market_features_bounded_de_slice` | yes |
| 4 | `validate_powerunits_market_driver_features_bounded_de_window` → then `execute_powerunits_market_driver_features_bounded_de_slice` | yes |
| 5 | Outage playbook Phase A+B — execute only after „Ja, outage repair …“ | repair only |

## Telegram copy-paste prompts for operator Ron

Send **one message at a time**, wait for Hermes result, then next.

**Step 1**
```
execute_powerunits_entsoe_market_bounded_slice für DE: 24h gestern UTC. Nur dieser Schritt, Ergebnis kurz. Nicht read_powerunits_doc.
```

**Step 2** (only if ERA5 data available)
```
execute_powerunits_era5_weather_bounded_slice für DE: 24h gestern UTC. Nur dieser Schritt. Bei 502/CDS nicht verfügbar: stoppen und melden.
```

**Step 3a validate**
```
validate_powerunits_market_features_bounded_de_window für DE: 24h gestern UTC. Nur validate.
```

**Step 3b execute** (only if validate not failed)
```
execute_powerunits_market_features_bounded_de_slice für DE: 24h gestern UTC. Nur dieser Schritt.
```

**Step 4a validate**
```
validate_powerunits_market_driver_features_bounded_de_window für DE: 24h gestern UTC. Nur validate.
```

**Step 4b execute**
```
execute_powerunits_market_driver_features_bounded_de_slice für DE: 24h gestern UTC. Nur dieser Schritt.
```

**Step 5 diagnose**
```
DE Outage Repair Playbook Phase A+B für 24h gestern UTC. Tools direkt aufrufen. Stoppe vor Execute.
```

**Step 5 execute** (only after you type Ja)
```
Ja, outage repair ausführen für DE: 24h gestern UTC, version v1. Danach validate + inventory delta für bounded_outage_awareness.
```

## Completion

- Each step: success/failure + pipeline run id + one-line ops meaning
- Do not auto-chain steps 1→5 in a single turn
