# R5 — Powerful Developer Hermes

**Slice:** R5  
**Date:** 2026-08-23  
**Depends on:** `GATE_1 = CLOSED` (R1)  
**Status:** developer environment only — no production mutation.
`R5_GATE = CLOSED` (PR #67 human-merged). Entry point:
[`hermes_r5_closeout_v1.md`](./hermes_r5_closeout_v1.md).
Ordinary upstream maintenance follows the update contract in
[`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md)
and does not reopen this gate.

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
ISOLATION_BOUNDARY          = CONTAINER
ISOLATION_BOUNDARY_FALLBACK = DEDICATED_OS_PRINCIPAL
ISOLATION_BOUNDARY_REJECTED = PROCESS_CONSTRUCTED_ENV
PATH_STUB_SECURITY_ROLE     = NONE
workspace_acl_script_role   = FALLBACK_ONLY
```

Empirical Linux-container proof: [`hermes_r5_container_boundary_v1.md`](./hermes_r5_container_boundary_v1.md).
Developer DX (persistent home, fullstack tooling, one-command launch):
[`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md).
The dedicated `hermes-dev` account and `scope-workspace-authority.ps1` remain
defense in depth. Do not run the ACL script against `C:\`, `D:\`, or `W:\`.

```text
DEVELOPER_HERMES_CONTROLLER      = PINNED_PURE_UPSTREAM
DEVELOPER_RUNTIME_SOURCE         = /opt/hermes
GENERIC_FINAL_TOOLSET_CAP_ACTIVE = NO
OPERATOR_HERMES_TARGET           = UPSTREAM_NEAR + GENERIC_FINAL_TOOLSET_CAP
CONTAINER_MOUNT_BOUNDARY         = HOST/FILESYSTEM BOUNDARY
EGRESS_BOUNDARY                  = OUTBOUND CONFIDENTIALITY BOUNDARY
HERMES_WRITE_SAFE_ROOT           = DEFENSE IN DEPTH
REPO_A_REPO_B_SAME_TRUST_DOMAIN  = YES
R5_F06_STATUS                    = ENFORCED_EGRESS_POLICY
```

The sandbox has **two** boundaries, and confusing them is the fastest way to
reason wrongly about this system. The mount contract decides what of the
**host** is reachable. The network topology decides where data may **go**.
Neither substitutes for the other: a perfect mount boundary still lets a
compromised process upload the repository, and a perfect egress boundary still
lets it read whatever you mounted.

Developer Hermes runs the pinned official image (`Hermes Agent v0.20.5`,
SHA `fcbd1076a93841fa88855acce810e342a5b78101`) from `/opt/hermes`. It does
**not** execute `/workspace/hermes-agent` as the controller runtime. The
generic Operator-Hermes final-toolset cap is intentionally absent. A future
test image that runs a modified checkout is a separate capability and is
not part of this sandbox.

Repo A and Repo B are **one** Developer-Hermes trust domain. Both binds are
intentionally RW. Cross-repo mutation is expected. The two host bind mounts
define the outer host boundary; they do not isolate the repos from each
other.

`R5_F06_STATUS = ENFORCED_EGRESS_POLICY`: outbound traffic now leaves only
through the egress broker, and only to destinations a human approved in
[`egress_policy.json`](../../scripts/r5_developer_hermes/container/egress/egress_policy.json).
Arbitrary direct egress is denied by the Docker topology, not by proxy
environment variables. Public web research stays available because it is
**provider-mediated**: the sandbox sends a query to an approved processor,
which performs the external retrieval; the sandbox never connects to the
researched site. Approving a processor is an explicit human trust decision and
does not approve the sites it reads. See
[`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md)
for the decision and the evidence. Desktop and Bot Mode stay
`NEEDS_REMEDIATION`.

```text
R5_CONFIDENTIALITY_CONTRACT = HOST_AND_PRODUCTION_ISOLATION
                              + PRIVATE_REPO_CONFIDENTIALITY_AGAINST_
                                ARBITRARY_THIRD_PARTIES
SELECTED_EGRESS_ARCHITECTURE = ENFORCING_BROKER_ON_INTERNAL_DOCKER_NETWORK
```

Runtime proofs must also show source/image/container identity convergence.
See [`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md)
(`CHECKED_IN_RUNTIME_CONTRACT == BUILT_IMAGE_IDENTITY ==
RUNNING_CONTAINER_IMAGE_IDENTITY`). Versioned docs and tests are canonical;
`.r5-dev/artifacts` is gitignored host evidence only.


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

Environment absence is not authority absence.

### The boundary that replaces it

The canonical primary boundary is now a **Linux container** with an explicit
two-repository bind-mount allowlist. Production authority is absent because
it is not mounted, copied, or inherited. See
[`hermes_r5_container_boundary_v1.md`](./hermes_r5_container_boundary_v1.md).

The dedicated non-administrative local Windows account (`hermes-dev`) is
kept as defense in depth. Host Railway/GitHub/cloud CLI stores still sit
under `C:\Users\<host>`. Provisioning scripts remain in
`scripts/r5_developer_hermes/principal/`.
`scope-workspace-authority.ps1` is `FALLBACK_ONLY`.

Pinned modern runtime (unchanged from R1):

```text
UPSTREAM_RELEASE       = v2026.8.19
UPSTREAM_RELEASE_SHA   = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_IMAGE_DIGEST  = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

## Workspace

| Tree | Host bind (literal allowlist) | Container | Mode |
|---|---|---|---|
| Repo A | `W:\hermes-dev\workspace\hermes-agent` | `/workspace/hermes-agent` | RW |
| Repo B | `W:\hermes-dev\workspace\EU-PP-Database` | `/workspace/EU-PP-Database` | RW |

No parent, sibling, or credentials-directory substitution. No per-file
allowlist. Persistent `HERMES_HOME` is the Docker named volume
`r5-developer-hermes-home` at `/opt/data`.

```text
DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST
GIT_HOOKS                  = CONTAINED_CODE_EXECUTION
RESET_DEVELOPER_HERMES_HOME = launch-developer-hermes.ps1 -Mode reset
```

Dedicated clones are container execution workspaces. The host must not run
pytest, Python, PowerShell, Node/npm, Git hooks, launchers, or repo scripts
from `W:\hermes-dev`. Container output may be malicious or compromised even
though it cannot autonomously escape the container. The canonical launcher
runs from `W:\Workbench\hermes-agent` and refuses a resolved path under
`W:\hermes-dev`.

Git hooks inside the container are contained code execution — part of the
arbitrary-code authority already granted there. The host-side clone rule is
the protection that matters.

Use `-Mode reset` after suspected prompt injection, a bad Skill, bad config,
or poisoned persistent state. Reset stops the container and removes only
`r5-developer-hermes-home`. It never accepts an arbitrary volume name and
never touches Repo A/B, host secrets, or production.

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
No Desktop, Bot Mode, or model-routing implementation.
`DESKTOP_CONTAINER_COMPATIBILITY = NEEDS_REMEDIATION`
`BOT_MODE_CONTAINER_COMPATIBILITY = NEEDS_REMEDIATION`
