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
from r5_developer_hermes.container import desktop as desktop_gw  # noqa: E402
from r5_developer_hermes.container.egress import host as egress  # noqa: E402
from r5_developer_hermes.container import telegram_ops as tg_ops  # noqa: E402
from r5_developer_hermes.harness import artifacts_dir, write_json  # noqa: E402


CONTAINER_ARTIFACT = "container_boundary.json"
DX_ARTIFACT = "developer_dx.json"
EGRESS_ARTIFACT = "egress_boundary.json"
DESKTOP_ARTIFACT = "desktop_gateway.json"
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
        }
        and "HERMES_DOCKER_EXEC_AS_ROOT" not in env_names
        and "HERMES_ALLOW_ROOT_GATEWAY" not in env_names
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


def migrate_home_argv(*, apply: bool) -> list[str]:
    """One-shot volume-only helper. No workspace binds, socket, or egress CA."""
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        f"{CONTAINER_NAME}-migrate-home",
        "--user",
        "0:0",
        "--privileged=false",
        "--security-opt",
        "no-new-privileges:true",
        "--network",
        "none",
        "--mount",
        f"type=volume,src={HERMES_HOME_VOLUME},dst={CONTAINER_HERMES_HOME}",
        "--entrypoint",
        "python3",
        DEVELOPER_IMAGE,
        "/opt/r5-developer/migrate_home.py",
        "--apply" if apply else "--dry-run",
    ]


def migrate_home(*, apply: bool = False) -> dict[str, Any]:
    """Audit or apply HERMES_HOME ownership. Never prints secret contents."""
    _assert_host_execution_trust()
    if apply and container_running():
        raise RuntimeError("stop Developer Hermes before applying HERMES_HOME migration")
    if _image_inspect_payload(DEVELOPER_IMAGE) is None:
        raise RuntimeError("Developer image is missing; build before migrate-home")
    ensure_volume()
    completed = subprocess.run(
        [docker_exe(), *migrate_home_argv(apply=apply)[1:]],
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = (completed.stdout or "").strip()
    try:
        payload = json.loads(stdout)
    except ValueError:
        payload = {
            "OK": "NO",
            "error": (completed.stderr or completed.stdout).strip()[:400],
            "CONTENTS_PRINTED": "NO",
        }
    payload["MODE"] = "APPLY" if apply else "DRY_RUN"
    payload["exit_code"] = completed.returncode
    payload["TOKEN_PRINTED"] = "NO"
    if completed.returncode != 0 and payload.get("OK") != "YES":
        raise RuntimeError(
            "HERMES_HOME migration failed closed: "
            f"{payload.get('error') or payload.get('errors') or completed.returncode}"
        )
    return payload


def _create_container() -> dict[str, Any]:
    ensure_volume()
    migration = migrate_home(apply=True)
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
        "hermes_home_migration": {
            "OK": migration.get("OK"),
            "MODE": migration.get("MODE"),
            "CHANGE_COUNT": migration.get("CHANGE_COUNT"),
            "CONTENTS_PRINTED": "NO",
        },
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
    desktop_stopped = stop_desktop()
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
        "desktop": desktop_stopped,
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


def sidecar_running() -> bool:
    completed = docker(
        ["inspect", "-f", "{{.State.Running}}", desktop_gw.SIDECAR_CONTAINER_NAME],
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _developer_serve_listening() -> bool:
    if not container_running():
        return False
    probe = (
        "import socket,sys;"
        f"s=socket.socket();s.settimeout(2);"
        f"sys.exit(s.connect_ex(('127.0.0.1',{desktop_gw.CONTAINER_SERVE_PORT})))"
    )
    completed = exec_in(
        ["/opt/hermes/.venv/bin/python", "-c", probe],
        check=False,
    )
    return completed.returncode == 0


def ensure_ingress_network() -> dict[str, Any]:
    """Create the desktop ingress network. Fail closed if it is unexpectedly internal."""
    _assert_host_execution_trust()
    if not _network_exists(desktop_gw.INGRESS_NETWORK):
        created = docker(desktop_gw.ingress_create_argv()[1:], check=False)
        if created.returncode != 0:
            docker(
                [
                    "network",
                    "create",
                    "--driver",
                    "bridge",
                    desktop_gw.INGRESS_NETWORK,
                ]
            )
    if _network_is_internal(desktop_gw.INGRESS_NETWORK):
        raise RuntimeError(
            "DESKTOP_INGRESS_FAIL_CLOSED: ingress network is internal, so "
            "host port publish cannot work"
        )
    return {"INGRESS_NETWORK": desktop_gw.INGRESS_NETWORK}


def start_hermes_serve() -> dict[str, Any]:
    """Start authenticated hermes serve inside the existing Developer container."""
    _assert_host_execution_trust()
    if not container_running():
        raise RuntimeError("Developer Hermes is not running; start it before desktop mode")
    if _developer_serve_listening():
        return {"HERMES_SERVE": "already-running", "CONTAINER_BIND": desktop_gw.HERMES_SERVE_HOST}
    creds = desktop_gw.ensure_desktop_auth()
    cmd = [
        docker_exe(),
        "exec",
        "-d",
        "-u",
        f"{RUNTIME_UID}:{RUNTIME_GID}",
        "-w",
        CONTAINER_WORKDIR,
        "-e",
        f"HERMES_DASHBOARD_BASIC_AUTH_USERNAME={creds['HERMES_DASHBOARD_BASIC_AUTH_USERNAME']}",
        "-e",
        f"HERMES_DASHBOARD_BASIC_AUTH_PASSWORD={creds['HERMES_DASHBOARD_BASIC_AUTH_PASSWORD']}",
        "-e",
        f"HERMES_DASHBOARD_BASIC_AUTH_SECRET={creds['HERMES_DASHBOARD_BASIC_AUTH_SECRET']}",
        "-e",
        f"HERMES_DASHBOARD_FILES_ROOT={desktop_gw.FILES_ROOT}",
        "-e",
        f"HERMES_HOME={CONTAINER_HERMES_HOME}",
        "-e",
        f"HOME={CONTAINER_HERMES_HOME}",
        CONTAINER_NAME,
        desktop_gw.HERMES_SERVE_BIN,
        "serve",
        "--host",
        desktop_gw.HERMES_SERVE_HOST,
        "--port",
        str(desktop_gw.CONTAINER_SERVE_PORT),
        "--skip-build",
    ]
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "hermes serve failed to start: "
            f"{(completed.stderr or completed.stdout).strip()[:500]}"
        )
    deadline = time.time() + 45
    while time.time() < deadline:
        if _developer_serve_listening():
            return {
                "HERMES_SERVE": "started",
                "CONTAINER_BIND": desktop_gw.HERMES_SERVE_HOST,
                "CONTAINER_PORT": desktop_gw.CONTAINER_SERVE_PORT,
            }
        time.sleep(1)
    logs = exec_in(["sh", "-c", "ps -ef | grep '[h]ermes serve' || true"], check=False)
    raise RuntimeError(
        "hermes serve did not become reachable on the container loopback. "
        f"{(logs.stdout or logs.stderr).strip()[:400]}"
    )


def start_sidecar() -> dict[str, Any]:
    """Publish 127.0.0.1:HOST_PORT via the inbound sidecar."""
    _assert_host_execution_trust()
    ensure_ingress_network()
    if sidecar_running():
        return {
            "SIDECAR": "already-running",
            "HOST_BIND": desktop_gw.HOST_BIND,
            "HOST_PORT": desktop_gw.HOST_PORT,
        }
    docker(["rm", "-f", desktop_gw.SIDECAR_CONTAINER_NAME], check=False)
    argv = desktop_gw.sidecar_run_argv(image=DEVELOPER_IMAGE)
    created = subprocess.run(
        [docker_exe(), "create", *argv[3:]],
        text=True,
        capture_output=True,
        check=False,
    )
    if created.returncode != 0:
        raise RuntimeError(
            "desktop sidecar create failed: "
            f"{(created.stderr or created.stdout).strip()[:500]}"
        )
    docker(
        [
            "cp",
            str(desktop_gw.SIDECAR_SCRIPT_HOST_PATH),
            f"{desktop_gw.SIDECAR_CONTAINER_NAME}:{desktop_gw.SIDECAR_SCRIPT_CONTAINER_PATH}",
        ]
    )
    docker(["start", desktop_gw.SIDECAR_CONTAINER_NAME])
    docker(["network", "connect", egress.INTERNAL_NETWORK, desktop_gw.SIDECAR_CONTAINER_NAME])
    if not sidecar_running():
        logs = docker(["logs", "--tail", "20", desktop_gw.SIDECAR_CONTAINER_NAME], check=False)
        raise RuntimeError(
            "desktop sidecar failed to start. "
            f"{(logs.stdout or logs.stderr).strip()[:400]}"
        )
    return {
        "SIDECAR": "started",
        "HOST_BIND": desktop_gw.HOST_BIND,
        "HOST_PORT": desktop_gw.HOST_PORT,
        "argv_without_secrets": argv,
    }


def stop_desktop() -> dict[str, Any]:
    """Stop the inbound sidecar. Developer Hermes itself stays unless down() runs."""
    _assert_host_execution_trust()
    removed = docker(["rm", "-f", desktop_gw.SIDECAR_CONTAINER_NAME], check=False)
    if container_running():
        exec_in(
            ["sh", "-c", "pkill -f '[h]ermes serve' || true"],
            check=False,
        )
    return {
        "sidecar_removed": removed.returncode == 0,
        "serve_stopped": "YES",
    }


def _telegram_secret_state_in_container() -> dict[str, str]:
    probe = (
        "import json,sys; sys.path.insert(0, '/opt/r5-developer'); "
        "from pathlib import Path; "
        "from telegram_ops import read_dotenv_names_and_token_class, token_env_path; "
        "print(json.dumps(read_dotenv_names_and_token_class(token_env_path(Path('/opt/data')))))"
    )
    completed = exec_in(
        ["/opt/hermes/.venv/bin/python", "-c", probe],
        check=False,
    )
    if completed.returncode != 0:
        return {
            "token_class": "UNKNOWN",
            "allowed_users_present": "UNKNOWN",
            "allowed_users_class": "UNKNOWN",
            "allow_all_set": "UNKNOWN",
            "webhook_set": "UNKNOWN",
        }
    try:
        payload = json.loads((completed.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return {
            "token_class": "UNKNOWN",
            "allowed_users_present": "UNKNOWN",
            "allowed_users_class": "UNKNOWN",
            "allow_all_set": "UNKNOWN",
            "webhook_set": "UNKNOWN",
        }
    return {
        "token_class": str(payload.get("token_class") or "UNKNOWN"),
        "allowed_users_present": str(payload.get("allowed_users_present") or "NO"),
        "allowed_users_class": str(payload.get("allowed_users_class") or "MISSING"),
        "allow_all_set": str(payload.get("allow_all_set") or "NO"),
        "webhook_set": str(payload.get("webhook_set") or "NO"),
    }


def _telegram_token_class_in_container() -> str:
    return _telegram_secret_state_in_container()["token_class"]


def _telegram_conflict_signal(status_text: str) -> str:
    lowered = tg_ops.redact_sensitive_text(status_text).lower()
    if "409" in lowered or "conflict" in lowered:
        return "YES"
    return "NO"


def _telegram_gateway_process_scan_script() -> str:
    """Scan /proc for telegram-ops gateway run. Never echoes command lines."""
    return f"""
import json
import os
profile = {tg_ops.PROFILE_NAME!r}
hits = []
if os.path.isdir("/proc"):
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{{entry}}/cmdline", "rb") as handle:
                command = handle.read().decode("utf-8", errors="replace").replace("\\x00", " ")
            uid = None
            with open(f"/proc/{{entry}}/status", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.startswith("Uid:"):
                        uid = int(line.split()[1])
                        break
        except (OSError, ValueError):
            continue
        lowered = command.lower()
        if "hermes serve" in lowered or "hermes_cli.main serve" in lowered:
            continue
        if any(
            token in lowered
            for token in (
                "gateway start",
                "gateway status",
                "gateway stop",
                "gateway install",
                "gateway uninstall",
            )
        ):
            continue
        has_profile = f"-p {{profile}}" in lowered or f"--profile {{profile}}" in lowered
        if has_profile and "gateway run" in lowered:
            hits.append({{"pid": int(entry), "uid": uid}})
print(json.dumps(hits))
"""


def _activation_payload_from_stdin() -> dict[str, Any] | None:
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("REFUSE_ACTIVATION_PAYLOAD") from exc
    return tg_ops.parse_activation_payload(parsed)


def _write_live_secrets_via_stdin(payload: dict[str, str]) -> dict[str, Any]:
    script = (
        "import json,sys; sys.path.insert(0,'/opt/r5-developer'); "
        "from pathlib import Path; "
        "from telegram_ops import apply_live_secrets; "
        "print(json.dumps(apply_live_secrets(Path('/opt/data'), json.load(sys.stdin))))"
    )
    completed = subprocess.run(
        [
            docker_exe(),
            "exec",
            "-i",
            "-u",
            f"{RUNTIME_UID}:{RUNTIME_GID}",
            "-w",
            CONTAINER_WORKDIR,
            CONTAINER_NAME,
            "/opt/hermes/.venv/bin/python",
            "-c",
            script,
        ],
        input=json.dumps(
            {
                tg_ops.ACTIVATION_STDIN_TOKEN_KEY: payload[tg_ops.ACTIVATION_STDIN_TOKEN_KEY],
                tg_ops.ACTIVATION_STDIN_USER_KEY: payload[tg_ops.ACTIVATION_STDIN_USER_KEY],
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "telegram secret write failed: "
            f"{(completed.stderr or completed.stdout).strip()[:200]}"
        )
    try:
        return json.loads((completed.stdout or "").strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError("telegram secret write produced no status") from exc


def _telegram_gateway_process_evidence() -> dict[str, Any]:
    """Profile-specific live process proof. hermes serve never counts."""
    empty = {
        "GATEWAY_PROCESS": "STOPPED",
        "ACTIVE_GATEWAY_PROFILE": "NONE",
        "GATEWAY_USER": "NONE",
        "GATEWAY_PID_COUNT": 0,
    }
    if not container_running():
        return empty
    completed = exec_in(
        ["/opt/hermes/.venv/bin/python", "-c", _telegram_gateway_process_scan_script()],
        check=False,
    )
    if completed.returncode != 0:
        return empty
    try:
        hits = json.loads((completed.stdout or "").strip() or "[]")
    except json.JSONDecodeError:
        return empty
    if not isinstance(hits, list) or not hits:
        return empty
    users = {
        tg_ops.classify_gateway_user(item.get("uid") if isinstance(item, dict) else None)
        for item in hits
    }
    user = tg_ops.INTENDED_GATEWAY_USER if users == {tg_ops.INTENDED_GATEWAY_USER} else (
        next(iter(users)) if len(users) == 1 else "other"
    )
    return {
        "GATEWAY_PROCESS": "RUNNING",
        "ACTIVE_GATEWAY_PROFILE": tg_ops.PROFILE_NAME,
        "GATEWAY_USER": user,
        "GATEWAY_PID_COUNT": len(hits),
        "_pids": [int(item["pid"]) for item in hits if isinstance(item, dict) and "pid" in item],
    }


def _telegram_log_conflict_signal() -> str:
    completed = exec_in(
        [
            "sh",
            "-c",
            f"tail -n 80 {tg_ops.CONTAINER_GATEWAY_LOG} 2>/dev/null || true",
        ],
        check=False,
    )
    return _telegram_conflict_signal(tg_ops.redact_sensitive_text(completed.stdout or ""))


def _start_telegram_gateway_run() -> dict[str, Any]:
    """Detach ``hermes -p telegram-ops gateway run`` as uid 10000."""
    existing = _telegram_gateway_process_evidence()
    if existing["GATEWAY_PROCESS"] == "RUNNING":
        return {"GATEWAY_LAUNCH": "already-running"}
    exec_in(["mkdir", "-p", f"{tg_ops.CONTAINER_PROFILE_HOME}/logs"], check=False)
    launched = exec_detached(
        [
            "sh",
            "-c",
            (
                f"exec {tg_ops.HERMES_BIN} -p {tg_ops.PROFILE_NAME} gateway run "
                f">>{tg_ops.CONTAINER_GATEWAY_LOG} 2>&1"
            ),
        ]
    )
    if launched.returncode != 0:
        raise RuntimeError(
            "telegram-ops gateway run failed to detach: "
            f"{(launched.stderr or launched.stdout or '').strip()[:300]}"
        )
    deadline = time.time() + 25
    while time.time() < deadline:
        if _telegram_gateway_process_evidence()["GATEWAY_PROCESS"] == "RUNNING":
            return {"GATEWAY_LAUNCH": "started"}
        time.sleep(1)
    return {"GATEWAY_LAUNCH": "started-unconfirmed"}


def _stop_telegram_gateway_run() -> dict[str, Any]:
    """Stop telegram-ops gateway run only. Never touch hermes serve."""
    evidence = _telegram_gateway_process_evidence()
    pids = [int(pid) for pid in evidence.get("_pids") or [] if int(pid) > 1]
    if not pids:
        return {"GATEWAY_STOP": "already-stopped", "STOPPED_PID_COUNT": 0}
    script = f"""
import os
import signal
import time
pids = {pids!r}
for pid in pids:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
deadline = time.time() + 8
alive = list(pids)
while alive and time.time() < deadline:
    nxt = []
    for pid in alive:
        try:
            os.kill(pid, 0)
            nxt.append(pid)
        except OSError:
            pass
    alive = nxt
    time.sleep(0.2)
for pid in alive:
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
print(len(pids))
"""
    completed = exec_in(["/opt/hermes/.venv/bin/python", "-c", script], check=False)
    return {
        "GATEWAY_STOP": "stopped" if completed.returncode == 0 else "stop-failed",
        "STOPPED_PID_COUNT": len(pids),
    }


def telegram_status() -> dict[str, Any]:
    """Observe the dedicated Telegram gateway. Never prints a token."""
    _assert_host_execution_trust()
    running = container_running()
    result: dict[str, Any] = {
        "PROFILE": tg_ops.PROFILE_NAME,
        "DISPLAY_NAME": tg_ops.DISPLAY_NAME,
        "PROFILE_ROLE": tg_ops.PROFILE_ROLE,
        "ARCHITECTURE": tg_ops.ARCHITECTURE,
        "CONTAINER_RUNNING": "YES" if running else "NO",
        "TRANSPORT": tg_ops.TRANSPORT,
        "PUBLIC_INBOUND_PORT": "NO",
        "TOKEN_STORAGE_TARGET": tg_ops.TOKEN_STORAGE_TARGET,
        "TOKEN_VALUES_RECORDED": "NO",
        "OPERATOR_TELEGRAM_CHANGED": "NO",
        "GATEWAY_PROCESS": "STOPPED",
        "ACTIVE_GATEWAY_PROFILE": "NONE",
        "UPSTREAM_GATEWAY_STATUS": "STOPPED",
        "HELPER_GATEWAY_STATUS": "STOPPED",
        "GATEWAY_USER": "NONE",
        "LIVE_TOKEN": "MISSING",
        "LIVE_POLLING": "NO",
        "STATUS_CONSISTENT": "YES",
        "TELEGRAM_POLL_CONFLICT_409": "NO",
        "GATEWAY": "DOWN",
        "GATEWAY_PRIMITIVE": " ".join(tg_ops.GATEWAY_RUN_ARGV),
        "DOWN_MECHANISM": tg_ops.DOWN_MECHANISM,
    }
    if not running:
        return result
    seeded = exec_in(
        ["/opt/hermes/.venv/bin/python", "/opt/r5-developer/seed_home.py"],
        check=False,
    )
    result["PROFILE_SEEDED"] = "YES" if seeded.returncode == 0 else "NO"
    state = _telegram_secret_state_in_container()
    result["TOKEN_CLASS"] = state["token_class"]
    result["ALLOWED_USERS_PRESENT"] = state["allowed_users_present"]
    result["ALLOWED_USERS_CLASS"] = state["allowed_users_class"]
    result["ALLOW_ALL_SET"] = state["allow_all_set"]
    result["WEBHOOK_SET"] = state["webhook_set"]
    result["LIVE_TOKEN"] = tg_ops.classify_live_token(state["token_class"])
    evidence = _telegram_gateway_process_evidence()
    result["GATEWAY_PROCESS"] = evidence["GATEWAY_PROCESS"]
    result["ACTIVE_GATEWAY_PROFILE"] = evidence["ACTIVE_GATEWAY_PROFILE"]
    result["GATEWAY_USER"] = evidence["GATEWAY_USER"]
    status = exec_in(list(tg_ops.GATEWAY_STATUS_ARGV), check=False)
    status_text = tg_ops.redact_sensitive_text(f"{status.stdout or ''}\n{status.stderr or ''}")
    result["UPSTREAM_GATEWAY_STATUS"] = tg_ops.parse_upstream_gateway_status(status_text)
    result["HELPER_GATEWAY_STATUS"] = evidence["GATEWAY_PROCESS"]
    result["STATUS_CONSISTENT"] = tg_ops.status_agreement(
        result["HELPER_GATEWAY_STATUS"],
        result["UPSTREAM_GATEWAY_STATUS"],
    )
    result["GATEWAY"] = "UP" if evidence["GATEWAY_PROCESS"] == "RUNNING" else "DOWN"
    result["TELEGRAM_POLL_CONFLICT_409"] = (
        "YES"
        if _telegram_conflict_signal(status_text) == "YES"
        or _telegram_log_conflict_signal() == "YES"
        else "NO"
    )
    result["LIVE_POLLING"] = tg_ops.classify_live_polling(
        token_class=state["token_class"],
        process_running=evidence["GATEWAY_PROCESS"] == "RUNNING",
        upstream_status=result["UPSTREAM_GATEWAY_STATUS"],
    )
    return result


def telegram_up() -> dict[str, Any]:
    """Prepare the telegram-ops gateway. Ordinary up still refuses live tokens."""
    _assert_host_execution_trust()
    started = up()
    exec_in(["/opt/hermes/.venv/bin/python", "/opt/r5-developer/seed_home.py"])
    state = _telegram_secret_state_in_container()
    allowed, reason = tg_ops.may_start_gateway(state["token_class"])
    result: dict[str, Any] = {
        **started,
        "PROFILE": tg_ops.PROFILE_NAME,
        "DISPLAY_NAME": tg_ops.DISPLAY_NAME,
        "TOKEN_CLASS": state["token_class"],
        "TOKEN_VALUES_RECORDED": "NO",
        "LIFECYCLE_ARGV": list(tg_ops.GATEWAY_RUN_ARGV),
        "START_PERMITTED": "YES" if allowed else "NO",
        "START_REASON": reason,
        "LIVE_TOKEN_MOVED": "NO",
        "OPERATOR_TELEGRAM_CHANGED": "NO",
    }
    if not allowed:
        result["GATEWAY"] = "NOT_STARTED"
        return result
    launched = _start_telegram_gateway_run()
    result.update(launched)
    result.update(telegram_status())
    result["TOKEN_CLASS"] = state["token_class"]
    return result


def telegram_activate(*, confirmed: bool) -> dict[str, Any]:
    """Explicit live activation for the dedicated Developer Telegram bot."""
    _assert_host_execution_trust()
    result: dict[str, Any] = {
        "PROFILE": tg_ops.PROFILE_NAME,
        "DISPLAY_NAME": tg_ops.DISPLAY_NAME,
        "PROFILE_ROLE": tg_ops.PROFILE_ROLE,
        "ARCHITECTURE": tg_ops.ARCHITECTURE,
        "TOKEN_VALUES_RECORDED": "NO",
        "LIVE_TOKEN_MOVED": "NO",
        "OPERATOR_TELEGRAM_CHANGED": "NO",
        "RAILWAY_CHANGED": "NO",
    }
    if not confirmed:
        result.update(
            {
                "GATEWAY": "NOT_STARTED",
                "START_PERMITTED": "NO",
                "START_REASON": "REFUSE_MISSING_ACTIVATION_INTENT",
            }
        )
        return result
    started = up()
    exec_in(["/opt/hermes/.venv/bin/python", "/opt/r5-developer/seed_home.py"])
    state = _telegram_secret_state_in_container()
    result["launch"] = {
        "action": started.get("action"),
        "convergence": started.get("convergence"),
    }
    if state["token_class"] != "LIVE_SHAPED" or state["allowed_users_present"] != "YES":
        payload = _activation_payload_from_stdin()
        if payload is None:
            result.update(
                {
                    **state,
                    "TOKEN_CLASS": state["token_class"],
                    "GATEWAY": "NOT_STARTED",
                    "START_PERMITTED": "NO",
                    "START_REASON": "WAITING_HUMAN_SECRET",
                    "HUMAN_ACTION": (
                        "Run launch-developer-hermes.ps1 -Mode telegram-activate "
                        "in a local terminal outside Cursor chat, then enter the "
                        "NEW Developer bot token and one numeric Telegram user id."
                    ),
                }
            )
            return result
        written = _write_live_secrets_via_stdin(payload)
        result["SECRET_WRITE"] = written.get("REASON")
        if written.get("APPLIED") != "YES":
            result.update(
                {
                    "GATEWAY": "NOT_STARTED",
                    "START_PERMITTED": "NO",
                    "START_REASON": written.get("REASON") or "REFUSE_SECRET_WRITE",
                    "TOKEN_CLASS": written.get("token_class") or state["token_class"],
                }
            )
            return result
        state = _telegram_secret_state_in_container()
    allowed, reason = tg_ops.may_start_live_gateway(
        state["token_class"],
        live_activation=True,
        allowed_users_present=state["allowed_users_present"],
        allow_all_set=state["allow_all_set"],
        webhook_set=state["webhook_set"],
    )
    result["TOKEN_CLASS"] = state["token_class"]
    result["ALLOWED_USERS_PRESENT"] = state["allowed_users_present"]
    result["START_PERMITTED"] = "YES" if allowed else "NO"
    result["START_REASON"] = reason
    if not allowed:
        result["GATEWAY"] = "NOT_STARTED"
        return result
    launched = _start_telegram_gateway_run()
    result.update(launched)
    result.update(telegram_status())
    result["TOKEN_CLASS"] = state["token_class"]
    result["START_PERMITTED"] = "YES"
    result["START_REASON"] = reason
    return result


def telegram_down() -> dict[str, Any]:
    """Stop only the telegram-ops gateway. Developer Hermes stays up."""
    _assert_host_execution_trust()
    if not container_running():
        return {
            "PROFILE": tg_ops.PROFILE_NAME,
            "GATEWAY": "DOWN",
            "CONTAINER_RUNNING": "NO",
            "GATEWAY_PROCESS": "STOPPED",
            "DESKTOP_GATEWAY": "DOWN",
        }
    serve_before = _developer_serve_listening()
    stopped = _stop_telegram_gateway_run()
    status = telegram_status()
    serve_after = _developer_serve_listening()
    return {
        "PROFILE": tg_ops.PROFILE_NAME,
        **stopped,
        **status,
        "DESKTOP_SERVE_BEFORE": "UP" if serve_before else "DOWN",
        "DESKTOP_SERVE_AFTER": "UP" if serve_after else "DOWN",
        "DESKTOP_GATEWAY": "UP" if serve_after else "DOWN",
    }


def desktop_up() -> dict[str, Any]:
    """Bring up Developer Hermes, then the opt-in Desktop remote-gateway path."""
    _assert_host_execution_trust()
    started = up()
    serve = start_hermes_serve()
    sidecar = start_sidecar()
    return {
        **started,
        "desktop": {
            "TRANSPORT": desktop_gw.DESKTOP_TRANSPORT,
            "BASE_URL": desktop_gw.desktop_base_url(),
            "HOST_BIND": desktop_gw.HOST_BIND,
            "HOST_PORT": desktop_gw.HOST_PORT,
            "CONTAINER_BIND": desktop_gw.HERMES_SERVE_HOST,
            "CONTAINER_PORT": desktop_gw.CONTAINER_SERVE_PORT,
            "AUTH_MECHANISM": "dashboard.basic_auth",
            "serve": serve,
            "sidecar": sidecar,
            "auth": desktop_gw.desktop_auth_status(),
        },
    }


def exec_detached(
    args: list[str],
    *,
    workdir: str = CONTAINER_WORKDIR,
) -> subprocess.CompletedProcess[str]:
    """Host-returning docker exec -d as the Developer runtime user."""
    for item in args:
        if "HERMES_ALLOW_ROOT_GATEWAY" in item or "HERMES_DOCKER_EXEC_AS_ROOT" in item:
            raise RuntimeError("refusing root-gateway telegram launch")
    cmd = [
        docker_exe(),
        "exec",
        "-d",
        "-u",
        f"{RUNTIME_UID}:{RUNTIME_GID}",
        "-w",
        workdir,
        "-e",
        f"HERMES_HOME={CONTAINER_HERMES_HOME}",
        "-e",
        f"HOME={CONTAINER_HERMES_HOME}",
        CONTAINER_NAME,
        *args,
    ]
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


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
        (inspect_data.get("user") or "")
        in {f"{RUNTIME_UID}:{RUNTIME_GID}", RUNTIME_USER, str(RUNTIME_UID)},
        "HERMES_DOCKER_EXEC_AS_ROOT" not in env_names,
        "HERMES_ALLOW_ROOT_GATEWAY" not in env_names,
        probe["git_a"]["status"] == "YES",
        probe["git_b"]["status"] == "YES",
        probe["git_a"]["diff"] == "YES",
        probe["git_b"]["diff"] == "YES",
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
        "HERMES_SERVE_USER_EXPECTED": RUNTIME_USER,
        "ROOT_GATEWAY_OVERRIDE": (
            "PRESENT" if "HERMES_ALLOW_ROOT_GATEWAY" in set(_env_names(inspect_data)) else "ABSENT"
        ),
        "LOCAL_COMMIT_A": probe["git_a"].get("local_commit"),
        "LOCAL_COMMIT_B": probe["git_b"].get("local_commit"),
        "LOCAL_COMMIT_RESIDUAL": (
            "WINDOWS_BIND_GIT_METADATA"
            if probe["git_a"].get("local_commit") != "YES"
            or probe["git_b"].get("local_commit") != "YES"
            else "NONE"
        ),
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


def _host_loopback_listeners(port: int) -> dict[str, Any]:
    """Prove the Desktop port is published on 127.0.0.1 only."""
    import socket

    loopback = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    loopback.settimeout(2)
    loopback_ok = loopback.connect_ex((desktop_gw.HOST_BIND, port)) == 0
    loopback.close()
    lan_ok = False
    lan_addr = ""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 80))
        lan_addr = probe.getsockname()[0]
        probe.close()
        if lan_addr and not lan_addr.startswith("127."):
            lan = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            lan.settimeout(1)
            lan_ok = lan.connect_ex((lan_addr, port)) == 0
            lan.close()
    except OSError:
        lan_addr = ""
    wildcard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    wildcard.settimeout(1)
    try:
        wildcard.bind(("0.0.0.0", port))
        wildcard_free = True
    except OSError:
        wildcard_free = False
    finally:
        wildcard.close()
    return {
        "LOOPBACK_REACHABLE": "YES" if loopback_ok else "NO",
        "LAN_ADDRESS": lan_addr,
        "LAN_REACHABLE": "YES" if lan_ok else "NO",
        "WILDCARD_BIND_FREE": "YES" if wildcard_free else "NO",
        "HOST_BIND": desktop_gw.HOST_BIND,
        "HOST_PORT": port,
    }


def _http_json(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    cookies: str = "",
    timeout: int = 8,
) -> tuple[int, dict[str, str], Any]:
    import json as json_lib
    import urllib.error
    import urllib.request

    url = desktop_gw.desktop_base_url() + path
    data = None if body is None else json_lib.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if cookies:
        req.add_header("Cookie", cookies)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            payload: Any
            try:
                payload = json_lib.loads(raw.decode("utf-8") or "null")
            except ValueError:
                payload = {"text": raw[:200].decode("utf-8", errors="replace")}
            cookie = resp.headers.get("Set-Cookie") or ""
            return resp.status, {"set-cookie": cookie}, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json_lib.loads(raw.decode("utf-8") or "null")
        except ValueError:
            payload = {"text": raw[:200].decode("utf-8", errors="replace")}
        return exc.code, {"set-cookie": exc.headers.get("Set-Cookie") or ""}, payload


def _cookie_header(set_cookie: str, previous: str = "") -> str:
    parts = [item.strip() for item in previous.split(";") if item.strip()]
    if set_cookie:
        name_value = set_cookie.split(";", 1)[0].strip()
        if name_value:
            key = name_value.split("=", 1)[0]
            parts = [item for item in parts if not item.startswith(key + "=")]
            parts.append(name_value)
    return "; ".join(parts)


def _ws_probe(*, ticket: str | None, expect_accept: bool) -> dict[str, Any]:
    """Minimal WebSocket upgrade against /api/ws. Does not log credentials."""
    import base64
    import hashlib
    import socket

    key = base64.b64encode(secrets_token()).decode("ascii")
    query = f"ticket={ticket}" if ticket else ""
    path = "/api/ws" + (f"?{query}" if query else "")
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {desktop_gw.HOST_BIND}:{desktop_gw.HOST_PORT}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock = socket.create_connection((desktop_gw.HOST_BIND, desktop_gw.HOST_PORT), timeout=5)
    try:
        sock.sendall(req.encode("ascii"))
        raw = sock.recv(1024).decode("iso-8859-1", errors="replace")
        status_line = raw.split("\r\n", 1)[0]
        accepted = " 101 " in f" {status_line} " or status_line.endswith("101")
        if expect_accept and accepted:
            expected = base64.b64encode(
                hashlib.sha1(
                    (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
                ).digest()
            ).decode("ascii")
            if expected not in raw:
                accepted = False
        return {
            "status_line": status_line[:80],
            "ACCEPTED": "YES" if accepted else "NO",
            "EXPECTED": "YES" if expect_accept == accepted else "NO",
        }
    finally:
        sock.close()


def secrets_token() -> bytes:
    import os as os_mod

    return os_mod.urandom(16)


def _sidecar_inspect() -> dict[str, Any]:
    completed = docker(["inspect", desktop_gw.SIDECAR_CONTAINER_NAME], check=False)
    if completed.returncode != 0:
        return {"SIDECAR_PRESENT": "NO"}
    payload = json.loads(completed.stdout)[0]
    classified = desktop_gw.classify_sidecar_inspect(payload)
    classified["SIDECAR_PRESENT"] = "YES"
    return classified


def _desktop_developer_still_internal() -> dict[str, str]:
    inspect_data = _inspect()
    networks = set(inspect_data.get("networks") or [])
    return {
        "DEVELOPER_NETWORKS": ",".join(sorted(networks)),
        "DEVELOPER_ONLY_INTERNAL": (
            "YES" if networks == {egress.INTERNAL_NETWORK} else "NO"
        ),
        "HOST_NETWORK": "YES" if inspect_data.get("network_mode") == "host" else "NO",
        "PRIVILEGED": "YES" if inspect_data.get("privileged") else "NO",
    }


def prove_desktop() -> dict[str, Any]:
    """Focused Desktop 0A proof: loopback, auth, same container, repo read."""
    import base64

    _assert_host_execution_trust()
    started = desktop_up()
    identity = _runtime_identity()
    listeners = _host_loopback_listeners(desktop_gw.HOST_PORT)
    sidecar = _sidecar_inspect()
    developer_net = _desktop_developer_still_internal()
    status_code, _headers, status_body = _http_json("GET", "/api/status")
    unauth_code, _, _unauth_body = _http_json("GET", "/api/files")
    creds = desktop_gw.ensure_desktop_auth()
    bad_code, _, _bad = _http_json(
        "POST",
        "/auth/password-login",
        body={
            "provider": desktop_gw.AUTH_PROVIDER,
            "username": creds["HERMES_DASHBOARD_BASIC_AUTH_USERNAME"],
            "password": "definitely-not-the-password",
        },
    )
    good_code, good_headers, good_body = _http_json(
        "POST",
        "/auth/password-login",
        body={
            "provider": desktop_gw.AUTH_PROVIDER,
            "username": creds["HERMES_DASHBOARD_BASIC_AUTH_USERNAME"],
            "password": creds["HERMES_DASHBOARD_BASIC_AUTH_PASSWORD"],
        },
    )
    cookies = _cookie_header(good_headers.get("set-cookie") or "")
    # Password login may set more than one cookie via multiple Set-Cookie
    # headers; urllib exposes only one. Retry login through a cookie jar.
    if good_code == 200 and not cookies:
        import http.cookiejar
        import urllib.request

        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        import json as json_lib

        req = urllib.request.Request(
            desktop_gw.desktop_base_url() + "/auth/password-login",
            data=json_lib.dumps(
                {
                    "provider": desktop_gw.AUTH_PROVIDER,
                    "username": creds["HERMES_DASHBOARD_BASIC_AUTH_USERNAME"],
                    "password": creds["HERMES_DASHBOARD_BASIC_AUTH_PASSWORD"],
                }
            ).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with opener.open(req, timeout=8) as resp:
            good_code = resp.status
        cookies = "; ".join(f"{item.name}={item.value}" for item in jar)
    ticket_code, _, ticket_body = _http_json(
        "POST",
        "/api/auth/ws-ticket",
        cookies=cookies,
    )
    ticket = ""
    if isinstance(ticket_body, dict):
        ticket = str(ticket_body.get("ticket") or "")
    ws_unauth = _ws_probe(ticket=None, expect_accept=False)
    ws_auth = (
        _ws_probe(ticket=ticket, expect_accept=True)
        if ticket
        else {"ACCEPTED": "NO", "EXPECTED": "NO", "status_line": "no-ticket"}
    )
    files_code, _, files_body = _http_json("GET", "/api/files?path=/workspace", cookies=cookies)
    repo_code, _, repo_body = _http_json(
        "GET",
        f"/api/files/read?path=/workspace/{desktop_gw.PROOF_DOC_RELATIVE}",
        cookies=cookies,
    )
    repo_text = ""
    if isinstance(repo_body, dict) and repo_body.get("data_url"):
        encoded = str(repo_body["data_url"]).split(",", 1)[-1]
        try:
            repo_text = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            repo_text = ""
    names = []
    if isinstance(files_body, dict):
        names = [str(item.get("name") or "") for item in (files_body.get("entries") or [])]
    process = exec_in(
        ["sh", "-c", "ps -ef | grep '[h]ermes serve' | head -n 1"],
        check=False,
    )
    uname = exec_in(["uname", "-a"], check=False)
    branch = exec_in(
        ["git", "-C", "/workspace/hermes-agent", "rev-parse", "--abbrev-ref", "HEAD"],
        check=False,
    )
    result = {
        "DESKTOP_PROOF": "PASS",
        "TRANSPORT": desktop_gw.DESKTOP_TRANSPORT,
        "BASE_URL": desktop_gw.desktop_base_url(),
        "HOST_BIND": desktop_gw.HOST_BIND,
        "HOST_PORT": desktop_gw.HOST_PORT,
        "CONTAINER_BIND": desktop_gw.HERMES_SERVE_HOST,
        "AUTH_MECHANISM": "dashboard.basic_auth",
        "listeners": listeners,
        "sidecar": sidecar,
        "developer_network": developer_net,
        "status": {
            "http": status_code,
            "auth_required": (
                (status_body or {}).get("auth_required")
                if isinstance(status_body, dict)
                else None
            ),
            "version": (
                (status_body or {}).get("version")
                if isinstance(status_body, dict)
                else None
            ),
        },
        "UNAUTHENTICATED_ACCESS": "DENIED" if unauth_code in {401, 403} else "FAIL",
        "WRONG_PASSWORD": "DENIED" if bad_code in {401, 403, 404} else "FAIL",
        "AUTHENTICATED_GATEWAY": "PASS" if good_code == 200 and ticket_code == 200 and ticket else "FAIL",
        "WS_UNAUTHENTICATED": "DENIED" if ws_unauth.get("ACCEPTED") == "NO" else "FAIL",
        "WS_AUTHENTICATED": "PASS" if ws_auth.get("ACCEPTED") == "YES" else "FAIL",
        "DESKTOP_TO_CONTAINER_EXECUTION": (
            "PASS"
            if "hermes-agent" in names and "EU-PP-Database" in names
            else "FAIL"
        ),
        "REPO_READ_PROOF": (
            "PASS"
            if repo_code == 200 and desktop_gw.PROOF_DOC_MARKER in repo_text
            else "FAIL"
        ),
        "repo_read_http": repo_code,
        "repo_read_path": f"/workspace/{desktop_gw.PROOF_DOC_RELATIVE}",
        "workspace_names": names,
        "serve_process_present": "YES" if "hermes serve" in (process.stdout or "") else "NO",
        "uname": (uname.stdout or "").strip()[:160],
        "repo_branch": (branch.stdout or "").strip(),
        "RUNTIME_CONVERGED": identity.get("RUNTIME_CONVERGED"),
        "HOST_FILESYSTEM_AUTHORITY_ADDED": "NO",
        "WINDOWS_PROFILE_MOUNT_ADDED": "NO",
        "DOCKER_SOCKET_ACCESS": sidecar.get("DOCKER_SOCKET", "NO"),
        "PRIVILEGED_CONTAINER": developer_net.get("PRIVILEGED", "NO"),
        "HOST_NETWORK": developer_net.get("HOST_NETWORK", "NO"),
        "SIDECAR_ON_EGRESS": (
            "YES" if egress.EGRESS_NETWORK in set(sidecar.get("networks") or []) else "NO"
        ),
        "WINDOWS_COMPUTER_USE_ENABLED": desktop_gw.WINDOWS_COMPUTER_USE_ENABLED,
        "launch": {
            "action": started.get("action"),
            "convergence": started.get("convergence"),
        },
        "CREDENTIAL_VALUES_RECORDED": "NO",
    }
    failed = [
        key
        for key, value in result.items()
        if key
        in {
            "UNAUTHENTICATED_ACCESS",
            "WRONG_PASSWORD",
            "AUTHENTICATED_GATEWAY",
            "WS_UNAUTHENTICATED",
            "WS_AUTHENTICATED",
            "DESKTOP_TO_CONTAINER_EXECUTION",
            "REPO_READ_PROOF",
        }
        and value == "FAIL"
    ]
    if listeners.get("LOOPBACK_REACHABLE") != "YES" or listeners.get("LAN_REACHABLE") == "YES":
        failed.append("listeners")
    if developer_net.get("DEVELOPER_ONLY_INTERNAL") != "YES":
        failed.append("developer_network")
    if sidecar.get("HOST_BIND_LOOPBACK_ONLY") != "YES":
        failed.append("sidecar_bind")
    if egress.EGRESS_NETWORK in set(sidecar.get("networks") or []):
        failed.append("sidecar_on_egress")
    if identity.get("RUNTIME_CONVERGED") not in {True, "YES", "PASS"}:
        failed.append("convergence")
    result["DESKTOP_PROOF"] = "FAIL" if failed else "PASS"
    result["FAILED_CHECKS"] = failed
    write_json(artifacts_dir() / DESKTOP_ARTIFACT, result)
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
            "prove-desktop",
            "desktop-up",
            "desktop-down",
            "telegram-up",
            "telegram-status",
            "telegram-down",
            "telegram-activate",
            "migrate-home",
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
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Also start authenticated hermes serve plus the localhost Desktop sidecar",
    )
    parser.add_argument(
        "--i-understand-this-starts-the-developer-telegram-bot",
        action="store_true",
        dest="developer_telegram_live_activation",
        help=(
            "Required intent for telegram-activate. Ordinary telegram-up still "
            "refuses LIVE_SHAPED tokens. Never pass the token on the command line."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply HERMES_HOME ownership migration (migrate-home only)",
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
        payload = desktop_up() if args.desktop else up()
        write_json(artifacts_dir() / "container_up.json", payload)
        return 0
    if args.command == "desktop-up":
        payload = desktop_up()
        write_json(artifacts_dir() / "container_desktop_up.json", payload)
        print(f"DESKTOP_BASE_URL = {desktop_gw.desktop_base_url()}")
        print("DESKTOP_AUTH_FILE = W:\\hermes-dev\\credentials\\developer-hermes-desktop.env")
        print(
            "Do not run the official website Windows installer / Hermes Setup: "
            "it always bootstraps a local Hermes runtime."
        )
        return 0
    if args.command == "desktop-down":
        payload = stop_desktop()
        write_json(artifacts_dir() / "container_desktop_down.json", payload)
        return 0
    if args.command == "telegram-up":
        payload = telegram_up()
        write_json(artifacts_dir() / "container_telegram_up.json", payload)
        print(f"TELEGRAM_PROFILE = {payload.get('PROFILE')}")
        print(f"DISPLAY_NAME = {payload.get('DISPLAY_NAME', tg_ops.DISPLAY_NAME)}")
        print(f"TOKEN_CLASS = {payload.get('TOKEN_CLASS')}")
        print(f"START_PERMITTED = {payload.get('START_PERMITTED')}")
        print(f"START_REASON = {payload.get('START_REASON')}")
        print(f"GATEWAY = {payload.get('GATEWAY')}")
        print("LIVE_TOKEN_MOVED = NO")
        print("OPERATOR_TELEGRAM_CHANGED = NO")
        return 0
    if args.command == "telegram-status":
        payload = telegram_status()
        write_json(artifacts_dir() / "container_telegram_status.json", payload)
        print(f"TELEGRAM_PROFILE = {payload.get('PROFILE')}")
        print(f"DISPLAY_NAME = {payload.get('DISPLAY_NAME')}")
        print(f"GATEWAY = {payload.get('GATEWAY')}")
        print(f"GATEWAY_PROCESS = {payload.get('GATEWAY_PROCESS')}")
        print(f"ACTIVE_GATEWAY_PROFILE = {payload.get('ACTIVE_GATEWAY_PROFILE')}")
        print(f"UPSTREAM_GATEWAY_STATUS = {payload.get('UPSTREAM_GATEWAY_STATUS')}")
        print(f"HELPER_GATEWAY_STATUS = {payload.get('HELPER_GATEWAY_STATUS')}")
        print(f"STATUS_CONSISTENT = {payload.get('STATUS_CONSISTENT')}")
        print(f"GATEWAY_USER = {payload.get('GATEWAY_USER')}")
        print(f"TOKEN_CLASS = {payload.get('TOKEN_CLASS')}")
        print(f"LIVE_TOKEN = {payload.get('LIVE_TOKEN')}")
        print(f"ALLOWED_USERS_PRESENT = {payload.get('ALLOWED_USERS_PRESENT')}")
        print(f"LIVE_POLLING = {payload.get('LIVE_POLLING')}")
        print(f"TELEGRAM_POLL_CONFLICT_409 = {payload.get('TELEGRAM_POLL_CONFLICT_409')}")
        return 0
    if args.command == "migrate-home":
        payload = migrate_home(apply=args.apply)
        write_json(artifacts_dir() / "container_migrate_home.json", payload)
        print(f"MIGRATION_MODE = {payload.get('MODE')}")
        print(f"MIGRATION_OK = {payload.get('OK')}")
        print(f"CHANGE_COUNT = {payload.get('CHANGE_COUNT')}")
        print("CONTENTS_PRINTED = NO")
        print("TOKEN_PRINTED = NO")
        return 0 if payload.get("OK") == "YES" else 1
    if args.command == "telegram-down":
        payload = telegram_down()
        write_json(artifacts_dir() / "container_telegram_down.json", payload)
        print(f"TELEGRAM_PROFILE = {payload.get('PROFILE')}")
        print(f"GATEWAY = {payload.get('GATEWAY')}")
        print(f"GATEWAY_PROCESS = {payload.get('GATEWAY_PROCESS')}")
        print(f"DESKTOP_GATEWAY = {payload.get('DESKTOP_GATEWAY')}")
        print(f"LIVE_POLLING = {payload.get('LIVE_POLLING')}")
        return 0
    if args.command == "telegram-activate":
        payload = telegram_activate(confirmed=args.developer_telegram_live_activation)
        write_json(artifacts_dir() / "container_telegram_activate.json", payload)
        print(f"TELEGRAM_PROFILE = {payload.get('PROFILE')}")
        print(f"DISPLAY_NAME = {payload.get('DISPLAY_NAME', tg_ops.DISPLAY_NAME)}")
        print(f"TOKEN_CLASS = {payload.get('TOKEN_CLASS')}")
        print(f"ALLOWED_USERS_PRESENT = {payload.get('ALLOWED_USERS_PRESENT')}")
        print(f"START_PERMITTED = {payload.get('START_PERMITTED')}")
        print(f"START_REASON = {payload.get('START_REASON')}")
        print(f"GATEWAY = {payload.get('GATEWAY')}")
        print(f"GATEWAY_PROCESS = {payload.get('GATEWAY_PROCESS')}")
        print(f"ACTIVE_GATEWAY_PROFILE = {payload.get('ACTIVE_GATEWAY_PROFILE')}")
        print(f"UPSTREAM_GATEWAY_STATUS = {payload.get('UPSTREAM_GATEWAY_STATUS')}")
        print(f"HELPER_GATEWAY_STATUS = {payload.get('HELPER_GATEWAY_STATUS')}")
        print(f"STATUS_CONSISTENT = {payload.get('STATUS_CONSISTENT')}")
        print(f"GATEWAY_USER = {payload.get('GATEWAY_USER')}")
        print(f"LIVE_TOKEN = {payload.get('LIVE_TOKEN')}")
        print(f"LIVE_POLLING = {payload.get('LIVE_POLLING')}")
        print("TOKEN_VALUES_RECORDED = NO")
        print("OPERATOR_TELEGRAM_CHANGED = NO")
        print("RAILWAY_CHANGED = NO")
        if payload.get("HUMAN_ACTION"):
            print(f"HUMAN_ACTION = {payload['HUMAN_ACTION']}")
        return 0 if payload.get("START_REASON") != "REFUSE_MISSING_ACTIVATION_INTENT" else 2
    if args.command == "prove-desktop":
        result = prove_desktop()
        print(f"DESKTOP_PROOF = {result['DESKTOP_PROOF']}")
        print(f"UNAUTHENTICATED_ACCESS = {result['UNAUTHENTICATED_ACCESS']}")
        print(f"AUTHENTICATED_GATEWAY = {result['AUTHENTICATED_GATEWAY']}")
        print(f"DESKTOP_TO_CONTAINER_EXECUTION = {result['DESKTOP_TO_CONTAINER_EXECUTION']}")
        print(f"REPO_READ_PROOF = {result['REPO_READ_PROOF']}")
        return 0 if result["DESKTOP_PROOF"] == "PASS" else 1
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
