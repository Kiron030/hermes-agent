"""Logical HERMES_HOME export. Raw Docker Desktop volume paths are forbidden."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from r5_developer_hermes.container.contract import DEVELOPER_IMAGE
from r5_developer_hermes.recovery.contract import (
    HERMES_HOME_VOLUME,
    RAW_DOCKER_DESKTOP_PATH_COPY,
    VOLUME_BACKUP_MECHANISM,
)
from r5_developer_hermes.recovery.docker_state import default_docker_runner
from r5_developer_hermes.recovery.staging import file_sha256


DockerRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]

EXPORT_IMAGE = DEVELOPER_IMAGE
FORBIDDEN_HOST_VOLUME_MARKERS = (
    "dockerdesktopwsl",
    "docker-desktop-data",
    "wsl$",
    "\\wsl",
    "/var/lib/docker/volumes",
    "\\var\\lib\\docker\\volumes",
)


class VolumeExportError(RuntimeError):
    pass


def assert_not_raw_docker_path(path: str) -> None:
    raw = path.lower()
    lowered = raw.replace("/", "\\")
    haystacks = (raw, lowered)
    if any(marker.lower() in blob for blob in haystacks for marker in FORBIDDEN_HOST_VOLUME_MARKERS):
        raise VolumeExportError("raw Docker Desktop volume filesystem copy is forbidden")


def export_hermes_home_logical(
    dest: Path,
    *,
    volume: str = HERMES_HOME_VOLUME,
    image: str = EXPORT_IMAGE,
    runner: DockerRunner | None = None,
) -> dict[str, Any]:
    """Archive the named volume through a helper container. Volume is read-only."""
    docker = runner or default_docker_runner
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "hermes-home.tar"
    assert_not_raw_docker_path(str(dest))
    inspect = docker(["volume", "inspect", "-f", "{{.Name}}", volume])
    if inspect.returncode != 0 or (inspect.stdout or "").strip() != volume:
        raise VolumeExportError("HERMES_HOME volume is missing")
    # Write the archive inside a throwaway container onto a host bind. Do not
    # copy Docker Desktop's raw volume implementation path.
    completed = docker(
        [
            "run",
            "--rm",
            "--user",
            "0:0",
            "-v",
            f"{volume}:/opt/data:ro",
            "-v",
            f"{dest}:/backup",
            image,
            "tar",
            "-C",
            "/opt/data",
            "-cf",
            "/backup/hermes-home.tar",
            ".",
        ]
    )
    if completed.returncode != 0 or not archive.is_file() or archive.stat().st_size <= 0:
        raise VolumeExportError("logical HERMES_HOME export failed")
    return {
        "path": str(archive),
        "volume": volume,
        "mechanism": VOLUME_BACKUP_MECHANISM,
        "raw_docker_desktop_path_copy": RAW_DOCKER_DESKTOP_PATH_COPY,
        "sha256": file_sha256(archive),
        "size": archive.stat().st_size,
    }
