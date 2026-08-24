"""Focused Desktop 0A contract: official remote gateway, loopback sidecar."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from r5_developer_hermes.container import desktop as desktop_gw
from r5_developer_hermes.container.contract import (
    AUTHORITY_ENV_NAMES,
    BIND_MOUNTS,
    DESKTOP_CONTAINER_COMPATIBILITY,
    DEVELOPER_IMAGE,
    docker_run_argv,
)
from r5_developer_hermes.container.egress import host as egress
from r5_developer_hermes.harness import REPO_ROOT


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"
LAUNCHER = CONTAINER_DIR / "launch-developer-hermes.ps1"


def test_desktop_compatibility_is_official_remote_gateway() -> None:
    assert DESKTOP_CONTAINER_COMPATIBILITY == "OFFICIAL_REMOTE_GATEWAY"
    assert desktop_gw.DESKTOP_TRANSPORT == "LOCALHOST_SIDECAR"
    assert desktop_gw.DESKTOP_CLASSIFICATION == "MATERIAL"
    assert desktop_gw.WINDOWS_COMPUTER_USE_ENABLED == "NO"
    assert desktop_gw.HOST_BIND == "127.0.0.1"
    assert desktop_gw.HOST_PORT == 19119
    assert desktop_gw.HERMES_SERVE_HOST == "0.0.0.0"


def test_default_developer_argv_still_has_no_published_port() -> None:
    argv = docker_run_argv()
    assert "--publish" not in argv
    assert "-p" not in argv
    assert argv[argv.index("--network") + 1] == egress.INTERNAL_NETWORK
    assert "--privileged=false" in argv
    assert "host" not in argv[argv.index("--network") + 1]


def test_sidecar_argv_is_loopback_only_and_has_no_host_authority() -> None:
    argv = desktop_gw.sidecar_run_argv(image=DEVELOPER_IMAGE)
    joined = " ".join(argv)
    assert argv[:3] == ["docker", "run", "--detach"]
    assert "--publish" in argv
    assert argv[argv.index("--publish") + 1] == desktop_gw.sidecar_publish_spec()
    assert argv[argv.index("--publish") + 1].startswith("127.0.0.1:")
    assert "--privileged=false" in argv
    assert argv[argv.index("--sysctl") + 1] == "net.ipv4.ip_forward=0"
    assert "--network" in argv
    assert argv[argv.index("--network") + 1] == desktop_gw.INGRESS_NETWORK
    assert argv[argv.index("--network") + 1] != "host"
    assert "type=bind" not in joined
    assert "/var/run/docker.sock" not in joined
    assert r"\\.\pipe\docker_engine" not in joined
    assert "C:\\Users" not in joined
    assert "W:\\Workbench" not in joined
    for source, _dst in BIND_MOUNTS:
        assert source not in joined
    for name in AUTHORITY_ENV_NAMES:
        assert name not in joined
    assert "OPENAI_API_KEY" not in joined
    assert "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD" not in joined


def test_ingress_network_disables_masquerade() -> None:
    argv = desktop_gw.ingress_create_argv()
    assert "com.docker.network.bridge.enable_ip_masquerade=false" in argv
    assert "--internal" not in argv
    assert desktop_gw.INGRESS_NETWORK == "r5-desktop-ingress"


def test_desktop_auth_file_refuses_unknown_and_duplicate_keys(tmp_path: Path) -> None:
    good = tmp_path / "desktop.env"
    minted = desktop_gw.ensure_desktop_auth(good)
    assert minted["HERMES_DASHBOARD_BASIC_AUTH_USERNAME"] == "developer"
    assert minted["HERMES_DASHBOARD_BASIC_AUTH_PASSWORD"]
    assert minted["HERMES_DASHBOARD_BASIC_AUTH_SECRET"]
    again = desktop_gw.ensure_desktop_auth(good)
    assert again == minted

    extra = tmp_path / "extra.env"
    extra.write_text("NOT_A_DESKTOP_KEY=nope\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="non-allowlisted"):
        desktop_gw.parse_desktop_auth_file(extra)

    dup = tmp_path / "dup.env"
    dup.write_text(
        "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=developer\n"
        "HERMES_DASHBOARD_BASIC_AUTH_USERNAME=other\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="duplicate"):
        desktop_gw.parse_desktop_auth_file(dup)


def test_sidecar_inspect_classifier_rejects_non_loopback_publish() -> None:
    payload = {
        "Config": {"Image": DEVELOPER_IMAGE, "Env": ["R5_DESKTOP_BACKEND_HOST=x"]},
        "HostConfig": {"Privileged": False, "NetworkMode": desktop_gw.INGRESS_NETWORK},
        "NetworkSettings": {
            "Networks": {desktop_gw.INGRESS_NETWORK: {}, egress.INTERNAL_NETWORK: {}},
            "Ports": {"9119/tcp": [{"HostIp": "0.0.0.0", "HostPort": "19119"}]},
        },
        "Mounts": [],
    }
    classified = desktop_gw.classify_sidecar_inspect(payload)
    assert classified["HOST_BIND_LOOPBACK_ONLY"] == "NO"
    assert classified["PRIVILEGED"] == "NO"
    assert classified["HOST_NETWORK"] == "NO"
    assert classified["DOCKER_SOCKET"] == "NO"


def test_launcher_exposes_opt_in_desktop_mode() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "desktop" in text
    assert "desktop-up" in text
    launch_py = (CONTAINER_DIR / "launch.py").read_text(encoding="utf-8")
    assert "prove-desktop" in launch_py
    assert "--desktop" in launch_py
    assert "desktop_up" in launch_py
    assert "website Windows installer" in launch_py
    readme = (REPO_ROOT / "scripts" / "r5_developer_hermes" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "bootstrap-installer" in readme
    assert "HERMES_DESKTOP_REMOTE_URL" in readme
    sidecar = (CONTAINER_DIR / "desktop_sidecar.py").read_text(encoding="utf-8")
    assert "create_connection" in sidecar
    assert "HTTP CONNECT" in sidecar or "not an HTTP CONNECT" in sidecar.lower() or "not an HTTP" in sidecar


def test_sidecar_upstream_is_fixed_and_not_a_generic_proxy() -> None:
    """Destination comes from launch env only. Clients cannot pick a relay dest."""
    assert set(inspect.signature(desktop_gw.sidecar_run_argv).parameters) == {"image", "name"}
    argv = desktop_gw.sidecar_run_argv(image=DEVELOPER_IMAGE)
    env_vals = [argv[index + 1] for index, item in enumerate(argv) if item == "--env"]
    assert env_vals == [
        f"R5_DESKTOP_BACKEND_HOST={desktop_gw.BACKEND_DNS_NAME}",
        f"R5_DESKTOP_BACKEND_PORT={desktop_gw.CONTAINER_SERVE_PORT}",
        f"R5_DESKTOP_LISTEN_PORT={desktop_gw.SIDECAR_LISTEN_PORT}",
    ]
    assert desktop_gw.BACKEND_DNS_NAME == "r5-developer-hermes"
    assert desktop_gw.CONTAINER_SERVE_PORT == 9119

    source = (CONTAINER_DIR / "desktop_sidecar.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    assert imported <= {"__future__", "os", "socket", "threading"}

    create_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_connection"
    ]
    assert len(create_calls) == 1
    dest = create_calls[0].args[0]
    assert isinstance(dest, ast.Tuple)
    names = [elt.id for elt in dest.elts if isinstance(elt, ast.Name)]
    assert names == ["BACKEND_HOST", "BACKEND_PORT"]

    assert "argparse" not in source
    assert "sys.argv" not in source
    assert "socks" not in source.lower()
    assert "urllib" not in source
    assert "requests" not in source
    assert source.count("CONNECT") == 1
    assert "not an HTTP CONNECT" in source


def test_docs_state_official_desktop_remote_gateway() -> None:
    arch = (
        REPO_ROOT
        / "docs"
        / "architecture"
        / "hermes_r5_developer_hermes_v1.md"
    ).read_text(encoding="utf-8")
    dx = (REPO_ROOT / "docs" / "architecture" / "hermes_r5_developer_dx_v1.md").read_text(
        encoding="utf-8"
    )
    assert "OFFICIAL_REMOTE_GATEWAY" in arch or "OFFICIAL_REMOTE_GATEWAY" in dx
    assert "Computer Use" in dx or "computer_use" in dx.lower()
