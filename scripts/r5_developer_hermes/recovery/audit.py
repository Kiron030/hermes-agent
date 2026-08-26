#!/usr/bin/env python3
"""Read-only Developer Hermes recovery audit (Slice 1).

Does not stop runtimes, mutate Docker, install restic, or print secrets.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))

from r5_developer_hermes.container.contract import (  # noqa: E402
    IMAGE_CONTRACT_VERSION,
    PINNED_DIGEST,
    RUNTIME_GID,
    RUNTIME_UID,
    assert_trusted_host_launcher,
)
from r5_developer_hermes.harness import REPO_ROOT, load_pin, repo_b_root  # noqa: E402
from r5_developer_hermes.recovery.contract import (  # noqa: E402
    DEFAULT_STAGING_PACK,
    HERMES_HOME_CLASS,
    HERMES_HOME_VOLUME,
    LIVE_MANIFEST_RELATIVE,
    OFF_DEVICE_ENCRYPTED_BACKUP,
    PRODUCTION_SECRET_PATHS_EXCLUDED,
    READINESS_BLOCKED,
    READINESS_BLOCKED_LOCAL_WORK,
    READINESS_READY,
    RECOVERY_ARCHITECTURE,
    RECOVERY_SCHEMA_VERSION,
    REQUIRED_HOST_PATHS,
)
from r5_developer_hermes.recovery.desktop_state import inspect_desktop_source  # noqa: E402
from r5_developer_hermes.recovery.docker_state import inspect_docker  # noqa: E402
from r5_developer_hermes.recovery.git_state import (  # noqa: E402
    classify_local_work,
    inspect_repo_a,
    inspect_repo_b,
    local_git_coverage_status,
)
from r5_developer_hermes.recovery.manifest import (  # noqa: E402
    build_manifest,
    extract_hermes_pins,
    strip_volatile,
    write_manifest,
)
from r5_developer_hermes.recovery.secrets import (  # noqa: E402
    assert_no_secret_leaks,
    inspect_developer_secret_slots,
    missing_host_slots,
    production_paths_are_excluded,
    slot_summaries,
    unexpected_slots,
)
from r5_developer_hermes.recovery.staging import (  # noqa: E402
    load_staging_index,
    staging_record,
    verify_staging_hashes,
)


def evaluate_readiness(
    *,
    git_items: list[Any],
    docker_findings: list[str],
    pin_findings: list[str],
    unexpected: list[Any],
    missing_slots: list[Any],
    staging_status: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    git_status = local_git_coverage_status(git_items)
    if git_status == "BLOCKED":
        reasons.append(READINESS_BLOCKED_LOCAL_WORK)
    if staging_status != "PASS":
        reasons.append("STAGING_HASHES_FAIL")
    if "MISSING_HERMES_HOME_VOLUME" in docker_findings:
        reasons.append("MISSING_HERMES_HOME_VOLUME")
    if "WRONG_RUNTIME_UID_GID" in docker_findings:
        reasons.append("WRONG_RUNTIME_UID_GID")
    if "STALE_OR_WRONG_UPSTREAM_PIN" in docker_findings or "STALE_OR_WRONG_UPSTREAM_PIN" in pin_findings:
        reasons.append("STALE_OR_WRONG_UPSTREAM_PIN")
    if "STALE_OR_WRONG_IMAGE_CONTRACT" in docker_findings or "STALE_OR_WRONG_IMAGE_CONTRACT" in pin_findings:
        reasons.append("STALE_OR_WRONG_IMAGE_CONTRACT")
    if unexpected:
        reasons.append("UNEXPECTED_SECRET_SLOT")
    if missing_slots:
        reasons.append("MISSING_DEVELOPER_SECRET_SLOT")
    if reasons:
        if READINESS_BLOCKED_LOCAL_WORK in reasons and len(reasons) == 1:
            return READINESS_BLOCKED_LOCAL_WORK, reasons
        return READINESS_BLOCKED, reasons
    return READINESS_READY, reasons


def check_checked_in_pins(pin: Mapping[str, Any] | None = None) -> list[str]:
    data = dict(pin) if pin is not None else load_pin()
    findings: list[str] = []
    if str(data.get("upstream_image_digest") or "") != PINNED_DIGEST:
        findings.append("STALE_OR_WRONG_UPSTREAM_PIN")
    if str(data.get("developer_image_contract_version") or "") != IMAGE_CONTRACT_VERSION:
        findings.append("STALE_OR_WRONG_IMAGE_CONTRACT")
    return list(dict.fromkeys(findings))


def run_audit(
    *,
    repo_a_root: Path | None = None,
    repo_b: Path | None = None,
    staging_root: Path | None = None,
    credentials_dir: Path | None = None,
    desktop_root: Path | None = None,
    write_live_manifest: bool = False,
    now: datetime | None = None,
    git_runner=None,
    docker_runner=None,
    inspect_payload: dict[str, Any] | None = None,
    volumes_present: dict[str, bool] | None = None,
    telegram_meta: dict[str, Any] | None = None,
    pin: Mapping[str, Any] | None = None,
    skip_host_trust: bool = False,
    staging_index_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not skip_host_trust:
        assert_trusted_host_launcher(Path(__file__), repo_a_root or REPO_ROOT)

    root_a = Path(repo_a_root) if repo_a_root is not None else REPO_ROOT
    root_b = Path(repo_b) if repo_b is not None else repo_b_root()
    staging = Path(staging_root) if staging_root is not None else DEFAULT_STAGING_PACK

    pin_data = dict(pin) if pin is not None else load_pin()
    pins = extract_hermes_pins(pin_data)
    pin_findings = check_checked_in_pins(pin_data)

    snap_a = inspect_repo_a(root_a, runner=git_runner)
    snap_b = inspect_repo_b(root_b, runner=git_runner)

    if staging_index_override is not None:
        staging_index = dict(staging_index_override)
        staging_verify = {
            "path": str(staging),
            "hash_manifest": "hashes.sha256",
            "status": staging_index.get("hash_status") or "PASS",
            "checked": staging_index.get("checked") or 0,
            "missing": [],
            "mismatched": [],
        }
    else:
        staging_verify = verify_staging_hashes(staging)
        staging_index = load_staging_index(staging, git_runner=git_runner)
        staging_index["hash_status"] = staging_verify["status"]

    git_items = classify_local_work(snap_a, repo="A", staging_index=staging_index)
    if snap_b is not None:
        git_items.extend(classify_local_work(snap_b, repo="B", staging_index=staging_index))

    docker = inspect_docker(
        runner=docker_runner,
        expected_contract_version=pins["developer_image_contract_version"],
        inspect_payload=inspect_payload,
        volumes_present=volumes_present,
        telegram_meta=telegram_meta,
    )
    slots = inspect_developer_secret_slots(
        credentials_dir=credentials_dir,
        telegram_meta=docker.telegram_slot,
    )
    desktop = inspect_desktop_source(
        desktop_root,
        expected_sha=pins["upstream_release_sha"],
        expected_release=pins["upstream_release"],
    )
    if desktop.get("status") == "WRONG_PIN":
        pin_findings.append("STALE_OR_WRONG_UPSTREAM_PIN")

    readiness, reasons = evaluate_readiness(
        git_items=git_items,
        docker_findings=docker.findings,
        pin_findings=pin_findings,
        unexpected=unexpected_slots(slots),
        missing_slots=missing_host_slots(slots),
        staging_status=str(staging_verify.get("status") or "FAIL"),
    )

    excluded = production_paths_are_excluded(
        REQUIRED_HOST_PATHS,
        [str(item["path"]) for item in slots if item.get("kind") == "host_file"],
    )

    manifest = build_manifest(
        repo_a=snap_a.to_dict(),
        repo_b=(snap_b.to_dict() if snap_b is not None else {"canonical_sha": ""}),
        hermes=pins,
        desktop=desktop,
        recovery_staging_pack=staging_record(staging, staging_verify, staging_index),
        created_at=None if now is None else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if hasattr(now, "strftime")
        else str(now),
        extra={"runtime": {"user": "hermes", "uid": RUNTIME_UID, "gid": RUNTIME_GID, "HERMES_HOME": "/opt/data"}},
    )

    report: dict[str, Any] = {
        "recovery_schema_version": RECOVERY_SCHEMA_VERSION,
        "recovery_architecture": RECOVERY_ARCHITECTURE,
        "off_device_encrypted_backup": OFF_DEVICE_ENCRYPTED_BACKUP,
        "repo_a": snap_a.to_dict(),
        "repo_b": snap_b.to_dict() if snap_b is not None else None,
        "hermes_pins": pins,
        "git_coverage": local_git_coverage_status(git_items),
        "local_work": [item.to_dict() for item in git_items],
        "docker": docker.to_dict(),
        "secret_slots": slot_summaries(slots),
        "production_secret_paths_excluded": "YES" if excluded else "NO",
        "staging": staging_record(staging, staging_verify, staging_index),
        "desktop": desktop,
        "backup_readiness": readiness,
        "backup_readiness_reasons": reasons,
        "hermes_home_volume": HERMES_HOME_VOLUME,
        "hermes_home_class": HERMES_HOME_CLASS,
        "pin_findings": pin_findings,
        "manifest": manifest,
    }
    assert_no_secret_leaks(report, context="developer-hermes-recovery-audit")
    if write_live_manifest:
        dest = root_a / LIVE_MANIFEST_RELATIVE
        write_manifest(dest, manifest)
        report["live_manifest_path"] = str(dest)
        assert_no_secret_leaks(dest.read_text(encoding="utf-8"), context=str(dest))
    return report


def format_human_report(report: Mapping[str, Any]) -> str:
    slots = report.get("secret_slots") or []
    slot_lines = [
        f"- {item['id']}: {item['status']} ({item['purpose']}; {item['path']})"
        for item in slots
    ]
    repo_a = report.get("repo_a") or {}
    repo_b = report.get("repo_b") or {}
    lines = [
        f"SLICE = RECOVERY_1_MANIFEST_AND_AUDIT",
        f"RECOVERY_ARCHITECTURE = {report.get('recovery_architecture')}",
        f"CURRENT_CANONICAL_REPO_A_SHA = {repo_a.get('canonical_sha')}",
        f"CURRENT_CANONICAL_REPO_B_SHA = {repo_b.get('canonical_sha') if repo_b else ''}",
        f"HERMES_HOME_VOLUME = {report.get('hermes_home_volume')}",
        f"HERMES_HOME_CLASS = {report.get('hermes_home_class')}",
        f"LOCAL_GIT_COVERAGE = {report.get('git_coverage')}",
        f"RECOVERY_0B_STAGING_HASHES = {(report.get('staging') or {}).get('hash_status')}",
        f"BACKUP_READINESS = {report.get('backup_readiness')}",
        f"OFF_DEVICE_ENCRYPTED_BACKUP = {report.get('off_device_encrypted_backup')}",
        f"PRODUCTION_SECRET_PATHS_EXCLUDED = {report.get('production_secret_paths_excluded')}",
        "DEVELOPER_SECRET_SLOTS =",
        *slot_lines,
        f"BACKUP_READINESS_REASONS = {','.join(report.get('backup_readiness_reasons') or []) or 'NONE'}",
    ]
    text = "\n".join(lines) + "\n"
    assert_no_secret_leaks(text, context="human-audit-report")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Developer Hermes recovery audit")
    parser.add_argument("--json", action="store_true", help="Print the non-secret JSON report")
    parser.add_argument("--write-manifest", action="store_true", help="Write the live gitignored manifest")
    parser.add_argument("--staging", default="", help="Recovery 0B staging pack path")
    parser.add_argument("--repo-b", default="", help="Repo B checkout (read-only git inspect)")
    parser.add_argument("--credentials-dir", default="", help="Override Developer credentials directory")
    args = parser.parse_args(argv)
    report = run_audit(
        repo_b=Path(args.repo_b) if args.repo_b else None,
        staging_root=Path(args.staging) if args.staging else None,
        credentials_dir=Path(args.credentials_dir) if args.credentials_dir else None,
        write_live_manifest=args.write_manifest,
    )
    if args.json:
        print(json.dumps(strip_volatile(report), indent=2, sort_keys=True))
    else:
        print(format_human_report(report), end="")
    return 0 if report["backup_readiness"] == READINESS_READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
