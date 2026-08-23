# R5 — Developer Hermes proof report

**Slice:** R5  
**Date:** 2026-08-23  
**Base:** `origin/powerunits-internal-setup` @ `fc1700ccebe8a87f527084c7ba848aa8d0b7c692`  
**Proof tree:** `.r5-dev/` (gitignored)  
**This report does not start R2 or R3.**

```text
R5_STATUS = PARTIAL_PENDING_ISOLATION
CAPABILITY_RESULT = PASS
GATE_1_CLOSED = YES
SECURITY_OBJECTIVE = POWERFUL_IN_WORKSPACE / NOT_POWERFUL_IN_PRODUCTION
```

> **Isolation claim withdrawn.** An independent review disproved the original
> `PROCESS_CONSTRUCTED_ENV` boundary on this host. The capability result stands
> unchanged; every production-authority verdict below is now sourced from an
> OS-principal proof that requires a human provisioning step. See
> [Isolation remediation](#isolation-remediation).

---

## Runtime

```text
DEVELOPER_RUNTIME     = pinned modern Hermes v2026.8.19 / 0.20.5
UPSTREAM_RELEASE_SHA  = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_IMAGE_DIGEST = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
REUSED_R1_SOURCE      = YES
LISTEN_ADDRESS        = none
PUBLIC_INGRESS        = NO
```

Separate instance: dedicated `HERMES_HOME` at `.r5-dev/home`, constructed
child env, `approvals.mode: off`. Not the Stage-1 operator clamp.

---

## Isolation remediation

```text
ISOLATION_BOUNDARY          = DEDICATED_OS_PRINCIPAL   (target)
ISOLATION_BOUNDARY_REJECTED = PROCESS_CONSTRUCTED_ENV
CURRENT_BOUNDARY_SUFFICIENT = NO
PATH_STUB_SECURITY_ROLE     = NONE
DOCKER_ON_THIS_HOST         = UNAVAILABLE
CONTAINER_USED              = NO
```

### What the independent review overturned

The constructed environment was real — production names genuinely never reach
the child — but it was never an authority boundary:

| Assumption in R5 v1 | Measured reality |
|---|---|
| Synthetic `HOME`/`USERPROFILE` separates credentials | Railway resolves config via the Windows known-folder API; with `HOME`, `USERPROFILE`, `APPDATA` and `LOCALAPPDATA` all redirected to an empty directory, `railway whoami` still returned a live session |
| PATH stubs remove deploy authority | Defeated by absolute path, `cmd`, PowerShell and Python `subprocess` alike; the stub files are writable by the instance itself |
| Child cannot reach the host profile | Identical account SID, `FullControl` on `C:\Users\<host>` |
| `railway`/`vercel` were "present but unauthenticated" | `shutil.which` resolved the stub first, so the proof measured itself; `vercel` is not installed on this host at all |

### The replacement

A dedicated non-administrative local account (`hermes-dev`) with explicit
`Modify` on the two approved workspace roots. Host credential stores become
unreachable as a consequence of default NTFS profile ownership rather than an
enumerated deny list.

Artifacts, for human execution:

| Script | Elevation | Role |
|---|---|---|
| `principal/preflight-principal.ps1` | no | mechanised Phase A; records host SID, absolute deploy-CLI paths, sentinel, host-only secret layout |
| `principal/bootstrap-host-secrets.ps1` | no | creates the host-only secret root; `-Relocate` moves workspace secrets out |
| `principal/run-with-host-secrets.ps1` | no | keeps human local development working by injecting those files into the process environment |
| `principal/provision-principal.ps1` | **yes** | creates the standard account, adds additive ACEs only |
| `principal/launch-developer-hermes.ps1` | no | `runas` into the principal; no cached credentials |
| `principal/verify-principal-isolation.ps1` | no | Phase C property proof, fail-closed |

### Preflight result on this host

```text
PREFLIGHT_RESULT = BLOCKED
```

Cleared:

- `W:` is a local fixed NTFS volume, not `subst`, not a network share, so a
  second principal sees it natively.
- `python`, `git` and `gh` are system-wide and readable by `BUILTIN\Users`.
- The pinned R1 venv is repo-local with base `C:\Python311`, so
  `SEPARATE_DEV_ENVIRONMENT_REQUIRED = NO`.
- Every `railway` binary resolves through `C:\nvm4w\nodejs` into
  `C:\Users\<host>\AppData\Local\nvm\...`, i.e. into the host profile. A second
  principal loses the deploy CLI as a side effect of the boundary, not because
  of a stub.

Open:

- `uv`, `node` and `npm` are user-profile-only, so `hermes-dev` cannot re-sync
  the pinned venv or run the Node-based LSP. Capability limitation, not a
  security defect.
- `W:\` already grants `Modify` to Authenticated Users, so `hermes-dev` inherits
  Modify across the whole volume. Explicit grants are still added so the
  boundary survives a later tightening of the volume root.
- Two blockers below.

### Blockers

```text
[SECRETS_INSIDE_APPROVED_WORKSPACE]  4 files
[SECRETS_IN_GIT_HISTORY]             1 file
```

Repo B carries secret-class files inside the tree that R5 requires to be
read/write:

| Path (Repo B) | Size | Tracked | In history | Remediation |
|---|---|---|---|---|
| `.env` | 3796 | no | no | relocate → `repo-b.env` |
| `app/.env.local` | 209 | no | no | relocate → `app.env` |
| `scripts/mapbox/.env.local` | 179 | no | no | relocate → `mapbox.env` |
| `.env.pgurl` | 0 in tree, **91 in `HEAD`** | **yes** | **yes** (`1ee4b5f`) | rotate, then untrack |

No OS-principal boundary can close this. `WORKSPACE_REPO_B_RW = YES` and
`PRODUCTION_SECRET_FILES_REACHABLE = NO` are contradictory while a live
credential lives inside the mounted workspace. The three untracked files were
never committed, so moving them out of the tree is sufficient; that is the
relocation half of the remediation.

`.env.pgurl` is the different case. Its working-tree copy is now empty, but the
tracked 91-byte blob in `1ee4b5f` is still readable — `git show HEAD:.env.pgurl`
needs no working-tree file, a deny ACE on the file changes nothing, and denying
read on `.git` would cost the required `GIT` capability. Rotation is the only
mitigation that holds; untracking is hygiene that follows it. The credential
points at the legacy `trolley.proxy.rlwy.net:47583` sandbox, not the production
Timescale SoT.

Contents were never read; this inventory is names, sizes and git metadata only.

### Secret relocation and blast radius

```text
HOST_ONLY_SECRET_ROOT                   = %USERPROFILE%\.powerunits\secrets\
PRODUCTION_CREDENTIAL_ROTATION_REQUIRED = NO
LEGACY_DB_ROTATION_REQUIRED             = YES
LEGACY_DB_RAILWAY_SERVICE               = HUMAN_CONFIRMATION_REQUIRED
LEGACY_DB_GITHUB_SECRET_NAMES           = none
```

`LEGACY_DB_GITHUB_SECRET_NAMES` is proven rather than assumed: repository
Actions secrets `total_count = 0`, and the `Preview` and `Production`
environments hold `0` secrets each. `bounded-validate-smoke.yml` references
`secrets.DATABASE_URL`, which is unset, so its `smoke-skipped-no-secret` branch
is what runs; `backend-pytest-offline.yml` uses a hardcoded placeholder DSN and
no secret at all.

Full loading-mechanism inventory, layout, launcher and the ordered human
runbook: [`hermes_r5_secret_relocation_v1.md`](./hermes_r5_secret_relocation_v1.md).

---

## Workspace

```text
WORKSPACE_REPO_A_RW = YES   # W:\Workbench\hermes-agent
WORKSPACE_REPO_B_RW = YES   # W:\Workbench\EU-PP-Database
```

Proven via `model_tools.handle_function_call`:

- Repo A: `search_files` located `def isolated_env`; `read_file` of the R1
  harness; `write_file` under `.r5-dev/scratch`.
- Repo B: `read_file` of `README.md`; `write_file` of a temporary scratch
  proof that was deleted after the probe.

No per-file allowlist. No human approval on those writes.

---

## Capability probes (Hermes dispatch)

Path: `model_tools.handle_function_call` in the pinned upstream venv.

```text
ORDINARY_WORKSPACE_APPROVALS = 0
TOOL_CALL_COUNT              = 17
DEVELOPER_TASK_PROBE         = PASS
DEVELOPER_EXPERIENCE         = STRONG
```

| Probe | Result |
|---|---|
| A code exploration | `PASS` |
| B bounded edit | `PASS` |
| C fail → fix → green | `PASS` (exit 1 then 0) |
| D git status/diff | `PASS` (`M r5_add.py`, real diff) |
| E skills_list / skill_view | `PASS` (`r5-dev-skill`) |
| F web | `NOT_RUN_CREDENTIAL_REQUIRED` |

```text
FILESYSTEM   = PROVEN_NOW
TERMINAL     = PROVEN_NOW
GIT          = PROVEN_NOW
TEST_LOOP    = PROVEN_NOW
SKILLS       = PROVEN_NOW
WEB          = AVAILABLE_NOT_YET_PROVEN
BROWSER      = DEFERRED
DELEGATION   = DEFERRED
PROFILES     = AVAILABLE_NOT_YET_PROVEN
BOT_MODE     = DEFERRED
OBSERVABILITY = AVAILABLE_NOT_YET_PROVEN
```

Catalog presence was not treated as proof. Delegation was not expanded.

---

## Production authority

Environment hygiene — still true, still necessary, no longer sufficient:

```text
PRODUCTION_DB_CREDENTIAL_PRESENT    = NO
POWERUNITS_EXECUTE_SECRET_PRESENT   = NO
DEPLOYMENT_CREDENTIAL_PRESENT       = NO
PRODUCTION_WRITE_REACHABLE          = NO
```

Authority properties — sourced from the OS-principal proof, fail-closed:

```text
PRODUCTION_DEPLOY_REACHABLE         = NOT_PROVEN
PRODUCTION_SECRET_FILES_REACHABLE   = NOT_PROVEN
```

Mechanical evidence (values never printed):

1. Child env assertion: all production-authority names absent, including when
   the parent had them injected in tests.
2. Modern dispatch of `execute_powerunits_option_d_bounded_slice` →
   `Unknown tool`.
3. Fork `check_powerunits_option_d_execute_requirements()` → `False`.
4. Deploy-CLI resolution now skips the stub directory and probes the real
   binaries. Item 4 in the previous revision claimed the stubs proved absence of
   authority; it measured the stubs and has been removed.
5. `PRODUCTION_DEPLOY_REACHABLE` and `PRODUCTION_SECRET_FILES_REACHABLE` read
   `NOT_PROVEN` until `.r5-dev/artifacts/principal_isolation.json` exists and
   passes. `authority_proof()["pass"]` is `False` while they do.

Deleting `.r5-dev/` cannot touch production. No production `.env` was read.

---

## SQLite

```text
SQLITE_RUNTIME_STATUS = KNOWN_RUNTIME_DEPENDENCY_DEBT
SQLITE_WAL_MODE       = delete
sqlite_version        = 3.38.4
```

Hermes warned: linked 3.38.4 is vulnerable to the WAL-reset bug and used
`journal_mode=DELETE`. Upgrade path: SQLite 3.51.3+ (or backports 3.50.7 /
3.44.6) via newer CPython / `hermes update`. Not an R5 blocker.

---

## Human action required

Phase C cannot run until the secrets are out of the workspace *and* the
principal exists. Creating the principal first would only produce a `FAIL` on
the in-workspace secret checks, so the order matters:

```text
1. bootstrap-host-secrets.ps1              create the host-only secret root
2. bootstrap-host-secrets.ps1 -Relocate    move the three untracked files out
3. run-with-host-secrets.ps1               confirm human local dev still works
4. rotate the legacy trolley DB credential (Railway UI)
5. untrack .env.pgurl                      Repo-B change, separate PR
6. provision-principal.ps1                 ELEVATED; creates hermes-dev
7. launch-developer-hermes.ps1 -Mode verify / -Mode probes
```

Exact commands, expected failures and confirmation points:
[`hermes_r5_secret_relocation_v1.md`](./hermes_r5_secret_relocation_v1.md#runbook-human-execution).

The password is entered interactively and never stored. Do not authenticate
`gh` or `railway` for `hermes-dev`, and do not copy SSH keys or Credential
Manager state into it — their absence is the point.

## Tests

```text
python -m pytest tests/r5_developer_hermes -q
32 passed
```

New coverage: boundary fails closed without principal evidence; the boundary is
only claimed on proof; PATH stubs are declared non-security; deploy-CLI
resolution skips the stub directory; provisioning scripts never cache
credentials and never reset an ACL; the host secret root is derived from the
profile rather than hardcoded; relocation moves and never copies; no principal
script creates a link back into the workspace; the launcher writes no value to
disk and refuses to run as the dedicated principal; provisioning refuses to
grant the secret root and never widens a toolchain ACL.

---

## Rollback

Delete `.r5-dev/` (or `HERMES_R5_PROOF_ROOT`). Production was never attached.

---

## R3 evidence

```text
R3_DEVELOPER_EXPERIENCE_EVIDENCE = READY_WITH_ISOLATION_CAVEAT
```

A representative developer task (locate symbol → edit → fail/fix test →
inspect diff) completed with zero ordinary-workspace approvals.

---

## What R5 did not do

No production Railway/Vercel deploy. No production DB. No execute secret.
No `.env` harvest. No R2 plugin. No R3 shadow comparison. No merge.
