# Powerunits Hermes — operator env cheat sheet (v1)

**Purpose:** one-page map for Railway variables vs tools. Canonical detail: `docs/powerunits_bounded_flags_consolidated_v1.md`.

## Profile bundles (recommended)

Set **one** profile on Railway; individual vars remain as overrides.

| Profile | Env | Use when |
|---------|-----|----------|
| **Read health** | `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health` | Daily ops, triptychon, validates — **no execute** |
| **Operator execute** | `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_operator_execute` | Above + bounded recompute (market, ENTSO-E, ERA5, outage repair) |

At container start, `apply_powerunits_runtime_policy.py` fills **missing** profile keys only — explicit Railway values win.

**Always required (both profiles):**

- `POWERUNITS_INTERNAL_EXECUTE_BASE_URL`
- `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`
- `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`

## Data-health triptychon (read-only)

| Tool | Env gate |
|------|----------|
| `read_powerunits_coverage_snapshot_v1` | `HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED=1` |
| `inventory_powerunits_bounded_coverage_v1` | `HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED=1` |
| `read_powerunits_worker_country_coverage_freshness_v1` | `HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED=1` |

**Skill:** `skills/productivity/powerunits-data-health-triptychon/SKILL.md`

## Execute families (operator profile only)

| Family | Primary gate |
|--------|----------------|
| Market features DE/PL | `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED` |
| Option D PL | `HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED` (+ preflight) |
| ENTSO-E market | `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED` |
| ENTSO-E forecast | `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED` |
| ERA5 weather | `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED` |
| Outage repair DE | `HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED` |

**Outage playbook skill:** `skills/productivity/powerunits-de-outage-repair-playbook/SKILL.md` — execute **only after human confirmation**.

## Posture fingerprint

Telegram / CLI:

```
summarize_powerunits_operator_posture
```

Returns `bounded_profile_v1_read_only`, `data_health_fingerprint_de_read_only`, `caution_flags`.

## Tier uplift (next qualitative step)

| Tier | Env | Adds |
|------|-----|------|
| **0** (today) | `HERMES_POWERUNITS_CAPABILITY_TIER=0` | Trusted Analyst, bounded tools |
| **1** | `=1` after baseline tag | Workspace analysis overlay |

See `docs/powerunits_hermes_progressive_posture_v1.md` before tier increases.

**Last updated:** 2026-07-11
