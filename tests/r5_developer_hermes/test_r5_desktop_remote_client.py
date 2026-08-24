"""Official pinned Desktop remote-only client helpers stay off the local bootstrap path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from r5_developer_hermes.container.contract import (
    assert_trusted_host_launcher,
    is_under_dedicated_clone_root,
)
from r5_developer_hermes.desktop_remote_client import (
    CANDIDATE_SOURCES,
    FORBIDDEN_HOST_COMMANDS,
    OFFICIAL_AUTH_MODE,
    OFFICIAL_REMOTE_URL,
    PACK_SOURCE_PATHS,
    PREFERRED_SOURCE,
    classify_windows_hermes_process,
    connection_state_path,
    helper_invokes_local_bootstrap,
    official_connection_document,
    official_pack_command,
    password_login_supported,
    pinned_release,
    seed_connection_state,
    validate_connection_state,
)
from r5_developer_hermes.harness import REPO_ROOT


HELPER = REPO_ROOT / "scripts" / "r5_developer_hermes" / "desktop_remote_client.py"
PINNED_STARTUP = (
    "export async function runPrimaryBackendStartup"
)


def test_helper_does_not_construct_local_bootstrap_argv() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert helper_invokes_local_bootstrap(text) is False
    assert "assert_trusted_host_launcher" in text
    assert "DEDICATED_CONTAINER_CLONES" in text or "is_under_dedicated_clone_root" in text
    for command in FORBIDDEN_HOST_COMMANDS:
        assert f"subprocess.run([{command!r}" not in text
        assert f'subprocess.run(["{command}"' not in text


def test_official_connection_schema_is_remote_oauth_only() -> None:
    document = official_connection_document()
    validated = validate_connection_state(document)
    assert validated["url"] == OFFICIAL_REMOTE_URL
    assert validated["authMode"] == OFFICIAL_AUTH_MODE
    assert validated["POINTS_ONLY_AT_OFFICIAL_REMOTE"] == "YES"
    with pytest.raises(ValueError, match="additional remote"):
        validate_connection_state(
            {
                "mode": "remote",
                "remote": {"url": OFFICIAL_REMOTE_URL, "authMode": "oauth"},
                "profiles": {
                    "other": {"mode": "remote", "url": "http://127.0.0.1:9", "authMode": "oauth"}
                },
            }
        )


def test_seed_connection_creates_and_refuses_unrelated_remote(tmp_path: Path) -> None:
    target = tmp_path / "Hermes" / "connection.json"
    created = seed_connection_state(target)
    assert created["action"] == "created"
    assert json.loads(target.read_text(encoding="utf-8")) == official_connection_document()
    again = seed_connection_state(target)
    assert again["action"] == "unchanged"

    local_only = tmp_path / "local.json"
    local_only.write_text(
        json.dumps({"mode": "local", "remote": {}, "profiles": {"keep": {}}}),
        encoding="utf-8",
    )
    merged = seed_connection_state(local_only)
    assert merged["action"] == "merged"
    payload = json.loads(local_only.read_text(encoding="utf-8"))
    assert payload["mode"] == "remote"
    assert payload["profiles"] == {"keep": {}}

    conflict = tmp_path / "conflict.json"
    conflict.write_text(
        json.dumps(
            {
                "mode": "remote",
                "remote": {"url": "https://example.test", "authMode": "oauth"},
                "profiles": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        seed_connection_state(conflict)


def test_connection_path_is_official_userdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert connection_state_path() == tmp_path / "Hermes" / "connection.json"


def test_pin_and_pack_command_stay_on_exact_upstream() -> None:
    pin = pinned_release()
    assert pin["upstream_release"] == "v2026.8.19"
    assert pin["upstream_release_sha"] == "fcbd1076a93841fa88855acce810e342a5b78101"
    assert pin["upstream_project_version"] == "0.20.5"
    assert "hermes-desktop-official-v2026.8.19" in str(PREFERRED_SOURCE)
    assert all(not is_under_dedicated_clone_root(path) for path in CANDIDATE_SOURCES)
    assert PACK_SOURCE_PATHS == ("apps/desktop", "apps/shared")
    source = next((path for path in CANDIDATE_SOURCES if (path / "apps" / "desktop" / "package.json").is_file()), None)
    if source is None:
        pytest.skip("pinned Desktop source is not on this host")
    assert official_pack_command(source) == "npm run pack"
    package = json.loads((source / "apps" / "desktop" / "package.json").read_text(encoding="utf-8"))
    assert "--dir" in package["scripts"]["pack"]
    assert "--publish never" in package["scripts"]["pack"]
    startup = (source / "apps" / "desktop" / "electron" / "primary-backend-startup.ts").read_text(
        encoding="utf-8"
    )
    assert PINNED_STARTUP in startup
    assert "ensureLocalRuntime" in startup
    assert "const savedRemote = await resolveRemote()" in startup
    assert password_login_supported(source) is True


def test_process_classifier_ignores_inspector_docker_and_official_ui() -> None:
    assert (
        classify_windows_hermes_process(
            {
                "Name": "powershell.exe",
                "CommandLine": "Get-CimInstance Win32_Process desktop_remote_client.py",
            }
        )
        is None
    )
    assert (
        classify_windows_hermes_process(
            {"Name": "docker.exe", "CommandLine": "docker exec hermes serve"}
        )
        is None
    )
    assert (
        classify_windows_hermes_process(
            {
                "Name": "Hermes.exe",
                "ExecutablePath": r"W:\cache\hermes-desktop-official-v2026.8.19\apps\desktop\release\win-unpacked\Hermes.exe",
            }
        )
        is None
    )
    assert (
        classify_windows_hermes_process(
            {
                "Name": "hermes.exe",
                "ExecutablePath": r"C:\Users\User\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe",
                "CommandLine": "hermes serve",
            }
        )
        == "agent"
    )


def test_host_launcher_trust_is_not_weakened() -> None:
    assert_trusted_host_launcher(HELPER, REPO_ROOT)
    with pytest.raises(RuntimeError, match="HOST_LAUNCHER_FROM_CONTAINER_CLONE"):
        assert_trusted_host_launcher(r"W:\hermes-dev\workspace\hermes-agent\x.py")


def test_docs_name_the_official_remote_client_helper() -> None:
    readme = (REPO_ROOT / "scripts" / "r5_developer_hermes" / "README.md").read_text(encoding="utf-8")
    assert "desktop_remote_client.py" in readme
    assert "npm run pack" in readme
    dx = (REPO_ROOT / "docs" / "architecture" / "hermes_r5_developer_dx_v1.md").read_text(
        encoding="utf-8"
    )
    assert "desktop_remote_client.py" in dx
    assert "connection.json" in dx
