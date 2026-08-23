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
ISOLATION_BOUNDARY = PROCESS_CONSTRUCTED_ENV
```

The developer child is spawned with an environment **constructed** from a
safe passthrough allowlist. Production DB, execute-secret, Railway, and
Vercel names are never copied. The harness does **not** sanitize
`os.environ` in-process and then `update` it again.

Docker is optional. If the host has no Docker CLI, this process boundary
is the repo-supported mechanism (same family as R1). Do not treat a
missing container runtime as a fake container.

Host Railway/Vercel CLI logins can survive a stripped env on Windows.
The constructed `PATH` therefore shadows `railway` / `vercel` with
fail-closed stubs. Env tokens remain absent.

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

Do not add approval bureaucracy to look secure. The security boundary is
that this process does not possess production credentials.

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
