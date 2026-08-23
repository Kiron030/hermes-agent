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
ISOLATION_BOUNDARY = PROCESS_CONSTRUCTED_ENV
DOCKER_ON_THIS_HOST = UNAVAILABLE
```

The host supervisor pattern (`env.update(os.environ)` after sanitizing) is
why in-process redaction is not a credential boundary. R5 therefore
**constructs** a child environment from a safe passthrough allowlist and
spawns Hermes in that child. Production names are never copied.

Docker is not required. When the Docker CLI is absent, this process
boundary is the repo-supported mechanism introduced by R1. An optional
OCI path remains the R1 pinned digest; this host did not use it.

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

Mechanical fail-closed proofs:

1. Modern runtime `handle_function_call(execute_powerunits_option_d_bounded_slice)` → unknown tool.
2. Fork `check_powerunits_option_d_execute_requirements()` → false without secrets.
3. Railway / Vercel CLIs are absent or unauthenticated.

Deleting `.r5-dev/` has zero production effect.

## SQLite

The current developer runtime links SQLite 3.38.4. Hermes itself warns
this build is vulnerable to the WAL-reset bug and uses
`journal_mode=DELETE`. Treat as `KNOWN_RUNTIME_DEPENDENCY_DEBT`. Do not
force WAL. Upgrade path: SQLite 3.51.3+ (or backports 3.50.7 / 3.44.6)
via a newer CPython / `hermes update` / the official image on a Docker host.

Host Railway CLI logins can survive a stripped env because the Windows
user profile is not a container. The constructed child PATH therefore
shadows `railway` / `vercel` with fail-closed stubs. Env tokens remain
absent.

## Commands

See `scripts/r5_developer_hermes/README.md`.

## Out of scope

No production Railway/Vercel deploy. No production DB. No execute secret.
No `.env` harvest. No R2 plugin work. No R3 shadow comparison.
