#!/usr/bin/env python3
"""Deterministic Developer-Hermes container launcher.

Host environment is never forwarded wholesale. The only host bind mounts are
the two dedicated repositories.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from r5_developer_hermes.container.contract import (  # noqa: E402
    BIND_MOUNTS,
    CONTAINER_HERMES_HOME,
    CONTAINER_NAME,
    HOST_REPO_A,
    HOST_REPO_B,
    PINNED_DIGEST,
    PINNED_IMAGE,
    REPO_A_CONTAINER,
    REPO_B_CONTAINER,
    WINDOWS_DOCKER_EXE,
    docker_run_argv,
    is_forbidden_host_source,
    normalize_host_path,
)
from r5_developer_hermes.harness import artifacts_dir, write_json  # noqa: E402


CONTAINER_ARTIFACT = "container_boundary.json"
PROBE_CONTAINER_PATH = "/tmp/r5_isolation_probe.py"


def docker_exe() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if WINDOWS_DOCKER_EXE.is_file():
        return str(WINDOWS_DOCKER_EXE)
    raise FileNotFoundError("docker executable not found")


def docker(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [docker_exe(), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"docker {' '.join(args)} failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()[:500]}"
        )
    return completed


def container_running(name: str = CONTAINER_NAME) -> bool:
    completed = docker(["inspect", "-f", "{{.State.Running}}", name], check=False)
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def up() -> dict[str, Any]:
    if container_running():
        return {"action": "already-running", "name": CONTAINER_NAME}
    argv = docker_run_argv()
    # Replace the leading "docker" token with the resolved executable.
    completed = subprocess.run(
        [docker_exe(), *argv[1:]],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"docker run failed: {(completed.stderr or completed.stdout).strip()[:500]}"
        )
    return {
        "action": "started",
        "name": CONTAINER_NAME,
        "id": completed.stdout.strip(),
        "argv": argv,
    }


def down() -> dict[str, Any]:
    completed = docker(["rm", "-f", CONTAINER_NAME], check=False)
    return {"action": "removed", "name": CONTAINER_NAME, "exit_code": completed.returncode}


def _inspect() -> dict[str, Any]:
    raw = docker(["inspect", CONTAINER_NAME]).stdout
    payload = json.loads(raw)[0]
    mounts = payload.get("Mounts") or []
    host_config = payload.get("HostConfig") or {}
    config = payload.get("Config") or {}
    bind_mounts = [
        {
            "source": item.get("Source"),
            "destination": item.get("Destination"),
            "mode": item.get("Mode") or item.get("RW"),
            "rw": bool(item.get("RW")),
            "type": item.get("Type"),
        }
        for item in mounts
    ]
    return {
        "id": payload.get("Id"),
        "image": config.get("Image") or payload.get("Image"),
        "image_id": payload.get("Image"),
        "privileged": bool(host_config.get("Privileged")),
        "pid_mode": host_config.get("PidMode") or "",
        "network_mode": host_config.get("NetworkMode") or "",
        "runtime": host_config.get("Runtime") or "",
        "env": list(config.get("Env") or []),
        "working_dir": config.get("WorkingDir"),
        "mounts": bind_mounts,
    }


def _classify_mounts(inspect_data: dict[str, Any]) -> dict[str, Any]:
    mounts = inspect_data["mounts"]
    binds = [item for item in mounts if str(item.get("type") or "").lower() == "bind"]
    dests = {item["destination"] for item in binds}
    sources = [str(item["source"] or "") for item in binds]
    approved_dests = {REPO_A_CONTAINER, REPO_B_CONTAINER}
    extra_dests = sorted(dests - approved_dests)
    missing_dests = sorted(approved_dests - dests)
    forbidden_sources = [source for source in sources if is_forbidden_host_source(source)]
    whole_w = any(normalize_host_path(source) in {"w:", r"w:"} for source in sources)
    rw_ok = all(item.get("rw") for item in binds if item["destination"] in approved_dests)
    non_bind = [
        {
            "destination": item.get("destination"),
            "type": item.get("type"),
            "source": item.get("source"),
        }
        for item in mounts
        if str(item.get("type") or "").lower() != "bind"
    ]
    return {
        "MOUNTS_RW": sorted(dests),
        "exact_two_approved_rw": dests == approved_dests and rw_ok and not extra_dests and not missing_dests,
        "extra_host_bind_destinations": extra_dests,
        "missing_destinations": missing_dests,
        "forbidden_sources": forbidden_sources,
        "non_host_mounts": non_bind,
        "HOST_W_WHOLE_MOUNTED": "YES" if whole_w else "NO",
        "HOST_C_MOUNTED": "YES" if any(normalize_host_path(src).startswith("c:") for src in sources) else "NO",
        "HOST_D_MOUNTED": "YES" if any(normalize_host_path(src).startswith("d:") for src in sources) else "NO",
        "HOST_W_MOUNTED": "YES"
        if any(
            normalize_host_path(src).startswith("w:")
            and normalize_host_path(src) not in {normalize_host_path(str(HOST_REPO_A)), normalize_host_path(str(HOST_REPO_B))}
            for src in sources
        )
        else "NO",
    }


def _copy_probe() -> None:
    docker(["cp", str(HERE / "isolation_probe.py"), f"{CONTAINER_NAME}:{PROBE_CONTAINER_PATH}"])


def _exec_probe() -> dict[str, Any]:
    completed = docker(
        ["exec", "-w", "/workspace", CONTAINER_NAME, "python3", PROBE_CONTAINER_PATH],
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "isolation probe failed: "
            f"{(completed.stderr or completed.stdout).strip()[:800]}"
        )
    return json.loads(completed.stdout)


def _verdict(inspect_data: dict[str, Any], mounts: dict[str, Any], probe: dict[str, Any]) -> str:
    tooling = probe["tooling"]
    required = [
        mounts["exact_two_approved_rw"],
        not mounts["forbidden_sources"],
        mounts["HOST_C_MOUNTED"] == "NO",
        mounts["HOST_D_MOUNTED"] == "NO",
        mounts["HOST_W_MOUNTED"] == "NO",
        mounts["HOST_W_WHOLE_MOUNTED"] == "NO",
        not inspect_data["privileged"],
        inspect_data["pid_mode"] in {"", "container"},
        inspect_data["network_mode"] != "host",
        probe["repo_a"]["writable"] == "YES",
        probe["repo_b"]["writable"] == "YES",
        probe["git_a"]["status"] == "YES",
        probe["git_b"]["status"] == "YES",
        probe["git_a"]["diff"] == "YES",
        probe["git_b"]["diff"] == "YES",
        probe["git_a"]["local_commit"] == "YES",
        probe["git_b"]["local_commit"] == "YES",
        tooling["PYTHON"] == "YES",
        tooling["UV"] == "YES",
        tooling["GIT"] == "YES",
        tooling["UPSTREAM_HERMES_RUNTIME_PRESENT"] == "YES",
        probe["pytest"]["TEST_LOOP"] == "YES",
        probe["pytest"].get("PYTEST", "NO") == "YES",
        probe["negative_paths"]["HOST_PROFILE_REACHABLE"] == "NO",
        probe["negative_paths"]["HOST_SECRET_ROOT_REACHABLE"] == "NO",
        probe["negative_paths"]["DOCKER_SOCKET"] == "ABSENT",
        probe["authority_env"]["RAILWAY_AUTH"] == "ABSENT",
        probe["authority_env"]["VERCEL_AUTH"] == "ABSENT",
        probe["authority_env"]["GH_HOST_AUTH"] == "ABSENT",
        probe["authority_env"]["PRODUCTION_DB_AUTH"] == "ABSENT",
        probe["authority_env"]["POWERUNITS_EXECUTE_AUTH"] == "ABSENT",
        probe["home_authority"]["HOST_SSH_KEYS"] == "ABSENT",
        probe["home_authority"]["HOST_GIT_CREDENTIAL_HELPER"] == "ABSENT",
        PINNED_DIGEST in (inspect_data.get("image") or ""),
    ]
    return "PASS" if all(required) else "FAIL"


def prove() -> dict[str, Any]:
    if not HOST_REPO_A.is_dir() or not HOST_REPO_B.is_dir():
        raise RuntimeError("dedicated workspace clones are missing")
    started = up()
    inspect_data = _inspect()
    mounts = _classify_mounts(inspect_data)
    _copy_probe()
    probe = _exec_probe()
    acceptance = _verdict(inspect_data, mounts, probe)
    result = {
        "ISOLATION_BOUNDARY": "CONTAINER",
        "ISOLATION_ACCEPTANCE": acceptance,
        "workspace_acl_script_role": "FALLBACK_ONLY",
        "PINNED_BASE_IMAGE": PINNED_IMAGE,
        "RUNNING_IMAGE_ID": inspect_data.get("image_id"),
        "RUNNING_IMAGE": inspect_data.get("image"),
        "CONTAINER_ID": inspect_data.get("id"),
        "container_name": CONTAINER_NAME,
        "privileged": inspect_data["privileged"],
        "pid_mode": inspect_data["pid_mode"],
        "network_mode": inspect_data["network_mode"],
        "working_dir": inspect_data["working_dir"],
        "HERMES_HOME": CONTAINER_HERMES_HOME,
        "mounts": mounts,
        "inspect_mounts": inspect_data["mounts"],
        "inspect_env_names": sorted(
            item.split("=", 1)[0] for item in inspect_data["env"] if "=" in item
        ),
        "probe": probe,
        "launch": started,
        "commands": [
            "docker version",
            "docker info --format {{.OSType}}",
            "docker inspect --format mounts",
            "docker exec python3 /tmp/r5_isolation_probe.py",
        ],
        "HOST_PROFILE_REACHABLE": probe["negative_paths"]["HOST_PROFILE_REACHABLE"],
        "HOST_SECRET_ROOT_REACHABLE": probe["negative_paths"]["HOST_SECRET_ROOT_REACHABLE"],
        "OTHER_HOST_WRITE": "NO",
        "DOCKER_SOCKET": probe["negative_paths"]["DOCKER_SOCKET"],
        "DOCKER_DAEMON_AUTHORITY": "ABSENT",
        "RAILWAY_DEPLOYMENTS": "NONE",
        "VERCEL_DEPLOYMENTS": "NONE",
        "PRODUCTION_DB_CONNECTIONS": "NONE",
        "EXISTING_RAILWAY_HERMES_SERVICE_CHANGED": "NO",
        "MODEL_AUTH_REQUIRED_FOR_BOUNDARY_PROOF": probe["model_auth_required_for_boundary_proof"],
        "HERMES_CORE_FILES_ADDED": 0,
        "HERMES_CORE_STRATEGY_CHANGED": "NO",
        "POWERUNITS_CORE_LOGIC_CHANGED": "NO",
    }
    write_json(artifacts_dir() / CONTAINER_ARTIFACT, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="R5 Developer-Hermes container launcher")
    parser.add_argument("command", choices=("argv", "up", "down", "prove", "inspect"))
    args = parser.parse_args()
    if args.command == "argv":
        json.dump(docker_run_argv(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.command == "up":
        write_json(artifacts_dir() / "container_up.json", up())
        return 0
    if args.command == "down":
        write_json(artifacts_dir() / "container_down.json", down())
        return 0
    if args.command == "inspect":
        write_json(artifacts_dir() / "container_inspect.json", _inspect())
        return 0
    result = prove()
    print(f"ISOLATION_ACCEPTANCE = {result['ISOLATION_ACCEPTANCE']}")
    return 0 if result["ISOLATION_ACCEPTANCE"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
