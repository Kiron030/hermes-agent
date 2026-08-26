# Operator observability 2 — DB health read

**Slice:** `OPERATOR_OBSERVABILITY_2_DB_HEALTH_READ`  
**Status:** implemented in Repo A + Repo B; **not deployed**. Human merge gate required.  
**Predecessor:** [`powerunits_operator_observability_1_country_coverage_v1.md`](powerunits_operator_observability_1_country_coverage_v1.md)

```text
Operator Hermes
  → read_powerunits_db_health_*_v1 / read_powerunits_timescale_observe_v1
  → POST /internal/hermes/bounded/v1/db-health/{storage,planner,indexes,vacuum,sessions,statements,timescale}
  → Repo B catalog + pg_stat_* + timescaledb_information
```

Hermes does **not** receive `DATABASE_URL_TIMESCALE` on this path and does **not** execute SQL.

This slice reuses the country-coverage control plane. It does **not** add a second DB architecture.

## Tool contracts

| Tool | Route | Effect |
|------|-------|--------|
| `read_powerunits_db_health_storage_v1` | `…/db-health/storage` | `READ` |
| `read_powerunits_db_health_planner_v1` | `…/db-health/planner` | `READ` |
| `read_powerunits_db_health_indexes_v1` | `…/db-health/indexes` | `READ` |
| `read_powerunits_db_health_vacuum_v1` | `…/db-health/vacuum` | `READ` |
| `read_powerunits_db_health_sessions_v1` | `…/db-health/sessions` | `READ` |
| `read_powerunits_db_health_statements_v1` | `…/db-health/statements` | `READ` |
| `read_powerunits_timescale_observe_v1` | `…/db-health/timescale` | `READ` |

| Field | Value |
|-------|--------|
| Toolset | `powerunits_db_observe` |
| Gate | `HERMES_POWERUNITS_DB_HEALTH_READ_ENABLED` |
| Credentials | existing `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` |
| Profile | added to `stage1_read_health` (fills missing keys only; explicit Railway values win) |
| Approval | none (read) |

Inputs: optional `relation` (catalog id) and `limit` (top-N). No SQL, free table names, or URLs.

## Performance lesson from country coverage

Unscoped whole-history `MIN`/`MAX` caused Timescale chunk-lock amplification. DB health therefore:

- reads catalog / `pg_stat_*` / `timescaledb_information` only
- never scans allowlisted data tables
- skips Timescale chunk heap sizing (`SKIPPED_TO_AVOID_CHUNK_FANOUT`)
- sets `statement_timeout=8s` and `lock_timeout=2s` in Repo B
- bounds top-N (default 10 / 20, hard max 25 / 50)

## Security

```text
EFFECT_CLASS = READ
DB_CREDENTIAL_IN_HERMES = NO
ARBITRARY_SQL = NO
ARBITRARY_HTTP = NO
WRITE_AUTHORITY_ADDED = NO
```

`pg_stat_statements` missing → `UNAVAILABLE`, not a system failure. No `CREATE EXTENSION`.  
CAGG / policy / job absence → `NOT_CONFIGURED`. Query text is omitted or redacted to a fingerprint.

Developer Hermes does not receive this toolset. Country coverage remains registered and unchanged.

**Next slice:** `OPERATOR_OBSERVABILITY_3_PLATFORM_OBSERVE`
