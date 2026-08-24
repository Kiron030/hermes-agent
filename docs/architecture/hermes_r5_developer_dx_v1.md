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

```text
DEVELOPER_HERMES_CONTROLLER      = PINNED_PURE_UPSTREAM
DEVELOPER_RUNTIME_SOURCE         = /opt/hermes
GENERIC_FINAL_TOOLSET_CAP_ACTIVE = NO
TYPESCRIPT_PINNED                = 7.0.2
PYTEST_PINNED                    = 9.1.1
DEDICATED_CONTAINER_CLONES       = DO_NOT_EXECUTE_ON_HOST
GIT_HOOKS                        = CONTAINED_CODE_EXECUTION
RESET_DEVELOPER_HERMES_HOME      = launch-developer-hermes.ps1 -Mode reset
LINUX_CAPABILITY_HARDENING       = DEFERRED_WITH_RATIONALE
R5_F06_STATUS                    = OPEN_POLICY_DECISION
DESKTOP_CONTAINER_COMPATIBILITY  = NEEDS_REMEDIATION
BOT_MODE_CONTAINER_COMPATIBILITY = NEEDS_REMEDIATION
```

The controller is pinned `/opt/hermes`, not the mounted checkout. TypeScript
and pytest are pinned at image build; pytest is not fetched unconstrained
on every test run. `cap_drop ALL` is deferred: the container already runs
unprivileged as root only so Windows bind-mount Git works, and a guessed
capability subset would risk the proven DX.

Dedicated clones under `W:\hermes-dev` are container workspaces. Do not
execute them on the host. Reset the named volume
`r5-developer-hermes-home` after suspected prompt injection or poisoned
persistent state. Egress policy is an open decision
(`R5_EGRESS_POLICY_GATE`).

## Launch

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1
```

Workspace roots are fixed. The launcher does not accept raw host mount
parameters. It refuses to run if its resolved script or repository root is
under `W:\hermes-dev`. Reset:

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode reset
```

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

```text
DESKTOP_CONTAINER_COMPATIBILITY  = NEEDS_REMEDIATION
BOT_MODE_CONTAINER_COMPATIBILITY = NEEDS_REMEDIATION
MODEL_ROUTING_CONFIGURABLE_WITHOUT_CORE_FORK = YES
```

Not implemented in this slice. Inventory only: Desktop can later act as a
remote-gateway control surface; Bot Mode can later run headlessly via
outbound platform polling. Do not widen mounts or publish ports for those
features here. Future routing intent remains Terra default, Luna
cheap/auxiliary, Sol explicit escalation.
