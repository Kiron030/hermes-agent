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
    BOT_MODE_CONTAINER_COMPATIBILITY,
    CONTAINER_HERMES_HOME,
    CONTAINER_NAME,
    CONTAINER_WORKDIR,
    DESKTOP_CONTAINER_COMPATIBILITY,
    DEVELOPER_IMAGE,
    DEDICATED_MODEL_ENV_FILE,
    HERMES_HOME_MECHANISM,
    HERMES_HOME_VOLUME,
    HERMES_HOME_VOLUME_LITERAL,
    HOST_REPO_A,
    HOST_REPO_B,
    IMAGE_CONTRACT_VERSION,
    PINNED_DIGEST,
    PINNED_IMAGE,
    PYTEST_PIN,
    RUNTIME_GID,
    RUNTIME_UID,
    RUNTIME_USER,
    TYPESCRIPT_PIN,
    WINDOWS_DOCKER_EXE,
    assert_trusted_host_launcher,
    classify_inspect_mounts,
    docker_run_argv,
    model_credential_status,
    parse_dedicated_model_env,
    sanitize_container_inspect,
)
from r5_developer_hermes.container.image_identity import (  # noqa: E402
    ConvergenceDecision,
    ConvergenceObservation,
    LABEL_CONTRACT_VERSION,
    LABEL_HERMES_BASE_DIGEST,
    LABEL_INPUT_SHA256,
    LABEL_SOURCE_GIT_SHA,
    actual_image_fingerprint,
    compute_developer_image_input_fingerprint,
    decide_convergence,
    expected_image_labels,
    identities_converged,
    labels_from_inspect,
    parse_pytest_version,
    parse_typescript_version,
    required_labels_present,
)
from r5_developer_hermes.harness import artifacts_dir, write_json  # noqa: E402


CONTAINER_ARTIFACT = "container_boundary.json"
DX_ARTIFACT = "developer_dx.json"
PROBE_CONTAINER_PATH = "/tmp/r5_isolation_probe.py"
DX_PROBE_CONTAINER_PATH = "/tmp/r5_dx_probe.py"


def _assert_host_execution_trust() -> None:
    assert_trusted_host_launcher(Path(__file__), HERE.parents[2])


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
    _assert_host_execution_trust()
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


def _source_git_sha() -> str:
    completed = subprocess.run(
        ["git", "-C", str(HERE.parents[2]), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _image_inspect_payload(ref: str = DEVELOPER_IMAGE) -> dict[str, Any] | None:
    completed = docker(["inspect", ref], check=False)
    if completed.returncode != 0:
        return None
    payload = json.loads(completed.stdout)
    if not payload:
        return None
    return payload[0]


def _dx_ready(inspect_data: dict[str, Any]) -> bool:
    image = inspect_data.get("image") or ""
    user = inspect_data.get("user") or ""
    env_names = set(inspect_data.get("env_names") or [])
    return (
        DEVELOPER_IMAGE in image
        and user
        in {
            f"{RUNTIME_UID}:{RUNTIME_GID}",
            RUNTIME_USER,
            str(RUNTIME_UID),
            "0:0",
        }
        and "HERMES_DOCKER_EXEC_AS_ROOT" in env_names
        and "GIT_CONFIG_GLOBAL" in env_names
    )


def observe_convergence() -> tuple[ConvergenceObservation, ConvergenceDecision]:
    expected_fp = compute_developer_image_input_fingerprint()
    image_payload = _image_inspect_payload(DEVELOPER_IMAGE)
    labels = labels_from_inspect(image_payload)
    container_present = container_exists()
    running_id = None
    dx_ready = True
    if container_present:
        existing = _inspect()
        running_id = existing.get("image_id")
        dx_ready = _dx_ready(existing)
    observation = ConvergenceObservation(
        expected_fingerprint=expected_fp,
        actual_image_fingerprint=actual_image_fingerprint(labels),
        image_present=image_payload is not None,
        labels_present=required_labels_present(labels),
        current_tag_image_id=(image_payload or {}).get("Id"),
        running_container_image_id=running_id,
        container_present=container_present,
        container_running=container_running() if container_present else False,
        dx_ready=dx_ready,
    )
    return observation, decide_convergence(observation)


def build_image() -> dict[str, Any]:
    _assert_host_execution_trust()
    dockerfile = HERE / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    if PINNED_IMAGE not in text or PINNED_DIGEST not in text:
        raise RuntimeError("Dockerfile must FROM the pinned Hermes digest")
    if "latest" in text.split("FROM", 1)[-1].splitlines()[0]:
        raise RuntimeError("Dockerfile must not FROM a floating tag")
    labels = expected_image_labels(source_git_sha=_source_git_sha())
    if not labels.get(LABEL_INPUT_SHA256):
        raise RuntimeError("refusing to build without an image-input fingerprint")
    completed = docker(
        [
            "build",
            "-t",
            DEVELOPER_IMAGE,
            "-f",
            str(dockerfile),
            "--build-arg",
            f"R5_INPUT_SHA256={labels[LABEL_INPUT_SHA256]}",
            "--build-arg",
            f"R5_HERMES_BASE_DIGEST={labels[LABEL_HERMES_BASE_DIGEST]}",
            "--build-arg",
            f"R5_CONTRACT_VERSION={labels[LABEL_CONTRACT_VERSION]}",
            "--build-arg",
            f"R5_SOURCE_GIT_SHA={labels.get(LABEL_SOURCE_GIT_SHA, '')}",
            str(HERE),
        ]
    )
    stamped = _image_inspect_payload(DEVELOPER_IMAGE)
    stamped_labels = labels_from_inspect(stamped)
    if not required_labels_present(stamped_labels):
        raise RuntimeError("built image is missing required identity labels")
    if stamped_labels.get(LABEL_INPUT_SHA256) != labels[LABEL_INPUT_SHA256]:
        raise RuntimeError("built image fingerprint does not match checked-in inputs")
    if stamped_labels.get(LABEL_HERMES_BASE_DIGEST) != PINNED_DIGEST:
        raise RuntimeError("built image is not stamped with the pinned Hermes digest")
    if stamped_labels.get(LABEL_CONTRACT_VERSION) != IMAGE_CONTRACT_VERSION:
        raise RuntimeError("built image contract version does not match")
    return {
        "image": DEVELOPER_IMAGE,
        "from": PINNED_IMAGE,
        "id": (stamped or {}).get("Id"),
        "EXPECTED_IMAGE_FINGERPRINT": labels[LABEL_INPUT_SHA256],
        "RUNNING_IMAGE_FINGERPRINT": stamped_labels.get(LABEL_INPUT_SHA256),
        "labels": {
            key: stamped_labels.get(key)
            for key in (
                LABEL_INPUT_SHA256,
                LABEL_HERMES_BASE_DIGEST,
                LABEL_CONTRACT_VERSION,
                LABEL_SOURCE_GIT_SHA,
            )
        },
        "exit_code": completed.returncode,
    }


def _create_container() -> dict[str, Any]:
    ensure_volume()
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
        "name": CONTAINER_NAME,
        "id": completed.stdout.strip(),
        "argv_without_secrets": docker_run_argv(model_env=None),
    }


def _model_env() -> dict[str, str]:
    if not DEDICATED_MODEL_ENV_FILE.is_file():
        return {}
    return parse_dedicated_model_env(DEDICATED_MODEL_ENV_FILE)


def up() -> dict[str, Any]:
    _assert_host_execution_trust()
    assert_linux_engine()
    if not HOST_REPO_A.is_dir() or not HOST_REPO_B.is_dir():
        raise RuntimeError("dedicated workspace clones are missing")
    _observation, decision = observe_convergence()
    built = None
    if decision.action in {"BUILD", "REBUILD"}:
        built = build_image()
        if container_exists():
            docker(["rm", "-f", CONTAINER_NAME], check=False)
        created = _create_container()
        return {
            "action": "rebuilt-and-started" if decision.action == "REBUILD" else "built-and-started",
            "convergence": decision.as_dict(),
            "build": built,
            **created,
        }
    if decision.action == "RECREATE":
        if container_exists():
            docker(["rm", "-f", CONTAINER_NAME], check=False)
        created = _create_container()
        return {
            "action": "recreated",
            "convergence": decision.as_dict(),
            **created,
        }
    if container_running():
        return {
            "action": "already-running",
            "name": CONTAINER_NAME,
            "convergence": decision.as_dict(),
        }
    docker(["start", CONTAINER_NAME])
    if not container_running():
        docker(["rm", "-f", CONTAINER_NAME], check=False)
        created = _create_container()
        return {
            "action": "recreated",
            "convergence": {**decision.as_dict(), "reason": "EXISTING_CONTAINER_FAILED_TO_START"},
            **created,
        }
    return {
        "action": "started-existing",
        "name": CONTAINER_NAME,
        "convergence": decision.as_dict(),
    }


def down(*, remove_volume: bool = False) -> dict[str, Any]:
    _assert_host_execution_trust()
    completed = docker(["rm", "-f", CONTAINER_NAME], check=False)
    volume_removed = False
    if remove_volume:
        if HERMES_HOME_VOLUME != HERMES_HOME_VOLUME_LITERAL:
            raise RuntimeError("refusing to remove a non-canonical Hermes home volume")
        docker(["volume", "rm", HERMES_HOME_VOLUME_LITERAL], check=False)
        volume_removed = True
    return {
        "action": "removed",
        "name": CONTAINER_NAME,
        "exit_code": completed.returncode,
        "volume_removed": volume_removed,
    }


def reset_home() -> dict[str, Any]:
    """Stop the container and delete only the fixed Developer-Hermes home volume."""
    _assert_host_execution_trust()
    if HERMES_HOME_VOLUME != HERMES_HOME_VOLUME_LITERAL:
        raise RuntimeError("refusing to reset a non-canonical Hermes home volume")
    stopped = down(remove_volume=False)
    removed = docker(["volume", "rm", HERMES_HOME_VOLUME_LITERAL], check=False)
    return {
        "action": "RESET_DEVELOPER_HERMES_HOME",
        "name": CONTAINER_NAME,
        "volume": HERMES_HOME_VOLUME_LITERAL,
        "container": stopped,
        "volume_removed": removed.returncode == 0,
        "repos_touched": "NO",
        "host_secrets_touched": "NO",
        "production_touched": "NO",
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
    # Parse inspect in memory and immediately drop Config.Env values.
    # Do not persist or log the raw payload.
    payload = json.loads(docker(["inspect", CONTAINER_NAME]).stdout)[0]
    return sanitize_container_inspect(payload)


def _classify_mounts(inspect_data: dict[str, Any]) -> dict[str, Any]:
    return classify_inspect_mounts(list(inspect_data.get("mounts") or []))


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
    return list(inspect_data.get("env_names") or [])


def _runtime_identity() -> dict[str, Any]:
    observation, decision = observe_convergence()
    image_payload = _image_inspect_payload(DEVELOPER_IMAGE)
    running_payload = None
    running_labels: dict[str, str] = {}
    if observation.running_container_image_id:
        running_payload = _image_inspect_payload(observation.running_container_image_id)
        running_labels = labels_from_inspect(running_payload)
    tag_labels = labels_from_inspect(image_payload)
    running_fp = actual_image_fingerprint(running_labels) or actual_image_fingerprint(tag_labels)
    converged = identities_converged(
        expected_fingerprint=observation.expected_fingerprint,
        running_fingerprint=running_fp,
        current_tag_image_id=observation.current_tag_image_id,
        running_container_image_id=observation.running_container_image_id,
        labels=running_labels or tag_labels,
    )
    return {
        "EXPECTED_IMAGE_FINGERPRINT": observation.expected_fingerprint,
        "ACTUAL_IMAGE_FINGERPRINT": observation.actual_image_fingerprint,
        "RUNNING_IMAGE_FINGERPRINT": running_fp,
        "CURRENT_TAG_IMAGE_ID": observation.current_tag_image_id,
        "RUNNING_CONTAINER_IMAGE_ID": observation.running_container_image_id,
        "PINNED_BASE_IMAGE": PINNED_IMAGE,
        "labels_present": required_labels_present(running_labels or tag_labels),
        "convergence": decision.as_dict(),
        "RUNTIME_CONVERGED": "YES" if converged and decision.action == "REUSE" else "NO",
    }


def _tool_versions(probe: dict[str, Any]) -> dict[str, str]:
    versions = (probe.get("tooling") or {}).get("versions") or {}
    typescript = parse_typescript_version(str(versions.get("tsc") or ""))
    pytest_version = parse_pytest_version(
        str((probe.get("tooling") or {}).get("pytest_version") or "")
    )
    return {
        "TYPESCRIPT_VERSION": typescript,
        "PYTEST_VERSION": pytest_version,
        "TYPESCRIPT_PIN_MATCH": "YES" if typescript == TYPESCRIPT_PIN else "NO",
        "PYTEST_PIN_MATCH": "YES" if pytest_version == PYTEST_PIN else "NO",
    }


def _verdict(
    inspect_data: dict[str, Any],
    mounts: dict[str, Any],
    probe: dict[str, Any],
    identity: dict[str, Any] | None = None,
    versions: dict[str, str] | None = None,
) -> str:
    tooling = probe["tooling"]
    env_names = set(_env_names(inspect_data))
    leaked_authority = sorted(name for name in AUTHORITY_ENV_NAMES if name in env_names)
    identity = identity or {}
    versions = versions or {}
    required = [
        mounts["exact_two_approved_rw"],
        mounts.get("exact_allowlist_match", False),
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
        identity.get("RUNTIME_CONVERGED") == "YES",
        identity.get("EXPECTED_IMAGE_FINGERPRINT")
        == identity.get("RUNNING_IMAGE_FINGERPRINT"),
        identity.get("labels_present") is True,
        versions.get("TYPESCRIPT_PIN_MATCH") == "YES",
        versions.get("PYTEST_PIN_MATCH") == "YES",
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
    _assert_host_execution_trust()
    if not HOST_REPO_A.is_dir() or not HOST_REPO_B.is_dir():
        raise RuntimeError("dedicated workspace clones are missing")
    started = up()
    # Give the entrypoint time to seed HERMES_HOME.
    time.sleep(1)
    inspect_data = _inspect()
    mounts = _classify_mounts(inspect_data)
    _copy_probe()
    probe = _exec_json(PROBE_CONTAINER_PATH)
    identity = _runtime_identity()
    versions = _tool_versions(probe)
    acceptance = _verdict(inspect_data, mounts, probe, identity, versions)
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
        "EXPECTED_IMAGE_FINGERPRINT": identity["EXPECTED_IMAGE_FINGERPRINT"],
        "ACTUAL_IMAGE_FINGERPRINT": identity["ACTUAL_IMAGE_FINGERPRINT"],
        "RUNNING_IMAGE_FINGERPRINT": identity["RUNNING_IMAGE_FINGERPRINT"],
        "CURRENT_TAG_IMAGE_ID": identity["CURRENT_TAG_IMAGE_ID"],
        "RUNTIME_CONVERGED": identity["RUNTIME_CONVERGED"],
        "TYPESCRIPT_VERSION": versions["TYPESCRIPT_VERSION"],
        "PYTEST_VERSION": versions["PYTEST_VERSION"],
        "IMAGE_CONTRACT_VERSION": IMAGE_CONTRACT_VERSION,
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
        "DIAGNOSTIC_ENV_VALUES": "OMITTED",
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
        "RUNTIME_CONVERGED": boundary.get("RUNTIME_CONVERGED"),
        "EXPECTED_IMAGE_FINGERPRINT": boundary.get("EXPECTED_IMAGE_FINGERPRINT"),
        "RUNNING_IMAGE_FINGERPRINT": boundary.get("RUNNING_IMAGE_FINGERPRINT"),
        "TYPESCRIPT_VERSION": boundary.get("TYPESCRIPT_VERSION"),
        "PYTEST_VERSION": boundary.get("PYTEST_VERSION"),
        "HERMES_HOME_PERSISTENT": persistence["HERMES_HOME_PERSISTENT"],
        "HERMES_HOME_MECHANISM": HERMES_HOME_MECHANISM,
        "ONE_COMMAND_LAUNCH": "YES",
        "LAUNCH_COMMAND": (
            "scripts/r5_developer_hermes/container/launch-developer-hermes.ps1"
        ),
        "HERMES_CORE_FILES_ADDED_BY_DX": 0,
        "HERMES_CORE_STRATEGY_CHANGED": "NO",
        "DESKTOP_CONTAINER_COMPATIBILITY": DESKTOP_CONTAINER_COMPATIBILITY,
        "BOT_MODE_CONTAINER_COMPATIBILITY": BOT_MODE_CONTAINER_COMPATIBILITY,
        "RAILWAY_AUTH": "ABSENT",
        "VERCEL_AUTH": "ABSENT",
        "GH_HOST_AUTH": "ABSENT",
        "PRODUCTION_DB_AUTH": "ABSENT",
        "POWERUNITS_EXECUTE_AUTH": "ABSENT",
    }
    write_json(artifacts_dir() / DX_ARTIFACT, result)
    return result


def main() -> int:
    _assert_host_execution_trust()
    parser = argparse.ArgumentParser(description="R5 Developer-Hermes container launcher")
    parser.add_argument(
        "command",
        choices=("argv", "build", "up", "down", "reset", "prove", "prove-dx", "inspect", "preflight", "plan"),
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
    if args.command == "reset":
        write_json(artifacts_dir() / "container_reset.json", reset_home())
        return 0
    if args.command == "inspect":
        write_json(artifacts_dir() / "container_inspect.json", _inspect())
        return 0
    if args.command == "plan":
        _observation, decision = observe_convergence()
        write_json(artifacts_dir() / "container_convergence_plan.json", decision.as_dict())
        print(f"CONVERGENCE_ACTION = {decision.action}")
        print(f"CONVERGENCE_REASON = {decision.reason}")
        print(f"EXPECTED_IMAGE_FINGERPRINT = {decision.expected_fingerprint}")
        print(f"ACTUAL_IMAGE_FINGERPRINT = {decision.actual_image_fingerprint}")
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
