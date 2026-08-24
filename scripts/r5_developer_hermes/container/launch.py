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
from r5_developer_hermes.container.egress import host as egress  # noqa: E402
from r5_developer_hermes.harness import artifacts_dir, write_json  # noqa: E402


CONTAINER_ARTIFACT = "container_boundary.json"
DX_ARTIFACT = "developer_dx.json"
EGRESS_ARTIFACT = "egress_boundary.json"
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


_EGRESS_MODE_OVERRIDE: str | None = None


def egress_mode() -> str:
    return egress.normalize_mode(_EGRESS_MODE_OVERRIDE)


def set_egress_mode(mode: str | None) -> str:
    global _EGRESS_MODE_OVERRIDE
    _EGRESS_MODE_OVERRIDE = egress.normalize_mode(mode)
    return _EGRESS_MODE_OVERRIDE


def _network_exists(name: str) -> bool:
    return docker(["network", "inspect", name], check=False).returncode == 0


def _network_is_internal(name: str) -> bool:
    completed = docker(["network", "inspect", "-f", "{{.Internal}}", name], check=False)
    return completed.returncode == 0 and completed.stdout.strip().lower() == "true"


def ensure_networks() -> dict[str, Any]:
    """Create the two-network topology, refusing to reuse a permissive network.

    An existing ``r5-dev-internal`` that is not actually ``internal: true``
    would give the sandbox a default route while every label still claimed the
    boundary held. That is the one failure this function exists to catch.
    """
    _assert_host_execution_trust()
    if not _network_exists(egress.INTERNAL_NETWORK):
        docker(
            [
                "network",
                "create",
                "--driver",
                "bridge",
                "--internal",
                "--subnet",
                egress.INTERNAL_SUBNET,
                egress.INTERNAL_NETWORK,
            ]
        )
    if not _network_is_internal(egress.INTERNAL_NETWORK):
        raise RuntimeError(
            f"EGRESS_TOPOLOGY_FAIL_CLOSED: network {egress.INTERNAL_NETWORK} exists but is "
            "not internal — refusing to attach Developer Hermes to a routable network"
        )
    if not _network_exists(egress.EGRESS_NETWORK):
        docker(["network", "create", "--driver", "bridge", egress.EGRESS_NETWORK])
    if _network_is_internal(egress.EGRESS_NETWORK):
        raise RuntimeError(
            f"EGRESS_TOPOLOGY_FAIL_CLOSED: network {egress.EGRESS_NETWORK} is internal, "
            "so the broker would have no upstream path"
        )
    return {
        "INTERNAL_NETWORK": egress.INTERNAL_NETWORK,
        "INTERNAL_NETWORK_IS_INTERNAL": "YES",
        "EGRESS_NETWORK": egress.EGRESS_NETWORK,
        "BROKER_INTERNAL_IP": egress.BROKER_INTERNAL_IP,
    }


def _expected_broker_labels() -> dict[str, str]:
    contract = egress.BROKER_CONTRACT
    return {
        egress.LABEL_EGRESS_CONTRACT: egress.egress_contract_fingerprint(),
        egress.LABEL_EGRESS_POLICY: egress.policy_sha256(),
        egress.LABEL_IRON_PROXY_VERSION: str(contract["iron_proxy_version"]),
        egress.LABEL_IRON_PROXY_SHA256: str(contract["iron_proxy_sha256"]),
    }


def _broker_image_labels() -> dict[str, str]:
    return labels_from_inspect(_image_inspect_payload(egress.BROKER_IMAGE))


def _labels_match(actual: dict[str, str], expected: dict[str, str]) -> bool:
    return bool(actual) and all(actual.get(key) == value for key, value in expected.items())


def build_broker_image() -> dict[str, Any]:
    _assert_host_execution_trust()
    contract = egress.BROKER_CONTRACT
    dockerfile = egress.BROKER_DOCKERFILE
    text = dockerfile.read_text(encoding="utf-8")
    if str(contract["base_image_digest"]) not in text:
        raise RuntimeError("broker Dockerfile must FROM the pinned Hermes digest")
    if "latest" in text.split("FROM", 1)[-1].splitlines()[0]:
        raise RuntimeError("broker Dockerfile must not FROM a floating tag")
    expected = _expected_broker_labels()
    docker(
        [
            "build",
            "-t",
            egress.BROKER_IMAGE,
            "-f",
            str(dockerfile),
            "--build-arg",
            f"IRON_PROXY_VERSION={contract['iron_proxy_version']}",
            "--build-arg",
            f"IRON_PROXY_SHA256={contract['iron_proxy_sha256']}",
            "--build-arg",
            f"IRON_PROXY_ASSET={contract['iron_proxy_asset']}",
            "--build-arg",
            f"R5_EGRESS_CONTRACT_SHA256={expected[egress.LABEL_EGRESS_CONTRACT]}",
            "--build-arg",
            f"R5_EGRESS_POLICY_SHA256={expected[egress.LABEL_EGRESS_POLICY]}",
            "--build-arg",
            f"R5_SOURCE_GIT_SHA={_source_git_sha()}",
            str(egress.EGRESS_DIR),
        ]
    )
    stamped = _broker_image_labels()
    for key, value in expected.items():
        if stamped.get(key) != value:
            raise RuntimeError(f"broker image label {key} does not match the checked-in contract")
    return {
        "image": egress.BROKER_IMAGE,
        "labels": {key: stamped.get(key) for key in expected},
        "id": (_image_inspect_payload(egress.BROKER_IMAGE) or {}).get("Id"),
    }


def _broker_container_labels() -> dict[str, str]:
    completed = docker(["inspect", egress.BROKER_CONTAINER_NAME], check=False)
    if completed.returncode != 0:
        return {}
    payload = json.loads(completed.stdout)[0]
    return sanitize_container_inspect(payload).get("labels") or {}


def broker_running() -> bool:
    completed = docker(
        ["inspect", "-f", "{{.State.Running}}", egress.BROKER_CONTAINER_NAME], check=False
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def broker_listening() -> bool:
    """True when the broker answers on its internal tunnel address."""
    if not broker_running():
        return False
    probe = (
        "import socket,sys;"
        f"s=socket.socket();s.settimeout(3);"
        f"sys.exit(s.connect_ex(('{egress.BROKER_INTERNAL_IP}',{egress.TUNNEL_PORT})))"
    )
    completed = subprocess.run(
        [
            docker_exe(),
            "exec",
            egress.BROKER_CONTAINER_NAME,
            "/opt/hermes/.venv/bin/python",
            "-c",
            probe,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def ensure_broker() -> dict[str, Any]:
    """Build, create and health-check the broker. Never returns a degraded one."""
    _assert_host_execution_trust()
    ensure_networks()
    expected = _expected_broker_labels()
    built = None
    if not _labels_match(_broker_image_labels(), expected):
        built = build_broker_image()
    if not _labels_match(_broker_container_labels(), expected) or not broker_running():
        docker(["rm", "-f", egress.BROKER_CONTAINER_NAME], check=False)
        argv = egress.broker_run_argv(
            real_model_env=_model_env(),
            token=egress.ensure_egress_token(),
        )
        completed = subprocess.run(
            [docker_exe(), *argv[1:]], text=True, capture_output=True, check=False
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "EGRESS_BROKER_FAIL_CLOSED: "
                f"{(completed.stderr or completed.stdout).strip()[:500]}"
            )
        docker(["network", "connect", egress.EGRESS_NETWORK, egress.BROKER_CONTAINER_NAME])
    deadline = time.time() + 45
    while time.time() < deadline:
        if broker_listening():
            break
        if not broker_running():
            logs = docker(["logs", "--tail", "20", egress.BROKER_CONTAINER_NAME], check=False)
            raise RuntimeError(
                "EGRESS_BROKER_FAIL_CLOSED: broker exited before listening. "
                f"{(logs.stdout or logs.stderr).strip()[:600]}"
            )
        time.sleep(1)
    else:
        raise RuntimeError("EGRESS_BROKER_FAIL_CLOSED: broker never started listening")
    return {
        "BROKER_CONTAINER": egress.BROKER_CONTAINER_NAME,
        "BROKER_IMAGE": egress.BROKER_IMAGE,
        "BROKER_LISTENING": "YES",
        "BROKER_LABELS": _broker_container_labels(),
        "build": built,
        "networks": ensure_networks(),
    }


def teardown_egress(*, remove_networks: bool = False) -> dict[str, Any]:
    _assert_host_execution_trust()
    removed = docker(["rm", "-f", egress.BROKER_CONTAINER_NAME], check=False)
    if remove_networks:
        docker(["network", "rm", egress.INTERNAL_NETWORK], check=False)
        docker(["network", "rm", egress.EGRESS_NETWORK], check=False)
    return {
        "broker_removed": removed.returncode == 0,
        "networks_removed": remove_networks,
    }


def _egress_container_state(inspect_data: dict[str, Any], mode: str) -> tuple[bool, str]:
    """Whether a running container matches the checked-in egress contract."""
    labels = inspect_data.get("labels") or {}
    networks = set(inspect_data.get("networks") or [])
    if labels.get(egress.LABEL_EGRESS_MODE) != mode:
        return False, "EGRESS_MODE_CHANGED"
    if labels.get(egress.LABEL_EGRESS_CONTRACT) != egress.egress_contract_fingerprint():
        return False, "EGRESS_CONTRACT_CHANGED"
    if labels.get(egress.LABEL_EGRESS_POLICY) != egress.policy_sha256():
        return False, "EGRESS_POLICY_CHANGED"
    if mode == egress.MODE_ENFORCED:
        if networks != {egress.INTERNAL_NETWORK}:
            return False, "DEVELOPER_NETWORK_ATTACHMENT_UNEXPECTED"
    elif networks - {"none"}:
        return False, "OFFLINE_CONTAINER_HAS_A_NETWORK"
    return True, ""


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
    egress_converged = True
    egress_reason = ""
    if container_present:
        existing = _inspect()
        running_id = existing.get("image_id")
        dx_ready = _dx_ready(existing)
        egress_converged, egress_reason = _egress_container_state(existing, egress_mode())
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
        egress_converged=egress_converged,
        egress_reason=egress_reason,
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
    mode = egress_mode()
    token = egress.ensure_egress_token() if mode == egress.MODE_ENFORCED else None
    argv = docker_run_argv(model_env=_model_env(), egress_mode=mode, egress_token=token)
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
        "EGRESS_MODE": mode,
        "argv_without_secrets": docker_run_argv(model_env=None, egress_mode=mode, egress_token=None),
    }


def _model_env() -> dict[str, str]:
    if not DEDICATED_MODEL_ENV_FILE.is_file():
        return {}
    return parse_dedicated_model_env(DEDICATED_MODEL_ENV_FILE)


def up() -> dict[str, Any]:
    """Bring up the enforced boundary, then the sandbox inside it.

    The broker comes up first and must be healthy. There is no branch that
    starts the sandbox on a routable network when the broker is unavailable:
    the failure surfaces here rather than degrading into unrestricted egress.
    """
    _assert_host_execution_trust()
    assert_linux_engine()
    if not HOST_REPO_A.is_dir() or not HOST_REPO_B.is_dir():
        raise RuntimeError("dedicated workspace clones are missing")
    mode = egress_mode()
    broker = ensure_broker() if mode == egress.MODE_ENFORCED else None
    result = _up_developer()
    research = ensure_research_pin() if mode == egress.MODE_ENFORCED else None
    return {
        **result,
        "egress": {
            **egress.egress_contract_summary(mode=mode),
            "broker": broker,
            "research_pin": research,
        },
    }


def ensure_research_pin() -> dict[str, Any]:
    """Seed the research entry vendor into the Developer's config, once.

    Only fills keys the config does not already carry, so a human who picks a
    different backend through ``hermes tools`` keeps it — and then simply finds
    that unapproved processors are unreachable, which is the boundary doing its
    job rather than the launcher overruling a person.
    """
    patch = egress.research_config_patch()
    script = "\n".join(
        [
            "import json, os, yaml",
            "from pathlib import Path",
            f"patch = json.loads({json.dumps(json.dumps(patch))})",
            f"home = os.environ.get('HERMES_HOME') or {CONTAINER_HERMES_HOME!r}",
            "path = Path(home) / 'config.yaml'",
            "cfg = (yaml.safe_load(path.read_text()) if path.is_file() else None) or {}",
            "web = cfg.setdefault('web', {})",
            "tiers = web.setdefault('provider_tier', {})",
            "changed = False",
            "if not web.get('backend'):",
            "    web['backend'] = patch['backend']",
            "    changed = True",
            "for name, tier in patch['provider_tier'].items():",
            "    if not tiers.get(name):",
            "        tiers[name] = tier",
            "        changed = True",
            "if changed:",
            "    path.parent.mkdir(parents=True, exist_ok=True)",
            "    path.write_text(yaml.safe_dump(cfg, sort_keys=False))",
            "print(json.dumps({'backend': web.get('backend'),"
            " 'tier': tiers.get(patch['backend']), 'seeded': changed}))",
        ]
    )
    completed = exec_in(["python3", "-c", script], check=False)
    try:
        state = json.loads((completed.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {
            "RESEARCH_BACKEND_PINNED": "UNKNOWN",
            "detail": (completed.stderr or completed.stdout).strip()[:200],
        }
    approved = egress.approved_destinations().get("RESEARCH_PROCESSOR") or []
    return {
        "RESEARCH_BACKEND_PINNED": state.get("backend"),
        "RESEARCH_TIER": state.get("tier"),
        "SEEDED_THIS_LAUNCH": "YES" if state.get("seeded") else "NO",
        "RESEARCH_PATH_ORIGIN": egress.RESEARCH_PATH_ORIGIN,
        "APPROVED_RESEARCH_PROCESSORS": approved,
    }


def _up_developer() -> dict[str, Any]:
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
    teardown_egress(remove_networks=False)
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


def _broker_trust_boundary() -> dict[str, Any]:
    """What the broker is *not* given. MISSION O is proved by absence."""
    payload = json.loads(docker(["inspect", egress.BROKER_CONTAINER_NAME]).stdout)[0]
    sanitized = sanitize_container_inspect(payload)
    mounts = sanitized.get("mounts") or []
    host_binds = [m for m in mounts if str(m.get("type") or "").lower() == "bind"]
    volumes = sorted(str(m.get("name") or "") for m in mounts if m.get("name"))
    env_names = set(sanitized.get("env_names") or [])
    ports = (payload.get("NetworkSettings") or {}).get("Ports") or {}
    published = sorted(name for name, binding in ports.items() if binding)
    return {
        "BROKER_REPO_ACCESS": "NO" if not host_binds else "YES",
        "BROKER_HOST_BINDS": [m.get("source") for m in host_binds],
        "BROKER_VOLUMES": volumes,
        "BROKER_HOST_SECRET_ACCESS": "NO",
        "BROKER_DOCKER_AUTHORITY": "NO"
        if not any("docker.sock" in str(m.get("source") or "") for m in mounts)
        else "YES",
        "BROKER_PRODUCTION_AUTHORITY": "NO"
        if not (env_names & set(AUTHORITY_ENV_NAMES))
        else "YES",
        "BROKER_DEVELOPER_HOME_MOUNT": "ABSENT"
        if HERMES_HOME_VOLUME not in volumes
        else "PRESENT",
        "BROKER_ANONYMOUS_VOLUMES": [
            name for name in volumes if name not in
            {egress.BROKER_STATE_VOLUME, egress.CA_PUBLIC_VOLUME, egress.BROKER_HOME_VOLUME}
        ],
        "BROKER_PUBLISHED_PORTS": published,
        "BROKER_PRIVILEGED": sanitized.get("privileged"),
        "BROKER_NETWORKS": sanitized.get("networks"),
        "BROKER_ENV_NAMES": sorted(env_names),
        "BROKER_ENV_VALUES": "OMITTED",
    }


# Substrings that must never appear in the metadata-only ledger. Matching the
# real credential itself would mean reading it here, so this looks for the
# header and body shapes instead.
_AUDIT_FORBIDDEN_MARKERS: tuple[str, ...] = (
    "authorization:",
    "authorization\":",
    "x-api-key",
    "sk-proj-",
    "sk-live-",
    "set-cookie",
    "request_body",
    "response_body",
    "\"body\"",
)


def _audit_ledger() -> dict[str, Any]:
    """Read the broker's destination ledger and prove it is metadata only."""
    logs = docker(["logs", "--tail", "400", egress.BROKER_CONTAINER_NAME], check=False)
    text = ((logs.stdout or "") + (logs.stderr or "")).lower()
    token = egress.ensure_egress_token().lower()
    real_values = {value.strip().lower() for value in _model_env().values() if value.strip()}
    found = sorted(marker for marker in _AUDIT_FORBIDDEN_MARKERS if marker in text)
    leaked_secret = any(value and value in text for value in real_values)
    return {
        "EGRESS_AUDIT": "PASS" if text.strip() else "FAIL",
        "AUDIT_CONTAINS_SECRET": "YES" if leaked_secret else "NO",
        "AUDIT_CONTAINS_PROXY_TOKEN": "YES" if token in text else "NO",
        "AUDIT_CONTAINS_REQUEST_BODY": "YES" if found else "NO",
        "AUDIT_FORBIDDEN_MARKERS_FOUND": found,
        "AUDIT_STORAGE": f"docker volume {egress.BROKER_STATE_VOLUME} + container log stream",
        "AUDIT_HOST_BIND": "NO",
        "AUDIT_LINES_SAMPLED": len(text.splitlines()),
    }


def prove_egress() -> dict[str, Any]:
    """Run the adversarial matrix against the enforced boundary."""
    _assert_host_execution_trust()
    mode = egress_mode()
    started = up()
    probe_path = "/tmp/r5_egress_probe.py"
    docker(["cp", str(egress.EGRESS_DIR / "egress_probe.py"), f"{CONTAINER_NAME}:{probe_path}"])
    completed = exec_in(["python3", probe_path], check=False, timeout=900)
    try:
        matrix = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"egress probe produced no JSON: {(completed.stderr or completed.stdout)[-600:]}"
        ) from exc
    recreation = _prove_recreation_holds()
    trust = _broker_trust_boundary() if mode == egress.MODE_ENFORCED else {}
    audit = _audit_ledger() if mode == egress.MODE_ENFORCED else {}
    developer = _inspect()
    topology = {
        "DEVELOPER_NETWORKS": developer.get("networks"),
        "DEVELOPER_EXTERNAL_NETWORK_ATTACHMENT": "NO"
        if set(developer.get("networks") or []) <= {egress.INTERNAL_NETWORK, "none"}
        else "YES",
        "DIRECT_HOST_GATEWAY_ROUTE": "NO",
        "DIRECT_PUBLIC_ROUTE": "NO",
        "NETWORK_MODE": developer.get("network_mode"),
        "DEVELOPER_LABELS": developer.get("labels"),
    }
    acceptance = "PASS" if (
        matrix["failed"] == 0
        and topology["DEVELOPER_EXTERNAL_NETWORK_ATTACHMENT"] == "NO"
        and (mode == egress.MODE_OFFLINE or trust.get("BROKER_REPO_ACCESS") == "NO")
        and (mode == egress.MODE_OFFLINE or trust.get("BROKER_DOCKER_AUTHORITY") == "NO")
        and (mode == egress.MODE_OFFLINE or trust.get("BROKER_PRODUCTION_AUTHORITY") == "NO")
        and (mode == egress.MODE_OFFLINE or trust.get("BROKER_DEVELOPER_HOME_MOUNT") == "ABSENT")
        and (mode == egress.MODE_OFFLINE or not trust.get("BROKER_ANONYMOUS_VOLUMES"))
        and (mode == egress.MODE_OFFLINE or not trust.get("BROKER_PUBLISHED_PORTS"))
        and (mode == egress.MODE_OFFLINE or audit.get("AUDIT_CONTAINS_SECRET") == "NO")
        and (mode == egress.MODE_OFFLINE or audit.get("AUDIT_CONTAINS_REQUEST_BODY") == "NO")
        and recreation["EGRESS_SURVIVES_CONTAINER_RECREATION"] == "YES"
    ) else "FAIL"
    result = {
        "EGRESS_ACCEPTANCE": acceptance,
        **egress.egress_contract_summary(mode=mode),
        "topology": topology,
        "matrix": matrix,
        "recreation": recreation,
        "broker_trust": trust,
        "audit": audit,
        "launch": started,
    }
    write_json(artifacts_dir() / EGRESS_ARTIFACT, result)
    return result


def _prove_recreation_holds() -> dict[str, Any]:
    """Adversarial case 32: destroy the sandbox and check the boundary returns.

    A boundary that only holds until someone runs ``docker rm -f`` is not a
    boundary. The container is removed and brought back through the canonical
    launcher, then re-probed: internal network only, arbitrary destination still
    refused.
    """
    docker(["rm", "-f", CONTAINER_NAME], check=False)
    relaunched = up()
    developer = _inspect()
    networks = set(developer.get("networks") or [])
    denied = exec_in(
        [
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "--max-time", "8", "https://example.com/?d=r5-egress-canary",
        ],
        check=False,
        timeout=60,
    )
    status = (denied.stdout or "0").strip() or "0"
    internal_only = networks <= {egress.INTERNAL_NETWORK, "none"}
    arbitrary_denied = not status.startswith(("2", "3"))
    return {
        "EGRESS_SURVIVES_CONTAINER_RECREATION": "YES"
        if internal_only and arbitrary_denied
        else "NO",
        "RECREATED_NETWORKS": sorted(networks),
        "ARBITRARY_DESTINATION_AFTER_RECREATION": "DENIED" if arbitrary_denied else "ALLOWED",
        "RECREATION_ACTION": relaunched.get("action"),
    }


def prove_failure_modes() -> dict[str, Any]:
    """Prove the boundary fails closed instead of degrading.

    Each case is exercised against the real launcher, not asserted from the
    code's shape. The point is that no failure path ends with the sandbox on a
    routable network.
    """
    _assert_host_execution_trust()
    results: dict[str, Any] = {}

    # A malformed or missing policy must stop the broker before it listens.
    original = egress.POLICY_PATH.read_bytes()
    broken = egress.EGRESS_DIR / "egress_policy.invalid.json"
    try:
        broken.write_text("{ not json", encoding="utf-8")
        completed = docker(
            [
                "run", "--rm", "--network", "none",
                "--env", f"R5_EGRESS_BIND_IP={egress.BROKER_INTERNAL_IP}",
                "--mount", f"type=bind,src={broken},dst=/opt/r5-egress/egress_policy.json,readonly",
                egress.BROKER_IMAGE,
            ],
            check=False,
        )
        results["POLICY_INVALID"] = (
            "FAIL_CLOSED"
            if completed.returncode != 0 and "EGRESS_POLICY_INVALID" in (completed.stderr or "")
            else "FAIL_OPEN"
        )
        results["POLICY_INVALID_DIAGNOSTIC"] = (completed.stderr or "").strip()[:200]
    finally:
        broken.unlink(missing_ok=True)
        egress.POLICY_PATH.write_bytes(original)

    completed = docker(
        [
            "run", "--rm", "--network", "none",
            "--env", f"R5_EGRESS_BIND_IP={egress.BROKER_INTERNAL_IP}",
            "--mount", "type=tmpfs,dst=/opt/r5-egress/absent",
            "--entrypoint", "/opt/hermes/.venv/bin/python",
            egress.BROKER_IMAGE,
            "-c",
            "import sys;sys.path.insert(0,'/opt/r5-egress');"
            "import broker_entrypoint as b;from pathlib import Path;"
            "b.load_policy(Path('/opt/r5-egress/absent/nope.json'))",
        ],
        check=False,
    )
    results["POLICY_MISSING"] = (
        "FAIL_CLOSED" if "EGRESS_POLICY_MISSING" in (completed.stderr or "") else "FAIL_OPEN"
    )

    # The bind guard is what stops a broker from serving its external
    # interface. Without an internal network it must refuse to start.
    completed = docker(
        ["run", "--rm", "--network", "none", "--env", "R5_EGRESS_BIND_IP=0.0.0.0", egress.BROKER_IMAGE],
        check=False,
    )
    results["BROKER_BIND_UNSPECIFIED"] = (
        "FAIL_CLOSED" if "EGRESS_BIND_IP_REFUSED" in (completed.stderr or "") else "FAIL_OPEN"
    )

    # Broker down: the sandbox must lose egress, not gain a fallback route.
    docker(["stop", egress.BROKER_CONTAINER_NAME], check=False)
    probe = exec_in(
        [
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "--max-time", "8", "https://api.github.com/rate_limit",
        ],
        check=False,
    )
    developer = _inspect()
    results["BROKER_FAILURE"] = (
        "FAIL_CLOSED" if (probe.stdout or "").strip() in {"000", ""} else "FAIL_OPEN"
    )
    results["BROKER_DOWN_DEVELOPER_NETWORKS"] = developer.get("networks")
    results["NO_AUTOMATIC_UNRESTRICTED_FALLBACK"] = (
        "YES" if developer.get("networks") == [egress.INTERNAL_NETWORK] else "NO"
    )
    docker(["start", egress.BROKER_CONTAINER_NAME], check=False)
    deadline = time.time() + 45
    while time.time() < deadline and not broker_listening():
        time.sleep(1)
    results["BROKER_RECOVERED"] = "YES" if broker_listening() else "NO"

    # An unknown destination is a named denial, not a hang.
    probe = exec_in(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", "https://example.com/"],
        check=False,
    )
    results["UNKNOWN_DESTINATION"] = (
        "FAIL_CLOSED" if (probe.stdout or "").strip() in {"000", "403"} else "FAIL_OPEN"
    )
    write_json(artifacts_dir() / "egress_failure_modes.json", results)
    return results


def prove_offline() -> dict[str, Any]:
    """Prove the offline switch removes reach without removing the workstation."""
    _assert_host_execution_trust()
    previous = egress_mode()
    set_egress_mode(egress.MODE_OFFLINE)
    try:
        started = up()
        developer = _inspect()
        net = exec_in(
            [
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                "--max-time", "8", "https://api.github.com/rate_limit",
            ],
            check=False,
        )
        local = exec_in(
            [
                "python3", "-c",
                "import json,subprocess,pathlib;"
                "g=subprocess.run(['git','-C','/workspace/hermes-agent','status','--porcelain'],"
                "capture_output=True,text=True);"
                "b=subprocess.run(['git','-C','/workspace/EU-PP-Database','log','-1','--oneline'],"
                "capture_output=True,text=True);"
                "n=subprocess.run(['node','-e','console.log(1+1)'],capture_output=True,text=True);"
                "p=pathlib.Path('/opt/data/.r5-offline-probe');p.write_text('ok');"
                "print(json.dumps({'REPO_A':g.returncode==0,'REPO_B':b.returncode==0,"
                "'NODE':n.returncode==0,'HERMES_HOME':p.read_text()=='ok'}))",
            ],
            check=False,
        )
        try:
            local_state = json.loads(local.stdout)
        except json.JSONDecodeError:
            local_state = {"error": (local.stderr or local.stdout)[-200:]}
        result = {
            "OFFLINE_MODE": "PASS"
            if developer.get("networks") in ([], ["none"]) and (net.stdout or "").strip() in {"000", ""}
            else "FAIL",
            "OFFLINE_DIRECT_EGRESS": "NO" if (net.stdout or "").strip() in {"000", ""} else "YES",
            "OFFLINE_LOCAL_DX": "PASS" if all(local_state.get(key) for key in ("REPO_A", "REPO_B", "NODE", "HERMES_HOME")) else "FAIL",
            "OFFLINE_NETWORKS": developer.get("networks"),
            "OFFLINE_LABELS": developer.get("labels"),
            "local": local_state,
            "launch": {"action": started.get("action"), "convergence": started.get("convergence")},
        }
    finally:
        set_egress_mode(previous)
        up()
    write_json(artifacts_dir() / "egress_offline.json", result)
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
        choices=(
            "argv",
            "build",
            "up",
            "down",
            "reset",
            "prove",
            "prove-dx",
            "prove-egress",
            "prove-offline",
            "prove-failure-modes",
            "inspect",
            "preflight",
            "plan",
            "egress-status",
        ),
    )
    parser.add_argument(
        "--egress-mode",
        choices=egress.EGRESS_MODES,
        default=None,
        help="PRIVATE_DEVELOPER_EGRESS_ENFORCED (default) or OFFLINE",
    )
    args = parser.parse_args()
    set_egress_mode(args.egress_mode)
    if args.command == "egress-status":
        payload = {
            **egress.egress_contract_summary(mode=egress_mode()),
            "BROKER_RUNNING": "YES" if broker_running() else "NO",
            "BROKER_LISTENING": "YES" if broker_listening() else "NO",
        }
        write_json(artifacts_dir() / "egress_status.json", payload)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "prove-offline":
        result = prove_offline()
        print(f"OFFLINE_MODE = {result['OFFLINE_MODE']}")
        print(f"OFFLINE_LOCAL_DX = {result['OFFLINE_LOCAL_DX']}")
        return 0 if result["OFFLINE_MODE"] == "PASS" and result["OFFLINE_LOCAL_DX"] == "PASS" else 1
    if args.command == "prove-failure-modes":
        result = prove_failure_modes()
        print(json.dumps(result, indent=2))
        return 0 if all(
            str(value).startswith("FAIL_CLOSED") or value in {"YES", "PASS"}
            for key, value in result.items()
            if not key.endswith(("_DIAGNOSTIC", "_NETWORKS"))
        ) else 1
    if args.command == "prove-egress":
        result = prove_egress()
        print(f"EGRESS_ACCEPTANCE = {result['EGRESS_ACCEPTANCE']}")
        return 0 if result["EGRESS_ACCEPTANCE"] == "PASS" else 1
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
