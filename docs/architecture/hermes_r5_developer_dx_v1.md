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
R5_F06_STATUS                    = ENFORCED_EGRESS_POLICY
EGRESS_MODE                      = PRIVATE_DEVELOPER_EGRESS_ENFORCED (or OFFLINE)
DESKTOP_CONTAINER_COMPATIBILITY  = OFFICIAL_REMOTE_GATEWAY
BOT_MODE_CONTAINER_COMPATIBILITY = NEEDS_REMEDIATION
```

The controller is pinned `/opt/hermes`, not the mounted checkout. TypeScript
and pytest are pinned at image build; pytest is not fetched unconstrained
on every test run. `cap_drop ALL` is deferred: the container already runs
unprivileged as root only so Windows bind-mount Git works, and a guessed
capability subset would risk the proven DX.

## Runtime identity

Future Developer-Hermes runtime claims must refer to the **actual running
image**, not merely Dockerfile contents, the image tag, expected config, or
the source commit.

```text
CHECKED_IN_RUNTIME_CONTRACT
== BUILT_IMAGE_IDENTITY
== RUNNING_CONTAINER_IMAGE_IDENTITY
```

The launcher computes `DEVELOPER_IMAGE_INPUT_FINGERPRINT` from the minimum
material image-input set (`Dockerfile`, `.dockerignore`, `entrypoint.sh`,
`seed_home.py`, the bundled skill, and `image_inputs/build_contract.json`).
The built image is stamped with:

```text
io.powerunits.r5.input-sha256
io.powerunits.r5.hermes-base-digest
io.powerunits.r5.contract-version
```

`up`, `prove`, and the default shell launch compare expected fingerprint,
tagged image ID, and running container image ID. Missing image → build.
Fingerprint or missing label → rebuild (fail closed). Same tag, old image
ID → recreate container. Identities match → reuse; no unnecessary rebuild.

Live proofs fail closed unless `EXPECTED_IMAGE_FINGERPRINT` equals
`RUNNING_IMAGE_FINGERPRINT` and both image IDs agree.

## Knowledge retention

Versioned docs under `docs/architecture/` and tests under
`tests/r5_developer_hermes/` are the canonical reusable knowledge.
`.r5-dev/artifacts` is machine-specific evidence and stays gitignored.
Red-team findings that changed architecture belong in these docs, not only
in old transcripts. D-01: a matching image tag is not proof that the
running container was built from the current checked-in runtime contract.

## Upstream update contract

```text
UPSTREAM_UPDATE_CONTRACT                 = ESTABLISHED
R5_GATE                                  = CLOSED
R5_REOPENED_BY_ROUTINE_UPDATE            = NO
NO_FLOATING_TAGS                         = YES
DOCKER_PULL_LATEST                       = FORBIDDEN
EGRESS_POLICY_WIDENED_BY_UPDATE          = HUMAN_DECISION_ONLY
AUTO_MERGE                               = NO
DEVELOPER_UPDATE_IMPLIES_DEPLOYMENT      = NO
DEFAULT_IMPLEMENTATION_MODEL             = Grok 4.6
GROK_FIRST                               = YES
OPUS_ROUTINE_USAGE                       = NO
```

Pin the new upstream Hermes version/digest, rebuild the Developer image,
prove convergence, run update-class-proportionate Egress/regression
checks, smoke the real runtime if warranted, then raise a focused PR for
human merge without deployment.

This is the post-merge Developer-Hermes maintenance contract. It does
not reopen R5. Developer Hermes is the local Docker
development/research runtime; Operator Hermes is a separate Railway
runtime. A Developer-Hermes pin/rebuild is not a Railway action and
must not enable Auto Deploy or deploy Operator Hermes.

### Update classes

Classify every upstream change before gathering evidence. The class
sets the evidence budget. Do not replay the historical R5 adversarial
campaign on a routine pin.

| Class | When | Evidence | Review |
|---|---|---|---|
| `ROUTINE` | Normal upstream Hermes release or the dependency refresh inherent to that pin. No new privileges, destinations, host mounts, production authority, or trust-boundary change. | Update pin/digest → rebuild → convergence → focused regression on changed areas → small real-Hermes smoke only if warranted → focused PR → human merge. | Grok-first. No broad security review. |
| `MATERIAL` | Behavior changes enough that existing contracts need targeted re-proof, but no fundamentally new trust boundary. Examples: meaningful runtime restructuring, changed networking or tool-execution behavior, material package/install semantics, changes that affect filesystem or Egress enforcement assumptions, a major version jump with relevant architecture. | Identify the affected existing contracts. Run targeted regression/adversarial checks **only** for those contracts. Document the delta. Keep scope bounded. | Grok remains the default. No automatic broad re-audit unless evidence actually points to one. |
| `TRUST_BOUNDARY_CHANGE` | A genuinely new high-impact capability or authority. Examples: new host filesystem access, Docker daemon access, remote Git push, production credentials or authority, arbitrary/direct Internet Egress, a new unmediated network path, a new secret-bearing execution boundary, or combining Developer-Hermes general terminal capability with production authority. | Explicit architectural review, explicit Human GO, narrowly scoped security analysis, and dedicated tests/proofs for the **new** boundary. | Only here may a narrowly scoped Opus review be considered, and only if the change genuinely warrants it. Opus is not routinely required. |

An ordinary upstream version bump starts as `ROUTINE`. Promote only on
observed evidence, not on version-number anxiety.

### Deterministic workflow

```text
new upstream version / pin / digest
  -> update checked-in inputs
     (pin.json, contract.py, Dockerfile FROM, image_inputs/build_contract.json)
  -> rebuild Developer DX image and egress broker via the canonical launcher
  -> runtime convergence verification
     CHECKED_IN_RUNTIME_CONTRACT
     == BUILT_IMAGE_IDENTITY
     == RUNNING_CONTAINER_IMAGE_IDENTITY
     plus EGRESS_CONTRACT_FINGERPRINT on the running labels
  -> Egress-aware focused regression, proportionate to the update class
  -> small real-Hermes smoke if warranted
  -> focused PR
  -> human review
  -> human merge
```

No automatic merge. No deployment. No Railway action is part of a
Developer-Hermes update. If Railway Auto Deploy is disabled, leave it
disabled.

### Egress-aware update requirement

An upstream update can move the outbound-confidentiality boundary
without touching a single R5 file, because the *code that dials out* is
upstream's. When relevant to the class, determine whether the new
version changes assumptions around:

- provider endpoints or the default provider
- DNS behavior
- package repositories, including lazy/at-first-use downloads
- proxy semantics and TLS/proxy behavior
- GitHub HTTPS read
- network tooling
- subprocess/tool execution that could bypass intended mediation
- new gateway, telemetry, or update-check destinations
- a new or upgraded egress component (upstream's own `iron-proxy` pin)

`ROUTINE` still requires pin/rebuild/convergence and a look at release
notes plus the checklist below when the delta could touch networking.
It does **not** require the full historical R5 adversarial campaign.
`MATERIAL` re-runs only the affected egress/filesystem rows.
`TRUST_BOUNDARY_CHANGE` proves the new path.

A destination the new version wants is not automatically approved; it
goes through the same human policy decision as any other. When a new
upstream version ships a *better* egress mechanism than the one we
pinned, record it as `UPSTREAM_NATIVE_REPLACEMENT_CANDIDATE` and handle
it in its own slice — never by silently upgrading inside an unrelated
change.

The research path is the one that bites hardest: it is a *ring* of
vendors, and upstream may reorder it, add a vendor, or change which one
an unconfigured install starts on. Re-read
`plugins/web/keyless_mcp.py` and `tools/web_tools.py::_get_backend` when
the class warrants it, and re-check that `RESEARCH_BACKEND` in
`scripts/r5_developer_hermes/container/egress/host.py` still names an
approved processor. If it does not, research fails closed — safe, but
broken.

Detail for the checklist items:
[`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md) §14.

### Cost policy

```text
DEFAULT_IMPLEMENTATION_MODEL = Grok 4.6
```

Use Grok for routine implementation, documentation, update work,
focused regression analysis, Desktop, Bot Mode, model-routing
implementation, and small reviews.

Avoid giant prompts, broad repeated security campaigns, repeatedly
proving already-closed R5 facts, and routine Opus usage.

Opus is an exception for genuinely new high-impact trust-boundary
decisions only, and even then prompts and reviews stay narrow.

Dedicated clones under `W:\hermes-dev` remain container workspaces. Do
not execute them on the host. Reset the named volume
`r5-developer-hermes-home` after suspected prompt injection or poisoned
persistent state. Egress policy is decided **and enforced** — see
[`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md).
The container reaches only approved destinations, through the broker.

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
DESKTOP_CONTAINER_COMPATIBILITY  = OFFICIAL_REMOTE_GATEWAY
BOT_MODE_CONTAINER_COMPATIBILITY = NEEDS_REMEDIATION
MODEL_ROUTING_CONFIGURABLE_WITHOUT_CORE_FORK = YES
WINDOWS_COMPUTER_USE_ENABLED     = NO
```

Official Hermes Desktop (unchanged) connects as a Remote Gateway client to
`http://127.0.0.1:19119`. The Developer container stays on the internal
Docker network. A localhost-only authenticated sidecar is the dual-homed
party. Credentials live in
`W:\hermes-dev\credentials\developer-hermes-desktop.env` and are never
mounted. Do not install a second Hermes runtime on Windows and do not
enable Computer Use.

The official website Windows download is Hermes Setup
(`apps/bootstrap-installer`), not a thin client. It always bootstraps a
local agent under `%LOCALAPPDATA%\hermes`. Do not run it for Developer
Hermes. Electron Remote Gateway can skip that local spawn only when
`connection.json` (or a complete env remote) is already remote *before*
`startHermes()` falls through to `resolveHermesBackend()`.

Reproduce the official remote-only Windows client from the exact pin
with `scripts/r5_developer_hermes/desktop_remote_client.py`: locate the
pinned source, `npm run pack`, and pre-seed
`%APPDATA%\Hermes\connection.json` before the first Electron start.
`authMode=oauth` is the official cookie / ws-ticket gate (including
password-login). Do not switch the gateway to token auth for this path.

Post-merge host residue is not a merge blocker. Distinguish three
classes and clean them only after merge, never from the PR:

- Pre-existing Hermes HOME (`%APPDATA%\Hermes` and any older
  `%LOCALAPPDATA%\hermes` profile) predates this slice. Leave it unless
  a human confirms it is unused.
- Aborted website-installer / bootstrap residue under
  `%LOCALAPPDATA%\hermes` is leftover from the rejected Setup /
  `install.ps1` path. Do not delete it as part of this merge.
- Official source-built Desktop pack artifacts live under
  `W:\cache\hermes-desktop-official-v2026.8.19`. Those are generated
  host outputs, not repo truth, and stay untracked.

Bot Mode remains unimplemented. Future routing intent remains Terra
default, Luna cheap/auxiliary, Sol explicit escalation.

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode desktop
```
