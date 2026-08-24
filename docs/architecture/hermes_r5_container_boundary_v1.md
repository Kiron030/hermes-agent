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

## Runtime workspace

| Tree | Host path | Container path | Mode |
|---|---|---|---|
| Repo A | `W:\hermes-dev\workspace\hermes-agent` | `/workspace/hermes-agent` | RW |
| Repo B | `W:\hermes-dev\workspace\EU-PP-Database` | `/workspace/EU-PP-Database` | RW |

`W:\Workbench\...` is not the Developer-Hermes runtime workspace.

`HERMES_HOME` is container-local: `/tmp/r5-hermes-home`.

## Launcher

`scripts/r5_developer_hermes/container/launch.py` starts the pinned image
with `--privileged=false`, bridge networking, no host PID namespace, no
Docker socket, and an explicit environment allowlist.

Pinned image:

```text
nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

## Out of scope

No production Railway/Vercel deploy. No production DB. No host secret
injection. No Node/TypeScript DX expansion (`R5_DEVELOPER_DX_XS`).
No Desktop or Bot Mode isolation claim.
