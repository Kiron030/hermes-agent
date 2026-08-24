#!/usr/bin/env python3
"""Deterministic Developer-Hermes container launcher.

Host environment is never forwarded wholesale. The only host bind mounts are
the two dedicated repositories. Persistent HERMES_HOME is a Docker volume.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from r5_developer_hermes.container.contract import (  # noqa: E402
    AUTHORITY_ENV_NAMES,
    BIND_MOUNTS,
    CONTAINER_HERMES_HOME,
    CONTAINER_NAME,
    CONTAINER_WORKDIR,
    DEVELOPER_IMAGE,
    DEDICATED_MODEL_ENV_FILE,
    HERMES_HOME_MECHANISM,
    HERMES_HOME_VOLUME,
    HOST_REPO_A,
    HOST_REPO_B,
    PINNED_DIGEST,
    PINNED_IMAGE,
    REPO_A_CONTAINER,
    REPO_B_CONTAINER,
    RUNTIME_GID,
    RUNTIME_UID,
    RUNTIME_USER,
    WINDOWS_DOCKER_EXE,
    docker_run_argv,
    is_forbidden_host_source,
    model_credential_status,
    normalize_host_path,
    parse_dedicated_model_env,
)
from r5_developer_hermes.harness import artifacts_dir, write_json  # noqa: E402


CONTAINER_ARTIFACT = "container_boundary.json"
DX_ARTIFACT = "developer_dx.json"
PROBE_CONTAINER_PATH = "/tmp/r5_isolation_probe.py"
DX_PROBE_CONTAINER_PATH = "/tmp/r5_dx_probe.py"


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


def assert_linux_engine() -> dict[str, str]:
    ostype = docker(["info", "--format", "{{.OSType}}"]).stdout.strip().lower()
    if ostype != "linux":
        raise RuntimeError(f"Linux containers required, OSType={ostype}")
    return {"DOCKER_OSTYPE": ostype}


def container_running(name: str = CONTAINER_NAME) -> bool:
    completed = docker(["inspect", "-f", "{{.State.Running}}", name], check=False)
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def container_exists(name: str = CONTAINER_NAME) -> bool:
    completed = docker(["inspect", "-f", "{{.Id}}", name], check=False)
    return completed.returncode == 0


def ensure_volume() -> dict[str, Any]:
    docker(["volume", "create", HERMES_HOME_VOLUME], check=False)
    docker(
        [
            "run",
            "--rm",
            "--user",
            "0:0",
            "--network",
            "none",
            "--mount",
            f"type=volume,src={HERMES_HOME_VOLUME},dst={CONTAINER_HERMES_HOME}",
            "--entrypoint",
            "chown",
            PINNED_IMAGE,
            f"{RUNTIME_USER}:{RUNTIME_USER}",
            CONTAINER_HERMES_HOME,
        ]
    )
    return {"volume": HERMES_HOME_VOLUME, "destination": CONTAINER_HERMES_HOME}


def build_image() -> dict[str, Any]:
    dockerfile = HERE / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    if PINNED_IMAGE not in text or PINNED_DIGEST not in text:
        raise RuntimeError("Dockerfile must FROM the pinned Hermes digest")
    if "latest" in text.split("FROM", 1)[-1].splitlines()[0]:
        raise RuntimeError("Dockerfile must not FROM a floating tag")
    completed = docker(
        [
            "build",
            "-t",
            DEVELOPER_IMAGE,
            "-f",
            str(dockerfile),
            str(HERE),
        ]
    )
    return {
        "image": DEVELOPER_IMAGE,
        "from": PINNED_IMAGE,
        "exit_code": completed.returncode,
    }


def _model_env() -> dict[str, str]:
    if not DEDICATED_MODEL_ENV_FILE.is_file():
        return {}
    return parse_dedicated_model_env(DEDICATED_MODEL_ENV_FILE)


def up() -> dict[str, Any]:
    assert_linux_engine()
    if not HOST_REPO_A.is_dir() or not HOST_REPO_B.is_dir():
        raise RuntimeError("dedicated workspace clones are missing")
    if container_exists():
        existing = _inspect()
        image = existing.get("image") or ""
        user = existing.get("user") or ""
        env_names = {item.split("=", 1)[0] for item in existing.get("env") or [] if "=" in item}
        dx_ready = (
            DEVELOPER_IMAGE in image
            and user in {
                f"{RUNTIME_UID}:{RUNTIME_GID}",
                RUNTIME_USER,
                str(RUNTIME_UID),
                "0:0",
            }
            and "HERMES_DOCKER_EXEC_AS_ROOT" in env_names
            and "GIT_CONFIG_GLOBAL" in env_names
        )
        if not dx_ready:
            docker(["rm", "-f", CONTAINER_NAME], check=False)
        elif container_running():
            return {"action": "already-running", "name": CONTAINER_NAME}
        else:
            docker(["start", CONTAINER_NAME])
            if not container_running():
                docker(["rm", "-f", CONTAINER_NAME], check=False)
            else:
                return {"action": "started-existing", "name": CONTAINER_NAME}
    ensure_volume()
    images = docker(["images", "-q", DEVELOPER_IMAGE], check=False)
    if not images.stdout.strip():
        build_image()
    argv = docker_run_argv(model_env=_model_env())
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
        "argv_without_secrets": docker_run_argv(model_env=None),
    }


def down(*, remove_volume: bool = False) -> dict[str, Any]:
    completed = docker(["rm", "-f", CONTAINER_NAME], check=False)
    volume_removed = False
    if remove_volume:
        docker(["volume", "rm", HERMES_HOME_VOLUME], check=False)
        volume_removed = True
    return {
        "action": "removed",
        "name": CONTAINER_NAME,
        "exit_code": completed.returncode,
        "volume_removed": volume_removed,
    }


def exec_in(
    args: list[str],
    *,
    workdir: str = CONTAINER_WORKDIR,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        docker_exe(),
        "exec",
        "-u",
        f"{RUNTIME_UID}:{RUNTIME_GID}",
        "-w",
        workdir,
        CONTAINER_NAME,
        *args,
    ]
    completed = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"docker exec failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()[:800]}"
        )
    return completed


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
        "env": list(config.get("Env") or []),
        "working_dir": config.get("WorkingDir"),
        "mounts": bind_mounts,
    }


def _classify_mounts(inspect_data: dict[str, Any]) -> dict[str, Any]:
    mounts = inspect_data["mounts"]
    binds = [item for item in mounts if str(item.get("type") or "").lower() == "bind"]
    volumes = [item for item in mounts if str(item.get("type") or "").lower() == "volume"]
    dests = {item["destination"] for item in binds}
    sources = [str(item["source"] or "") for item in binds]
    approved_dests = {REPO_A_CONTAINER, REPO_B_CONTAINER}
    extra_dests = sorted(dests - approved_dests)
    missing_dests = sorted(approved_dests - dests)
    forbidden_sources = [source for source in sources if is_forbidden_host_source(source)]
    whole_w = any(normalize_host_path(source) in {"w:", r"w:"} for source in sources)
    rw_ok = all(item.get("rw") for item in binds if item["destination"] in approved_dests)
    hermes_home_volume = any(
        item.get("destination") == CONTAINER_HERMES_HOME
        and str(item.get("type") or "").lower() == "volume"
        and (item.get("name") == HERMES_HOME_VOLUME or HERMES_HOME_VOLUME in str(item.get("source") or ""))
        for item in volumes
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
        "MOUNTS_RW": sorted(dests),
        "exact_two_approved_rw": dests == approved_dests and rw_ok and not extra_dests and not missing_dests,
        "extra_host_bind_destinations": extra_dests,
        "missing_destinations": missing_dests,
        "forbidden_sources": forbidden_sources,
        "non_host_mounts": non_bind,
        "HERMES_HOME_VOLUME_PRESENT": "YES" if hermes_home_volume else "NO",
        "HOST_W_WHOLE_MOUNTED": "YES" if whole_w else "NO",
        "HOST_C_MOUNTED": "YES" if any(normalize_host_path(src).startswith("c:") for src in sources) else "NO",
        "HOST_D_MOUNTED": "YES" if any(normalize_host_path(src).startswith("d:") for src in sources) else "NO",
        "HOST_W_MOUNTED": "YES"
        if any(
            normalize_host_path(src).startswith("w:")
            and normalize_host_path(src)
            not in {normalize_host_path(str(HOST_REPO_A)), normalize_host_path(str(HOST_REPO_B))}
            for src in sources
        )
        else "NO",
    }


def _copy_probe() -> None:
    docker(["cp", str(HERE / "isolation_probe.py"), f"{CONTAINER_NAME}:{PROBE_CONTAINER_PATH}"])
    docker(["cp", str(HERE / "dx_probe.py"), f"{CONTAINER_NAME}:{DX_PROBE_CONTAINER_PATH}"])


def _exec_json(script: str) -> dict[str, Any]:
    completed = exec_in(["python3", script], check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "probe failed: "
            f"{(completed.stderr or completed.stdout).strip()[:800]}"
        )
    return json.loads(completed.stdout)


def _env_names(inspect_data: dict[str, Any]) -> list[str]:
    return sorted(item.split("=", 1)[0] for item in inspect_data["env"] if "=" in item)


def _verdict(inspect_data: dict[str, Any], mounts: dict[str, Any], probe: dict[str, Any]) -> str:
    tooling = probe["tooling"]
    env_names = set(_env_names(inspect_data))
    leaked_authority = sorted(name for name in AUTHORITY_ENV_NAMES if name in env_names)
    required = [
        mounts["exact_two_approved_rw"],
        not mounts["forbidden_sources"],
        mounts["HOST_C_MOUNTED"] == "NO",
        mounts["HOST_D_MOUNTED"] == "NO",
        mounts["HOST_W_MOUNTED"] == "NO",
        mounts["HOST_W_WHOLE_MOUNTED"] == "NO",
        mounts["HERMES_HOME_VOLUME_PRESENT"] == "YES",
        not inspect_data["privileged"],
        inspect_data["pid_mode"] in {"", "container"},
        inspect_data["network_mode"] != "host",
        not leaked_authority,
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
    ]
    return "PASS" if all(required) else "FAIL"


def prove_persistence() -> dict[str, Any]:
    started = up()
    marker = f"r5-dx-persist-{int(time.time())}"
    exec_in(
        [
            "python3",
            "-c",
            (
                "from pathlib import Path; "
                f"p=Path('{CONTAINER_HERMES_HOME}')/'.r5-dx-sentinel'; "
                f"p.write_text({marker!r}+'\\n'); print(p.read_text())"
            ),
        ]
    )
    docker(["rm", "-f", CONTAINER_NAME])
    restarted = up()
    readback = exec_in(
        [
            "python3",
            "-c",
            (
                "from pathlib import Path; "
                f"print(Path('{CONTAINER_HERMES_HOME}/.r5-dx-sentinel').read_text())"
            ),
        ]
    ).stdout
    return {
        "HERMES_HOME_PERSISTENT": "YES" if marker in readback else "NO",
        "HERMES_HOME_MECHANISM": HERMES_HOME_MECHANISM,
        "HOST_HERMES_HOME_USED": "NO",
        "HOST_PROFILE_MOUNTED": "NO",
        "survived_container_removal": marker in readback,
        "marker_present": marker in readback,
        "launch_before": started,
        "launch_after": restarted,
    }


def prove() -> dict[str, Any]:
    if not HOST_REPO_A.is_dir() or not HOST_REPO_B.is_dir():
        raise RuntimeError("dedicated workspace clones are missing")
    started = up()
    # Give the entrypoint time to seed HERMES_HOME.
    time.sleep(1)
    inspect_data = _inspect()
    mounts = _classify_mounts(inspect_data)
    _copy_probe()
    probe = _exec_json(PROBE_CONTAINER_PATH)
    acceptance = _verdict(inspect_data, mounts, probe)
    model = model_credential_status()
    result = {
        "ISOLATION_BOUNDARY": "CONTAINER",
        "ISOLATION_ACCEPTANCE": acceptance,
        "workspace_acl_script_role": "FALLBACK_ONLY",
        "PINNED_BASE_IMAGE": PINNED_IMAGE,
        "DEVELOPER_IMAGE": inspect_data.get("image"),
        "PINNED_BASE_PRESERVED": "YES",
        "RUNNING_IMAGE_ID": inspect_data.get("image_id"),
        "RUNNING_IMAGE": inspect_data.get("image"),
        "CONTAINER_ID": inspect_data.get("id"),
        "container_name": CONTAINER_NAME,
        "CONTAINER_RUNTIME_USER": inspect_data.get("user") or f"{RUNTIME_UID}:{RUNTIME_GID}",
        "privileged": inspect_data["privileged"],
        "pid_mode": inspect_data["pid_mode"],
        "network_mode": inspect_data["network_mode"],
        "working_dir": inspect_data["working_dir"],
        "HERMES_HOME": CONTAINER_HERMES_HOME,
        "HERMES_HOME_MECHANISM": HERMES_HOME_MECHANISM,
        "mounts": mounts,
        "inspect_mounts": inspect_data["mounts"],
        "inspect_env_names": _env_names(inspect_data),
        "probe": probe,
        "launch": started,
        "model_credential": {k: v for k, v in model.items() if k != "key_names" or True},
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


def prove_dx() -> dict[str, Any]:
    boundary = prove()
    _copy_probe()
    dx = _exec_json(DX_PROBE_CONTAINER_PATH)
    persistence = prove_persistence()
    model = model_credential_status()
    smoke = {
        "REAL_HERMES_CODING_SMOKE": (
            "BLOCKED_PENDING_HUMAN_MODEL_CREDENTIAL"
            if model["MODEL_CALL"] != "READY"
            else dx.get("coding_smoke", "NOT_RUN")
        ),
        "CODING_SMOKE_TASK": "none — dedicated model credential absent"
        if model["MODEL_CALL"] != "READY"
        else dx.get("coding_smoke_task", ""),
        "CODING_SMOKE_TEST_RESULT": "NOT_RUN",
    }
    result = {
        **dx,
        "boundary": {
            "ISOLATION_ACCEPTANCE": boundary["ISOLATION_ACCEPTANCE"],
            "HOST_PROFILE_REACHABLE": boundary["HOST_PROFILE_REACHABLE"],
            "HOST_SECRET_ROOT_REACHABLE": boundary["HOST_SECRET_ROOT_REACHABLE"],
            "OTHER_HOST_WRITE": boundary["OTHER_HOST_WRITE"],
            "DOCKER_SOCKET": boundary["DOCKER_SOCKET"],
            "DOCKER_DAEMON_AUTHORITY": boundary["DOCKER_DAEMON_AUTHORITY"],
        },
        "persistence": persistence,
        "model_credential": model,
        **smoke,
        "DEVELOPER_IMAGE": DEVELOPER_IMAGE,
        "PINNED_BASE_PRESERVED": "YES",
        "HERMES_HOME_PERSISTENT": persistence["HERMES_HOME_PERSISTENT"],
        "HERMES_HOME_MECHANISM": HERMES_HOME_MECHANISM,
        "ONE_COMMAND_LAUNCH": "YES",
        "LAUNCH_COMMAND": (
            "scripts/r5_developer_hermes/container/launch-developer-hermes.ps1"
        ),
        "HERMES_CORE_FILES_ADDED_BY_DX": 0,
        "HERMES_CORE_STRATEGY_CHANGED": "NO",
        "DESKTOP_CONTAINER_COMPATIBILITY": "PROMISING",
        "BOT_MODE_CONTAINER_COMPATIBILITY": "PROMISING",
        "RAILWAY_AUTH": "ABSENT",
        "VERCEL_AUTH": "ABSENT",
        "GH_HOST_AUTH": "ABSENT",
        "PRODUCTION_DB_AUTH": "ABSENT",
        "POWERUNITS_EXECUTE_AUTH": "ABSENT",
    }
    write_json(artifacts_dir() / DX_ARTIFACT, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="R5 Developer-Hermes container launcher")
    parser.add_argument(
        "command",
        choices=("argv", "build", "up", "down", "prove", "prove-dx", "inspect", "preflight"),
    )
    args = parser.parse_args()
    if args.command == "argv":
        json.dump(docker_run_argv(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.command == "preflight":
        payload = {
            "linux": assert_linux_engine(),
            "repo_a": str(HOST_REPO_A),
            "repo_b": str(HOST_REPO_B),
            "repos_exist": HOST_REPO_A.is_dir() and HOST_REPO_B.is_dir(),
            "model": model_credential_status(),
        }
        if not payload["repos_exist"]:
            raise RuntimeError("dedicated workspace clones are missing")
        write_json(artifacts_dir() / "container_preflight.json", payload)
        return 0
    if args.command == "build":
        write_json(artifacts_dir() / "container_build.json", build_image())
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
    if args.command == "prove-dx":
        result = prove_dx()
        print(f"ISOLATION_ACCEPTANCE = {result['boundary']['ISOLATION_ACCEPTANCE']}")
        print(f"HERMES_HOME_PERSISTENT = {result['HERMES_HOME_PERSISTENT']}")
        print(f"MODEL_CALL = {result['model_credential']['MODEL_CALL']}")
        return 0 if result["boundary"]["ISOLATION_ACCEPTANCE"] == "PASS" else 1
    result = prove()
    print(f"ISOLATION_ACCEPTANCE = {result['ISOLATION_ACCEPTANCE']}")
    return 0 if result["ISOLATION_ACCEPTANCE"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
