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

CONTAINER_NAME = "r5-developer-hermes"
CONTAINER_WORKDIR = "/workspace"
CONTAINER_HERMES_HOME = "/tmp/r5-hermes-home"
CONTAINER_HOME = "/tmp/r5-hermes-home"

HOST_WORKSPACE_ROOT = Path(r"W:\hermes-dev\workspace")
HOST_REPO_A = HOST_WORKSPACE_ROOT / "hermes-agent"
HOST_REPO_B = HOST_WORKSPACE_ROOT / "EU-PP-Database"

REPO_A_CONTAINER = "/workspace/hermes-agent"
REPO_B_CONTAINER = "/workspace/EU-PP-Database"

BIND_MOUNTS: tuple[tuple[str, str], ...] = (
    (str(HOST_REPO_A), REPO_A_CONTAINER),
    (str(HOST_REPO_B), REPO_B_CONTAINER),
)

ENV_ALLOWLIST: dict[str, str] = {
    "HERMES_HOME": CONTAINER_HERMES_HOME,
    "HOME": CONTAINER_HOME,
    "TERM": "xterm",
    "LANG": "C.UTF-8",
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
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
)

WINDOWS_DOCKER_EXE = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")


def normalize_host_path(path: str) -> str:
    return path.replace("/", "\\").rstrip("\\").lower()


def is_forbidden_host_source(source: str) -> bool:
    """True when a Docker mount source is a forbidden host path.

    The two approved repository binds under W:\\hermes-dev\\workspace are the
    only W: paths that may appear. A source of ``W:\\`` itself is forbidden.
    """
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


def docker_run_argv(image: str = PINNED_IMAGE, name: str = CONTAINER_NAME) -> list[str]:
    """Deterministic ``docker run`` argument vector. Host env is not forwarded."""
    argv = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--privileged=false",
        "--network",
        "bridge",
        "--workdir",
        CONTAINER_WORKDIR,
        "--entrypoint",
        "/bin/bash",
        "--security-opt",
        "no-new-privileges:true",
        "--tmpfs",
        "/opt/data:rw,noexec,nosuid,size=64m",
    ]
    for key, value in ENV_ALLOWLIST.items():
        argv.extend(["--env", f"{key}={value}"])
    for source, destination in BIND_MOUNTS:
        argv.extend(["--mount", f"type=bind,src={source},dst={destination}"])
    argv.extend(
        [
            image,
            "-lc",
            "mkdir -p /tmp/r5-hermes-home /workspace && exec sleep infinity",
        ]
    )
    return argv
