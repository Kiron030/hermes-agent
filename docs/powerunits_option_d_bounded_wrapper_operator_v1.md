# Option D bounded wrapper — operator notes (v1)

**What this is:** An **operator-run** Python entrypoint in **Repo A (`hermes-agent`)** that validates a **fixed first-release slice** (PL / `v1` / window ≤ 24h UTC), checks env, then runs **`uv run python -m services.data_ingestion.jobs.market_feature_job`** inside the **Powerunits product repo** checkout. It adds **no** Hermes tool, **no** Telegram surface, **no** new DB objects — same write semantics as the product job alone.

**What this is not:** Not a **Hermes writer** capability; not Stage 2; not safe to expose to untrusted chat interfaces.

**Spec:** `docs/powerunits_option_d_bounded_wrapper_spec_v1.md`  
**Implementation:** `tools/powerunits_option_d_bounded_market_features.py` (`python -m tools.powerunits_option_d_bounded_market_features`)

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Product checkout** | Local clone of **Powerunits / EU-PP-Database** (or equivalent) with `backend/services/.../market_feature_job.py`. |
| **`POWERUNITS_OPTION_D_PRODUCT_ROOT`** | Absolute path to the **repo root** (directory that contains `backend/`). |
| **`uv`** | On `PATH`; wrapper invokes `uv run` from `backend/`. |
| **`.env` or exported env** | `DATABASE_URL`, `DATABASE_URL_TIMESCALE`, `MARKET_FEATURES_WRITE_TARGET=timescale` (wrapper **rejects** other write targets). |

---

## Example invocation

From **hermes-agent** repo root (adjust paths):

```powershell
$env:POWERUNITS_OPTION_D_PRODUCT_ROOT = "W:\Workbench\EU-PP-Database"
$env:MARKET_FEATURES_WRITE_TARGET = "timescale"
# DATABASE_URL / DATABASE_URL_TIMESCALE loaded from product .env or set explicitly
cd W:\Workbench\hermes-agent
python -m tools.powerunits_option_d_bounded_market_features `
  --country PL `
  --start 2024-01-01T00:00:00Z `
  --end 2024-01-02T00:00:00Z `
  --version v1
```

**Stdout:** exactly **one** JSON line (machine-readable). **Exit code:** `0` success, `2` validation, `3` env, `4` job failure, `5` wrapper internal error — see spec.

---

## Assumptions (mapping spec → code)

- **Delegation** is **subprocess** `uv run … -m services.data_ingestion.jobs.market_feature_job` with `cwd=<product>/backend`, not an in-process import — keeps **hermes-agent** free of `pandas` / full product deps.
- **Job failure** is inferred from subprocess **return code ≠ 0** **or** parsed `status=failed` / `Error:` in combined stdout/stderr (the product CLI may exit `0` even on failed runs).
- **`POWERUNITS_OPTION_D_PRODUCT_ROOT`** is the required bridge to Repo B; it was not in the original one-pager spec but is necessary for Repo-A-only layout.

---

## Rollback

Same as product runbook / Option D memo — `DELETE` on `market_features_hourly` for the same `(country_code, version, timestamp_utc)` window. Wrapper does **not** execute rollback.
