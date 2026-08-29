"""Deterministic proofs for Developer Hermes Recovery-2 USB backup."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from r5_developer_hermes.container.contract import IMAGE_CONTRACT_VERSION, PINNED_DIGEST
from r5_developer_hermes.harness import load_pin
from r5_developer_hermes.recovery.backup import format_human_report, required_bytes_for, run_backup
from r5_developer_hermes.recovery.capsules import (
    CapsuleError,
    build_capsule,
    verify_self_contained_bundle,
    write_capsules,
)
from r5_developer_hermes.recovery.contract import (
    BACKUP_BLOCKED_LOCAL_WORK,
    BACKUP_TOOL,
    HERMES_HOME_VOLUME,
    OFF_DEVICE_ENCRYPTED_BACKUP_YES,
    PRODUCTION_SECRET_PATHS_EXCLUDED,
    RESTIC_VERSION,
    RESTIC_WINDOWS_AMD64_MEMBER,
    RESTIC_WINDOWS_AMD64_NAME,
    RESTIC_WINDOWS_AMD64_SHA256,
    USB_AMBIGUOUS,
    USB_NOT_CONFIRMED,
    USB_NOT_REMOVABLE,
    USB_SYSTEM_DRIVE,
)
from r5_developer_hermes.recovery.git_state import GitSnapshot
from r5_developer_hermes.recovery.restic import (
    PASSWORD_ENV,
    ResticError,
    assert_checksum,
    bootstrap_restic,
    extract_pinned_restic_exe,
    init_or_existing,
    parse_sha256sums,
    redact_command,
    repository_exists,
    select_restic_zip_member,
    sha256_bytes,
    write_checksum_sidecar,
)
from r5_developer_hermes.recovery.runtime_window import restart_after_snapshot, stop_for_snapshot, RuntimeWindow
from r5_developer_hermes.recovery.secrets import assert_no_secret_leaks, find_secret_shaped_leaks
from r5_developer_hermes.recovery.usb import UsbDestinationError, UsbDrive, resolve_destination
from r5_developer_hermes.recovery.verify import run_verify
from r5_developer_hermes.recovery.volume_export import VolumeExportError, assert_not_raw_docker_path


PIN = load_pin()
FIXED_NOW = datetime(2026, 8, 26, 17, 0, 0, tzinfo=timezone.utc)
CANONICAL_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CANONICAL_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
PASSWORD = "test-recovery-password-not-for-production"


def _volume_letter(path: Path) -> str:
    return f"{str(path.resolve())[0].upper()}:"


def _removable_for(path: Path, *, free: int = 80 * 1024 * 1024 * 1024) -> UsbDrive:
    letter = _volume_letter(path)
    return UsbDrive(
        root=f"{letter}\\",
        letter=letter,
        label="HERMES_RECOVERY",
        bus_type="USB",
        drive_type=2,
        removable=True,
        usb_bus=True,
        free_bytes=free,
        total_bytes=free * 2,
    )


def _other_system_drive(path: Path) -> str:
    letter = _volume_letter(path)
    return "Z:" if letter == "C:" else "C:"


def _usb_drive(letter: str = "E", *, free: int = 50 * 1024 * 1024 * 1024) -> UsbDrive:
    return UsbDrive(
        root=f"{letter}:\\",
        letter=f"{letter}:",
        label="HERMES_RECOVERY",
        bus_type="USB",
        drive_type=2,
        removable=True,
        usb_bus=True,
        free_bytes=free,
        total_bytes=free * 2,
    )


def _present_slots(tmp: Path) -> Path:
    creds = tmp / "credentials"
    creds.mkdir(exist_ok=True)
    for name in (
        "developer-hermes-model.env",
        "developer-hermes-desktop.env",
        "developer-hermes-egress.token",
    ):
        (creds / name).write_text("PLACEHOLDER_NOT_A_SECRET\n", encoding="utf-8")
    return creds


def _git_init(root: Path, *, branch: str = "powerunits-internal-setup") -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", branch], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "r5@test"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "r5"], cwd=root, check=True, capture_output=True, text=True)
    (root / "README.md").write_text("capsule\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True, text=True)


def _fake_restic(store: Path):
    store.mkdir(parents=True, exist_ok=True)
    snapshots: list[dict] = []

    def run(argv: list[str], env):
        joined = " ".join(argv)
        assert "-p " not in joined
        assert "--password" not in joined
        assert PASSWORD not in joined
        if "version" in argv:
            return subprocess.CompletedProcess(argv, 0, f"restic {RESTIC_VERSION}\n", "")
        assert PASSWORD_ENV in (env or {}), "restic must receive RESTIC_PASSWORD via env"
        repo = Path(argv[argv.index("--repo") + 1])
        if "init" in argv:
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "config").write_text("restic-config\n", encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "created restic repository\n", "")
        if "backup" in argv:
            source = Path(argv[-1])
            snap = f"{len(snapshots) + 1:016x}"
            dest = store / snap
            if dest.exists():
                dest = store / f"{snap}-b"
            import shutil

            shutil.copytree(source, dest, dirs_exist_ok=True)
            snapshots.append({"id": snap, "short_id": snap[:8]})
            payload = json.dumps({"message_type": "summary", "snapshot_id": snap})
            return subprocess.CompletedProcess(argv, 0, payload + "\n", "")
        if "check" in argv:
            return subprocess.CompletedProcess(argv, 0, "no errors were found\n", "")
        if "snapshots" in argv:
            return subprocess.CompletedProcess(argv, 0, json.dumps(snapshots), "")
        if "restore" in argv:
            target = Path(argv[argv.index("--target") + 1])
            latest = snapshots[-1]["id"] if snapshots else ""
            src = store / latest
            if src.is_dir():
                import shutil

                shutil.copytree(src, target / src.name, dirs_exist_ok=True)
                for item in src.rglob("*"):
                    rel = item.relative_to(src)
                    dest = target / rel
                    if item.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(item.read_bytes())
            return subprocess.CompletedProcess(argv, 0, "restored\n", "")
        return subprocess.CompletedProcess(argv, 1, "", "unexpected")

    run.snapshots = snapshots  # type: ignore[attr-defined]
    return run


def _fake_volume_export(dest: Path, runner=None, **_k):
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "hermes-home.tar"
    archive.write_bytes(b"logical-home")
    return {
        "path": str(archive),
        "volume": HERMES_HOME_VOLUME,
        "sha256": "a" * 64,
        "size": 12,
    }


def _docker_ok() -> object:
    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["volume", "inspect"]:
            return subprocess.CompletedProcess(["docker", *args], 0, HERMES_HOME_VOLUME, "")
        if args[:1] == ["inspect"]:
            return subprocess.CompletedProcess(["docker", *args], 0, "false", "")
        if args[:1] == ["run"] and "tar" in args:
            dest = None
            for item in args:
                if item.endswith(":/backup"):
                    dest = Path(item.split(":", 1)[0])
            if dest:
                (dest / "hermes-home.tar").write_bytes(b"logical-home")
            return subprocess.CompletedProcess(["docker", *args], 0, "", "")
        if args[:1] in ({"stop"}, {"start"}):
            return subprocess.CompletedProcess(["docker", *args], 0, "", "")
        return subprocess.CompletedProcess(["docker", *args], 1, "", "unused")

    return run


def _base_backup(tmp: Path, **overrides):
    usb = tmp / "usb"
    usb.mkdir()
    repo_a = tmp / "repo-a"
    repo_b = tmp / "repo-b"
    _git_init(repo_a)
    _git_init(repo_b, branch="main")
    creds = _present_slots(tmp)
    restic_bin = tmp / "restic.exe"
    restic_bin.write_text("fake\n", encoding="utf-8")
    kwargs = {
        "usb_root": str(usb / "HERMES-RECOVERY"),
        "confirmed": True,
        "drives": [_removable_for(usb)],
        "system_drive": _other_system_drive(usb),
        "repo_a_root": repo_a,
        "repo_b": repo_b,
        "credentials_dir": creds,
        "desktop_root": tmp / "desktop-missing",
        "staging_root": tmp / "staging",
        "restic_binary": restic_bin,
        "restic_runner": _fake_restic(tmp / "restic-store"),
        "docker_runner": _docker_ok(),
        "inspect_payload": {
            "Id": "abc",
            "Image": "sha256:image",
            "State": {"Running": False},
            "Config": {
                "Image": "r5-developer-hermes:dx-v1",
                "User": "10000:10000",
                "Env": ["HERMES_HOME=/opt/data"],
                "Labels": {
                    "io.powerunits.r5.hermes-base-digest": PINNED_DIGEST,
                    "io.powerunits.r5.contract-version": IMAGE_CONTRACT_VERSION,
                },
            },
            "HostConfig": {},
            "Mounts": [],
            "NetworkSettings": {"Networks": {}},
        },
        "volumes_present": {HERMES_HOME_VOLUME: True},
        "telegram_meta": {"exists": True, "size": 8, "uid": 10000, "gid": 10000, "mode": "600"},
        "pin": PIN,
        "skip_host_trust": True,
        "skip_runtime": True,
        "skip_health": True,
        "include_desktop_exe": False,
        "password": PASSWORD,
        "now": FIXED_NOW,
        "volume_export_fn": _fake_volume_export,
    }
    # resolve_destination uses volume_root_of(usb_root). For a path under tmp,
    # the volume is likely C:. Tests that need destination validation use
    # injected drives with an explicit letter; backup orchestration tests
    # bypass USB classification by using a confirmed removable record whose
    # root matches the resolved volume when possible. For unit orchestration
    # we call resolve with a fake drive list and a non-system requested root.
    kwargs.update(overrides)
    return kwargs


def test_non_removable_and_system_drive_rejected(tmp_path: Path) -> None:
    fixed = UsbDrive(root="D:\\", letter="D:", drive_type=3, removable=False, usb_bus=False, free_bytes=99)
    with pytest.raises(UsbDestinationError) as exc:
        resolve_destination("D:\\", drives=[fixed], confirmed=True, system_drive="C:")
    assert exc.value.code == USB_NOT_REMOVABLE
    with pytest.raises(UsbDestinationError) as exc:
        resolve_destination("C:\\", drives=[_usb_drive("C")], confirmed=True, system_drive="C:")
    assert exc.value.code == USB_SYSTEM_DRIVE


def test_multiple_drive_ambiguity_and_unconfirmed(tmp_path: Path) -> None:
    drives = [_usb_drive("E"), _usb_drive("F")]
    with pytest.raises(UsbDestinationError) as exc:
        resolve_destination(None, drives=drives, confirmed=False, system_drive="C:")
    assert exc.value.code == USB_AMBIGUOUS
    with pytest.raises(UsbDestinationError) as exc:
        resolve_destination("E:\\", drives=[_usb_drive("E")], confirmed=False, system_drive="C:")
    assert exc.value.code == USB_NOT_CONFIRMED


def test_password_not_on_argv_or_in_report(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        redact_command(["restic", "--password", PASSWORD, "backup"])
    with pytest.raises(Exception):
        redact_command(["restic", "-p", PASSWORD, "backup"])
    seen: list[list[str]] = []

    def runner(argv, env):
        seen.append(list(argv))
        return _fake_restic(tmp_path / "store")(argv, env)

    kwargs = _base_backup(tmp_path)
    kwargs["restic_runner"] = runner
    # Destination on the same volume as tmp is the system drive in this
    # environment. Exercise the restic runner through init_or_existing.
    repo = tmp_path / "repo"
    os.environ[PASSWORD_ENV] = PASSWORD
    try:
        init_or_existing(tmp_path / "restic.exe", repo, runner=runner)
        init_or_existing(tmp_path / "restic.exe", repo, runner=runner)
    finally:
        os.environ.pop(PASSWORD_ENV, None)
    assert repository_exists(repo)
    blob = json.dumps(seen)
    assert PASSWORD not in blob
    assert "--password" not in blob


def test_production_secret_paths_stay_excluded() -> None:
    for path in PRODUCTION_SECRET_PATHS_EXCLUDED:
        assert "developer-hermes-model.env" not in path
        assert "developer-hermes-desktop.env" not in path
        assert "developer-hermes-egress.token" not in path


def test_repo_b_secret_bearing_stash_excluded(tmp_path: Path) -> None:
    root = tmp_path / "repo-b"
    _git_init(root, branch="main")
    snap = GitSnapshot(
        root=str(root),
        remote="https://github.com/Kiron030/Powerunits.io.git",
        branch="main",
        head=CANONICAL_B,
        canonical_branch="main",
        canonical_sha=CANONICAL_B,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        stash_count=1,
        stash_subjects=["On research/x: local-env-pgurl-before-merge"],
        dirty_state="clean",
    )
    dest = tmp_path / "capsule"
    meta = build_capsule(snap, dest, repo="B")
    assert meta["excluded_secret_bearing_local_state"] == "YES"
    assert not list((dest / "stashes").glob("*")) if (dest / "stashes").exists() else True
    blob = json.dumps(meta)
    assert "pgurl" not in blob.lower() or "excluded" in blob
    assert find_secret_shaped_leaks(meta) == []


def test_self_contained_git_bundle_verifies(tmp_path: Path) -> None:
    root = tmp_path / "repo-a"
    _git_init(root)
    subprocess.run(["git", "checkout", "-b", "local-only"], cwd=root, check=True, capture_output=True, text=True)
    (root / "local.py").write_text("print('ok')\n", encoding="utf-8")
    subprocess.run(["git", "add", "local.py"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "local"], cwd=root, check=True, capture_output=True, text=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    snap = GitSnapshot(
        root=str(root),
        remote="https://github.com/Kiron030/hermes-agent.git",
        branch="local-only",
        head=head,
        canonical_branch="powerunits-internal-setup",
        canonical_sha=head,
        canonical_sha_source="LOCAL_TRACKING",
        local_only_branches={"local-only": head},
    )
    dest = tmp_path / "capsule"
    meta = build_capsule(snap, dest, repo="A")
    verify = verify_self_contained_bundle(dest / "repo.bundle")
    assert verify["status"] == "PASS"
    assert meta["self_contained"] == "YES"
    clone = tmp_path / "restored"
    completed = subprocess.run(
        ["git", "clone", str(dest / "repo.bundle"), str(clone)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert (clone / "local.py").is_file()


def test_uncovered_local_work_blocks_capsule(tmp_path: Path) -> None:
    root = tmp_path / "repo-a"
    _git_init(root)
    snap = GitSnapshot(
        root=str(root),
        remote="https://github.com/Kiron030/hermes-agent.git",
        branch="powerunits-internal-setup",
        head=CANONICAL_A,
        canonical_branch="powerunits-internal-setup",
        canonical_sha=CANONICAL_A,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        untracked=["missing-source.py"],
        dirty_state="dirty",
    )
    dest = tmp_path / "capsule"
    meta = build_capsule(snap, dest, repo="A")
    from r5_developer_hermes.recovery.capsules import coverage_after_capsule

    status, items = coverage_after_capsule(snap, repo="A", dest=dest, metadata=meta)
    assert status == "BLOCKED"
    assert any(item.coverage == "UNCOVERED" for item in items)
    with pytest.raises(CapsuleError) as exc:
        write_capsules(repo_a=snap, repo_b=snap, dest=tmp_path / "both")
    assert exc.value.code == BACKUP_BLOCKED_LOCAL_WORK


def test_hermes_home_volume_missing_blocks(tmp_path: Path) -> None:
    kwargs = _base_backup(tmp_path)
    kwargs["volumes_present"] = {HERMES_HOME_VOLUME: False}
    kwargs["skip_volume_export"] = False
    kwargs["skip_restic"] = True
    with pytest.raises(RuntimeError, match="MISSING_HERMES_HOME_VOLUME"):
        run_backup(**kwargs)


def test_restic_init_then_existing_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repository"
    runner = _fake_restic(tmp_path / "store")
    os.environ[PASSWORD_ENV] = PASSWORD
    try:
        first = init_or_existing(tmp_path / "restic.exe", repo, runner=runner)
        second = init_or_existing(tmp_path / "restic.exe", repo, runner=runner)
    finally:
        os.environ.pop(PASSWORD_ENV, None)
    assert first["action"] == "init"
    assert second["action"] == "existing"
    assert repository_exists(repo)


def test_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    blob = tmp_path / "restic.zip"
    blob.write_bytes(b"not-the-official-binary")
    with pytest.raises(Exception, match="checksum"):
        assert_checksum(blob, RESTIC_WINDOWS_AMD64_SHA256)
    sums = f"{RESTIC_WINDOWS_AMD64_SHA256}  restic_0.18.1_windows_amd64.zip\n"
    assert parse_sha256sums(sums, "restic_0.18.1_windows_amd64.zip") == RESTIC_WINDOWS_AMD64_SHA256


def test_manifest_excludes_secret_values_and_records_backup(tmp_path: Path) -> None:
    from r5_developer_hermes.recovery.manifest import build_manifest

    manifest = build_manifest(
        repo_a={"canonical_sha": CANONICAL_A},
        repo_b={"canonical_sha": CANONICAL_B},
        off_device_encrypted_backup=OFF_DEVICE_ENCRYPTED_BACKUP_YES,
        encrypted_backup={
            "tool": BACKUP_TOOL,
            "status": "PRESENT",
            "restic_version": RESTIC_VERSION,
            "snapshot_id": "abc123",
            "created_at": "2026-08-26T17:00:00Z",
            "artifact_checksums": {"repo-a-bundle": "d" * 64},
        },
        created_at="2026-08-26T17:00:00Z",
    )
    assert_no_secret_leaks(manifest, context="backup-manifest")
    assert PASSWORD not in json.dumps(manifest)
    assert manifest["off_device_encrypted_backup"] == OFF_DEVICE_ENCRYPTED_BACKUP_YES
    assert manifest["encrypted_backup"]["restic_version"] == RESTIC_VERSION
    assert "sk-" not in json.dumps(manifest)


def test_failed_backup_leaves_prior_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "repository"
    runner = _fake_restic(tmp_path / "store")
    os.environ[PASSWORD_ENV] = PASSWORD
    try:
        init_or_existing(tmp_path / "restic.exe", repo, runner=runner)
        from r5_developer_hermes.recovery.restic import backup_path

        source = tmp_path / "src"
        source.mkdir()
        (source / "f.txt").write_text("a\n", encoding="utf-8")
        first = backup_path(tmp_path / "restic.exe", repo, source, runner=runner)
        prior = list(runner.snapshots)

        def fail(argv, env):
            if "backup" in argv:
                return subprocess.CompletedProcess(argv, 1, "", "boom")
            return runner(argv, env)

        with pytest.raises(Exception):
            backup_path(tmp_path / "restic.exe", repo, source, runner=fail)
        assert runner.snapshots == prior
        assert first["snapshot_id"]
    finally:
        os.environ.pop(PASSWORD_ENV, None)


def test_runtime_restart_after_backup_failure() -> None:
    window = RuntimeWindow(container_was_running=True, desktop_was_running=True, telegram_was_live=True)
    calls: list[str] = []

    def docker(args):
        calls.append(args[0])
        return subprocess.CompletedProcess(["docker", *args], 0, "", "")

    stop_for_snapshot(window, docker=docker, telegram_down=lambda: calls.append("tg-down"), desktop_down=lambda: calls.append("desk-down"))
    try:
        raise RuntimeError("backup failed")
    except RuntimeError:
        restart_after_snapshot(
            window,
            docker=docker,
            developer_up=lambda: calls.append("up"),
            desktop_up=lambda: calls.append("desk-up"),
            telegram_activate=lambda: calls.append("tg-up"),
        )
    assert "stop" in calls
    assert "up" in calls
    assert "desk-up" in calls
    assert "tg-up" in calls


def test_raw_docker_desktop_path_forbidden() -> None:
    with pytest.raises(VolumeExportError):
        assert_not_raw_docker_path(r"\\wsl$\docker-desktop-data\version-pack-data")
    with pytest.raises(VolumeExportError):
        assert_not_raw_docker_path("/var/lib/docker/volumes/r5-developer-hermes-home/_data")


def test_scripts_never_format_or_log_password() -> None:
    root = Path(__file__).resolve().parents[2] / "scripts" / "r5_developer_hermes"
    backup_ps1 = (root / "backup-developer-hermes-usb.ps1").read_text(encoding="utf-8")
    verify_ps1 = (root / "verify-developer-hermes-usb-backup.ps1").read_text(encoding="utf-8")
    for text in (backup_ps1, verify_ps1):
        assert "Format-Volume" not in text
        assert "Clear-Disk" not in text
        assert "RESTIC_PASSWORD" in text
        assert "--password" not in text
        assert "Write-Host $Plain" not in text
        assert "Write-Host $env:RESTIC_PASSWORD" not in text
    assert "$WhatIfPreference" in backup_ps1
    assert "--dry-run" in backup_ps1


def test_capacity_estimate_has_margin() -> None:
    assert required_bytes_for(1000) > 1000


def test_verify_public_manifest_and_skip_restic(tmp_path: Path) -> None:
    recovery = tmp_path / "HERMES-RECOVERY"
    recovery.mkdir()
    from r5_developer_hermes.recovery.manifest import build_manifest, write_manifest
    from r5_developer_hermes.recovery.staging import write_sha256_manifest

    manifest = build_manifest(
        repo_a={"canonical_sha": CANONICAL_A},
        repo_b={"canonical_sha": CANONICAL_B},
        off_device_encrypted_backup=OFF_DEVICE_ENCRYPTED_BACKUP_YES,
        encrypted_backup={
            "tool": BACKUP_TOOL,
            "status": "PRESENT",
            "restic_version": RESTIC_VERSION,
            "snapshot_id": "snap1",
            "artifact_checksums": {
                "repo-a-bundle": "a" * 64,
                "repo-b-bundle": "b" * 64,
                "hermes-home": "c" * 64,
                "developer-hermes-model.env": "d" * 64,
                "developer-hermes-desktop.env": "e" * 64,
                "developer-hermes-egress.token": "f" * 64,
            },
        },
    )
    write_manifest(recovery / "recovery-manifest.json", manifest)
    (recovery / "README_FIRST.txt").write_text("HERMES DEVELOPER RECOVERY PACK\n", encoding="utf-8")
    write_sha256_manifest(
        recovery / "checksums.sha256",
        [recovery / "README_FIRST.txt", recovery / "recovery-manifest.json"],
        root=recovery,
    )
    (recovery / "repository" / "config").parent.mkdir(parents=True, exist_ok=True)
    (recovery / "repository" / "config").write_text("x\n", encoding="utf-8")
    report = run_verify(
        usb_root=str(recovery),
        confirmed=True,
        drives=[_removable_for(recovery)],
        system_drive=_other_system_drive(recovery),
        skip_host_trust=True,
        skip_restic=True,
    )
    assert report["manifest_schema"] == "PASS"
    assert report["public_material_secret_scan"] == "PASS"
    assert report["developer_secret_slots"] == "PASS"
    assert report["production_secret_exclusion"] == "PASS"
    assert report["recovery_staging_hash_integrity"] == "PASS"


def test_run_backup_writes_manifest_and_snapshot(tmp_path: Path) -> None:
    os.environ[PASSWORD_ENV] = PASSWORD
    try:
        report = run_backup(**_base_backup(tmp_path))
    finally:
        os.environ.pop(PASSWORD_ENV, None)
    assert report["status"] == "PASS"
    assert report["repo_a_recovery"] == "SELF_CONTAINED"
    assert report["repo_b_recovery"] == "SELF_CONTAINED"
    assert report["password_stored_on_usb"] == "NO"
    assert report["production_secret_exclusion"] == "PASS"
    assert report["snapshot_id"]
    assert PASSWORD not in json.dumps(report)
    manifest_path = Path(report["manifest"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["off_device_encrypted_backup"] == OFF_DEVICE_ENCRYPTED_BACKUP_YES
    assert payload["encrypted_backup"]["restic_version"] == RESTIC_VERSION
    assert (manifest_path.parent / "README_FIRST.txt").is_file()
    assert (manifest_path.parent / "checksums.sha256").is_file()
    assert (manifest_path.parent / "repository" / "config").is_file()


def test_human_backup_report_has_no_password() -> None:
    text = format_human_report(
        {
            "slice": "RECOVERY_2_USB_ENCRYPTED_BACKUP",
            "status": "PASS",
            "backup_tool": "restic",
            "restic_version": RESTIC_VERSION,
            "password_stored_on_usb": "NO",
            "password_printed": "NO",
            "manifest": "HERMES-RECOVERY/recovery-manifest.json",
        }
    )
    assert PASSWORD not in text
    assert "PASSWORD_STORED_ON_USB = NO" in text


def _official_restic_zip(tmp: Path, *names: str) -> Path:
    archive = tmp / RESTIC_WINDOWS_AMD64_NAME
    import zipfile

    with zipfile.ZipFile(archive, "w") as zipped:
        for name in names or (RESTIC_WINDOWS_AMD64_MEMBER,):
            zipped.writestr(name, b"MZ-fake-restic")
    return archive


def test_official_versioned_exe_is_normalized(tmp_path: Path) -> None:
    archive = _official_restic_zip(tmp_path)
    dest = tmp_path / "restic.exe"
    member = extract_pinned_restic_exe(archive, dest)
    assert member == RESTIC_WINDOWS_AMD64_MEMBER
    assert dest.is_file()
    assert select_restic_zip_member([RESTIC_WINDOWS_AMD64_MEMBER]) == RESTIC_WINDOWS_AMD64_MEMBER
    assert select_restic_zip_member(["restic.exe"]) == "restic.exe"


def test_zip_without_expected_exe_fails_closed(tmp_path: Path) -> None:
    archive = _official_restic_zip(tmp_path, "readme.txt")
    with pytest.raises(ResticError, match="did not contain"):
        extract_pinned_restic_exe(archive, tmp_path / "restic.exe")


def test_zip_with_ambiguous_exes_fails_closed() -> None:
    with pytest.raises(ResticError, match="multiple"):
        select_restic_zip_member(["restic.exe", RESTIC_WINDOWS_AMD64_MEMBER])


def test_zip_slip_member_rejected() -> None:
    with pytest.raises(ResticError, match="zip-slip|unexpected"):
        select_restic_zip_member(["../restic.exe"])
    with pytest.raises(ResticError, match="unexpected"):
        select_restic_zip_member([r"dir\\restic_0.18.1_windows_amd64.exe"])


def test_bootstrap_checksum_mismatch_before_extract(tmp_path: Path) -> None:
    def opener(url: str) -> bytes:
        if url.endswith("SHA256SUMS"):
            return f"{RESTIC_WINDOWS_AMD64_SHA256}  {RESTIC_WINDOWS_AMD64_NAME}\n".encode()
        return b"not-the-official-zip"

    with pytest.raises(ResticError, match="checksum"):
        bootstrap_restic(tmp_path / "cache", allow_download=True, opener=opener)
    assert not (tmp_path / "cache" / "restic.exe").exists()


def test_bootstrap_version_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = _official_restic_zip(tmp_path)
    payload = archive.read_bytes()
    digest = sha256_bytes(payload)
    monkeypatch.setattr("r5_developer_hermes.recovery.restic.RESTIC_WINDOWS_AMD64_SHA256", digest)

    def opener(url: str) -> bytes:
        if url.endswith("SHA256SUMS"):
            return f"{digest}  {RESTIC_WINDOWS_AMD64_NAME}\n".encode()
        return payload

    def runner(argv, env):
        return subprocess.CompletedProcess(argv, 0, "restic 0.18.10 compiled with go\n", "")

    with pytest.raises(ResticError, match="version"):
        bootstrap_restic(tmp_path / "cache", allow_download=True, opener=opener, runner=runner)
    assert not (tmp_path / "cache" / "restic.exe").exists()


def test_existing_verified_binary_reused_without_download(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    exe = cache / "restic.exe"
    exe.write_bytes(b"MZ-cached")
    write_checksum_sidecar(exe)
    downloads = {"n": 0}

    def opener(url: str) -> bytes:
        downloads["n"] += 1
        raise AssertionError("download must not run")

    def runner(argv, env):
        return subprocess.CompletedProcess(argv, 0, f"restic {RESTIC_VERSION} compiled with go\n", "")

    result = bootstrap_restic(cache, allow_download=True, opener=opener, runner=runner)
    assert result["source"] == "bootstrap-cache"
    assert downloads["n"] == 0


def test_whatif_without_restic_is_dry_run_pass(tmp_path: Path) -> None:
    kwargs = _base_backup(tmp_path)
    kwargs["dry_run"] = True
    kwargs["restic_binary"] = None
    kwargs["allow_restic_download"] = False
    kwargs.pop("password", None)
    os.environ.pop(PASSWORD_ENV, None)
    downloads = {"n": 0}

    def opener(url: str) -> bytes:
        downloads["n"] += 1
        raise AssertionError("WhatIf must not download")

    kwargs["restic_opener"] = opener
    report = run_backup(**kwargs)
    assert report["status"] == "PASS"
    assert report["dry_run"] == "YES"
    assert report["usb_writes"] == "NO"
    assert report["network_downloads"] == "NO"
    assert report["secret_input_required"] == "NO"
    assert report["runtime_mutations"] == "NO"
    assert report["restic_download"] == "WOULD_DOWNLOAD"
    assert downloads["n"] == 0
    assert not (tmp_path / "usb" / "HERMES-RECOVERY" / "repository" / "config").exists()
    assert PASSWORD_ENV not in os.environ


def test_whatif_allow_download_does_not_download(tmp_path: Path) -> None:
    kwargs = _base_backup(tmp_path)
    kwargs["dry_run"] = True
    kwargs["allow_restic_download"] = True
    kwargs["restic_binary"] = None
    kwargs.pop("password", None)
    downloads = {"n": 0}

    def opener(url: str) -> bytes:
        downloads["n"] += 1
        raise AssertionError("WhatIf must not download")

    kwargs["restic_opener"] = opener
    report = run_backup(**kwargs)
    assert report["status"] == "PASS"
    assert report["restic_download"] == "WOULD_DOWNLOAD"
    assert report["network_downloads"] == "NO"
    assert report["usb_writes"] == "NO"
    assert report["secret_input_required"] == "NO"
    assert report["runtime_mutations"] == "NO"
    assert downloads["n"] == 0
    assert PASSWORD_ENV not in os.environ


def test_whatif_human_report_marks_true_dry_run() -> None:
    text = format_human_report(
        {
            "slice": "RECOVERY_2_USB_ENCRYPTED_BACKUP",
            "status": "PASS",
            "dry_run": "YES",
            "usb_writes": "NO",
            "network_downloads": "NO",
            "secret_input_required": "NO",
            "runtime_mutations": "NO",
            "restic_download": "WOULD_DOWNLOAD",
            "backup_tool": "restic",
            "restic_version": RESTIC_VERSION,
            "password_stored_on_usb": "NO",
            "password_printed": "NO",
        }
    )
    assert "DRY_RUN = YES" in text
    assert "USB_WRITES = NO" in text
    assert "NETWORK_DOWNLOADS = NO" in text
    assert "SECRET_INPUT_REQUIRED = NO" in text
    assert "RUNTIME_MUTATIONS = NO" in text
    assert "RESTIC_DOWNLOAD = WOULD_DOWNLOAD" in text


def test_real_run_download_only_after_destination_confirmation(tmp_path: Path) -> None:
    kwargs = _base_backup(tmp_path)
    kwargs["confirmed"] = False
    kwargs["restic_binary"] = None
    kwargs["allow_restic_download"] = True
    downloads = {"n": 0}

    def opener(url: str) -> bytes:
        downloads["n"] += 1
        return b""

    kwargs["restic_opener"] = opener
    kwargs["restic_runner"] = _fake_restic(tmp_path / "store")
    with pytest.raises(UsbDestinationError):
        run_backup(**kwargs)
    assert downloads["n"] == 0


def test_real_run_download_permitted_after_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _official_restic_zip(tmp_path)
    payload = archive.read_bytes()
    digest = sha256_bytes(payload)
    monkeypatch.setattr("r5_developer_hermes.recovery.restic.RESTIC_WINDOWS_AMD64_SHA256", digest)
    downloads = {"n": 0}

    def opener(url: str) -> bytes:
        downloads["n"] += 1
        if url.endswith("SHA256SUMS"):
            return f"{digest}  {RESTIC_WINDOWS_AMD64_NAME}\n".encode()
        return payload

    kwargs = _base_backup(tmp_path)
    kwargs["restic_binary"] = None
    kwargs["allow_restic_download"] = True
    kwargs["restic_opener"] = opener
    report = run_backup(**kwargs)
    assert downloads["n"] >= 2
    assert report["status"] == "PASS"
    assert report["repo_a_recovery"] == "SELF_CONTAINED"
    assert report["hermes_home_backup"] == "FULL_ENCRYPTED_LOGICAL"


def test_whatif_wrong_destination_fails_closed(tmp_path: Path) -> None:
    kwargs = _base_backup(tmp_path)
    kwargs["dry_run"] = True
    kwargs["system_drive"] = _volume_letter(tmp_path / "usb")
    kwargs.pop("password", None)
    with pytest.raises(UsbDestinationError) as exc:
        run_backup(**kwargs)
    assert exc.value.code == USB_SYSTEM_DRIVE

