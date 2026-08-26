#!/usr/bin/env python3
"""Encrypted Developer Hermes USB backup (Recovery 2).

Does not implement restore. Does not format disks. Does not touch
Operator Hermes or Railway. The restic password is read only from
RESTIC_PASSWORD and is never logged.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))

from r5_developer_hermes.container.contract import (  # noqa: E402
    RUNTIME_GID,
    RUNTIME_UID,
    assert_trusted_host_launcher,
)
from r5_developer_hermes.harness import REPO_ROOT, repo_b_root  # noqa: E402
from r5_developer_hermes.recovery.audit import (  # noqa: E402
    check_checked_in_pins,
    evaluate_readiness,
)
from r5_developer_hermes.recovery.capsules import CapsuleError, write_capsules  # noqa: E402
from r5_developer_hermes.recovery.contract import (  # noqa: E402
    BACKUP_BLOCKED_LOCAL_WORK,
    BACKUP_SPACE_MARGIN_BYTES,
    BACKUP_SPACE_MARGIN_RATIO,
    BACKUP_STATUS_PRESENT,
    BACKUP_TOOL,
    DESKTOP_OFFICIAL_SOURCE,
    DESKTOP_PACK_ARTIFACT_RELATIVE,
    HERMES_HOME_CLASS,
    HERMES_HOME_VOLUME,
    LIVE_MANIFEST_RELATIVE,
    OFF_DEVICE_ENCRYPTED_BACKUP_YES,
    READINESS_BLOCKED_LOCAL_WORK,
    READINESS_READY,
    REQUIRED_HOST_PATHS,
    RESTIC_VERSION,
    host_secret_slot_paths,
)
from r5_developer_hermes.recovery.desktop_state import inspect_desktop_source  # noqa: E402
from r5_developer_hermes.recovery.docker_state import inspect_docker  # noqa: E402
from r5_developer_hermes.recovery.git_state import inspect_repo_a, inspect_repo_b  # noqa: E402
from r5_developer_hermes.recovery.manifest import (  # noqa: E402
    build_manifest,
    extract_hermes_pins,
    write_manifest,
)
from r5_developer_hermes.recovery.restic import (  # noqa: E402
    PASSWORD_ENV,
    ResticError,
    backup_path,
    bootstrap_restic,
    init_or_existing,
    list_snapshots,
    repository_exists,
    restic_check,
)
from r5_developer_hermes.recovery.runtime_window import (  # noqa: E402
    observe_runtime,
    restart_after_snapshot,
    stop_for_snapshot,
)
from r5_developer_hermes.recovery.secrets import (  # noqa: E402
    assert_no_secret_leaks,
    inspect_developer_secret_slots,
    missing_host_slots,
    production_paths_are_excluded,
    unexpected_slots,
)
from r5_developer_hermes.recovery.staging import file_sha256, write_sha256_manifest  # noqa: E402
from r5_developer_hermes.recovery.usb import (  # noqa: E402
    UsbDestinationError,
    assert_capacity,
    resolve_destination,
)
from r5_developer_hermes.recovery.volume_export import export_hermes_home_logical  # noqa: E402


README_FIRST = """HERMES DEVELOPER RECOVERY PACK
==============================

Architecture: PINNED_GIT_REBUILD_PLUS_ENCRYPTED_HOME
Backup tool: restic (encrypted repository/)

This USB pack can reconstruct, together with the independently stored
recovery password:

  - Repo A (hermes-agent) from a self-contained Git capsule
  - Repo B (Powerunits.io / EU-PP-Database) from a self-contained Git capsule
  - Developer HERMES_HOME (logical volume export)
  - approved Developer credential slots only

The restic password / recovery key is NOT stored on this USB, not in Git,
and not in the backup repository. Store it in an off-device password
manager plus an optional physical copy.

Production secrets (Railway, Operator Telegram, DATABASE_URL*,
%USERPROFILE%\\.powerunits\\secrets, host GitHub credentials) are
intentionally absent.

Restore is implemented in Recovery 3. Do not treat this pack as a
completed machine rebuild until restore has been proven.

Recommended volume label: HERMES_RECOVERY
Never format this disk from the backup scripts.
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dir_size(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def required_bytes_for(source_bytes: int) -> int:
    return int(source_bytes * (1 + BACKUP_SPACE_MARGIN_RATIO)) + BACKUP_SPACE_MARGIN_BYTES


def copy_allowlisted_credentials(dest: Path, *, slots: list[Path] | None = None) -> list[dict[str, str]]:
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []
    for path in slots or list(host_secret_slot_paths()):
        if not path.is_file():
            raise RuntimeError(f"missing Developer secret slot: {path.name}")
        target = dest / path.name
        shutil.copy2(path, target)
        copied.append({"filename": path.name, "sha256": file_sha256(target), "purpose": path.name})
    return copied


def production_paths_absent_from_tree(root: Path) -> bool:
    blob = " ".join(str(path) for path in root.rglob("*")).lower()
    forbidden = ("powerunits\\secrets", "railway", "database_url", ".git-credentials")
    return not any(item in blob for item in forbidden)


def write_usb_bootstrap(recovery_root: Path, restic_binary: Path) -> None:
    bootstrap = recovery_root / "bootstrap"
    bootstrap.mkdir(parents=True, exist_ok=True)
    (recovery_root / "restic").mkdir(parents=True, exist_ok=True)
    (recovery_root / "repository").mkdir(parents=True, exist_ok=True)
    readme = recovery_root / "README_FIRST.txt"
    readme.write_text(README_FIRST, encoding="utf-8")
    target = bootstrap / restic_binary.name
    if restic_binary.is_file() and restic_binary.resolve() != target.resolve():
        shutil.copy2(restic_binary, target)
    runbook_src = REPO_ROOT / "docs" / "architecture" / "hermes_r5_developer_recovery_v1.md"
    if runbook_src.is_file():
        shutil.copy2(runbook_src, bootstrap / "hermes_r5_developer_recovery_v1.md")
    runbook2 = REPO_ROOT / "docs" / "architecture" / "hermes_r5_developer_recovery_v2.md"
    if runbook2.is_file():
        shutil.copy2(runbook2, bootstrap / "hermes_r5_developer_recovery_v2.md")


def run_backup(
    *,
    usb_root: str | Path | None,
    confirmed: bool = False,
    drives=None,
    enumerator=None,
    system_drive: str | None = None,
    repo_a_root: Path | None = None,
    repo_b: Path | None = None,
    credentials_dir: Path | None = None,
    desktop_root: Path | None = None,
    staging_root: Path | None = None,
    restic_binary: Path | None = None,
    allow_restic_download: bool = False,
    restic_runner=None,
    git_runner=None,
    docker_runner=None,
    inspect_payload: dict[str, Any] | None = None,
    volumes_present: dict[str, bool] | None = None,
    telegram_meta: dict[str, Any] | None = None,
    telegram_status: Mapping[str, Any] | None = None,
    pin: Mapping[str, Any] | None = None,
    skip_host_trust: bool = False,
    skip_runtime: bool = False,
    skip_volume_export: bool = False,
    skip_restic: bool = False,
    skip_health: bool = False,
    include_desktop_exe: bool = True,
    password: str | None = None,
    now: datetime | None = None,
    launch_hooks: Mapping[str, Callable[[], Any]] | None = None,
    volume_export_fn=None,
    health_fn=None,
) -> dict[str, Any]:
    if not skip_host_trust:
        assert_trusted_host_launcher(Path(__file__), repo_a_root or REPO_ROOT)
    if password is not None:
        os.environ[PASSWORD_ENV] = password
    if not os.environ.get(PASSWORD_ENV) and not skip_restic:
        raise ResticError("RESTIC_PASSWORD is missing; refusing to start backup")

    dest = resolve_destination(
        usb_root,
        drives=drives,
        enumerator=enumerator,
        confirmed=confirmed,
        system_drive=system_drive,
    )
    root_a = Path(repo_a_root) if repo_a_root is not None else REPO_ROOT
    root_b = Path(repo_b) if repo_b is not None else repo_b_root()
    pin_data = dict(pin) if pin is not None else extract_hermes_pins()
    pins = extract_hermes_pins(pin_data) if "upstream_release" in pin_data else pin_data
    pin_findings = check_checked_in_pins(pin_data if "upstream_image_digest" in pin_data else None)

    snap_a = inspect_repo_a(root_a, runner=git_runner)
    snap_b = inspect_repo_b(root_b, runner=git_runner)
    docker = inspect_docker(
        runner=docker_runner,
        expected_contract_version=str(pins.get("developer_image_contract_version") or ""),
        inspect_payload=inspect_payload,
        volumes_present=volumes_present,
        telegram_meta=telegram_meta,
    )
    slots = inspect_developer_secret_slots(
        credentials_dir=credentials_dir,
        telegram_meta=docker.telegram_slot,
    )
    if unexpected_slots(slots) or missing_host_slots(slots):
        raise RuntimeError("Developer secret-slot allowlist failed")
    if not docker.hermes_home_volume_present and not skip_volume_export:
        raise RuntimeError("MISSING_HERMES_HOME_VOLUME")

    readiness, reasons = evaluate_readiness(
        git_items=[],
        docker_findings=docker.findings,
        pin_findings=pin_findings,
        unexpected=unexpected_slots(slots),
        missing_slots=missing_host_slots(slots),
        staging_status="PASS",
    )
    # Recovery-0B is evidence only. Local-work coverage is decided after capsules.
    if readiness not in {READINESS_READY, READINESS_BLOCKED_LOCAL_WORK} and reasons:
        if any(item != READINESS_BLOCKED_LOCAL_WORK for item in reasons):
            raise RuntimeError(f"backup blocked: {','.join(reasons)}")

    recovery_root = Path(dest.recovery_root)
    recovery_root.mkdir(parents=True, exist_ok=True)
    repo_dir = recovery_root / "repository"
    bootstrap_dir = recovery_root / "bootstrap"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)

    restic_info = {"binary": str(restic_binary or ""), "version": RESTIC_VERSION, "source": "injected"}
    if restic_binary is None and not skip_restic:
        restic_info = bootstrap_restic(bootstrap_dir, allow_download=allow_restic_download, runner=restic_runner)
        restic_binary = Path(restic_info["binary"])
    elif restic_binary is not None:
        write_usb_bootstrap(recovery_root, restic_binary)

    staging = Path(staging_root) if staging_root is not None else Path(tempfile.mkdtemp(prefix="hermes-recovery2-"))
    staging.mkdir(parents=True, exist_ok=True)
    capsule_dir = staging / "capsules"
    home_dir = staging / "hermes-home"
    cred_dir = staging / "credentials"
    meta_dir = staging / "metadata"
    optional_dir = staging / "optional"
    for path in (capsule_dir, home_dir, cred_dir, meta_dir, optional_dir):
        path.mkdir(parents=True, exist_ok=True)

    prior_snapshots: list[dict[str, Any]] = []
    if not skip_restic and restic_binary is not None and repository_exists(repo_dir):
        try:
            prior_snapshots = list_snapshots(restic_binary, repo_dir, runner=restic_runner)
        except ResticError:
            prior_snapshots = []

    window = observe_runtime(docker=docker_runner, telegram_status=telegram_status)
    hooks = dict(launch_hooks or {})
    stopped_here = False
    report: dict[str, Any] = {
        "slice": "RECOVERY_2_USB_ENCRYPTED_BACKUP",
        "status": "FAIL",
        "usb": dest.to_dict(),
        "backup_tool": BACKUP_TOOL,
        "restic_version": RESTIC_VERSION,
        "password_stored_on_usb": "NO",
        "password_printed": "NO",
        "backup_incremental": "YES" if prior_snapshots else "NO",
        "runtime_mutations": "NONE",
        "operator_changed": "NO",
        "railway_changed": "NO",
    }
    try:
        capsule_report = write_capsules(repo_a=snap_a, repo_b=snap_b, dest=capsule_dir, runner=git_runner)
        if capsule_report["repo_a_local_only_coverage"] != "PASS" or capsule_report["repo_b_local_only_coverage"] != "PASS":
            raise CapsuleError(BACKUP_BLOCKED_LOCAL_WORK, "local-only work remains uncovered")

        host_slots = None
        if credentials_dir is not None:
            host_slots = [
                credentials_dir / "developer-hermes-model.env",
                credentials_dir / "developer-hermes-desktop.env",
                credentials_dir / "developer-hermes-egress.token",
            ]
        cred_meta = copy_allowlisted_credentials(cred_dir, slots=host_slots)
        if not production_paths_are_excluded(REQUIRED_HOST_PATHS, [str(path) for path in (host_slots or host_secret_slot_paths())]):
            raise RuntimeError("PRODUCTION_SECRET_EXCLUSION failed")
        if not production_paths_absent_from_tree(staging):
            raise RuntimeError("production secret path leaked into staging")

        if not skip_runtime:
            stop_for_snapshot(
                window,
                docker=docker_runner,
                telegram_down=hooks.get("telegram_down"),
                desktop_down=hooks.get("desktop_down"),
            )
            stopped_here = True
            report["runtime_mutations"] = "DEVELOPER_SNAPSHOT_WINDOW"

        home_meta = {
            "path": "",
            "volume": HERMES_HOME_VOLUME,
            "class": HERMES_HOME_CLASS,
            "sha256": "",
            "size": 0,
        }
        exporter = volume_export_fn or export_hermes_home_logical
        if not skip_volume_export:
            home_meta = exporter(home_dir, runner=docker_runner)

        desktop = inspect_desktop_source(
            desktop_root,
            expected_sha=str(pins.get("upstream_release_sha") or ""),
            expected_release=str(pins.get("upstream_release") or ""),
        )
        optional_exe = None
        exe = Path(desktop_root or DESKTOP_OFFICIAL_SOURCE) / DESKTOP_PACK_ARTIFACT_RELATIVE
        if include_desktop_exe and exe.is_file():
            optional_exe = optional_dir / "Hermes.exe"
            shutil.copy2(exe, optional_exe)

        source_bytes = _dir_size(staging)
        needed = required_bytes_for(source_bytes)
        if dest.drive is not None:
            assert_capacity(dest.drive, needed)

        write_usb_bootstrap(recovery_root, restic_binary or Path("restic.exe"))
        checksums: dict[str, str] = {}
        snapshot_id = None
        restic_action = {"action": "skipped"}
        if not skip_restic and restic_binary is not None:
            restic_action = init_or_existing(restic_binary, repo_dir, runner=restic_runner)
            backed = backup_path(
                restic_binary,
                repo_dir,
                staging,
                runner=restic_runner,
                tags=["developer-hermes-recovery-2"],
            )
            snapshot_id = backed.get("snapshot_id")
            checked = restic_check(restic_binary, repo_dir, runner=restic_runner)
            if checked["status"] != "PASS":
                raise ResticError("restic check failed after backup")

        created = now.strftime("%Y-%m-%dT%H:%M:%SZ") if now else _utc_now()
        artifact_checksums = {
            "repo-a-bundle": capsule_report["repo_a"]["bundle_sha256"],
            "repo-b-bundle": capsule_report["repo_b"]["bundle_sha256"],
            "hermes-home": home_meta.get("sha256") or "",
        }
        for item in cred_meta:
            artifact_checksums[item["filename"]] = item["sha256"]
        if optional_exe is not None:
            artifact_checksums["optional-hermes-exe"] = file_sha256(optional_exe)

        encrypted = {
            "tool": BACKUP_TOOL,
            "status": BACKUP_STATUS_PRESENT,
            "restic_version": RESTIC_VERSION,
            "snapshot_id": snapshot_id,
            "created_at": created,
            "repository": str(repo_dir),
            "usb_volume": dest.volume_root,
            "artifact_checksums": artifact_checksums,
            "hermes_home_class": HERMES_HOME_CLASS,
            "secret_bearing_repo_b_state_excluded": capsule_report["secret_bearing_repo_b_state_excluded"],
        }
        manifest = build_manifest(
            repo_a=snap_a.to_dict(),
            repo_b=snap_b.to_dict() if snap_b is not None else {"canonical_sha": ""},
            hermes=pins,
            desktop=desktop,
            future_backup={
                "tool": BACKUP_TOOL,
                "status": BACKUP_STATUS_PRESENT,
                "snapshot_id": snapshot_id,
                "artifact_checksums": artifact_checksums,
            },
            encrypted_backup=encrypted,
            off_device_encrypted_backup=OFF_DEVICE_ENCRYPTED_BACKUP_YES,
            created_at=created,
            extra={
                "runtime": {"user": "hermes", "uid": RUNTIME_UID, "gid": RUNTIME_GID, "HERMES_HOME": "/opt/data"},
                "repo_capsules": {
                    "repo_a": {"self_contained": "YES", "sha256": capsule_report["repo_a"]["bundle_sha256"]},
                    "repo_b": {"self_contained": "YES", "sha256": capsule_report["repo_b"]["bundle_sha256"]},
                    "repo_a_local_only_coverage": capsule_report["repo_a_local_only_coverage"],
                    "repo_b_local_only_coverage": capsule_report["repo_b_local_only_coverage"],
                    "secret_bearing_repo_b_state_excluded": capsule_report["secret_bearing_repo_b_state_excluded"],
                },
                "usb": dest.to_dict(),
            },
        )
        assert_no_secret_leaks(manifest, context="usb-recovery-manifest")
        live = write_manifest(recovery_root / "recovery-manifest.json", manifest)
        write_manifest(root_a / LIVE_MANIFEST_RELATIVE, manifest)
        public_files = [
            recovery_root / "README_FIRST.txt",
            live,
        ]
        if (bootstrap_dir / "restic.exe").is_file():
            public_files.append(bootstrap_dir / "restic.exe")
        write_sha256_manifest(recovery_root / "checksums.sha256", public_files, root=recovery_root)

        report.update(
            {
                "status": "PASS",
                "backup_readiness": READINESS_READY,
                "off_device_encrypted_backup": OFF_DEVICE_ENCRYPTED_BACKUP_YES,
                "manifest": str(live),
                "snapshot_id": snapshot_id,
                "restic": restic_action,
                "capsules": capsule_report,
                "hermes_home": home_meta,
                "developer_secret_allowlist": [
                    {"path": r"W:\hermes-dev\credentials\developer-hermes-model.env", "purpose": "Developer model provider keys"},
                    {"path": r"W:\hermes-dev\credentials\developer-hermes-desktop.env", "purpose": "Developer Desktop gateway basic-auth"},
                    {"path": r"W:\hermes-dev\credentials\developer-hermes-egress.token", "purpose": "Developer egress broker token"},
                    {"path": "/opt/data/profiles/telegram-ops/.env", "purpose": "Developer Telegram profile token slot"},
                ],
                "production_secret_exclusion": "PASS",
                "repo_a_recovery": "SELF_CONTAINED",
                "repo_b_recovery": "SELF_CONTAINED",
                "repo_a_local_only_coverage": capsule_report["repo_a_local_only_coverage"],
                "repo_b_local_only_coverage": capsule_report["repo_b_local_only_coverage"],
                "secret_bearing_repo_b_state_excluded": capsule_report["secret_bearing_repo_b_state_excluded"],
                "hermes_home_backup": "FULL_ENCRYPTED_LOGICAL",
                "prior_snapshot_count": len(prior_snapshots),
                "source_bytes": source_bytes,
                "required_bytes": needed,
            }
        )
        assert_no_secret_leaks(report, context="usb-backup-report")
        return report
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = exc.__class__.__name__
        report["error_code"] = getattr(exc, "code", "")
        report["prior_snapshot_count"] = len(prior_snapshots)
        if isinstance(exc, (UsbDestinationError, CapsuleError, ResticError)):
            raise
        raise
    finally:
        if stopped_here and not skip_runtime:
            try:
                restart_after_snapshot(
                    window,
                    docker=docker_runner,
                    developer_up=hooks.get("developer_up"),
                    desktop_up=hooks.get("desktop_up"),
                    telegram_activate=hooks.get("telegram_activate"),
                )
                if health_fn is not None and not skip_health:
                    report["health"] = health_fn()
            except Exception as restart_exc:  # pragma: no cover - reported to Human
                report["restart_error"] = restart_exc.__class__.__name__
        if staging_root is None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def format_human_report(report: Mapping[str, Any]) -> str:
    lines = [
        f"SLICE = {report.get('slice')}",
        f"SLICE_STATUS = {report.get('status')}",
        f"BACKUP_TOOL = {report.get('backup_tool')}",
        f"RESTIC_VERSION = {report.get('restic_version')}",
        f"REPO_A_RECOVERY = {report.get('repo_a_recovery')}",
        f"REPO_B_RECOVERY = {report.get('repo_b_recovery')}",
        f"REPO_A_LOCAL_ONLY_COVERAGE = {report.get('repo_a_local_only_coverage')}",
        f"REPO_B_LOCAL_ONLY_COVERAGE = {report.get('repo_b_local_only_coverage')}",
        f"SECRET_BEARING_REPO_B_STATE_EXCLUDED = {report.get('secret_bearing_repo_b_state_excluded')}",
        f"HERMES_HOME_BACKUP = {report.get('hermes_home_backup')}",
        f"PRODUCTION_SECRET_EXCLUSION = {report.get('production_secret_exclusion')}",
        f"PASSWORD_STORED_ON_USB = {report.get('password_stored_on_usb')}",
        f"PASSWORD_PRINTED = {report.get('password_printed')}",
        f"BACKUP_INCREMENTAL = {report.get('backup_incremental')}",
        f"MANIFEST = {report.get('manifest')}",
        f"SNAPSHOT_ID = {report.get('snapshot_id')}",
        f"OPERATOR_CHANGED = {report.get('operator_changed')}",
        f"RAILWAY_CHANGED = {report.get('railway_changed')}",
    ]
    text = "\n".join(lines) + "\n"
    assert_no_secret_leaks(text, context="human-backup-report")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Encrypted Developer Hermes USB backup")
    parser.add_argument("--usb-root", default="", help="Explicit USB volume or HERMES-RECOVERY root")
    parser.add_argument("--confirm-usb", action="store_true", help="Human confirmed the destination")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-b", default="")
    parser.add_argument("--credentials-dir", default="")
    parser.add_argument("--allow-restic-download", action="store_true")
    parser.add_argument("--skip-runtime", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_backup(
            usb_root=args.usb_root or None,
            confirmed=args.confirm_usb,
            repo_b=Path(args.repo_b) if args.repo_b else None,
            credentials_dir=Path(args.credentials_dir) if args.credentials_dir else None,
            allow_restic_download=args.allow_restic_download,
            skip_runtime=args.skip_runtime,
        )
    except (UsbDestinationError, CapsuleError, ResticError, RuntimeError) as exc:
        print(f"SLICE_STATUS = FAIL\nERROR = {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "capsules"}, indent=2, sort_keys=True, default=str))
    else:
        print(format_human_report(report), end="")
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
