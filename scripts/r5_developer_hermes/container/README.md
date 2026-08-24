# R5 Developer-Hermes container sandbox

Infrastructure around Hermes. Not Hermes-core.

```text
ISOLATION_BOUNDARY          = CONTAINER
ISOLATION_BOUNDARY_FALLBACK = DEDICATED_OS_PRINCIPAL
HERMES_HOME_MECHANISM       = DOCKER_NAMED_VOLUME
scope-workspace-authority.ps1 = FALLBACK_ONLY
```

The running container may bind-mount exactly two host paths:

```text
W:\hermes-dev\workspace\hermes-agent     -> /workspace/hermes-agent
W:\hermes-dev\workspace\EU-PP-Database   -> /workspace/EU-PP-Database
```

`HERMES_HOME` is the container-managed volume `r5-developer-hermes-home`
mounted at `/opt/data`. Host profiles, secrets, the Docker socket, and host
credential helpers stay unmounted.

## One-command launch

From any host PowerShell that can see Docker Desktop Linux containers:

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode prove
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode down
```

Python equivalents:

```powershell
python scripts/r5_developer_hermes/container/launch.py build
python scripts/r5_developer_hermes/container/launch.py up
python scripts/r5_developer_hermes/container/launch.py prove-dx
python scripts/r5_developer_hermes/container/launch.py down
```

`prove-dx` writes gitignored artifacts under `.r5-dev/artifacts/`.

## Model credential

Optional dedicated file (never the host profile secrets tree):

```text
W:\hermes-dev\credentials\developer-hermes-model.env
```

Allowlisted keys only: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`. Absent file → model calls stay blocked.

The official image write sandbox is overridden to
`HERMES_WRITE_SAFE_ROOT=/workspace:/opt/data` so the file tool can edit
the two approved repo mounts. Host paths stay unmounted.

Desktop and Bot Mode isolation are not claimed by this sandbox.
