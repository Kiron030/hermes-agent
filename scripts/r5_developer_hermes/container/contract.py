"""Canonical Developer-Hermes container filesystem and launch contract.

This is sandbox infrastructure around Hermes. It adds no PowerUnits domain
logic and does not change Hermes core.
"""

from __future__ import annotations

from pathlib import Path


PINNED_IMAGE = (
    "nousresearch/hermes-agent@sha256:"
    "3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09"
)
PINNED_DIGEST = "sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09"
DEVELOPER_IMAGE = "r5-developer-hermes:dx-v1"
DEVELOPER_IMAGE_FROM = PINNED_IMAGE

CONTAINER_NAME = "r5-developer-hermes"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_HERMES_HOME = "/opt/data"
CONTAINER_HOME = "/opt/data"
HERMES_HOME_VOLUME = "r5-developer-hermes-home"
HERMES_HOME_MECHANISM = "DOCKER_NAMED_VOLUME"

# Windows/WSL bind mounts make Repo A/B working trees writable to uid 10000,
# but `.git/objects` stays root-owned. Non-root therefore breaks local Git
# commits. The container stays unprivileged; this is not host root.
RUNTIME_USER = "root"
RUNTIME_UID = 0
RUNTIME_GID = 0
RUNTIME_USER_RATIONALE = (
    "ROOT_ACCEPTED_WITH_RATIONALE: Windows bind-mount .git/objects is not "
    "writable by uid 10000; unprivileged container root keeps local Git."
)

HOST_WORKSPACE_ROOT = Path(r"W:\hermes-dev\workspace")
HOST_REPO_A = HOST_WORKSPACE_ROOT / "hermes-agent"
HOST_REPO_B = HOST_WORKSPACE_ROOT / "EU-PP-Database"
DEDICATED_MODEL_ENV_FILE = Path(r"W:\hermes-dev\credentials\developer-hermes-model.env")

REPO_A_CONTAINER = "/workspace/hermes-agent"
REPO_B_CONTAINER = "/workspace/EU-PP-Database"

BIND_MOUNTS: tuple[tuple[str, str], ...] = (
    (str(HOST_REPO_A), REPO_A_CONTAINER),
    (str(HOST_REPO_B), REPO_B_CONTAINER),
)

VOLUME_MOUNTS: tuple[tuple[str, str], ...] = (
    (HERMES_HOME_VOLUME, CONTAINER_HERMES_HOME),
)

GIT_IDENTITY_NAME = "R5 Developer Hermes"
GIT_IDENTITY_EMAIL = "r5-developer-hermes@local"

MODEL_KEY_ALLOWLIST: tuple[str, ...] = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)

ENV_ALLOWLIST: dict[str, str] = {
    "HERMES_HOME": CONTAINER_HERMES_HOME,
    "HOME": CONTAINER_HOME,
    "TERM": "xterm",
    "LANG": "C.UTF-8",
    "GIT_CONFIG_GLOBAL": f"{CONTAINER_HERMES_HOME}/.gitconfig",
    "GIT_CONFIG_NOSYSTEM": "1",
    # Container runs as root for Windows bind-mount Git. Keep the official
    # hermes PATH shim from dropping to uid 10000 and then failing on home files.
    "HERMES_DOCKER_EXEC_AS_ROOT": "1",
    # Official image defaults this to /opt/data, which blocks write_file/patch
    # on the approved repo mounts. Keep Hermes home and the two-repo workspace.
    "HERMES_WRITE_SAFE_ROOT": "/workspace:/opt/data",
}

FORBIDDEN_HOST_SOURCES: tuple[str, ...] = (
    "C:\\",
    "D:\\",
    "W:\\",
    "W:\\Workbench",
    "W:\\dataset",
    "C:\\Users",
    "C:\\Users\\User",
    "C:\\Users\\User\\.powerunits",
    "C:\\Users\\User\\.powerunits\\secrets",
    "C:\\Temp",
    "D:\\Archiv",
    "\\\\.\\pipe\\docker_engine",
    "/var/run/docker.sock",
    "/run/docker.sock",
)

FORBIDDEN_CONTAINER_PATHS: tuple[str, ...] = (
    "/mnt/c",
    "/mnt/d",
    "/mnt/w",
    "/mnt/host",
    "/host",
    "/host_mnt",
    "/run/desktop/mnt/host",
    "/run/desktop/mnt/host/c",
    "/run/desktop/mnt/host/d",
    "/run/desktop/mnt/host/w",
    "/run/desktop/mnt/host/w/Workbench",
    "/run/desktop/mnt/host/w/dataset",
    "/run/desktop/mnt/host/c/Users",
    "/run/desktop/mnt/host/c/Users/User",
    "/run/desktop/mnt/host/c/Users/User/.powerunits",
    "/run/desktop/mnt/host/c/Users/User/.powerunits/secrets",
    "/var/run/docker.sock",
    "/run/docker.sock",
)

AUTHORITY_ENV_NAMES: tuple[str, ...] = (
    "RAILWAY_TOKEN",
    "RAILWAY_API_TOKEN",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_ENVIRONMENT_ID",
    "VERCEL_TOKEN",
    "VERCEL_ORG_ID",
    "VERCEL_PROJECT_ID",
    "VERCEL_DEPLOY_HOOK",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "DATABASE_URL",
    "DATABASE_URL_TIMESCALE",
    "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET",
    "POWERUNITS_INTERNAL_EXECUTE_BASE_URL",
    "SSH_AUTH_SOCK",
    "GIT_ASKPASS",
    "GITHUB_USER",
)

WINDOWS_DOCKER_EXE = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")


def normalize_host_path(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\").lower()


def is_forbidden_host_source(source: str) -> bool:
    """True when a Docker mount source is a forbidden host path.

    The two approved repository binds under W:\\hermes-dev\\workspace are the
    only W: paths that may appear. A source of ``W:\\`` itself is forbidden.
    Named Docker volumes are not host sources.
    """
    if not source or source.startswith("/var/lib/docker/volumes"):
        return False
    if "\\" not in source and not source[1:2] == ":":
        # Named volume or Linux-only path that is not a Windows host bind.
        if source.lower() == HERMES_HOME_VOLUME.lower():
            return False
        if source.startswith("/"):
            return "docker.sock" in source
        return False
    normalized = normalize_host_path(source)
    approved = {normalize_host_path(src) for src, _dst in BIND_MOUNTS}
    if normalized in approved:
        return False
    if normalized in {normalize_host_path(item) for item in FORBIDDEN_HOST_SOURCES}:
        return True
    if normalized.startswith(normalize_host_path(r"C:\Users")):
        return True
    if normalized.startswith(r"\\.\pipe"):
        return True
    if "docker.sock" in normalized.replace("\\", "/"):
        return True
    if normalized == "w:" or normalized == r"w:":
        return True
    return False


def parse_dedicated_model_env(path: Path | None = None) -> dict[str, str]:
    """Load the dedicated Developer-Hermes model file. Fail closed on extras."""
    target = path or DEDICATED_MODEL_ENV_FILE
    if not target.is_file():
        return {}
    parsed: dict[str, str] = {}
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError(f"invalid model credential line in {target.name}")
        key, _, value = line.partition("=")
        key = key.strip()
        if key in AUTHORITY_ENV_NAMES:
            raise RuntimeError(
                f"refusing production-authority name in dedicated model file: {key}"
            )
        if key not in MODEL_KEY_ALLOWLIST:
            raise RuntimeError(
                f"refusing non-allowlisted key in dedicated model file: {key}"
            )
        parsed[key] = value.strip().strip('"').strip("'")
    return parsed


def model_credential_status(path: Path | None = None) -> dict[str, str]:
    target = path or DEDICATED_MODEL_ENV_FILE
    if not target.is_file():
        return {
            "MODEL_CREDENTIAL_MODE": "DEDICATED_FILE_ABSENT",
            "MODEL_CALL": "BLOCKED_PENDING_HUMAN_KEY",
            "MODEL_CREDENTIAL_SCOPE": "DEVELOPER_HERMES_ONLY",
            "HOST_ENV_WHOLESALE": "NO",
            "keys_present": "NO",
        }
    keys = parse_dedicated_model_env(target)
    present = "YES" if keys else "NO"
    return {
        "MODEL_CREDENTIAL_MODE": "DEDICATED_FILE",
        "MODEL_CALL": "READY" if keys else "BLOCKED_PENDING_HUMAN_KEY",
        "MODEL_CREDENTIAL_SCOPE": "DEVELOPER_HERMES_ONLY",
        "HOST_ENV_WHOLESALE": "NO",
        "keys_present": present,
        "key_names": ",".join(sorted(keys)),
    }


def docker_run_argv(
    image: str = DEVELOPER_IMAGE,
    name: str = CONTAINER_NAME,
    model_env: dict[str, str] | None = None,
) -> list[str]:
    """Deterministic ``docker run`` argument vector. Host env is not forwarded."""
    argv = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--user",
        "0:0",
        "--privileged=false",
        "--network",
        "bridge",
        "--workdir",
        CONTAINER_WORKDIR,
        "--entrypoint",
        "/opt/r5-developer/entrypoint.sh",
        "--security-opt",
        "no-new-privileges:true",
    ]
    for key, value in ENV_ALLOWLIST.items():
        argv.extend(["--env", f"{key}={value}"])
    if model_env:
        for key, value in model_env.items():
            if key not in MODEL_KEY_ALLOWLIST:
                raise ValueError(f"refusing to inject non-allowlisted model key {key}")
            if key in AUTHORITY_ENV_NAMES:
                raise ValueError(f"refusing to inject production-authority name {key}")
            argv.extend(["--env", f"{key}={value}"])
    for volume, destination in VOLUME_MOUNTS:
        argv.extend(["--mount", f"type=volume,src={volume},dst={destination}"])
    for source, destination in BIND_MOUNTS:
        argv.extend(["--mount", f"type=bind,src={source},dst={destination}"])
    argv.extend([image, "sleep", "infinity"])
    return argv
