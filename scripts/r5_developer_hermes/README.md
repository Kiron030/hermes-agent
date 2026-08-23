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
ISOLATION_BOUNDARY          = DEDICATED_OS_PRINCIPAL
ISOLATION_BOUNDARY_REJECTED = PROCESS_CONSTRUCTED_ENV
PATH_STUB_SECURITY_ROLE     = NONE
```

The developer child is still spawned with an environment **constructed** from a
safe passthrough allowlist, and production names are still never copied. That is
env hygiene and it is worth keeping — but it is not the boundary. An independent
review showed the child keeps the host logon token, so it keeps host ACL rights,
and CLIs that resolve credentials through the Windows known-folder API stay
authenticated no matter what `HOME`, `USERPROFILE` or `APPDATA` say.

Isolation therefore comes from running Hermes as a **separate, non-administrative
local account** (`hermes-dev`) that has `Modify` on the two approved workspace
roots and no access to the host profile. See [`principal/`](./principal).

The `railway` / `vercel` PATH stubs remain only as a visible nudge for a careless
interactive command. `SECURITY_CONTROL = NO`: they are bypassed by any absolute
path, they live in a directory the instance can write to, and nothing in the
authority proof may depend on them.

Docker is optional and absent on this host; that does not change the above.

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

# ELEVATED account, creates hermes-dev and adds additive ACEs only
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1

# ordinary account again; runas prompts for the password and never caches it
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Mode verify
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Mode probes
```

Do not authenticate `gh` or `railway` as `hermes-dev`, and do not copy SSH keys
or Credential Manager state into that profile. Their absence is the boundary.

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
