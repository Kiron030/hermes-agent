# Option D — bounded wrapper CLI (design spec v1, one page)

**Status:** **Implemented** in Repo A — `python -m tools.powerunits_option_d_bounded_market_features` (see `docs/powerunits_option_d_bounded_wrapper_operator_v1.md`). **Delegation:** subprocess `uv run python -m services.data_ingestion.jobs.market_feature_job` in the product repo `backend/` — **no new SQL** in the wrapper.

**Related:** `docs/powerunits_option_d_next_write_capsule_step_v1.md`, experiment record in `docs/powerunits_option_d_pl_one_day_staging_gonogo_v1.md`.

---

## Purpose

Give operators a **single** entrypoint that **cannot** widen country/window/version by accident, then **delegates** to the existing market feature job (same delete + upsert semantics as production). Intended host: **controlled** machine (CI worker, bastion, or operator laptop with `.env`), **not** Hermes Stage 1.

---

## argv surface (required flags only — no positional, no optional slice args)

| Flag | Type | Semantics |
|------|------|-----------|
| `--country` | string | **Must** normalize to **`PL`** only for v1 release; any other value → **exit 2**. |
| `--start` | string | Inclusive UTC bound, **ISO-8601** with `Z` offset (e.g. `2024-01-01T00:00:00Z`). Parsed strictly; invalid → **exit 2**. |
| `--end` | string | **Exclusive** UTC bound, same format as `runbook` / `market_feature_job` CLI (`timestamp_utc < end`). Invalid or `end <= start` → **exit 2**. |
| `--version` | string | **Allowlist** `{v1}` only for first release; else → **exit 2**. |

**Forbidden in v1:** extra countries, comma lists, `--dry-run` that still writes, passthrough of arbitrary SQL, flags forwarded to `market_feature_job` beyond the four mapped parameters (`version`, `countries=[PL]`, `start`, `end`).

---

## Validation rules (hard fails before any DB write)

1. **Country:** after uppercasing, **`country == "PL"`** only.  
2. **Window:** `start` and `end` parse as UTC-aware; require **`end > start`** and **`(end - start) <= timedelta(hours=24)`** (no multi-day, no >24h spans).  
3. **Version:** **`version in {"v1"}`**.  
4. **Optional v1.1 (design note):** reject if `start` minute/second ≠ `00:00` for stricter “calendar day” alignment — **policy choice**; document if adopted.

On any validation failure: **no** call to `run()`; print JSON error to stdout (shape below) and **exit 2**.

---

## Environment dependencies

| Variable | Required | Role |
|----------|----------|------|
| `DATABASE_URL` | yes | Primary DB URL — job **reads** normalized inputs via `get_app_db_url()` (same as today). |
| `DATABASE_URL_TIMESCALE` | yes | Timescale write target when write target is timescale. |
| `MARKET_FEATURES_WRITE_TARGET` | yes, value **`timescale`** | Wrapper **must** verify equality before delegate; if missing or not `timescale` → **exit 3** (prevents silent primary write). |
| `POWERUNITS_OPTION_D_PRODUCT_ROOT` | yes (implementation) | Absolute path to Powerunits repo root (parent of `backend/`); required for `uv run … market_feature_job` delegation from Hermes repo layout. |

**Do not** print full URLs or passwords in logs — stdout JSON may include **host/db fingerprint** only (same class as operator runbooks).

---

## Delegation (no new SQL)

1. **`cd` / subprocess** into **`<POWERUNITS_OPTION_D_PRODUCT_ROOT>/backend`**.  
2. Run **`uv run python -m services.data_ingestion.jobs.market_feature_job`** with the same four parameters as the spec flags (equivalent to in-process **`run(...)`**).  
3. **Do not** embed `INSERT`/`DELETE`/`ON CONFLICT` in the wrapper — all writes remain inside the job module.

---

## stdout JSON shape (single line to stdout on exit; no secrets)

**Success (exit 0):**

```json
{
  "ok": true,
  "wrapper": "option_d_bounded_market_features_v1",
  "slice": {"country": "PL", "version": "v1", "start_utc": "…", "end_utc_exclusive": "…"},
  "write_target": "timescale",
  "db_fingerprint": {"primary_host": "…", "timescale_host": "…"},
  "job": {"status": "success", "run_id": "…", "rows_written": 24, "error_message": null}
}
```

**Validation failure (exit 2):**

```json
{"ok": false, "error_class": "validation", "code": 2, "message": "human-readable reason", "slice": null}
```

**Environment failure (exit 3):**

```json
{"ok": false, "error_class": "environment", "code": 3, "message": "MARKET_FEATURES_WRITE_TARGET must be timescale", "slice": null}
```

**Job failure (exit 4):** `error_class`: `"job_failed"`, include `job.status`, `job.error_message` if present (truncate long strings). **Unexpected exception (exit 5):** `error_class`: `"internal"` — message without stack secrets.

---

## Exit codes

| Code | Meaning |
|------|---------|
| **0** | Validation passed, delegate ran, **`job.status == success`**. |
| **2** | argv / policy validation failed (no delegate). |
| **3** | Required env missing or `MARKET_FEATURES_WRITE_TARGET != timescale`. |
| **4** | Delegate ran; **`job.status != success`** (business/job error). |
| **5** | Unexpected Python error in wrapper (bug); no partial success claim. |

---

## Explicitly **out of scope** (this spec)

- **Hermes tool wiring** — no new MCP/tool definitions, no `first_safe` changes.  
- **DB migrations / new Postgres roles** — no `CREATE ROLE`, no `SECURITY DEFINER` capsule in this step.  
- **Broadening slice** — no multi-country, no new `version` values, no arbitrary window without a **new** reviewed spec version (`v2` of this doc).  
- **Post-job driver refresh** — `market_driver_feature_job` not invoked unless a separate spec adds it.

---

*Contract: this file. Implementation: `tools/powerunits_option_d_bounded_market_features.py`.*
