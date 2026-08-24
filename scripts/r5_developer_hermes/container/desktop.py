"""Official Hermes Desktop remote-gateway contract for Developer Hermes.

This is inbound UI transport only. It does not add host filesystem, Docker
socket, host-network, Computer Use, or a second outbound Internet route.

The Developer container stays on the internal-only network. A localhost-only
authenticated sidecar is the dual-homed party and publishes 127.0.0.1.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any


CONTAINER_DIR = Path(__file__).resolve().parent

SIDECAR_CONTAINER_NAME = "r5-desktop-sidecar"
INGRESS_NETWORK = "r5-desktop-ingress"
HOST_BIND = "127.0.0.1"
HOST_PORT = 19119
CONTAINER_SERVE_PORT = 9119
SIDECAR_LISTEN_PORT = 9119
BACKEND_DNS_NAME = "r5-developer-hermes"
SIDECAR_SCRIPT_CONTAINER_PATH = "/tmp/r5_desktop_sidecar.py"
SIDECAR_SCRIPT_HOST_PATH = CONTAINER_DIR / "desktop_sidecar.py"

DESKTOP_AUTH_FILE = Path(r"W:\hermes-dev\credentials\developer-hermes-desktop.env")
DESKTOP_USERNAME = "developer"
AUTH_PROVIDER = "basic"

HERMES_SERVE_BIN = "/opt/hermes/.venv/bin/hermes"
HERMES_SERVE_HOST = "0.0.0.0"
FILES_ROOT = "/workspace"
PROOF_DOC_RELATIVE = "hermes-agent/scripts/r5_developer_hermes/pin.json"
PROOF_DOC_MARKER = "POWERFUL_IN_WORKSPACE"

LABEL_DESKTOP_ROLE = "io.powerunits.r5.desktop-role"
LABEL_DESKTOP_HOST_BIND = "io.powerunits.r5.desktop-host-bind"
LABEL_DESKTOP_HOST_PORT = "io.powerunits.r5.desktop-host-port"

DESKTOP_CONTAINER_COMPATIBILITY = "OFFICIAL_REMOTE_GATEWAY"
DESKTOP_TRANSPORT = "LOCALHOST_SIDECAR"
DESKTOP_CLASSIFICATION = "MATERIAL"
WINDOWS_COMPUTER_USE_ENABLED = "NO"


def desktop_auth_env_names() -> tuple[str, ...]:
    return (
        "HERMES_DASHBOARD_BASIC_AUTH_USERNAME",
        "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD",
        "HERMES_DASHBOARD_BASIC_AUTH_SECRET",
        "HERMES_DASHBOARD_FILES_ROOT",
    )


def parse_desktop_auth_file(path: Path | None = None) -> dict[str, str]:
    """Load the host-only Desktop gateway credential file. Values stay local."""
    target = path or DESKTOP_AUTH_FILE
    if not target.is_file():
        return {}
    parsed: dict[str, str] = {}
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError(f"invalid desktop credential line in {target.name}")
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in {
            "HERMES_DASHBOARD_BASIC_AUTH_USERNAME",
            "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD",
            "HERMES_DASHBOARD_BASIC_AUTH_SECRET",
        }:
            raise RuntimeError(f"refusing non-allowlisted desktop credential key: {key}")
        if key in parsed:
            raise RuntimeError(f"duplicate desktop credential key: {key}")
        parsed[key] = value.strip().strip('"').strip("'")
    return parsed


def ensure_desktop_auth(path: Path | None = None) -> dict[str, str]:
    """Read, or mint once, the Desktop gateway username/password/signing secret.

    Persisted next to the dedicated model and egress credentials under the
    host-only secret root that is never mounted into any container.
    """
    target = path or DESKTOP_AUTH_FILE
    existing = parse_desktop_auth_file(target) if target.is_file() else {}
    username = existing.get("HERMES_DASHBOARD_BASIC_AUTH_USERNAME") or DESKTOP_USERNAME
    password = existing.get("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD") or ""
    secret = existing.get("HERMES_DASHBOARD_BASIC_AUTH_SECRET") or ""
    if not password:
        password = secrets.token_urlsafe(24)
    if not secret:
        secret = secrets.token_hex(32)
    payload = (
        "HERMES_DASHBOARD_BASIC_AUTH_USERNAME="
        f"{username}\n"
        "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD="
        f"{password}\n"
        "HERMES_DASHBOARD_BASIC_AUTH_SECRET="
        f"{secret}\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload, encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return {
        "HERMES_DASHBOARD_BASIC_AUTH_USERNAME": username,
        "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD": password,
        "HERMES_DASHBOARD_BASIC_AUTH_SECRET": secret,
    }


def desktop_auth_status(path: Path | None = None) -> dict[str, str]:
    target = path or DESKTOP_AUTH_FILE
    parsed = parse_desktop_auth_file(target) if target.is_file() else {}
    present = bool(
        parsed.get("HERMES_DASHBOARD_BASIC_AUTH_USERNAME")
        and parsed.get("HERMES_DASHBOARD_BASIC_AUTH_PASSWORD")
        and parsed.get("HERMES_DASHBOARD_BASIC_AUTH_SECRET")
    )
    return {
        "DESKTOP_AUTH_FILE_PRESENT": "YES" if present else "NO",
        "DESKTOP_AUTH_FILE_PATH": str(target),
        "AUTH_MECHANISM": "dashboard.basic_auth",
        "AUTH_PROVIDER": AUTH_PROVIDER,
        "CREDENTIAL_VALUES_RECORDED": "NO",
    }


def sidecar_run_argv(
    *,
    image: str,
    name: str = SIDECAR_CONTAINER_NAME,
) -> list[str]:
    """Deterministic sidecar argv. No repos, secrets, socket, or host net."""
    return [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--user",
        "0:0",
        "--privileged=false",
        "--security-opt",
        "no-new-privileges:true",
        "--sysctl",
        "net.ipv4.ip_forward=0",
        "--network",
        INGRESS_NETWORK,
        "--publish",
        f"{HOST_BIND}:{HOST_PORT}:{SIDECAR_LISTEN_PORT}",
        "--env",
        f"R5_DESKTOP_BACKEND_HOST={BACKEND_DNS_NAME}",
        "--env",
        f"R5_DESKTOP_BACKEND_PORT={CONTAINER_SERVE_PORT}",
        "--env",
        f"R5_DESKTOP_LISTEN_PORT={SIDECAR_LISTEN_PORT}",
        "--label",
        f"{LABEL_DESKTOP_ROLE}=inbound-sidecar",
        "--label",
        f"{LABEL_DESKTOP_HOST_BIND}={HOST_BIND}",
        "--label",
        f"{LABEL_DESKTOP_HOST_PORT}={HOST_PORT}",
        "--entrypoint",
        "python3",
        image,
        SIDECAR_SCRIPT_CONTAINER_PATH,
    ]


def sidecar_publish_spec() -> str:
    return f"{HOST_BIND}:{HOST_PORT}:{SIDECAR_LISTEN_PORT}"


def desktop_base_url() -> str:
    return f"http://{HOST_BIND}:{HOST_PORT}"


def ingress_create_argv() -> list[str]:
    """Non-internal ingress network with masquerade disabled.

    Port publish needs a non-internal network. Disabling masquerade keeps
    this network from becoming a second NAT path to the Internet.
    """
    return [
        "docker",
        "network",
        "create",
        "--driver",
        "bridge",
        "--opt",
        "com.docker.network.bridge.enable_ip_masquerade=false",
        INGRESS_NETWORK,
    ]


def classify_sidecar_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    """Metadata-only sidecar trust check. Env values are discarded."""
    host_config = payload.get("HostConfig") or {}
    config = payload.get("Config") or {}
    mounts = payload.get("Mounts") or []
    ports = (payload.get("NetworkSettings") or {}).get("Ports") or {}
    networks = sorted(
        str(name)
        for name in ((payload.get("NetworkSettings") or {}).get("Networks") or {})
    )
    published: list[dict[str, str]] = []
    for container_port, bindings in ports.items():
        if not bindings:
            continue
        for binding in bindings:
            published.append(
                {
                    "container_port": str(container_port),
                    "host_ip": str(binding.get("HostIp") or ""),
                    "host_port": str(binding.get("HostPort") or ""),
                }
            )
    bind_sources = [
        str(item.get("Source") or "")
        for item in mounts
        if str(item.get("Type") or "").lower() == "bind"
    ]
    env_names = sorted(
        item.split("=", 1)[0]
        for item in (config.get("Env") or [])
        if isinstance(item, str) and item
    )
    return {
        "name": config.get("Hostname") or SIDECAR_CONTAINER_NAME,
        "image": config.get("Image") or payload.get("Image"),
        "privileged": bool(host_config.get("Privileged")),
        "network_mode": host_config.get("NetworkMode") or "",
        "pid_mode": host_config.get("PidMode") or "",
        "published": published,
        "networks": networks,
        "bind_sources": bind_sources,
        "env_names": env_names,
        "HOST_BIND_LOOPBACK_ONLY": (
            "YES"
            if published
            and all(item["host_ip"] == HOST_BIND for item in published)
            else "NO"
        ),
        "HOST_BINDS_PRESENT": "YES" if bind_sources else "NO",
        "DOCKER_SOCKET": (
            "YES"
            if any("docker.sock" in source or "docker_engine" in source for source in bind_sources)
            else "NO"
        ),
        "HOST_NETWORK": "YES" if host_config.get("NetworkMode") == "host" else "NO",
        "PRIVILEGED": "YES" if host_config.get("Privileged") else "NO",
    }
