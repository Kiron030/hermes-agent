# R5 — Powerful Developer Hermes

**Slice:** R5  
**Date:** 2026-08-23  
**Depends on:** `GATE_1 = CLOSED` (R1)  
**Status:** developer environment only — no production mutation

```text
SECURITY_OBJECTIVE =
  POWERFUL_IN_WORKSPACE
  NOT_POWERFUL_IN_PRODUCTION
```

This instance is **not** the constrained Stage-1 operator Hermes. It exists
so developers can search, edit, test, and inspect git in the mounted
workspace without micro-approvals. Production remains unreachable because
the process does not possess production authority.

## Isolation boundary

```text
ISOLATION_BOUNDARY          = DEDICATED_OS_PRINCIPAL
ISOLATION_BOUNDARY_REJECTED = PROCESS_CONSTRUCTED_ENV
DOCKER_ON_THIS_HOST         = UNAVAILABLE
PATH_STUB_SECURITY_ROLE     = NONE
```

### Why the first boundary was withdrawn

R5 v1 built the child environment from a safe passthrough allowlist, pointed
`HOME` / `USERPROFILE` at a synthetic directory, and shadowed `railway` /
`vercel` with fail-closed PATH stubs. An independent review disproved that
boundary on this host:

- The child kept the **host logon token** (identical account SID), so it kept
  `FullControl` over `C:\Users\<host>` no matter what the environment said.
- Railway's CLI resolves its config through the Windows known-folder API, not
  through environment variables. With `HOME`, `USERPROFILE`, `APPDATA` and
  `LOCALAPPDATA` all redirected to an empty directory, `railway whoami` still
  returned a live session.
- The PATH shadow fell to an absolute path, a `cmd` indirection, a PowerShell
  indirection and a Python `subprocess` call alike — and the stub files
  themselves sat in a directory the instance could write to.
- The old proof resolved the CLI with `shutil.which` while the stub directory
  was first on PATH, so it measured its own stub rather than the host CLI.

Environment absence is not authority absence. Only a different OS security
principal changes ACL authority and credential-store discovery at once.

### The boundary that replaces it

Developer Hermes runs as a dedicated, non-administrative local Windows
account (`hermes-dev`) with explicit `Modify` on the two approved workspace
roots and nothing in the host profile. The host user's Railway session, GitHub
CLI configuration, Credential Manager entries and cloud CLI stores all sit
under `C:\Users\<host>`, which a standard second account cannot traverse — the
protection is a consequence of default NTFS ownership, not of an enumerated
deny list.

Provisioning and proof scripts live in
`scripts/r5_developer_hermes/principal/`. Docker is still not required and is
still not installed on this host.

Pinned modern runtime (unchanged from R1):

```text
UPSTREAM_RELEASE       = v2026.8.19
UPSTREAM_RELEASE_SHA   = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_IMAGE_DIGEST  = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

## Workspace

| Tree | Default mount | Mode |
|---|---|---|
| Repo A | this `hermes-agent` checkout | read/write |
| Repo B | sibling `EU-PP-Database` or `HERMES_R5_REPO_B_ROOT` | read/write |

No per-file allowlist. Dedicated `HERMES_HOME` under `.r5-dev/home`.
Scratch git for probes: `.r5-dev/scratch/git-probe`.

## Developer policy

```yaml
approvals:
  mode: off
  cron_mode: deny
agent:
  disabled_toolsets: [delegation, browser, computer_use, cronjob]
```

```text
ORDINARY_WORKSPACE_APPROVALS = 0
```

Delegation is deferred on purpose. It must not block R5.

## Production impossibility

Asserted absent in the developer child (values never printed):

- `DATABASE_URL_TIMESCALE`, `DATABASE_URL`
- `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`
- `POWERUNITS_INTERNAL_EXECUTE_BASE_URL`
- Railway / Vercel deployment names from `scripts/r5_developer_hermes/pin.json`

Those assertions are environment hygiene. They are necessary and they are not
sufficient, so they no longer feed the production-authority verdict.

Mechanical fail-closed proofs:

1. Modern runtime `handle_function_call(execute_powerunits_option_d_bounded_slice)` → unknown tool.
2. Fork `check_powerunits_option_d_execute_requirements()` → false without secrets.
3. Deploy-CLI resolution deliberately **skips** the stub directory and probes the
   real binaries, so a shadowed PATH cannot manufacture a pass.
4. `PRODUCTION_DEPLOY_REACHABLE` and `PRODUCTION_SECRET_FILES_REACHABLE` are read
   from the Phase C principal proof (`.r5-dev/artifacts/principal_isolation.json`)
   and default to `NOT_PROVEN` when that proof is absent.

Deleting `.r5-dev/` has zero production effect.

## Secrets must live outside the approved workspace

An OS-principal boundary separates the developer instance from the *host
profile*. It cannot hide anything inside a workspace the instance is required to
read and write. Any credential living in Repo A or Repo B is therefore reachable
by design — and reachable through git object storage even when the working-tree
file is denied.

The consequence is a layout rule rather than a stack of deny ACEs:

```text
HOST_ONLY_SECRET_ROOT = %USERPROFILE%\.powerunits\secrets\
```

The root is derived from the running account's profile, never hardcoded, and the
dedicated principal is simply never granted it. Values reach local consumers
through the **process environment** via
`principal/run-with-host-secrets.ps1`; there is deliberately no symlink or
junction from a workspace into that root, because a link would restore exactly
the filesystem reachability the move removes.

Two cases behave differently:

- **Never committed.** Moving the file out of the tree is sufficient.
  `principal/bootstrap-host-secrets.ps1 -Relocate` does the move and refuses to
  copy.
- **Committed at any point.** The blob stays readable in `.git`, denying read on
  `.git` would destroy the required `GIT` capability, and untracking is hygiene
  rather than mitigation. Rotation is the only fix that holds.

Inventory, loading mechanisms, blast radius and the ordered human runbook:
[`hermes_r5_secret_relocation_v1.md`](./hermes_r5_secret_relocation_v1.md).

## SQLite

The current developer runtime links SQLite 3.38.4. Hermes itself warns
this build is vulnerable to the WAL-reset bug and uses
`journal_mode=DELETE`. Treat as `KNOWN_RUNTIME_DEPENDENCY_DEBT`. Do not
force WAL. Upgrade path: SQLite 3.51.3+ (or backports 3.50.7 / 3.44.6)
via a newer CPython / `hermes update` / the official image on a Docker host.

## Deploy-CLI stubs

The `railway` / `vercel` PATH stubs are retained purely as a visible "do not
deploy from here" nudge for a careless interactive command.

```text
SECURITY_CONTROL = NO
```

Nothing in the authority proof depends on them, and no test may treat them as a
boundary.

## Commands

See `scripts/r5_developer_hermes/README.md`.

## Out of scope

No production Railway/Vercel deploy. No production DB. No execute secret.
No `.env` harvest. No R2 plugin work. No R3 shadow comparison.
