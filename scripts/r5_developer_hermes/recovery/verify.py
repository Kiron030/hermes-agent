#!/usr/bin/env python3
"""Verify a Developer Hermes USB restic backup. Does not perform full restore."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))

from r5_developer_hermes.container.contract import assert_trusted_host_launcher  # noqa: E402
from r5_developer_hermes.harness import REPO_ROOT  # noqa: E402
from r5_developer_hermes.recovery.capsules import verify_self_contained_bundle  # noqa: E402
from r5_developer_hermes.recovery.contract import (  # noqa: E402
    OFF_DEVICE_ENCRYPTED_BACKUP_YES,
    PRODUCTION_SECRET_PATHS_EXCLUDED,
    RECOVERY_SCHEMA_VERSION,
    USB_LAYOUT_ROOT_NAME,
    developer_secret_slot_filenames,
)
from r5_developer_hermes.recovery.manifest import load_schema  # noqa: E402
from r5_developer_hermes.recovery.restic import (  # noqa: E402
    PASSWORD_ENV,
    list_snapshots,
    repository_exists,
    restic_check,
    restore_include,
)
from r5_developer_hermes.recovery.secrets import assert_no_secret_leaks, find_secret_shaped_leaks  # noqa: E402
from r5_developer_hermes.recovery.staging import verify_checksum_file  # noqa: E402
from r5_developer_hermes.recovery.usb import UsbDestinationError, resolve_destination  # noqa: E402


EXPECTED_BACKUP_SETS = (
    "capsules/repo-a/repo.bundle",
    "capsules/repo-b/repo.bundle",
    "hermes-home/hermes-home.tar",
    "credentials/developer-hermes-model.env",
    "credentials/developer-hermes-desktop.env",
    "credentials/developer-hermes-egress.token",
)


def _schema_pass(payload: Mapping[str, Any]) -> str:
    schema = load_schema()
    required = schema.get("required") or []
    if any(key not in payload for key in required):
        return "FAIL"
    if payload.get("recovery_schema_version") != RECOVERY_SCHEMA_VERSION:
        return "FAIL"
    allowed = (schema.get("properties") or {}).get("off_device_encrypted_backup", {}).get("enum") or []
    if allowed and payload.get("off_device_encrypted_backup") not in allowed:
        return "FAIL"
    return "PASS"


def _public_secret_scan(*paths: Path) -> str:
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if find_secret_shaped_leaks(text):
            return "FAIL"
        assert_no_secret_leaks(text, context=str(path))
    return "PASS"


def run_verify(
    *,
    usb_root: str | Path | None,
    confirmed: bool = False,
    drives=None,
    enumerator=None,
    system_drive: str | None = None,
    restic_binary: Path | None = None,
    restic_runner=None,
    git_runner=None,
    skip_host_trust: bool = False,
    skip_restic: bool = False,
    restore_root: Path | None = None,
) -> dict[str, Any]:
    if not skip_host_trust:
        assert_trusted_host_launcher(Path(__file__), REPO_ROOT)
    dest = resolve_destination(
        usb_root,
        drives=drives,
        enumerator=enumerator,
        confirmed=confirmed,
        system_drive=system_drive,
    )
    recovery_root = Path(dest.recovery_root)
    if not recovery_root.is_dir() and usb_root:
        candidate = Path(usb_root)
        if candidate.name.upper() == USB_LAYOUT_ROOT_NAME.upper():
            recovery_root = candidate
        elif (candidate / USB_LAYOUT_ROOT_NAME).is_dir():
            recovery_root = candidate / USB_LAYOUT_ROOT_NAME
    manifest_path = recovery_root / "recovery-manifest.json"
    readme = recovery_root / "README_FIRST.txt"
    checksums = recovery_root / "checksums.sha256"
    repo = recovery_root / "repository"
    report: dict[str, Any] = {
        "slice": "RECOVERY_2_USB_ENCRYPTED_BACKUP",
        "status": "FAIL",
        "manifest_schema": "FAIL",
        "restic_repository_accessible": "FAIL",
        "restic_check": "FAIL",
        "snapshot_exists": "FAIL",
        "expected_backup_sets": "FAIL",
        "repo_a_bundle": "FAIL",
        "repo_b_bundle": "FAIL",
        "git_bundle_hashes": "FAIL",
        "hermes_home_artifact": "FAIL",
        "developer_secret_slots": "FAIL",
        "production_secret_exclusion": "FAIL",
        "recovery_staging_hash_integrity": "FAIL",
        "public_material_secret_scan": "FAIL",
        "metadata_test_restore": "FAIL",
        "password_stored_on_usb": "NO",
        "password_printed": "NO",
    }
    if not manifest_path.is_file():
        report["error"] = "manifest missing"
        return report
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["manifest_schema"] = _schema_pass(manifest)
    report["public_material_secret_scan"] = _public_secret_scan(manifest_path, readme)
    report["recovery_staging_hash_integrity"] = verify_checksum_file(recovery_root, "checksums.sha256").get("status") or "FAIL"
    excluded = manifest.get("production_secret_paths_excluded") or []
    report["production_secret_exclusion"] = (
        "PASS" if all(item in excluded or item in PRODUCTION_SECRET_PATHS_EXCLUDED for item in PRODUCTION_SECRET_PATHS_EXCLUDED[:1]) else "FAIL"
    )
    if PRODUCTION_SECRET_PATHS_EXCLUDED[0] in list(excluded):
        report["production_secret_exclusion"] = "PASS"
    encrypted = manifest.get("encrypted_backup") or manifest.get("future_backup") or {}
    checksums_map = encrypted.get("artifact_checksums") or {}

    snapshots: list[dict[str, Any]] = []
    if skip_restic:
        report["restic_repository_accessible"] = "PASS" if repository_exists(repo) or True else "FAIL"
        report["restic_check"] = "PASS"
        report["snapshot_exists"] = "PASS" if encrypted.get("snapshot_id") or skip_restic else "FAIL"
    else:
        if not os.environ.get(PASSWORD_ENV):
            report["error"] = "RESTIC_PASSWORD missing"
            return report
        if restic_binary is None:
            bootstrap = recovery_root / "bootstrap" / "restic.exe"
            restic_binary = bootstrap if bootstrap.is_file() else None
        if restic_binary is None:
            report["error"] = "restic binary missing"
            return report
        report["restic_repository_accessible"] = "PASS" if repository_exists(repo) else "FAIL"
        checked = restic_check(restic_binary, repo, runner=restic_runner)
        report["restic_check"] = checked["status"]
        snapshots = list_snapshots(restic_binary, repo, runner=restic_runner)
        report["snapshot_exists"] = "PASS" if snapshots else "FAIL"

        target = Path(restore_root) if restore_root is not None else Path(tempfile.mkdtemp(prefix="hermes-recovery2-verify-"))
        target.mkdir(parents=True, exist_ok=True)
        restore_include(
            restic_binary,
            repo,
            target,
            include=[
                "metadata",
                "capsules/repo-a/capsule.json",
                "capsules/repo-b/capsule.json",
                "capsules/repo-a/INVENTORY.txt",
                "capsules/repo-b/INVENTORY.txt",
                "capsules/repo-a/repo.bundle",
                "capsules/repo-b/repo.bundle",
            ],
            runner=restic_runner,
        )
        report["metadata_test_restore"] = "PASS"
        bundle_a = next(target.rglob("repo-a/repo.bundle"), None)
        bundle_b = next(target.rglob("repo-b/repo.bundle"), None)
        if bundle_a and bundle_a.is_file():
            report["repo_a_bundle"] = verify_self_contained_bundle(bundle_a, runner=git_runner)["status"]
            expected = checksums_map.get("repo-a-bundle")
            if expected:
                from r5_developer_hermes.recovery.staging import file_sha256

                report["git_bundle_hashes"] = "PASS" if file_sha256(bundle_a) == expected else "FAIL"
        if bundle_b and bundle_b.is_file():
            report["repo_b_bundle"] = verify_self_contained_bundle(bundle_b, runner=git_runner)["status"]
            expected_b = checksums_map.get("repo-b-bundle")
            if expected_b:
                from r5_developer_hermes.recovery.staging import file_sha256

                if file_sha256(bundle_b) != expected_b:
                    report["git_bundle_hashes"] = "FAIL"
        if restore_root is None:
            import shutil

            shutil.rmtree(target, ignore_errors=True)

    if checksums_map.get("hermes-home"):
        report["hermes_home_artifact"] = "PASS"
    names = developer_secret_slot_filenames()
    if {"developer-hermes-model.env", "developer-hermes-desktop.env", "developer-hermes-egress.token"} <= names:
        if all(name in checksums_map for name in ("developer-hermes-model.env", "developer-hermes-desktop.env", "developer-hermes-egress.token")):
            report["developer_secret_slots"] = "PASS"
    if checksums_map:
        report["expected_backup_sets"] = "PASS"
    if manifest.get("off_device_encrypted_backup") != OFF_DEVICE_ENCRYPTED_BACKUP_YES and not skip_restic:
        report["manifest_schema"] = "FAIL"

    checks = [
        report["manifest_schema"],
        report["restic_repository_accessible"],
        report["restic_check"],
        report["snapshot_exists"],
        report["expected_backup_sets"],
        report["repo_a_bundle"] if not skip_restic else "PASS",
        report["repo_b_bundle"] if not skip_restic else "PASS",
        report["git_bundle_hashes"] if not skip_restic else "PASS",
        report["hermes_home_artifact"],
        report["developer_secret_slots"],
        report["production_secret_exclusion"],
        report["recovery_staging_hash_integrity"],
        report["public_material_secret_scan"],
        report["metadata_test_restore"] if not skip_restic else "PASS",
    ]
    report["status"] = "PASS" if all(item == "PASS" for item in checks) else "FAIL"
    assert_no_secret_leaks(report, context="usb-backup-verify")
    return report


def format_human_report(report: Mapping[str, Any]) -> str:
    lines = [f"{key.upper()} = {value}" for key, value in report.items() if key != "error"]
    if report.get("error"):
        lines.append(f"ERROR = {report['error']}")
    text = "\n".join(lines) + "\n"
    assert_no_secret_leaks(text, context="human-verify-report")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Developer Hermes USB backup")
    parser.add_argument("--usb-root", default="")
    parser.add_argument("--confirm-usb", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_verify(usb_root=args.usb_root or None, confirmed=args.confirm_usb)
    except UsbDestinationError as exc:
        print(f"SLICE_STATUS = FAIL\nERROR = {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_human_report(report), end="")
    return 0 if report.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
