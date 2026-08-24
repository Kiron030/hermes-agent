"""Canonical Developer-Hermes container filesystem and launch contract.

This is sandbox infrastructure around Hermes. It adds no PowerUnits domain
logic and does not change Hermes core.

Developer Hermes executes pinned pure upstream from ``/opt/hermes``.
The two bind mounts are one trust domain and the outer host boundary.
They are not an Operator-Hermes generic-final-toolset claim.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


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
HERMES_HOME_VOLUME_LITERAL = "r5-developer-hermes-home"
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

# Literal approved host bind sources. Security checks use these strings,
# never a value derived from a mutable workspace-root helper.
LITERAL_APPROVED_BIND_SOURCES: tuple[str, ...] = (
    r"W:\hermes-dev\workspace\hermes-agent",
    r"W:\hermes-dev\workspace\EU-PP-Database",
)
HOST_REPO_A = Path(LITERAL_APPROVED_BIND_SOURCES[0])
HOST_REPO_B = Path(LITERAL_APPROVED_BIND_SOURCES[1])
HOST_WORKSPACE_ROOT = HOST_REPO_A.parent
DEDICATED_MODEL_ENV_FILE = Path(r"W:\hermes-dev\credentials\developer-hermes-model.env")
DEDICATED_HOST_CLONE_ROOTS: tuple[str, ...] = (r"W:\hermes-dev",)

REPO_A_CONTAINER = "/workspace/hermes-agent"
REPO_B_CONTAINER = "/workspace/EU-PP-Database"

BIND_MOUNTS: tuple[tuple[str, str], ...] = (
    (LITERAL_APPROVED_BIND_SOURCES[0], REPO_A_CONTAINER),
    (LITERAL_APPROVED_BIND_SOURCES[1], REPO_B_CONTAINER),
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
DUPLICATE_MODEL_KEY_POLICY = "REJECT"

# Provenance — Developer Hermes is not Operator Hermes.
DEVELOPER_HERMES_CONTROLLER = "PINNED_PURE_UPSTREAM"
OPERATOR_HERMES_TARGET = "UPSTREAM_NEAR_PLUS_GENERIC_FINAL_TOOLSET_CAP"
DEVELOPER_RUNTIME_SOURCE = "/opt/hermes"
GENERIC_FINAL_TOOLSET_CAP_ACTIVE = "NO"
CONTAINER_MOUNT_BOUNDARY = "PRIMARY"
HERMES_WRITE_SAFE_ROOT_ROLE = "DEFENSE_IN_DEPTH"
REPO_A_REPO_B_SAME_TRUST_DOMAIN = "YES"
R5_F06_STATUS = "OPEN_POLICY_DECISION"
CANONICAL_LAUNCH_CONTRACT = "docker_run_argv"
COMPOSE_FILE_ROLE = "NON_AUTHORITATIVE_EXAMPLE"
DESKTOP_CONTAINER_COMPATIBILITY = "NEEDS_REMEDIATION"
BOT_MODE_CONTAINER_COMPATIBILITY = "NEEDS_REMEDIATION"
GIT_HOOKS_POSTURE = "CONTAINED_CODE_EXECUTION"
LINUX_CAPABILITY_HARDENING = "DEFERRED_WITH_RATIONALE"
LINUX_CAPABILITY_HARDENING_RATIONALE = (
    "The container already runs unprivileged (--privileged=false, "
    "no-new-privileges) as root only so Windows bind-mount .git/objects "
    "stay writable. cap_drop ALL plus a guessed add-back set needs an "
    "empirical Git/Node/Hermes/pytest/volume matrix and can break proven "
    "DX. LOW finding; mount allowlist remains the primary boundary."
)
TYPESCRIPT_PIN = "7.0.2"
PYTEST_PIN = "9.1.1"

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
    # on the approved repo mounts. Defense in depth only — the bind allowlist
    # is the primary host boundary.
    "HERMES_WRITE_SAFE_ROOT": "/workspace:/opt/data",
}

# Explicit rejects used by regression tests. The classifier does not rely
# on this list: any host bind outside the literal allowlist is forbidden.
FORBIDDEN_HOST_SOURCES: tuple[str, ...] = (
    "C:\\",
    "D:\\",
    "W:\\",
    r"W:\hermes-dev",
    r"W:\hermes-dev\credentials",
    r"C:\ProgramData",
    r"C:\Users",
    "W:\\Workbench",
    "W:\\dataset",
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

_DOCKER_DESKTOP_PREFIXES: tuple[str, ...] = (
    "/run/desktop/mnt/host/",
    "/host_mnt/",
    "/mnt/host/",
)


def env_names_only(env_items: list[Any] | tuple[Any, ...]) -> list[str]:
    """Return environment variable names. Values are discarded."""
    names: list[str] = []
    for item in env_items:
        if not isinstance(item, str) or not item:
            continue
        names.append(item.split("=", 1)[0])
    return sorted(names)


def sanitize_container_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep inspect fields that proofs may persist. Never keep Env values."""
    host_config = payload.get("HostConfig") or {}
    config = payload.get("Config") or {}
    mounts = payload.get("Mounts") or []
    bind_mounts = [
        {
            "source": item.get("Source"),
            "destination": item.get("Destination"),
            "mode": item.get("Mode") or item.get("RW"),
            "rw": bool(item.get("RW")),
            "type": item.get("Type"),
            "name": item.get("Name"),
        }
        for item in mounts
    ]
    return {
        "id": payload.get("Id"),
        "image": config.get("Image") or payload.get("Image"),
        "image_id": payload.get("Image"),
        "user": config.get("User") or "",
        "privileged": bool(host_config.get("Privileged")),
        "pid_mode": host_config.get("PidMode") or "",
        "network_mode": host_config.get("NetworkMode") or "",
        "runtime": host_config.get("Runtime") or "",
        "env_names": env_names_only(list(config.get("Env") or [])),
        "working_dir": config.get("WorkingDir"),
        "mounts": bind_mounts,
    }


def canonicalize_bind_source(path: str) -> str:
    """Comparable host path, including Docker Desktop / WSL source forms.

    Result examples:
      ``w:/hermes-dev/workspace/hermes-agent``
      ``c:/users/user``
      ``w:``
    """
    if not path:
        return ""
    raw = path.strip()
    slashy = raw.replace("\\", "/")
    lower = slashy.lower()
    if "docker.sock" in lower:
        return "/var/run/docker.sock"
    pipe = lower.replace("/", "\\")
    if pipe.startswith(r"\\.\pipe") or "docker_engine" in pipe:
        return r"\\.\pipe\docker_engine"

    while "//" in slashy:
        slashy = slashy.replace("//", "/")
    slashy = slashy.rstrip("/")
    lower = slashy.lower()

    for prefix in _DOCKER_DESKTOP_PREFIXES:
        if lower.startswith(prefix):
            return _drive_rest_to_canon(lower[len(prefix) :])
    if lower.startswith("/mnt/"):
        rest = lower[len("/mnt/") :]
        drive, _, tail = rest.partition("/")
        if len(drive) == 1 and drive.isalpha():
            return f"{drive}:/{tail}" if tail else f"{drive}:"

    if len(lower) >= 2 and lower[1] == ":" and lower[0].isalpha():
        drive = lower[0]
        rest = lower[2:].lstrip("/")
        return f"{drive}:/{rest}" if rest else f"{drive}:"
    return lower


def _drive_rest_to_canon(rest: str) -> str:
    if not rest:
        return ""
    if len(rest) >= 2 and rest[1] == ":":
        drive = rest[0]
        tail = rest[2:].lstrip("/")
        return f"{drive}:/{tail}" if tail else f"{drive}:"
    drive, _, tail = rest.partition("/")
    if len(drive) == 1 and drive.isalpha():
        return f"{drive}:/{tail}" if tail else f"{drive}:"
    return rest


def literal_approved_bind_source_set() -> set[str]:
    return {canonicalize_bind_source(item) for item in LITERAL_APPROVED_BIND_SOURCES}


def normalize_host_path(path: str) -> str:
    """Windows-backslash form of ``canonicalize_bind_source``."""
    return canonicalize_bind_source(path).replace("/", "\\")


def is_named_volume_source(source: str) -> bool:
    if not source:
        return False
    if source == HERMES_HOME_VOLUME or source == HERMES_HOME_VOLUME_LITERAL:
        return True
    return source.startswith("/var/lib/docker/volumes")


def is_host_bind_source(source: str) -> bool:
    """True when the source is a host filesystem path, not a named volume."""
    if not source or is_named_volume_source(source):
        return False
    canon = canonicalize_bind_source(source)
    if len(canon) >= 2 and canon[1] == ":":
        return True
    if source.startswith("/") or source.startswith("\\"):
        return True
    return False


def is_approved_bind_source(source: str) -> bool:
    return canonicalize_bind_source(source) in literal_approved_bind_source_set()


def is_forbidden_host_source(source: str) -> bool:
    """True when a Docker mount source is a host path outside the allowlist."""
    if not is_host_bind_source(source):
        return False
    return not is_approved_bind_source(source)


def bind_sources_match_literal_allowlist(sources: list[str] | tuple[str, ...]) -> bool:
    return {canonicalize_bind_source(item) for item in sources} == literal_approved_bind_source_set()


def assert_bind_sources_exactly_approved(sources: list[str] | tuple[str, ...]) -> None:
    if not bind_sources_match_literal_allowlist(sources):
        raise RuntimeError(
            "NORMALIZED_ACTUAL_BIND_SOURCE_SET != LITERAL_APPROVED_BIND_SOURCE_SET"
        )


def classify_inspect_mounts(mounts: list[dict[str, Any]]) -> dict[str, Any]:
    """Positive-allowlist classification of docker-inspect mount records."""
    binds = [item for item in mounts if str(item.get("type") or "").lower() == "bind"]
    volumes = [item for item in mounts if str(item.get("type") or "").lower() == "volume"]
    dests = {item.get("destination") for item in binds}
    sources = [str(item.get("source") or "") for item in binds]
    approved_dests = {REPO_A_CONTAINER, REPO_B_CONTAINER}
    extra_dests = sorted(dests - approved_dests)
    missing_dests = sorted(approved_dests - dests)
    normalized_actual = {canonicalize_bind_source(source) for source in sources}
    normalized_approved = literal_approved_bind_source_set()
    forbidden_sources = [source for source in sources if is_forbidden_host_source(source)]
    rw_ok = all(item.get("rw") for item in binds if item.get("destination") in approved_dests)
    exact = (
        normalized_actual == normalized_approved
        and dests == approved_dests
        and rw_ok
        and not extra_dests
        and not missing_dests
        and len(binds) == 2
        and not forbidden_sources
    )
    hermes_home_volume = any(
        item.get("destination") == CONTAINER_HERMES_HOME
        and str(item.get("type") or "").lower() == "volume"
        and (
            item.get("name") == HERMES_HOME_VOLUME
            or HERMES_HOME_VOLUME in str(item.get("source") or "")
        )
        for item in volumes
    )
    canons = [canonicalize_bind_source(source) for source in sources]
    extra_w = any(
        canon.startswith("w:") and canon not in normalized_approved for canon in canons
    )
    non_bind = [
        {
            "destination": item.get("destination"),
            "type": item.get("type"),
            "source": item.get("source"),
            "name": item.get("name"),
        }
        for item in mounts
        if str(item.get("type") or "").lower() != "bind"
    ]
    return {
        "MOUNTS_RW": sorted(dest for dest in dests if dest),
        "exact_two_approved_rw": exact,
        "exact_allowlist_match": normalized_actual == normalized_approved,
        "normalized_actual": sorted(normalized_actual),
        "normalized_approved": sorted(normalized_approved),
        "extra_host_bind_destinations": extra_dests,
        "missing_destinations": missing_dests,
        "forbidden_sources": forbidden_sources,
        "unapproved_sources": sorted(normalized_actual - normalized_approved),
        "non_host_mounts": non_bind,
        "HERMES_HOME_VOLUME_PRESENT": "YES" if hermes_home_volume else "NO",
        "HOST_W_WHOLE_MOUNTED": "YES" if any(canon == "w:" for canon in canons) else "NO",
        "HOST_C_MOUNTED": "YES" if any(canon.startswith("c:") for canon in canons) else "NO",
        "HOST_D_MOUNTED": "YES" if any(canon.startswith("d:") for canon in canons) else "NO",
        "HOST_W_MOUNTED": "YES" if extra_w else "NO",
    }


def canonicalize_host_fs_path(path: str | Path) -> str:
    """Absolute, ``..``-normalized, symlink-resolved host path (canonical form)."""
    raw = os.fspath(path)
    expanded = os.path.expandvars(os.path.expanduser(raw))
    abs_path = os.path.abspath(expanded)
    try:
        resolved = str(Path(abs_path).resolve(strict=False))
    except OSError:
        resolved = abs_path
    return canonicalize_bind_source(resolved)


def is_under_dedicated_clone_root(path: str | Path) -> bool:
    canon = canonicalize_host_fs_path(path)
    for root in DEDICATED_HOST_CLONE_ROOTS:
        root_canon = canonicalize_host_fs_path(root)
        if canon == root_canon or canon.startswith(root_canon + "/"):
            return True
    return False


def assert_trusted_host_launcher(
    script_path: str | Path,
    repo_root: str | Path | None = None,
) -> None:
    """Fail closed if this launcher is running from a dedicated container clone."""
    if is_under_dedicated_clone_root(script_path):
        raise RuntimeError(
            "HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED: "
            "DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST"
        )
    if repo_root is not None and is_under_dedicated_clone_root(repo_root):
        raise RuntimeError(
            "HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED: "
            "DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST"
        )


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
        if key in parsed:
            raise RuntimeError(
                f"duplicate allowlisted key in dedicated model file: {key}"
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
    sources = tuple(source for source, _destination in BIND_MOUNTS)
    assert_bind_sources_exactly_approved(sources)
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
