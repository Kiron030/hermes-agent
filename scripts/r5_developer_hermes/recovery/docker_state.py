"""Host-side read-only Docker inspection for Developer recovery.

Never inspects the Docker socket from inside Developer. Never mutates
containers, images, or volumes.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable

from r5_developer_hermes.container.contract import (
    CONTAINER_NAME,
    DEVELOPER_IMAGE,
    IMAGE_LABEL_CONTRACT_VERSION,
    IMAGE_LABEL_HERMES_BASE_DIGEST,
    PINNED_DIGEST,
    RUNTIME_GID,
    RUNTIME_UID,
    WINDOWS_DOCKER_EXE,
    sanitize_container_inspect,
)
from r5_developer_hermes.recovery.contract import (
    HERMES_HOME_VOLUME,
    NAMED_VOLUMES,
    REQUIRED_NAMED_VOLUMES,
    RUNTIME_USER,
)


DockerRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]

TELEGRAM_METADATA_PY = (
    "import json,os;"
    "p='/opt/data/profiles/telegram-ops/.env';"
    "d={'exists':os.path.isfile(p),'filename':'.env'};"
    "d.update({'size':os.stat(p).st_size,'uid':os.stat(p).st_uid,"
    "'gid':os.stat(p).st_gid,'mode':oct(os.stat(p).st_mode)[-3:]} ) "
    "if d['exists'] else None;"
    "print(json.dumps(d))"
)


def default_docker_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    from shutil import which

    exe = which("docker") or (str(WINDOWS_DOCKER_EXE) if WINDOWS_DOCKER_EXE.is_file() else "docker")
    try:
        return subprocess.run([exe, *args], text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["docker", *args], 127, "", "docker not found")


@dataclass
class DockerSnapshot:
    volumes_present: dict[str, bool] = field(default_factory=dict)
    developer_container_exists: bool = False
    developer_container_running: bool = False
    image: str = ""
    image_id: str = ""
    user: str = ""
    labels: dict[str, str] = field(default_factory=dict)
    telegram_slot: dict[str, Any] | None = None
    hermes_home_volume_present: bool = False
    runtime_uid_gid_ok: bool | None = None
    upstream_pin_ok: bool | None = None
    image_contract_ok: bool | None = None
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "volumes_present": dict(self.volumes_present),
            "developer_container_exists": self.developer_container_exists,
            "developer_container_running": self.developer_container_running,
            "image": self.image,
            "image_id": self.image_id,
            "user": self.user,
            "labels": dict(self.labels),
            "telegram_slot_inspected": self.telegram_slot is not None,
            "hermes_home_volume_present": self.hermes_home_volume_present,
            "runtime_uid_gid_ok": self.runtime_uid_gid_ok,
            "upstream_pin_ok": self.upstream_pin_ok,
            "image_contract_ok": self.image_contract_ok,
            "findings": list(self.findings),
        }


def _parse_user(user: str) -> tuple[int | None, int | None]:
    raw = (user or "").strip()
    if not raw or raw == RUNTIME_USER:
        return None, None
    if ":" in raw:
        uid_s, _, gid_s = raw.partition(":")
        try:
            return int(uid_s), int(gid_s)
        except ValueError:
            return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, None


def inspect_docker(
    *,
    runner: DockerRunner | None = None,
    expected_contract_version: str,
    inspect_payload: dict[str, Any] | None = None,
    volumes_present: dict[str, bool] | None = None,
    telegram_meta: dict[str, Any] | None = None,
) -> DockerSnapshot:
    docker = runner or default_docker_runner
    snapshot = DockerSnapshot()

    if volumes_present is not None:
        snapshot.volumes_present = dict(volumes_present)
    else:
        for item in NAMED_VOLUMES:
            name = item["name"]
            completed = docker(["volume", "inspect", "-f", "{{.Name}}", name])
            snapshot.volumes_present[name] = (
                completed.returncode == 0 and (completed.stdout or "").strip() == name
            )

    snapshot.hermes_home_volume_present = bool(
        snapshot.volumes_present.get(HERMES_HOME_VOLUME)
    )
    if not snapshot.hermes_home_volume_present:
        snapshot.findings.append("MISSING_HERMES_HOME_VOLUME")

    payload = inspect_payload
    if payload is None:
        completed = docker(["inspect", CONTAINER_NAME])
        if completed.returncode == 0 and (completed.stdout or "").strip():
            try:
                parsed = json.loads(completed.stdout)
                payload = parsed[0] if isinstance(parsed, list) else parsed
            except json.JSONDecodeError:
                payload = None

    if payload:
        safe = sanitize_container_inspect(payload)
        snapshot.developer_container_exists = True
        snapshot.developer_container_running = bool(
            ((payload.get("State") or {}).get("Running"))
        )
        snapshot.image = str(safe.get("image") or "")
        snapshot.image_id = str(safe.get("image_id") or "")
        snapshot.user = str(safe.get("user") or "")
        snapshot.labels = dict(safe.get("labels") or {})
        uid, gid = _parse_user(snapshot.user)
        if uid is None and snapshot.user in {"", RUNTIME_USER}:
            snapshot.runtime_uid_gid_ok = True
        elif uid == RUNTIME_UID and (gid in {None, RUNTIME_GID}):
            snapshot.runtime_uid_gid_ok = True
        else:
            snapshot.runtime_uid_gid_ok = False
            snapshot.findings.append("WRONG_RUNTIME_UID_GID")
        label_digest = snapshot.labels.get(IMAGE_LABEL_HERMES_BASE_DIGEST, "")
        if label_digest and label_digest != PINNED_DIGEST:
            snapshot.upstream_pin_ok = False
            snapshot.findings.append("STALE_OR_WRONG_UPSTREAM_PIN")
        elif label_digest:
            snapshot.upstream_pin_ok = True
        label_contract = snapshot.labels.get(IMAGE_LABEL_CONTRACT_VERSION, "")
        if label_contract and label_contract != expected_contract_version:
            snapshot.image_contract_ok = False
            snapshot.findings.append("STALE_OR_WRONG_IMAGE_CONTRACT")
        elif label_contract:
            snapshot.image_contract_ok = True
        if snapshot.image and snapshot.image not in {DEVELOPER_IMAGE, ""}:
            if DEVELOPER_IMAGE not in snapshot.image and PINNED_DIGEST not in snapshot.image:
                snapshot.findings.append("UNEXPECTED_DEVELOPER_IMAGE")
    else:
        snapshot.developer_container_exists = False

    if telegram_meta is not None:
        snapshot.telegram_slot = telegram_meta
    elif snapshot.developer_container_running:
        completed = docker(
            [
                "exec",
                "--user",
                f"{RUNTIME_UID}:{RUNTIME_GID}",
                CONTAINER_NAME,
                "/opt/hermes/.venv/bin/python",
                "-c",
                TELEGRAM_METADATA_PY,
            ]
        )
        if completed.returncode == 0 and (completed.stdout or "").strip():
            try:
                snapshot.telegram_slot = json.loads(completed.stdout)
            except json.JSONDecodeError:
                snapshot.telegram_slot = None
    return snapshot


def required_volume_findings(snapshot: DockerSnapshot) -> list[str]:
    findings = list(snapshot.findings)
    for name in REQUIRED_NAMED_VOLUMES:
        if not snapshot.volumes_present.get(name):
            if "MISSING_HERMES_HOME_VOLUME" not in findings and name == HERMES_HOME_VOLUME:
                findings.append("MISSING_HERMES_HOME_VOLUME")
    return findings
