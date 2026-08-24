# R5 Developer-Hermes container sandbox

Infrastructure around Hermes. Not Hermes-core.

```text
ISOLATION_BOUNDARY               = CONTAINER
ISOLATION_BOUNDARY_FALLBACK      = DEDICATED_OS_PRINCIPAL
HERMES_HOME_MECHANISM            = DOCKER_NAMED_VOLUME
DEVELOPER_HERMES_CONTROLLER      = PINNED_PURE_UPSTREAM
DEVELOPER_RUNTIME_SOURCE         = /opt/hermes
GENERIC_FINAL_TOOLSET_CAP_ACTIVE = NO
CONTAINER_MOUNT_BOUNDARY         = PRIMARY
HERMES_WRITE_SAFE_ROOT           = DEFENSE IN DEPTH
REPO_A_REPO_B_SAME_TRUST_DOMAIN  = YES
CANONICAL_LAUNCH_CONTRACT        = docker_run_argv
COMPOSE_FILE_ROLE                = NON_AUTHORITATIVE_EXAMPLE
DEDICATED_CONTAINER_CLONES       = DO_NOT_EXECUTE_ON_HOST
GIT_HOOKS                        = CONTAINED_CODE_EXECUTION
RESET_DEVELOPER_HERMES_HOME      = launch-developer-hermes.ps1 -Mode reset
R5_F06_STATUS                    = ENFORCED_EGRESS_POLICY
scope-workspace-authority.ps1    = FALLBACK_ONLY
```

The running controller is pinned upstream Hermes in `/opt/hermes`. The
mounted checkout is an editable workspace, not the executing runtime.

```text
CHECKED_IN_RUNTIME_CONTRACT
== BUILT_IMAGE_IDENTITY
== RUNNING_CONTAINER_IMAGE_IDENTITY
```

`launch.py up` / the one-command launcher rebuilds when the checked-in
image-input fingerprint disagrees with the stamped image labels, and
recreates the container when the running image ID is stale. A missing
identity label is never trusted. Matching identities reuse the current
image and container. Live `prove` fails closed on disagreement.

Versioned docs/tests are the reusable contract. `.r5-dev/artifacts` is
machine-specific evidence and remains gitignored.

The running container may bind-mount exactly two host paths:

```text
W:\hermes-dev\workspace\hermes-agent     -> /workspace/hermes-agent
W:\hermes-dev\workspace\EU-PP-Database   -> /workspace/EU-PP-Database
```

Repo A and Repo B are one trust domain. Both are intentionally RW.
Cross-repo mutation is expected. The two binds are the outer host
boundary; they do not isolate the repos from each other.

`HERMES_HOME` is the container-managed volume `r5-developer-hermes-home`
mounted at `/opt/data`. Host profiles, secrets, the Docker socket, and host
credential helpers stay unmounted.

## Trust rule: do not execute dedicated clones on the host

```text
DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST
```

`W:\hermes-dev\workspace\*` are container execution workspaces. Container
output may be malicious or compromised even though it cannot autonomously
escape the container. The host must not run pytest, Python, PowerShell,
Node/npm, Git hooks, launchers, or repo scripts from those trees.

`GIT_HOOKS = CONTAINED_CODE_EXECUTION` inside the container. That is part
of the arbitrary-code authority already granted there. The host-side clone
rule is the protection that matters.

The canonical launcher must run from `W:\Workbench\hermes-agent` and
refuses a resolved script or repository root under `W:\hermes-dev`.

## One-command launch

From the trusted host checkout:

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode prove
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode down
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode reset -WhatIf
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode reset
```

Python equivalents:

```powershell
python scripts/r5_developer_hermes/container/launch.py build
python scripts/r5_developer_hermes/container/launch.py up
python scripts/r5_developer_hermes/container/launch.py prove-dx
python scripts/r5_developer_hermes/container/launch.py reset
python scripts/r5_developer_hermes/container/launch.py down
```

`compose.yaml` is a non-authoritative example. Do not treat it as the
runtime contract.

`prove-dx` writes gitignored artifacts under `.r5-dev/artifacts/`.
Inspect/proof output may include environment variable **names** only.
Values are omitted. A host user with Docker daemon authority can still
inspect container environment; that does not enlarge the container trust
boundary.

## Reset persistent home

```text
RESET_DEVELOPER_HERMES_HOME
```

Use after suspected prompt injection, a bad Skill, bad config, or other
poisoned persistent state. The operation stops/removes the Developer-Hermes
container and deletes only the fixed named volume
`r5-developer-hermes-home`. It never accepts an arbitrary volume name and
never touches Repo A/B, host secrets, or production. The next launch
recreates and seeds a clean home.

## Model credential

Optional dedicated file (never the host profile secrets tree):

```text
W:\hermes-dev\credentials\developer-hermes-model.env
```

Allowlisted keys only: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`. Duplicate allowed keys fail closed. Absent file →
model calls stay blocked.

The official image write sandbox is overridden to
`HERMES_WRITE_SAFE_ROOT=/workspace:/opt/data` as defense in depth so the
file tool can edit the two approved repo mounts. Host paths stay unmounted.
The primary boundary is the bind-source allowlist.

Official Desktop is inbound UI transport only
(`DESKTOP_CONTAINER_COMPATIBILITY = OFFICIAL_REMOTE_GATEWAY`):
`127.0.0.1:19119` via an authenticated sidecar. Bot Mode isolation is
not claimed (`NEEDS_REMEDIATION`). Outbound egress is enforced
(`R5_F06_STATUS = ENFORCED_EGRESS_POLICY`). Closeout:
[`hermes_r5_closeout_v1.md`](../../../docs/architecture/hermes_r5_closeout_v1.md).
