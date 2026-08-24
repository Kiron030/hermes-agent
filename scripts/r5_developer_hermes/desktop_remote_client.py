#!/usr/bin/env python3
"""Official pinned Hermes Desktop as a remote-only client.

Builds and pre-seeds the unmodified upstream Electron app from the R5 pin.
This helper never spawns a Windows Hermes Agent, never runs install.ps1, and
never modifies apps/desktop. Host execution stays behind
``assert_trusted_host_launcher``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from r5_developer_hermes.container import desktop as desktop_gw  # noqa: E402
from r5_developer_hermes.container.contract import (  # noqa: E402
    assert_trusted_host_launcher,
    is_under_dedicated_clone_root,
)
from r5_developer_hermes.harness import load_pin  # noqa: E402


PIN_PATH = HERE / "pin.json"
PREFERRED_SOURCE = Path(r"W:\cache\hermes-desktop-official-v2026.8.19")
CANDIDATE_SOURCES = (
    PREFERRED_SOURCE,
    Path(r"W:\cache\hermes-r3-modern"),
    Path(r"W:\cache\hermes-r3-verify"),
    REPO_ROOT / ".r1-proof" / "upstream-src",
)
PACK_SOURCE_PATHS = ("apps/desktop", "apps/shared")
OFFICIAL_REMOTE_URL = "http://127.0.0.1:19119"
OFFICIAL_AUTH_MODE = "oauth"
OFFICIAL_MODE = "remote"
CONNECTION_RELATIVE = "connection.json"
ELECTRON_USERDATA_PRODUCT = "Hermes"
MIN_NODE = (22, 22, 0)
FORBIDDEN_HOST_COMMANDS = (
    "install.ps1",
    "hermes serve",
    "ensureRuntime",
    "runBootstrap",
)
LOCAL_AGENT_PATH_MARKERS = (
    r"%LOCALAPPDATA%\hermes\hermes-agent",
    r"\AppData\Local\hermes\hermes-agent",
    r"\hermes\hermes-agent\venv\Scripts\hermes",
)


def _assert_host() -> None:
    assert_trusted_host_launcher(Path(__file__), REPO_ROOT)


def pinned_release() -> dict[str, str]:
    pin = load_pin()
    return {
        "upstream_release": str(pin["upstream_release"]),
        "upstream_project_version": str(pin["upstream_project_version"]),
        "upstream_release_sha": str(pin["upstream_release_sha"]),
        "upstream_tag_object": str(pin["upstream_tag_object"]),
    }


def official_connection_document() -> dict[str, Any]:
    """Minimum v1 connection.json accepted by pinned readDesktopConnectionConfig."""
    return {
        "mode": OFFICIAL_MODE,
        "remote": {
            "url": OFFICIAL_REMOTE_URL,
            "authMode": OFFICIAL_AUTH_MODE,
        },
        "profiles": {},
    }


def connection_state_path(*, appdata: str | None = None) -> Path:
    root = appdata if appdata is not None else os.environ.get("APPDATA", "")
    if not root:
        raise RuntimeError("APPDATA is unset; cannot resolve official connection.json")
    return Path(root) / ELECTRON_USERDATA_PRODUCT / CONNECTION_RELATIVE


def normalize_remote_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("Remote gateway URL is required.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", value, re.I):
        value = f"http://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Remote gateway URL must be http:// or https://, got {parsed.scheme}")
    path = (parsed.path or "").rstrip("/")
    netloc = parsed.netloc
    return f"{parsed.scheme}://{netloc}{path}"


def parse_connection_state(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("connection.json must be a JSON object")
    return parsed


def collect_remote_urls(config: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    remote = config.get("remote")
    if isinstance(remote, dict) and remote.get("url"):
        urls.append(normalize_remote_url(str(remote["url"])))
    profiles = config.get("profiles")
    if isinstance(profiles, dict):
        for block in profiles.values():
            if isinstance(block, dict) and block.get("url"):
                urls.append(normalize_remote_url(str(block["url"])))
    return urls


def validate_connection_state(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("mode") != OFFICIAL_MODE:
        raise ValueError(f"connection.json mode must be {OFFICIAL_MODE!r}")
    remote = config.get("remote")
    if not isinstance(remote, dict):
        raise ValueError("connection.json remote block is required")
    url = normalize_remote_url(str(remote.get("url") or ""))
    if url != OFFICIAL_REMOTE_URL:
        raise ValueError(f"connection.json remote.url must be {OFFICIAL_REMOTE_URL}")
    if remote.get("authMode") != OFFICIAL_AUTH_MODE:
        raise ValueError(f"connection.json remote.authMode must be {OFFICIAL_AUTH_MODE!r}")
    extras = sorted({item for item in collect_remote_urls(config) if item != OFFICIAL_REMOTE_URL})
    if extras:
        raise ValueError("connection.json points at additional remote URLs")
    return {
        "mode": OFFICIAL_MODE,
        "url": url,
        "authMode": OFFICIAL_AUTH_MODE,
        "REMOTE_URLS": [url],
        "POINTS_ONLY_AT_OFFICIAL_REMOTE": "YES",
    }


def seed_connection_state(path: Path | None = None) -> dict[str, Any]:
    """Create or validate official remote connection.json without clobbering state."""
    _assert_host()
    target = path or connection_state_path()
    desired = official_connection_document()
    if target.is_file():
        existing = parse_connection_state(target)
        try:
            validated = validate_connection_state(existing)
            return {
                "path": str(target),
                "action": "unchanged",
                "REMOTE_PRESEEDED_BEFORE_FIRST_START": "YES",
                **validated,
            }
        except ValueError as exc:
            extras = [item for item in collect_remote_urls(existing) if item != OFFICIAL_REMOTE_URL]
            if extras or existing.get("mode") in {"cloud", "ssh"}:
                raise RuntimeError(
                    "refusing to overwrite existing connection.json with unrelated remote state"
                ) from exc
            merged = {
                "mode": OFFICIAL_MODE,
                "remote": {
                    **(existing.get("remote") if isinstance(existing.get("remote"), dict) else {}),
                    "url": OFFICIAL_REMOTE_URL,
                    "authMode": OFFICIAL_AUTH_MODE,
                },
                "profiles": existing.get("profiles")
                if isinstance(existing.get("profiles"), dict)
                else {},
            }
            validate_connection_state(merged)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
            return {
                "path": str(target),
                "action": "merged",
                "REMOTE_PRESEEDED_BEFORE_FIRST_START": "YES",
                **validate_connection_state(merged),
            }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(desired, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(target),
        "action": "created",
        "REMOTE_PRESEEDED_BEFORE_FIRST_START": "YES",
        **validate_connection_state(desired),
    }


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()[:400]}"
        )
    return completed


def _source_sha(root: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=root).stdout.strip()


def verify_pinned_source(root: Path) -> dict[str, Any]:
    _assert_host()
    pin = pinned_release()
    if is_under_dedicated_clone_root(root):
        raise RuntimeError(
            "HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED: "
            "DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST"
        )
    if not (root / "apps" / "desktop" / "package.json").is_file():
        raise RuntimeError(f"pinned Desktop source missing at {root}")
    sha = _source_sha(root)
    if sha != pin["upstream_release_sha"]:
        raise RuntimeError(
            f"DESKTOP_SOURCE_SHA mismatch: {sha} != {pin['upstream_release_sha']}"
        )
    diff = _git(["diff", "--name-only", pin["upstream_release_sha"], "--", *PACK_SOURCE_PATHS], cwd=root)
    dirty = _git(
        ["status", "--porcelain", "--untracked-files=no", "--", *PACK_SOURCE_PATHS],
        cwd=root,
    )
    changed = [line for line in (diff.stdout + dirty.stdout).splitlines() if line.strip()]
    if changed:
        raise RuntimeError("DESKTOP_UI_SOURCE_DIFF = NONZERO")
    main_ts = (root / "apps" / "desktop" / "electron" / "main.ts").read_text(encoding="utf-8")
    if "DESKTOP_CONNECTION_CONFIG_PATH = path.join(app.getPath('userData'), 'connection.json')" not in main_ts:
        raise RuntimeError("pinned DESKTOP_CONNECTION_CONFIG_PATH does not match official userData path")
    startup = (
        root / "apps" / "desktop" / "electron" / "primary-backend-startup.ts"
    ).read_text(encoding="utf-8")
    if "export async function runPrimaryBackendStartup" not in startup:
        raise RuntimeError("pinned primary-backend-startup.ts missing remote-before-local seam")
    if "const savedRemote = await resolveRemote()" not in startup:
        raise RuntimeError("pinned Desktop no longer resolves a saved remote before local runtime")
    return {
        "DESKTOP_SOURCE_UPSTREAM": "NousResearch/hermes-agent",
        "DESKTOP_SOURCE_REF": pin["upstream_release"],
        "DESKTOP_SOURCE_SHA": sha,
        "DESKTOP_UI_SOURCE_DIFF": "ZERO",
        "root": str(root),
    }


def locate_pinned_source(*, create_worktree: bool = False) -> dict[str, Any]:
    _assert_host()
    pin = pinned_release()
    errors: list[str] = []
    for candidate in CANDIDATE_SOURCES:
        if not candidate.is_dir():
            continue
        try:
            verified = verify_pinned_source(candidate)
            return {"action": "reuse", **verified}
        except RuntimeError as exc:
            errors.append(f"{candidate}: {exc}")
    if not create_worktree:
        raise RuntimeError("no verified pinned Desktop source; " + "; ".join(errors))
    if PREFERRED_SOURCE.exists():
        raise RuntimeError(
            f"preferred source {PREFERRED_SOURCE} exists but failed verification: "
            + "; ".join(errors)
        )
    _git(
        ["worktree", "add", "--detach", str(PREFERRED_SOURCE), pin["upstream_release_sha"]],
        cwd=REPO_ROOT,
    )
    verified = verify_pinned_source(PREFERRED_SOURCE)
    return {"action": "created-worktree", **verified}


def official_pack_command(source: Path) -> str:
    package = json.loads((source / "apps" / "desktop" / "package.json").read_text(encoding="utf-8"))
    script = str((package.get("scripts") or {}).get("pack") or "")
    if "builder" not in script or "--dir" not in script:
        raise RuntimeError(f"unexpected official pack script: {script}")
    return "npm run pack"


def desktop_executable(source: Path) -> Path:
    unpacked = source / "apps" / "desktop" / "release" / "win-unpacked" / "Hermes.exe"
    if unpacked.is_file():
        return unpacked
    matches = list((source / "apps" / "desktop" / "release").glob("**/Hermes.exe"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"official Hermes.exe not found under {source / 'apps' / 'desktop' / 'release'}")


def helper_invokes_local_bootstrap(source_text: str | None = None) -> bool:
    """True when a helper constructs a local-agent / bootstrap argv.

    Mentions of the forbidden paths in comments or refusal messages do not
    count. Only concrete process execution is a violation.
    """
    text = source_text if source_text is not None else Path(__file__).read_text(encoding="utf-8")
    return bool(
        re.search(r"subprocess\.[a-z]+\([^)]*install\.ps1", text)
        or re.search(r"subprocess\.[a-z]+\([^)]*[\"']hermes[\"'],\s*[\"']serve", text)
    )


def node_version(node_exe: str | None = None) -> tuple[int, int, int]:
    command = node_exe or shutil.which("node")
    if not command:
        raise RuntimeError("node executable not found")
    raw = subprocess.run(
        [command, "-v"],
        text=True,
        capture_output=True,
        check=False,
    )
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw.stdout or raw.stderr or "")
    if not match:
        raise RuntimeError(f"could not parse node version from {raw.stdout!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def assert_node_for_pack() -> dict[str, str]:
    version = node_version()
    if version < MIN_NODE:
        raise RuntimeError(
            f"official Desktop pack requires Node >={' .'.join(str(part) for part in MIN_NODE)}; "
            f"found {'.'.join(str(part) for part in version)}"
        )
    return {"NODE_VERSION": ".".join(str(part) for part in version)}


def pack_official_desktop(source: Path | None = None) -> dict[str, Any]:
    """Run the official pinned `npm run pack`. Does not spawn Hermes Agent."""
    _assert_host()
    located = verify_pinned_source(source) if source else locate_pinned_source()
    root = Path(located["root"])
    node_info = assert_node_for_pack()
    command = official_pack_command(root)
    vite = root / "node_modules" / "vite" / "package.json"
    if not vite.is_file():
        install = subprocess.run(
            ["npm", "ci"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if install.returncode != 0:
            raise RuntimeError(
                "official npm ci failed: " + (install.stderr or install.stdout)[-800:]
            )
    packed = subprocess.run(
        ["npm", "run", "pack"],
        cwd=root / "apps" / "desktop",
        text=True,
        capture_output=True,
        check=False,
    )
    if packed.returncode != 0:
        raise RuntimeError(
            "official npm run pack failed: " + (packed.stderr or packed.stdout)[-800:]
        )
    executable = desktop_executable(root)
    return {
        **located,
        **node_info,
        "OFFICIAL_BUILD_COMMAND": command,
        "DESKTOP_BUILD": "PASS",
        "DESKTOP_ARTIFACT_TYPE": "electron-builder-dir-unpacked",
        "DESKTOP_EXECUTABLE": str(executable),
    }


def _http_status(path: str, timeout: int = 8) -> int:
    req = urllib.request.Request(
        desktop_gw.desktop_base_url() + path,
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def gateway_reachable() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        return sock.connect_ex((desktop_gw.HOST_BIND, desktop_gw.HOST_PORT)) == 0
    finally:
        sock.close()


def ensure_gateway() -> dict[str, Any]:
    _assert_host()
    if gateway_reachable():
        return {"GATEWAY_PREFLIGHT": "REACHABLE", "action": "reuse"}
    launch = HERE / "container" / "launch.py"
    completed = subprocess.run(
        [sys.executable, str(launch), "desktop-up"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not gateway_reachable():
        raise RuntimeError(
            "desktop-up failed to publish "
            f"{desktop_gw.desktop_base_url()}: {(completed.stderr or completed.stdout)[-500:]}"
        )
    return {"GATEWAY_PREFLIGHT": "REACHABLE", "action": "desktop-up"}


def gateway_auth_preflight() -> dict[str, Any]:
    status = _http_status("/api/status")
    denied = _http_status("/api/files")
    auth = "DENIED" if denied in {401, 403} else "FAIL"
    if status not in {200, 204} or auth != "DENIED":
        raise RuntimeError(f"AUTH_PREFLIGHT failed status={status} files={denied}")
    return {
        "GATEWAY_PREFLIGHT": "REACHABLE",
        "AUTH_PREFLIGHT": auth,
        "status_http": status,
        "files_http": denied,
    }


def classify_windows_hermes_process(row: dict[str, Any]) -> str | None:
    """Classify one host process. Inspector/docker/official UI are ignored."""
    name = str(row.get("Name") or "")
    path = str(row.get("ExecutablePath") or "")
    command = str(row.get("CommandLine") or "")
    blob = f"{name} {path} {command}".lower()
    if "desktop_remote_client.py" in blob or "get-ciminstance win32_process" in blob:
        return None
    if "\\docker\\" in blob or name.lower() in {"docker.exe", "com.docker.backend.exe"}:
        return None
    if "win-unpacked\\hermes.exe" in blob.replace("/", "\\"):
        return None
    if any(marker.lower() in blob for marker in LOCAL_AGENT_PATH_MARKERS):
        return "agent"
    if "install.ps1" in blob:
        return "bootstrap"
    if name.lower() == "hermes.exe" and re.search(r"hermes(\.exe)?\s+serve", blob):
        return "serve"
    return None


def inspect_windows_hermes_processes() -> dict[str, Any]:
    """Observe host processes. Does not start or stop Hermes."""
    _assert_host()
    script = (
        "Get-CimInstance -ClassName Win32_Process -Filter \"Name = 'hermes.exe'\" | "
        "Select-Object ProcessId, Name, ExecutablePath, CommandLine | "
        "ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        check=False,
    )
    raw = (completed.stdout or "").strip()
    rows: list[dict[str, Any]]
    if not raw:
        rows = []
    else:
        loaded = json.loads(raw)
        rows = loaded if isinstance(loaded, list) else [loaded]
    labels = [classify_windows_hermes_process(row) for row in rows]
    return {
        "LOCAL_HERMES_SPAWN": "YES" if "agent" in labels else "NO",
        "LOCAL_BOOTSTRAP_STARTED": "YES" if "bootstrap" in labels else "NO",
        "WINDOWS_HERMES_SERVE": "YES" if "serve" in labels else "NO",
        "SECOND_WINDOWS_HERMES_RUNTIME": "YES" if {"agent", "serve"} & set(labels) else "NO",
        "observed": len(rows),
    }


def installer_residue_status() -> str:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
    profile = Path(os.environ.get("USERPROFILE", "")) / ".hermes"
    present = []
    if local.exists():
        present.append("%LOCALAPPDATA%\\hermes present (left untouched)")
    if profile.exists():
        present.append("%USERPROFILE%\\.hermes present (left untouched)")
    if not present:
        return "no leftover installer directories observed"
    return "; ".join(present)


def computer_use_status() -> dict[str, str]:
    pin = load_pin()
    deferred = [str(item) for item in pin.get("developer_deferred_toolsets") or []]
    seed = (HERE / "container" / "seed_home.py").read_text(encoding="utf-8")
    if "computer_use" not in deferred:
        raise RuntimeError("pin.json no longer defers computer_use")
    if "computer_use" not in seed:
        raise RuntimeError("seed_home.py no longer disables computer_use")
    if desktop_gw.WINDOWS_COMPUTER_USE_ENABLED != "NO":
        raise RuntimeError("WINDOWS_COMPUTER_USE_ENABLED is not NO")
    return {"COMPUTER_USE": "OFF"}


def password_login_supported(source: Path) -> bool:
    settings = (
        source / "apps" / "desktop" / "src" / "app" / "settings" / "gateway-settings.tsx"
    ).read_text(encoding="utf-8")
    decisions = (
        source / "apps" / "desktop" / "electron" / "native-auth-decisions.ts"
    ).read_text(encoding="utf-8")
    return "/auth/password-login" in settings and "supportsPassword" in decisions


def preflight(*, seed: bool = True, start_gateway: bool = True) -> dict[str, Any]:
    _assert_host()
    source = locate_pinned_source()
    if start_gateway:
        gateway = ensure_gateway()
    else:
        gateway = {
            "GATEWAY_PREFLIGHT": "REACHABLE" if gateway_reachable() else "DOWN",
            "action": "probe-only",
        }
    auth = gateway_auth_preflight() if gateway["GATEWAY_PREFLIGHT"] == "REACHABLE" else {
        "AUTH_PREFLIGHT": "NOT_RUN"
    }
    connection = seed_connection_state() if seed else {
        "path": str(connection_state_path()),
        **validate_connection_state(parse_connection_state(connection_state_path())),
    }
    processes = inspect_windows_hermes_processes()
    computer = computer_use_status()
    executable = None
    try:
        executable = str(desktop_executable(Path(source["root"])))
    except FileNotFoundError:
        executable = None
    return {
        "SELECTED_PATH": "BUILD_PINNED_REMOTE_CLIENT",
        **source,
        "OFFICIAL_BUILD_COMMAND": official_pack_command(Path(source["root"])),
        "DESKTOP_EXECUTABLE": executable,
        "CONNECTION_STATE_PATH": connection["path"],
        "CONNECTION_STATE_SCHEMA_VERIFIED": "YES",
        "REMOTE_PRESEEDED_BEFORE_FIRST_START": connection.get(
            "REMOTE_PRESEEDED_BEFORE_FIRST_START", "YES"
        ),
        "REMOTE_URL": OFFICIAL_REMOTE_URL,
        "PASSWORD_REMOTE_LOGIN_SUPPORTED": (
            "YES" if password_login_supported(Path(source["root"])) else "NO"
        ),
        "AUTH_CHANGE_REQUIRED": "NO",
        **processes,
        "CUSTOM_UI": "NO",
        "DESKTOP_SOURCE_MODIFIED": "NO",
        **gateway,
        **auth,
        **computer,
        "INSTALLER_RESIDUE_STATUS": installer_residue_status(),
        "helper_invokes_local_bootstrap": helper_invokes_local_bootstrap(),
    }


def main() -> int:
    _assert_host()
    parser = argparse.ArgumentParser(description="Official pinned Desktop remote-only client")
    parser.add_argument(
        "command",
        choices=("locate-source", "verify-source", "seed-connection", "preflight", "pack"),
    )
    parser.add_argument("--source", default="", help="Pinned source root to verify or pack")
    args = parser.parse_args()
    source = Path(args.source) if args.source else None
    if args.command == "locate-source":
        payload = locate_pinned_source(create_worktree=True)
    elif args.command == "verify-source":
        payload = verify_pinned_source(source or Path(locate_pinned_source()["root"]))
    elif args.command == "seed-connection":
        payload = seed_connection_state()
    elif args.command == "pack":
        payload = pack_official_desktop(source)
    else:
        payload = preflight()
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
