"""Narrow Developer runtime stop/start for a consistent HERMES_HOME snapshot.

Stops only local Developer writers. Does not tear down egress, does not
touch Operator Hermes or Railway, and never removes the named volume.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from r5_developer_hermes.container.contract import CONTAINER_NAME
from r5_developer_hermes.recovery.docker_state import default_docker_runner


DockerRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
LaunchFn = Callable[[], Mapping[str, Any]]


@dataclass
class RuntimeWindow:
    container_was_running: bool = False
    desktop_was_running: bool = False
    telegram_was_live: bool = False
    stopped: bool = False
    restarted: bool = False
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "container_was_running": self.container_was_running,
            "desktop_was_running": self.desktop_was_running,
            "telegram_was_live": self.telegram_was_live,
            "stopped": self.stopped,
            "restarted": self.restarted,
            "findings": list(self.findings),
        }


def _running(docker: DockerRunner, name: str) -> bool:
    completed = docker(["inspect", "-f", "{{.State.Running}}", name])
    return completed.returncode == 0 and (completed.stdout or "").strip() == "true"


def observe_runtime(*, docker: DockerRunner | None = None, telegram_status: Mapping[str, Any] | None = None) -> RuntimeWindow:
    runner = docker or default_docker_runner
    window = RuntimeWindow()
    window.container_was_running = _running(runner, CONTAINER_NAME)
    window.desktop_was_running = _running(runner, "r5-desktop-sidecar")
    if telegram_status is not None:
        window.telegram_was_live = str(telegram_status.get("LIVE_POLLING") or "") == "YES"
    return window


def stop_for_snapshot(
    window: RuntimeWindow,
    *,
    docker: DockerRunner | None = None,
    telegram_down: LaunchFn | None = None,
    desktop_down: LaunchFn | None = None,
) -> RuntimeWindow:
    runner = docker or default_docker_runner
    if window.telegram_was_live and telegram_down is not None:
        telegram_down()
    if window.desktop_was_running and desktop_down is not None:
        desktop_down()
    if window.container_was_running:
        # stop, do not rm, do not down (down tears egress).
        completed = runner(["stop", CONTAINER_NAME])
        if completed.returncode != 0:
            window.findings.append("DEVELOPER_STOP_FAILED")
            raise RuntimeError("failed to stop Developer container for consistent snapshot")
    window.stopped = True
    return window


def restart_after_snapshot(
    window: RuntimeWindow,
    *,
    docker: DockerRunner | None = None,
    developer_up: LaunchFn | None = None,
    desktop_up: LaunchFn | None = None,
    telegram_activate: LaunchFn | None = None,
) -> RuntimeWindow:
    runner = docker or default_docker_runner
    if window.container_was_running:
        if developer_up is not None:
            developer_up()
        else:
            started = runner(["start", CONTAINER_NAME])
            if started.returncode != 0:
                window.findings.append("DEVELOPER_START_FAILED")
                raise RuntimeError("failed to restart Developer container after snapshot")
    if window.desktop_was_running and desktop_up is not None:
        desktop_up()
    if window.telegram_was_live and telegram_activate is not None:
        telegram_activate()
    window.restarted = True
    return window
