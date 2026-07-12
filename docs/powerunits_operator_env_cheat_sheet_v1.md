# Powerunits Hermes — operator env cheat sheet (v1)

**Purpose:** one-page map for Railway variables vs tools. Canonical detail: `docs/powerunits_bounded_flags_consolidated_v1.md`.

## Profile bundles (recommended)

Set **one** profile on Railway; individual vars remain as overrides.

| Profile | Env | Use when |
|---------|-----|----------|
| **Read health** | `HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health` | Daily ops, triptychon, validates — **no execute**; ERA5 Tier-1 allowlist in profile |
| **Analyst read** | `=stage1_analyst_read` | Alias — multi-country read/analyze/synthesize |
| **Operator execute** | `=stage1_operator_execute` | Above + market features DE/PL, market driver DE, ENTSO-E, ERA5, outage repair |

## Country scope (Hermes mirror)

| Family | ISO2 |
|--------|------|
| National Tier-1 | DE, NL, BE, FR, AT, CZ, PL, FI, HU, SK, RO |
| Market features execute | DE, PL |
| Market driver execute | DE |
| Outage repair | DE |
| Empirical ENTSO-E (read-only candidate validate, Repo B) | DK, NO, IE |
| Policy-hold / complex price (not Tier-1 mirror) | ES, IT, SE |
| BZN advisory reads | DK, NO, SE (+ IT, IE prices) |

**Tier-2 / candidates:** documented in `country_scope_v1` — **not** in default triptychon (Repo B semantics differ). Deep-dive via BZN tools or future empirical validate Hermes tool.


Unset ENTSO-E allowlist ⇒ full national Tier-1. Unset ERA5 allowlist ⇒ DE-only (profile sets Tier-1 CSV).

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
| `read_powerunits_multi_country_data_health_v1` | All three gates above |

**Skills:** `powerunits-data-health-triptychon`, `powerunits-multi-country-analyst-read-v1`

## Execute families (operator profile only)

| Family | Primary gate |
|--------|----------------|
| Market features DE/PL | `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED` |
| Market driver DE | `HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED` |
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

Returns `bounded_profile_v1_read_only`, `data_health_fingerprint_de_read_only` (national Tier-1 baseline rollup), `caution_flags`.

## Tier uplift (next qualitative step)

| Tier | Env | Adds |
|------|-----|------|
| **0** (today) | `HERMES_POWERUNITS_CAPABILITY_TIER=0` | Trusted Analyst, bounded tools |
| **1** | `=1` after baseline tag | Workspace analysis overlay |

See `docs/powerunits_hermes_progressive_posture_v1.md` before tier increases.

**Last updated:** 2026-07-12
