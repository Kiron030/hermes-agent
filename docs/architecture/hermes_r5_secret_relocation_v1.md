# R5 secret relocation and dedicated-principal preparation (v1)

Companion to [`hermes_r5_developer_hermes_v1.md`](./hermes_r5_developer_hermes_v1.md)
and [`hermes_r5_proof_report_v1.md`](./hermes_r5_proof_report_v1.md).

```text
R5_CAPABILITY               = PASS
SAME_WINDOWS_USER_ISOLATION = INVALID
REQUIRED_BOUNDARY           = DEDICATED_NON_ADMIN_WINDOWS_PRINCIPAL
R5_STATUS                   = PARTIAL_PENDING_HUMAN_ISOLATION
```

The dedicated principal (`hermes-dev`) needs `Modify` on
`W:\Workbench\hermes-agent` and `W:\Workbench\EU-PP-Database`. That requirement
collides head-on with secret-class files that currently live *inside* those
roots: no OS boundary can hide a file in a tree the principal must be able to
write. This document resolves the collision by moving the secrets out, and
records everything a human needs in order to execute it.

Nothing here has been executed. Every OS, credential, repository-tracking and
remote change is a human step, listed in [Runbook](#runbook-human-execution).

---

## Mission A — how the secret files are actually loaded

Read-only inspection of Repo B at `W:\Workbench\EU-PP-Database`. No value was
read, printed or copied; only key names, call sites and load mechanisms.

### `.env` (Repo B root)

| CONSUMER | LOAD_MECHANISM | REQUIRES_FILENAME_IN_REPO | CAN_USE_PROCESS_ENV | CAN_USE_EXTERNAL_ENV_FILE |
|---|---|---|---|---|
| `backend/settings.py` (`Settings`, pydantic-settings) | `SettingsConfigDict(env_file=[<root>/.env, backend/.env])`; the list is built from files that exist, and process environment beats `env_file` | NO | YES | NO — the candidate paths are hardcoded |
| `backend/services/data_ingestion/_shared.py::_ensure_dotenv()` | `load_dotenv(<root>/.env)` with default `override=False`; a missing file is a silent no-op | NO | YES | NO |
| `scripts/maintenance/{verify_timescale_worker_schema,verify_plant_master_schema,report_postgres_disk_usage,generate_db_catalog_report}.py`, `scripts/export_system_catalog_to_excel.py`, `backend/tools/bucket_inspect.py` | same guarded `load_dotenv(REPO_ROOT / ".env")` pattern | NO | YES | NO |
| `backend/gem_units_location_restore_v1.py` | `--env-file` CLI argument, then `load_dotenv(env_file, override=False)` | NO | YES | **YES** |
| `scripts/maintenance/check_timescale_write_target_readiness.py` | `dotenv_values(<root>/.env)` — `dotenv_values` returns file content only and never consults `os.environ` | **YES** | **NO** | NO |
| `scripts/validate_timescale_shadow_model_dataset_view.py` | hand-rolled `open(<root>/".env")` parse for `DATABASE_URL_PRIMARY` / `DATABASE_URL_TIMESCALE` | **YES** | **NO** | NO |

Key names present (names only, 32 keys): `DATABASE_URL`,
`DATABASE_URL_PRIMARY`, `DATABASE_URL_TIMESCALE`,
`POSTGIS_STAGING_DATABASE_URL`, `TEST_DATABASE_URL`,
`VERCEL_AUTOMATION_BYPASS_SECRET`, `ANALYTICS_BASIC_AUTH_USER`,
`ANALYTICS_BASIC_AUTH_PASSWORD`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`,
`DAY_PASS_PROVIDER_PRICE_ID`, `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN`,
`NEXT_PUBLIC_PADDLE_ENVIRONMENT`, `ENTSOE_API_KEY`, `ERA5_WRITE_RAW_TO_DB`,
`S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
`PYTHONUNBUFFERED`, `ENTSOE_RAW_S3_*` (5), `ENTSOE_RAW_PG_WRITE`,
`OPEN_METEO_API_KEY`, `OPEN_METEO_HISTORICAL_BASE_URL`,
`OPEN_METEO_FORECAST_BASE_URL`,
`POWERUNITS_MERIT_INTERNAL_INDICATIVE_SECRET`, `FRED_API_KEY`.

**Two consumers are the only ones that genuinely require the filename in the
repository.** Both read the file directly instead of the environment. They are a
small Repo-B follow-up (accept `--env-file`, or fall back to `os.environ`), and
that change belongs in Repo B, not in this PR. Until then, those two scripts are
the only local workflow that relocation breaks.

### `app/.env.local`

| CONSUMER | LOAD_MECHANISM | REQUIRES_FILENAME_IN_REPO | CAN_USE_PROCESS_ENV | CAN_USE_EXTERNAL_ENV_FILE |
|---|---|---|---|---|
| `powerunits-analytics-app` (Next.js, `next dev --port 3001` / `next build`) | framework-native `.env.local` loading; there is no custom dotenv call anywhere in `app/`. Real shell variables take precedence over `.env*` files, and `NEXT_PUBLIC_*` values are inlined at build time from whatever the environment holds | NO | YES | NO |

Key names: `NEXT_PUBLIC_REGIONAL_INDICATOR_LAYER`,
`NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN`.

### `scripts/mapbox/.env.local`

| CONSUMER | LOAD_MECHANISM | REQUIRES_FILENAME_IN_REPO | CAN_USE_PROCESS_ENV | CAN_USE_EXTERNAL_ENV_FILE |
|---|---|---|---|---|
| `scripts/mapbox/apply_units_basemap_muse.ps1` | `Import-DotEnvFile` returns immediately when the file is absent and assigns a variable only when it is currently unset/blank, so the process environment always wins; `Get-SecretToken` additionally accepts `-SecretToken` or `MAPBOX_SECRET_TOKEN` / `MAPBOX_ACCESS_TOKEN` from the environment | NO | YES | NO (`-SecretToken` is the alternative injection point) |

Key names: `MAPBOX_SECRET_TOKEN`, `MAPBOX_USERNAME`,
`NEXT_PUBLIC_TERRITORIAL_DEMAND_LAYER`.

### `.env.pgurl`

| CONSUMER | LOAD_MECHANISM | REQUIRES_FILENAME_IN_REPO | CAN_USE_PROCESS_ENV | CAN_USE_EXTERNAL_ENV_FILE |
|---|---|---|---|---|
| `get_pgurl_only_db_url()` in `backend/services/data_ingestion/_shared.py` | `_read_first_pgurl()` reads the whole file as one URL; candidates are `<repo root>/.env.pgurl` then `./.env.pgurl`; raises when both are missing | **YES** | **NO** | partially — the CWD candidate means the file can also live in the current directory |
| `get_app_db_url()` | last resort only, after `DATABASE_URL_TIMESCALE` and `DATABASE_URL` | NO | YES | n/a |
| `get_timescale_db_url()` | never consults `.env.pgurl` | NO | YES | n/a |

`get_pgurl_only_db_url()` callers (9): `backend/scripts/copy_ownership_enrichment_to_timescale.py`,
`backend/services/data_ingestion/gem_excel_to_postgres.py`,
`backend/scripts/eic_crosswalk_bdew_mastr.py`,
`backend/scripts/eic_crosswalk_fr_es_registers.py`,
`backend/scripts/export_thermal_eic_review_list.py`,
`backend/scripts/gem_fleet_native_update.py`,
`backend/scripts/sync_gem_ownership_enrichment.py`,
`backend/scripts/thermal_eic_confidence_fill.py`,
`backend/scripts/thermal_eic_provisional_fill.py`,
`backend/scripts/waterfall_thermal_eic_trial.py`.

Repo B's own ops rule already restricts this resolver:
`docs/operations/database_routing_timescale_sot_v1.md` marks the target as
"Legacy enrichment sandbox — archive after Phase A" and says to reserve
`get_pgurl_only_db_url()` for explicitly legacy or archive experiments.

**Current state, observed 2026-08-23:** the working-tree `.env.pgurl` is **0
bytes** and shows as modified against `HEAD`. The tracked blob in commit
`1ee4b5f` is **91 bytes** and still contains the credential, so it remains
readable by anyone who can read the repository — `git show HEAD:.env.pgurl` needs
no working-tree file at all. Emptying the file changes nothing about that, which
is why rotation, not untracking, is the mitigation that holds.

---

## Mission B — host-only secret layout

```text
HOST_ONLY_SECRET_ROOT = %USERPROFILE%\.powerunits\secrets\
```

Derived at runtime from `$env:USERPROFILE`; no username is ever hardcoded. The
root sits inside the human account's profile, whose ACL already excludes every
other local principal, so `hermes-dev` is not denied by a special rule — it is
simply never granted.

| Logical name | External file | Replaces |
|---|---|---|
| `repo-b` | `%USERPROFILE%\.powerunits\secrets\repo-b.env` | `EU-PP-Database\.env` |
| `app` | `%USERPROFILE%\.powerunits\secrets\app.env` | `EU-PP-Database\app\.env.local` |
| `mapbox` | `%USERPROFILE%\.powerunits\secrets\mapbox.env` | `EU-PP-Database\scripts\mapbox\.env.local` |

**No symlink, junction or hardlink** from the workspace into this root. A link
would make the external file readable through the workspace path and restore
precisely the reachability being removed. Values reach the consumers through the
**process environment** instead, which Mission A shows every consumer but two
already prefers.

Prepared by
[`scripts/r5_developer_hermes/principal/bootstrap-host-secrets.ps1`](../../scripts/r5_developer_hermes/principal/bootstrap-host-secrets.ps1):
it creates the root and three empty env files, verifies that `hermes-dev` holds
no allow ACE, and with `-Relocate` **moves** (never copies) the three untracked
workspace files to their external names. It refuses to move a git-tracked file,
refuses to overwrite a non-empty target, and reports only sizes.

Why this is not per-file deny ACLs: a deny ACE hides a working-tree file while
leaving the same bytes readable in `.git`, and denying read on `.git` would
destroy the `GIT` capability R5 must keep. Deny ACEs stay available as a
short-lived stopgap (`provision-principal.ps1 -DenyInWorkspaceSecrets`) and are
explicitly **not** the long-term boundary.

---

## Mission C — preserving human local development

[`scripts/r5_developer_hermes/principal/run-with-host-secrets.ps1`](../../scripts/r5_developer_hermes/principal/run-with-host-secrets.ps1)
loads one or more logical env files into its own process environment and then
executes an ordinary development command. Children inherit the variables; the
values live nowhere but process memory and vanish with the window.

```powershell
# Repo-B backend
.\run-with-host-secrets.ps1 -Load repo-b -WorkingDirectory W:\Workbench\EU-PP-Database `
    uv run uvicorn main:app --reload

# analytics app
.\run-with-host-secrets.ps1 -Load app,repo-b -WorkingDirectory W:\Workbench\EU-PP-Database\app `
    npm run dev

# mapbox style script
.\run-with-host-secrets.ps1 -Load mapbox -WorkingDirectory W:\Workbench\EU-PP-Database `
    powershell -File scripts\mapbox\apply_units_basemap_muse.ps1

# what would be injected, without running anything
.\run-with-host-secrets.ps1 -Load repo-b -ListKeys
```

It never copies a secret file into a repository, never writes a value into any
file or artifact, never prints a value (key names only), and never creates a
link. Reading its source grants nothing: the authority is the profile ACL on the
secret root, and the script additionally refuses to start when the current
account is the dedicated principal.

Known gap, unchanged by this design: the two direct-file readers listed in
Mission A (`check_timescale_write_target_readiness.py`,
`validate_timescale_shadow_model_dataset_view.py`) do not consult the
environment and will fail after relocation until Repo B gives them an
`--env-file` argument or an `os.environ` fallback.

---

## Mission D — what `hermes-dev` may see in the workspace

After relocation, the two workspace roots must contain only source, tests, docs,
`*.example` placeholders, and — where a human has explicitly approved it —
DEV/TEST-only credentials. No valid production credential, and no invented
production-looking value: a fake that reads like a real DSN is a trap for the
next reader, not a safeguard.

Already present as the placeholder convention: `frontend/env.example`,
`scripts/mapbox/env.example`.

Enforced by evidence rather than assertion:
`preflight-principal.ps1` records every secret-class file found inside the
workspace roots with its `git_tracked` and `in_git_history` flags and raises
`SECRETS_INSIDE_APPROVED_WORKSPACE` / `SECRETS_IN_GIT_HISTORY`;
`verify-principal-isolation.ps1` fails acceptance while any of them is readable.
`PREFLIGHT_RESULT` therefore stays `BLOCKED` until the relocation is done.

Note on `W:` — the volume root already grants `Authenticated Users: Modify` by
inheritance, so `hermes-dev` will inherit Modify across the whole `W:` volume,
not only the two approved roots. Explicit grants are still applied so the
boundary survives a later tightening of the volume root, but any secret anywhere
on `W:` is in reach today. That is a second reason the secret root belongs in
the profile on `C:`.

---

## Mission E — legacy `.env.pgurl` blast radius (name-only)

```text
LEGACY_DB_HOST            = trolley.proxy.rlwy.net:47583  (database "railway")
LEGACY_DB_ROLE            = legacy enrichment sandbox, archive after Phase A
LEGACY_DB_RAILWAY_SERVICE = HUMAN_CONFIRMATION_REQUIRED
```

Repo B documents the host and the role but never names the Railway service that
owns it. `docs/operations/database_routing_timescale_sot_v1.md` names only the
**production** service (`TimescaleDB`, proxy `ballast.proxy.rlwy.net`) and the
dedicated test database (`powerunits-access-test-db`, `sakura.proxy.rlwy.net`).
No authenticated Railway command was issued for this inventory, so the service
behind `trolley.proxy.rlwy.net:47583` is identified by host and port only and
must be confirmed by a human in the Railway dashboard.

```text
LEGACY_DB_GITHUB_SECRET_NAMES = none
```

Proven, not assumed: repository Actions secrets `total_count = 0`, and the
`Preview` and `Production` environments each report `0` secrets. The only
workflow reference to a database secret is `secrets.DATABASE_URL` in
`.github/workflows/bounded-validate-smoke.yml`, which is currently unset — the
workflow's own `smoke-skipped-no-secret` branch is what runs.
`.github/workflows/backend-pytest-offline.yml` uses a hardcoded placeholder DSN
plus `PYTEST_FORCE_OFFLINE=1` and references no secret at all. Neither workflow
declares an `environment:`, so environment-scoped secrets are not reachable from
them either. If `DATABASE_URL` is configured later it would carry the Timescale
SoT, not the legacy pgurl.

```text
LEGACY_DB_OTHER_CONSUMERS =
  local only
  - .env.pgurl in the Repo-B working tree (currently 0 bytes)
  - the tracked 91-byte blob in commit 1ee4b5f (git history; still readable)
  - get_pgurl_only_db_url() -> the 9 backend scripts listed in Mission A
  - get_app_db_url() last-resort fallback, only when DATABASE_URL_TIMESCALE
    and DATABASE_URL are both unset
  no Railway service variable, CI secret or Vercel variable references it
```

```text
ROTATION_UPDATE_LOCATIONS =
  1. Railway: the Postgres service behind trolley.proxy.rlwy.net:47583
     (HUMAN_CONFIRMATION_REQUIRED) -> rotate/disable the credential
  2. local: %USERPROFILE%\.powerunits\secrets\ if any legacy DSN is still
     wanted for archive drills; otherwise nothing to update
  3. Repo B: untrack .env.pgurl (see runbook step 6)
  no GitHub Actions secret to update
  no Vercel environment variable to update
  no Railway service variable to update
```

Explicitly out of scope. None of these appear in Repo B's working tree or
history, so a Postgres remediation is no reason to touch them:

```text
OPENAI_ROTATION_REQUIRED                = NO
RAILWAY_ACCOUNT_TOKEN_ROTATION_REQUIRED = NO
VERCEL_ACCOUNT_TOKEN_ROTATION_REQUIRED  = NO
GITHUB_TOKEN_ROTATION_REQUIRED          = NO
HERMES_SECRET_ROTATION_REQUIRED         = NO
```

The Class-2 credentials (`.env`, `app/.env.local`,
`scripts/mapbox/.env.local`) were never committed. Their remediation is
relocation, not rotation.

---

## Mission F — provisioning artifacts

| Script | Runs as | Elevation | Does |
|---|---|---|---|
| `preflight-principal.ps1` | host user | no | read-only inspection; `-CreateSentinel` writes one harmless marker into the host profile |
| `bootstrap-host-secrets.ps1` | host user | no | creates the host-only secret root; `-Relocate` moves the three untracked files out of the workspace |
| `run-with-host-secrets.ps1` | host user | no | injects host-only env files into a normal dev command |
| `provision-principal.ps1` | host user | **yes** | creates `hermes-dev`, adds additive ACEs |
| `launch-developer-hermes.ps1` | host user | no | `runas` into `hermes-dev` |
| `verify-principal-isolation.ps1` | `hermes-dev` | no | Phase C property proof |

`provision-principal.ps1` properties: idempotent; demands elevation via
`IsInRole` and exits otherwise; creates a standard account in `BUILTIN\Users`
and refuses to continue if the account is in `Administrators`; asks for the
password interactively and never stores it; uses `AddAccessRule` only — no
`SetAccessRuleProtection`, no `RemoveAccessRule`, no `PurgeAccessRules`, so
existing ACEs and inheritance survive; grants `Modify` on the two workspace
roots and *this-folder-only* traverse on their ancestors; refuses any root
inside a user profile or inside the host-only secret root; and reports
`host_secret_root_granted = false`.

Toolchain: no ACL change is required on this host. `C:\Python311`,
`C:\Program Files\Git` and `C:\Program Files\GitHub CLI` already carry
`BUILTIN\Users: ReadAndExecute`, and `C:\nvm4w\nodejs` carries
`Authenticated Users: Modify` by inheritance. `provision-principal.ps1` verifies
this and reports `toolchain_acls_changed = false`; it never widens a toolchain
ACL on its own.

One capability limitation, deliberately not fixed with an ACL: `uv` lives at
`C:\Users\<host-user>\.local\bin\uv.exe`, a per-user location. `hermes-dev`
cannot execute it, and the host profile must not be opened up to make it
possible. R5 probes do not need `uv` because they run the repo-local R1 venv
interpreter directly. If `hermes-dev` ever needs `uv`, install it machine-wide;
do not grant access to the host profile.

---

## Runbook (human execution)

Ordered so that each step is verifiable before the next one can break anything.
Steps 1–3 are reversible and touch no credential. Nothing below has been run.

### 1. Create the host-only secret directory

```powershell
cd W:\Workbench\hermes-agent\scripts\r5_developer_hermes\principal
powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1
```

Creates `%USERPROFILE%\.powerunits\secrets\` with `repo-b.env`, `app.env`,
`mapbox.env` (header comment only) and confirms `hermes-dev` has no allow ACE.
Artifact: `.r5-dev\artifacts\host_secret_layout.json`.

### 2. Relocate the untracked workspace secret files

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1 -Relocate -WhatIf
powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1 -Relocate
```

Moves `EU-PP-Database\.env` → `repo-b.env`, `app\.env.local` → `app.env`,
`scripts\mapbox\.env.local` → `mapbox.env`. `Move-Item`, so no copy stays
behind. Do **not** create a symlink at the old paths afterwards.

Verify no secret-class file is left in the workspace:

```powershell
powershell -ExecutionPolicy Bypass -File .\preflight-principal.ps1
```

`in_workspace_secret_files` should then list only `.env.pgurl`, which step 6
removes.

### 3. Verify the normal human workflow still works

```powershell
.\run-with-host-secrets.ps1 -Load repo-b -ListKeys

.\run-with-host-secrets.ps1 -Load repo-b -WorkingDirectory W:\Workbench\EU-PP-Database `
    uv run python -c "from backend.settings import settings; print(bool(settings.database_url))"

.\run-with-host-secrets.ps1 -Load app,repo-b -WorkingDirectory W:\Workbench\EU-PP-Database\app `
    npm run dev
```

Expected known failures, both from Mission A and neither caused by the launcher:
`scripts/maintenance/check_timescale_write_target_readiness.py` and
`scripts/validate_timescale_shadow_model_dataset_view.py` read `<root>/.env`
directly. **Fix or accept this before continuing.** The Repo-B follow-up is to
give both an `--env-file` argument or an `os.environ` fallback.

Do not proceed to step 4 until local development is working again.

### 4. Rotate the legacy Railway database credential

```text
target  = the Railway Postgres service behind trolley.proxy.rlwy.net:47583
service = HUMAN_CONFIRMATION_REQUIRED
```

1. Railway dashboard → locate the Postgres service whose TCP proxy is
   `trolley.proxy.rlwy.net:47583`, database `railway`. Confirm it is the legacy
   enrichment sandbox and **not** `TimescaleDB` (`ballast.proxy.rlwy.net`) and
   **not** `powerunits-access-test-db` (`sakura.proxy.rlwy.net`).
2. Decide: rotate the password, or — since Repo B calls the host
   "archive after Phase A" — delete/disable the service outright. Deletion is
   the stronger remediation and removes the credential's value entirely.
3. If rotating: Railway service → *Variables* → regenerate the Postgres
   credential, then redeploy the service.

Do not rotate `TimescaleDB`, `powerunits-access-test-db`, Railway or Vercel
account tokens, GitHub credentials, OpenAI keys, or any Hermes secret. None of
them are exposed through Repo B.

### 5. Update the confirmed legacy consumers

```text
GitHub Actions secrets to update : none (proven: repo secret count 0)
Railway service variables        : none reference the legacy DSN
Vercel environment variables     : none reference the legacy DSN
```

Only if archive/rollback drills are still wanted: put the new legacy DSN into
`%USERPROFILE%\.powerunits\secrets\repo-b.env` under a clearly legacy key name,
and run the nine `get_pgurl_only_db_url()` scripts through
`run-with-host-secrets.ps1`. Otherwise there is nothing to update — the
credential simply stops existing.

### 6. Remove `.env.pgurl` from tracking and from the working tree

Only after step 4. Until the credential is invalidated, this step changes
nothing about exposure.

```powershell
cd W:\Workbench\EU-PP-Database
git rm --cached .env.pgurl
Remove-Item .env.pgurl
git commit -m "chore(secrets): untrack legacy .env.pgurl pointer"
```

`.gitignore` already lists `.env.pgurl`, so nothing further is needed to keep it
out. This is a Repo-B change and belongs in a Repo-B branch/PR — not in Hermes
PR #67.

### 7. Git history cleanup — explicitly deferred

The 91-byte blob in commit `1ee4b5f` stays readable after step 6. A history
rewrite (`git filter-repo`) is coordinated follow-up hygiene, requires a force
push and every clone to be re-based, and is **not** a substitute for step 4.
Deferred by decision, tracked here, not scheduled in this PR.

### 8. Create the dedicated principal

```powershell
cd W:\Workbench\hermes-agent\scripts\r5_developer_hermes\principal

# ordinary session: record host SID, sentinel and absolute CLI paths
powershell -ExecutionPolicy Bypass -File .\preflight-principal.ps1 -CreateSentinel

# ELEVATED session
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1
```

Choose the password at the prompt; it is never stored. Do not add `hermes-dev`
to `Administrators`. Do not sign in to `gh`, `railway` or any cloud CLI as
`hermes-dev`, and do not copy SSH keys or Credential Manager entries into that
profile — their absence is the boundary.

### 9. Grant the Repo A/B ACLs

Performed by step 8: additive `Modify` on `W:\Workbench\hermes-agent` and
`W:\Workbench\EU-PP-Database`, this-folder-only traverse on their ancestors, no
toolchain change, nothing granted inside the host profile or the secret root.
Confirm in `.r5-dev\artifacts\principal_provision.json` that
`host_secret_root_granted` and `toolchain_acls_changed` are both `false`.

### 10. Launch Phase C verification

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Mode verify
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Mode probes
```

Acceptance requires all of:

```text
CHILD_OS_PRINCIPAL                     = SEPARATE_PRINCIPAL
child_is_administrator                 = false
HOST_PROFILE_FILESYSTEM_REACHABLE      = NO
RAILWAY_AUTH_REACHABLE                 = NO
GH_AUTH_REACHABLE                      = NO
WINDOWS_CREDENTIAL_AUTHORITY_REACHABLE = NO
HOST_ONLY_SECRET_ROOT_REACHABLE        = NO
PRODUCTION_SECRET_FILES_REACHABLE      = NO
PRODUCTION_DEPLOY_REACHABLE            = NO
WORKSPACE_RW                           = YES (both roots)
GIT                                    = works
```

Every check is fail-closed: an inconclusive result is reported as `NOT_PROVEN`
and fails acceptance. `harness.py authority-proof` reads this artifact and keeps
reporting `NOT_PROVEN` until it exists and passes.
