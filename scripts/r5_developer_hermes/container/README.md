# R5 Developer-Hermes container sandbox

Infrastructure around Hermes. Not Hermes-core.

```text
ISOLATION_BOUNDARY          = CONTAINER
ISOLATION_BOUNDARY_FALLBACK = DEDICATED_OS_PRINCIPAL
scope-workspace-authority.ps1 = FALLBACK_ONLY
```

The running container may bind-mount exactly two host paths:

```text
W:\hermes-dev\workspace\hermes-agent     -> /workspace/hermes-agent
W:\hermes-dev\workspace\EU-PP-Database   -> /workspace/EU-PP-Database
```

`HERMES_HOME` is container-local (`/tmp/r5-hermes-home`). Host profiles,
secrets, the Docker socket, and host credential helpers stay unmounted.

## Commands

From the Repo A root, with Docker Desktop Linux-container mode:

```powershell
python scripts/r5_developer_hermes/container/launch.py argv
python scripts/r5_developer_hermes/container/launch.py up
python scripts/r5_developer_hermes/container/launch.py prove
python scripts/r5_developer_hermes/container/launch.py down
```

`prove` writes `.r5-dev/artifacts/container_boundary.json` (gitignored).

Desktop and Bot Mode isolation are not claimed by this sandbox.
