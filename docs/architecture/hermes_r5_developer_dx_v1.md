# R5 — Developer Hermes DX

**Slice:** `R5_DEVELOPER_DX_XS`  
**Date:** 2026-08-24  
**Depends on:** `R5_CONTAINER_BOUNDARY_XS = PASS`  
**Status:** high capability inside the proven container boundary

```text
ISOLATION_BOUNDARY            = CONTAINER
HERMES_HOME_MECHANISM         = DOCKER_NAMED_VOLUME
CONTAINER_RUNTIME_USER        = ROOT_ACCEPTED_WITH_RATIONALE
HERMES_CORE_FILES_ADDED_BY_DX = 0
```

The Linux-container two-repository bind-mount allowlist from
[`hermes_r5_container_boundary_v1.md`](./hermes_r5_container_boundary_v1.md)
remains invariant. This slice adds fullstack tooling, persistent isolated
state, skills, a one-command launcher, and isolated Git identity.

## Runtime

| Concern | Location |
|---|---|
| Pinned Hermes base | `nousresearch/hermes-agent@sha256:3811ed13…ccec09` |
| Derived DX image | `r5-developer-hermes:dx-v1` |
| Repo A | `/workspace/hermes-agent` (RW bind) |
| Repo B | `/workspace/EU-PP-Database` (RW bind) |
| Persistent home | named volume `r5-developer-hermes-home` → `/opt/data` |
| Runtime user | root inside an unprivileged container. uid 10000 cannot write Windows bind-mount `.git/objects`. |

Host profile, host secrets, Docker socket, Railway/Vercel/GitHub/production
DB credentials stay unmounted.

## Launch

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1
```

Workspace roots are fixed. The launcher does not accept raw host mount
parameters.

## Model credentials

Dedicated file only:

```text
W:\hermes-dev\credentials\developer-hermes-model.env
```

Allowlisted keys: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.
Production names are refused. Host `.env` and
`C:\Users\User\.powerunits\secrets` are never read.

Intended smoke/default model is `gpt-5.6-terra` via provider `openai-api`
with `agent.reasoning_effort: medium`. There is no automatic model routing.

The official Hermes image sets `HERMES_WRITE_SAFE_ROOT=/opt/data`. Developer
Hermes overrides that to `/workspace:/opt/data` so `write_file`/`patch` can
reach the two approved repo mounts without widening host paths.

## Desktop / Bot Mode

Not implemented in this slice. Inventory only: Desktop can later act as a
remote-gateway control surface; Bot Mode can later run headlessly via
outbound platform polling. Do not widen mounts or publish ports for those
features here.
