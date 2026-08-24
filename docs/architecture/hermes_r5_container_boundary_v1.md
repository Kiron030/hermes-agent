# R5 — Developer-Hermes Linux-container boundary

**Slice:** `R5_CONTAINER_BOUNDARY_XS`  
**Date:** 2026-08-24  
**Depends on:** `R5_ISOLATION_PIVOT_GATE = PASS`, `PREFERRED_R5_ISOLATION = CONTAINER`  
**Status:** `R5_CONTAINER_BOUNDARY_XS = PASS` — not Desktop, not Bot Mode

```text
ISOLATION_BOUNDARY            = CONTAINER
ISOLATION_BOUNDARY_FALLBACK   = DEDICATED_OS_PRINCIPAL
workspace_acl_script_role     = FALLBACK_ONLY
HERMES_CORE_FILES_ADDED       = 0
HERMES_CORE_STRATEGY_CHANGED  = NO
DOCKER_OSTYPE                 = linux
W_DRIVE_BIND_MOUNT_SUPPORTED  = YES
```

The container may read and write only the two dedicated development
repositories. Host credentials, production authority, and unrelated host
filesystems stay outside the mount set.

```text
CONTAINER_MOUNT_BOUNDARY         = PRIMARY SECURITY BOUNDARY
HERMES_WRITE_SAFE_ROOT           = DEFENSE IN DEPTH
DEVELOPER_HERMES_CONTROLLER      = PINNED_PURE_UPSTREAM
DEVELOPER_RUNTIME_SOURCE         = /opt/hermes
GENERIC_FINAL_TOOLSET_CAP_ACTIVE = NO
REPO_A_REPO_B_SAME_TRUST_DOMAIN  = YES
POSITIVE_MOUNT_ALLOWLIST         = YES
```

Mount verification is a positive allowlist after Docker Desktop / WSL path
normalization. The only approved host bind sources are exactly
`W:\hermes-dev\workspace\hermes-agent` and
`W:\hermes-dev\workspace\EU-PP-Database`. Repo A and Repo B are one trust
domain: both RW, cross-repo mutation expected. The binds are the outer host
boundary, not isolation between the two repos.

## Runtime workspace

| Tree | Host path | Container path | Mode |
|---|---|---|---|
| Repo A | `W:\hermes-dev\workspace\hermes-agent` | `/workspace/hermes-agent` | RW |
| Repo B | `W:\hermes-dev\workspace\EU-PP-Database` | `/workspace/EU-PP-Database` | RW |

`W:\Workbench\...` is not the Developer-Hermes runtime workspace.

`HERMES_HOME` started as disposable `/tmp/r5-hermes-home` for the boundary
proof. Developer DX persists it on the named volume
`r5-developer-hermes-home` at `/opt/data`. See
[`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md).

## Launcher

`scripts/r5_developer_hermes/container/launch.py` / `docker_run_argv()` is
the canonical launch contract. `compose.yaml` is a non-authoritative
example only. Before `up` / `prove` / default launch the launcher
converges the running image to the checked-in image-input fingerprint
(see [`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md)).
The launcher starts the pinned image with
`--privileged=false`, bridge networking, no host PID namespace, no
Docker socket, and an explicit environment allowlist. Inspect diagnostics
emit environment **names** only, never values. A host user with Docker
daemon authority can still read `Config.Env`; that does not enlarge the
container trust boundary.

Pinned image:

```text
nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

## Out of scope

No production Railway/Vercel deploy. No production DB. No host secret
injection. No Node/TypeScript DX expansion (`R5_DEVELOPER_DX_XS`).
No Desktop or Bot Mode isolation claim.
