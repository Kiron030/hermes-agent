# R5 — Developer Hermes proof report

**Slice:** R5  
**Date:** 2026-08-23  
**Base:** `origin/powerunits-internal-setup` @ `fc1700ccebe8a87f527084c7ba848aa8d0b7c692`  
**Proof tree:** `.r5-dev/` (gitignored)  
**This report does not start R2 or R3.**

```text
R5_STATUS = CONTAINER_BOUNDARY_PROVEN
CAPABILITY_RESULT = PASS
GATE_1_CLOSED = YES
SECURITY_OBJECTIVE = POWERFUL_IN_WORKSPACE / NOT_POWERFUL_IN_PRODUCTION
ISOLATION_BOUNDARY = CONTAINER
```

Canonical empirical container proof:
[`hermes_r5_container_boundary_v1.md`](./hermes_r5_container_boundary_v1.md).
The Windows principal path remains defense in depth / `FALLBACK_ONLY`.

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

### Blockers — resolved in Phase B2

The two original blockers were secret-class files inside the tree that R5
requires to be read/write. Both are now closed:

| Path (Repo B) | Was | Now |
|---|---|---|
| `.env` | 3796 bytes, untracked | relocated → `repo-b.env` (32 keys) |
| `app/.env.local` | 209 bytes, untracked | relocated → `app.env` (2 keys) |
| `scripts/mapbox/.env.local` | 179 bytes, untracked | relocated → `mapbox.env` (3 keys) |
| `.env.pgurl` | 0 in tree, 91 in history, tracked | `PROVEN_RETIRED_SECRET_AUTHORITY` |

The three untracked files were never committed, so moving them out of the tree
was sufficient. The human has done that; the workspace sources no longer exist.

`.env.pgurl` was the harder case and was not solved by hiding it. Its target —
the legacy Railway PostgreSQL sandbox, not the production Timescale SoT — was
deleted by a human operator, and Repo-B PR #547 (merge
`7bd3f9a09d94cfa1c26ccc9486920ec23f84699c`) removed the file from canonical
`main`. Preflight now classifies it through a five-element evidence contract
verified against git metadata on every run, so it reports as
`HISTORICAL_DEAD_AUTHORITY` (informational) instead of a rotation blocker. There
is no wholesale history-secret exemption, and every other secret-class finding
still blocks. Details:
[`hermes_r5_workspace_authority_v1.md`](./hermes_r5_workspace_authority_v1.md).

Contents were never read; this inventory is names, sizes and git metadata only.

### Blockers — remaining, both human OS actions

```text
[OTHER_WRITE_AUTHORITY_NOT_PROVEN]        C:\, D:\, W:\ grant inheritable write
                                          to Authenticated Users
[R5_MINIMUM_TOOLCHAIN_NOT_SYSTEM_WIDE]    uv resolves inside the host profile
```

`W:\` carries an inherit-only generic-write ACE for `Authenticated Users`, so a
fresh standard account inherits write across the whole volume before any grant
is made. Explicit workspace grants do not change that — which is exactly the
mistake the earlier version of this report made. That ACE cannot simply be
removed: the host user's `Administrators` membership is deny-only in an
unelevated token, so it is the only entry giving the human write access to their
own data. The design therefore scopes from the other side: a scoped workspace
root with inheritance disabled, plus a principal-specific inheritable write-deny
at each volume root. Read access is left intact, so nothing breaks.

`uv` is a hard requirement, not a nicety: `harness.py prepare_runtime()` runs
`uv sync --frozen`, so without a machine-wide `uv` the principal cannot rebuild
its pinned venv. Node and npm remain profile-only and are classified
`POST_R5_DEVELOPER_DX` — which is also what keeps the host Railway CLI shim out
of reach, since `C:\nvm4w\nodejs` is a symlink into the host profile.

Design, evidence, human runbook and rollback:
[`hermes_r5_workspace_authority_v1.md`](./hermes_r5_workspace_authority_v1.md).

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

Steps 1–5 are done. What remains is the authority boundary itself: creating the
principal before its write authority is scoped would only produce a `FAIL` on
the outside-write probes, so the order matters.

```text
DONE  bootstrap-host-secrets.ps1              host-only secret root created
DONE  bootstrap-host-secrets.ps1 -Relocate    three untracked files moved out
DONE  run-with-host-secrets.ps1               human local dev confirmed working
DONE  legacy trolley DB service deleted       (Railway; supersedes rotation)
DONE  .env.pgurl untracked on main            Repo-B PR #547, merged

0. install uv machine-wide                    ELEVATED; R5 minimum capability
1. provision-principal.ps1                    ELEVATED; creates hermes-dev
2. scope-workspace-authority.ps1              ELEVATED; scoped root + write-deny
3. clone Repo A / Repo B into the scoped root  as the host user
4. preflight-principal.ps1 -CreateSentinel     ELEVATED; expect READY
5. launch-developer-hermes.ps1 -Verify         Phase C property proof
```

Exact commands, expected output, acceptance criteria and the full rollback:
[`hermes_r5_workspace_authority_v1.md`](./hermes_r5_workspace_authority_v1.md#human_runbook).
Secret-relocation specifics remain in
[`hermes_r5_secret_relocation_v1.md`](./hermes_r5_secret_relocation_v1.md#runbook-human-execution).

Every ACL this touches is exported to `.r5-dev/acl-backups/` before the first
mutation, and `rollback-workspace-authority.ps1` restores from that export. No
existing ACL entry is modified or removed at any point.

The password is entered interactively and never stored. Do not authenticate
`gh` or `railway` for `hermes-dev`, and do not copy SSH keys or Credential
Manager state into it — their absence is the point.

## Tests

```text
python -m pytest tests/r5_developer_hermes -q
64 passed
```

New coverage: boundary fails closed without principal evidence; the boundary is
only claimed on proof; PATH stubs are declared non-security; deploy-CLI
resolution skips the stub directory; provisioning scripts never cache
credentials and never reset an ACL; the host secret root is derived from the
profile rather than hardcoded; relocation moves and never copies; no principal
script creates a link back into the workspace; the launcher writes no value to
disk and refuses to run as the dedicated principal; provisioning refuses to
grant the secret root and never widens a toolchain ACL.

Phase B2 added the retired-authority contract and the authority boundary: an
unknown historical credential, a live credential, a different historical secret
and missing or stale retirement evidence each still block, while the exact
`.env.pgurl` contract does not; every one of the five evidence elements is proven
load-bearing individually; the shipped evidence file is asserted to hold exactly
one entry and no wildcard; broad volume write is a preflight blocker and every
required gate is proven to be part of the pass expression; the scoping script
never removes an existing ACE, backs up every DACL before mutating, denies write
but never read, and refuses to protect a pre-existing directory; rollback
restores only the DACL and deletes nothing; Phase C proves write isolation by
attempting a write rather than reading an ACL.

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
