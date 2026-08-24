# R5 Powerful Developer Hermes

A separate modern-Hermes **developer** instance:

```text
POWERFUL_IN_WORKSPACE
NOT_POWERFUL_IN_PRODUCTION
```

This is not the constrained Stage-1 operator Hermes. Ordinary workspace
edits do not require micro-approvals. Production authority is absent from
the process, not "discouraged" by policy text.

## Isolation boundary

```text
ISOLATION_BOUNDARY          = CONTAINER
ISOLATION_BOUNDARY_FALLBACK = DEDICATED_OS_PRINCIPAL
ISOLATION_BOUNDARY_REJECTED = PROCESS_CONSTRUCTED_ENV
PATH_STUB_SECURITY_ROLE     = NONE
workspace_acl_script_role   = FALLBACK_ONLY
```

The developer child is still spawned with an environment **constructed** from a
safe passthrough allowlist, and production names are still never copied. That is
env hygiene and it is worth keeping — but it is not the boundary. An independent
review showed the child keeps the host logon token, so it keeps host ACL rights,
and CLIs that resolve credentials through the Windows known-folder API stay
authenticated no matter what `HOME`, `USERPROFILE` or `APPDATA` say.

Isolation therefore comes from a **Linux container** with an explicit
two-repository bind-mount allowlist. See [`container/`](./container).
The dedicated `hermes-dev` account remains defense in depth; see
[`principal/`](./principal). `scope-workspace-authority.ps1` is
`FALLBACK_ONLY` and must not be executed against `C:\`, `D:\`, or `W:\`.

The `railway` / `vercel` PATH stubs remain only as a visible nudge for a careless
interactive command. `SECURITY_CONTROL = NO`: they are bypassed by any absolute
path, they live in a directory the instance can write to, and nothing in the
authority proof may depend on them.

Docker Desktop Linux containers are the canonical R5 primary boundary.

Pinned modern runtime (from R1):

```text
nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

## Commands

From the Repo A root:

```bash
python scripts/r5_developer_hermes/harness.py preflight
python scripts/r5_developer_hermes/harness.py prepare-runtime
python scripts/r5_developer_hermes/harness.py isolate-env
python scripts/r5_developer_hermes/harness.py boot-smoke
python scripts/r5_developer_hermes/harness.py enumerate-tools
python scripts/r5_developer_hermes/harness.py sqlite-probe
python scripts/r5_developer_hermes/harness.py authority-proof
python scripts/r5_developer_hermes/harness.py developer-probes
python scripts/r5_developer_hermes/harness.py all
python scripts/r5_developer_hermes/container/launch.py prove
```

`prepare-runtime` reuses a matching R1 upstream worktree/venv when present.

## Dedicated principal workflow

`authority-proof` reads `PRODUCTION_DEPLOY_REACHABLE` and
`PRODUCTION_SECRET_FILES_REACHABLE` from
`.r5-dev/artifacts/principal_isolation.json` and reports `NOT_PROVEN` until that
file exists and passes. Produce it like this:

```powershell
cd scripts\r5_developer_hermes\principal

# ordinary account, read-only
powershell -ExecutionPolicy Bypass -File .\preflight-principal.ps1 -CreateSentinel

# ordinary account: move secrets out of the workspace FIRST (see below)
powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1 -Relocate

# ELEVATED account, creates hermes-dev and adds additive ACEs only
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1

# ELEVATED: scope its write authority. Backs up every DACL first.
powershell -ExecutionPolicy Bypass -File .\scope-workspace-authority.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File .\scope-workspace-authority.ps1

# ordinary account again; runas prompts for the password and never caches it
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Mode verify
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Mode probes
```

Do not authenticate `gh` or `railway` as `hermes-dev`, and do not copy SSH keys
or Credential Manager state into that profile. Their absence is the boundary.

## Workspace-only write authority

Creating the account and granting the two repositories is not enough. Every
local volume root on this class of host carries an inheritable `Authenticated
Users` write ACE, so a fresh standard account inherits write across whole volumes
before any grant exists. That ACE cannot simply be removed — in an unelevated
token the host user's `Administrators` membership is deny-only, so it is the only
entry giving the human write access to their own data.

`scope-workspace-authority.ps1` scopes from the other side instead, adding
nothing to any existing principal: a scoped root created with inheritance
**disabled** (so a volume-root deny cannot reach the grants inside it), plus a
principal-specific inheritable **write**-deny at each volume root. Read and
execute stay intact, so no tool, service or traversal breaks.

`rollback-workspace-authority.ps1` restores the DACLs from the backup the scoping
script writes before its first mutation. Design, evidence and the ordered human
runbook: [`hermes_r5_workspace_authority_v1.md`](../../docs/architecture/hermes_r5_workspace_authority_v1.md).

`uv` must be installed machine-wide: `harness.py prepare-runtime` runs
`uv sync --frozen`. Node and npm resolve through a symlink into the host profile
and stay out of reach — that is also what keeps the host Railway CLI shim
unreachable, so do not "fix" it by exposing the profile.

## Secrets must leave the workspace first

`hermes-dev` needs `Modify` on both workspace roots, so nothing inside them can
be hidden from it. Secret-class files therefore move to a host-only root that
lives in the human account's profile:

```text
HOST_ONLY_SECRET_ROOT = %USERPROFILE%\.powerunits\secrets\
```

`bootstrap-host-secrets.ps1` creates `repo-b.env`, `app.env` and `mapbox.env`
there and, with `-Relocate`, **moves** the three untracked Repo-B files out.
`run-with-host-secrets.ps1` keeps normal human development working by injecting
those files into the **process environment** — no symlink back into the
workspace, no copy, no value ever printed or written.

Full inventory, blast radius and the ordered human runbook (including the legacy
`.env.pgurl` rotation):
[`docs/architecture/hermes_r5_secret_relocation_v1.md`](../../docs/architecture/hermes_r5_secret_relocation_v1.md).

## Workspace

| Tree | Default | Access |
|---|---|---|
| Repo A | this `hermes-agent` checkout | read/write |
| Repo B | sibling `EU-PP-Database` or `HERMES_R5_REPO_B_ROOT` | read/write |

No per-file allowlist. Scratch git work for probes lives under `.r5-dev/`
(gitignored). Probe writes into Repo B use `.r5-developer-hermes-scratch/`
and are not a product change.

## Approvals

```text
approvals.mode = off
ORDINARY_WORKSPACE_APPROVALS = 0
```

Do not add approval bureaucracy to look secure. The security boundary is the OS
principal the process runs as — not approvals, not environment scrubbing, and
not PATH stubs.

## Web probe

If a dedicated non-production research key exists:

```bash
set HERMES_R5_WEB_API_KEY=<non-production-tavily-or-equivalent>
python scripts/r5_developer_hermes/harness.py developer-probes
```

Ambient `TAVILY_API_KEY` is not passed through. If no dedicated key:

```text
WEB_PROBE = NOT_RUN_CREDENTIAL_REQUIRED
```

That does not weaken R5.

## Tests

```bash
python -m pytest tests/r5_developer_hermes -q
```

## Rollback

Delete `.r5-dev/` (or `HERMES_R5_PROOF_ROOT`). Production is untouched
because it was never attached.
