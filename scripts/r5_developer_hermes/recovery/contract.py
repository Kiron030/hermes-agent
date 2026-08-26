"""Non-secret Developer Hermes recovery contract (Slice 1).

Machine-readable identities, volume classes, secret *slots*, and excluded
production paths. No credential values live here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


RECOVERY_SCHEMA_VERSION = "developer-hermes-recovery-v1"
RECOVERY_ARCHITECTURE = "PINNED_GIT_REBUILD_PLUS_ENCRYPTED_HOME"
OFF_DEVICE_ENCRYPTED_BACKUP = "NOT_YET"
OFF_DEVICE_ENCRYPTED_BACKUP_YES = "YES"
FUTURE_BACKUP_TOOL = "restic"
FUTURE_BACKUP_STATUS = "NOT_YET"
BACKUP_TOOL = "restic"
BACKUP_STATUS_PRESENT = "PRESENT"
RESTIC_VERSION = "0.18.1"
RESTIC_WINDOWS_AMD64_NAME = "restic_0.18.1_windows_amd64.zip"
RESTIC_WINDOWS_AMD64_SHA256 = "0c1a713440578cb400d2e76208feb24f1b339426b075a21f73b6b2132692515d"
RESTIC_RELEASE_BASE = "https://github.com/restic/restic/releases/download/v0.18.1"
USB_LAYOUT_ROOT_NAME = "HERMES-RECOVERY"
USB_RECOMMENDED_LABEL = "HERMES_RECOVERY"
BACKUP_SPACE_MARGIN_BYTES = 512 * 1024 * 1024
BACKUP_SPACE_MARGIN_RATIO = 0.20

REPO_A_CANONICAL_REMOTE = "https://github.com/Kiron030/hermes-agent.git"
REPO_A_CANONICAL_BRANCH = "powerunits-internal-setup"
REPO_B_CANONICAL_REMOTE = "https://github.com/Kiron030/Powerunits.io.git"
REPO_B_CANONICAL_BRANCH = "main"
REPO_B_LOCAL_NAME = "EU-PP-Database"

DEFAULT_STAGING_PACK = Path(
    r"W:\Workbench\backups\recovery-0b-local-git-safety-20260826T1445Z"
)
DEFAULT_STAGING_CREATED_AT = "2026-08-26T14:45:00Z"
STAGING_HASH_MANIFEST_NAME = "hashes.sha256"
STAGING_INVENTORY_NAME = "INVENTORY.txt"

HERMES_HOME_VOLUME = "r5-developer-hermes-home"
HERMES_HOME_CLASS = "MUST_BACKUP_ENCRYPTED_FULL_LOGICAL"
VOLUME_BACKUP_MECHANISM = "LOGICAL_VOLUME_EXPORT"
RAW_DOCKER_DESKTOP_PATH_COPY = "FORBIDDEN"

REGENERATABLE_VOLUME_CLASS = "REGENERATABLE_FROM_GIT_AND_HOST_SLOTS"

NAMED_VOLUMES: tuple[dict[str, str], ...] = (
    {
        "name": HERMES_HOME_VOLUME,
        "class": HERMES_HOME_CLASS,
        "mechanism": VOLUME_BACKUP_MECHANISM,
        "raw_docker_desktop_path_copy": RAW_DOCKER_DESKTOP_PATH_COPY,
        "role": "Developer HERMES_HOME /opt/data",
    },
    {
        "name": "r5-egress-broker-state",
        "class": REGENERATABLE_VOLUME_CLASS,
        "mechanism": "RECREATE_BROKER",
        "raw_docker_desktop_path_copy": RAW_DOCKER_DESKTOP_PATH_COPY,
        "role": "Egress broker private state; rebuild from Git + host token slot",
    },
    {
        "name": "r5-egress-ca-pub",
        "class": REGENERATABLE_VOLUME_CLASS,
        "mechanism": "RECREATE_BROKER",
        "raw_docker_desktop_path_copy": RAW_DOCKER_DESKTOP_PATH_COPY,
        "role": "Published broker CA; rebuild with broker",
    },
    {
        "name": "r5-egress-broker-home",
        "class": REGENERATABLE_VOLUME_CLASS,
        "mechanism": "RECREATE_BROKER",
        "raw_docker_desktop_path_copy": RAW_DOCKER_DESKTOP_PATH_COPY,
        "role": "Named /opt/data for broker image VOLUME; not Developer home",
    },
)

REQUIRED_NAMED_VOLUMES: tuple[str, ...] = (HERMES_HOME_VOLUME,)

RUNTIME_USER = "hermes"
RUNTIME_UID = 10000
RUNTIME_GID = 10000
HERMES_HOME = "/opt/data"

PROFILE_NAMES: tuple[str, ...] = ("default", "telegram-ops")

HOST_PATH_PORTABILITY = "LITERAL_W_DRIVE"
RESTORE_HOST_ROOT_DESIGN = "PRESERVE_W_ON_REPLACEMENT_MACHINE"
HOST_ROOT_PARAMETERIZATION = "DEFERRED"

REQUIRED_HOST_PATHS: tuple[str, ...] = (
    r"W:\hermes-dev\workspace\hermes-agent",
    r"W:\hermes-dev\workspace\EU-PP-Database",
    r"W:\hermes-dev\credentials",
    r"W:\cache\hermes-desktop-official-v2026.8.19",
)

DEVELOPER_CREDENTIALS_DIR = Path(r"W:\hermes-dev\credentials")
DESKTOP_OFFICIAL_SOURCE = Path(r"W:\cache\hermes-desktop-official-v2026.8.19")
DESKTOP_EXPECTED_PACKAGING_PATH = (
    r"W:\cache\hermes-desktop-official-v2026.8.19\apps\desktop"
)
DESKTOP_PACK_ARTIFACT_RELATIVE = r"apps\desktop\release\win-unpacked\Hermes.exe"
DESKTOP_SOURCE_OF_TRUTH = "OFFICIAL_PINNED_SOURCE_NOT_BUILT_EXE"

DEVELOPER_SECRET_SLOTS: tuple[dict[str, str], ...] = (
    {
        "id": "developer-hermes-model",
        "purpose": "Developer model provider keys",
        "path": r"W:\hermes-dev\credentials\developer-hermes-model.env",
        "expected_filename": "developer-hermes-model.env",
        "kind": "host_file",
    },
    {
        "id": "developer-hermes-desktop",
        "purpose": "Developer Desktop gateway basic-auth",
        "path": r"W:\hermes-dev\credentials\developer-hermes-desktop.env",
        "expected_filename": "developer-hermes-desktop.env",
        "kind": "host_file",
    },
    {
        "id": "developer-hermes-egress",
        "purpose": "Developer egress broker token",
        "path": r"W:\hermes-dev\credentials\developer-hermes-egress.token",
        "expected_filename": "developer-hermes-egress.token",
        "kind": "host_file",
    },
    {
        "id": "developer-telegram-ops-env",
        "purpose": "Developer Telegram profile token slot",
        "path": "/opt/data/profiles/telegram-ops/.env",
        "expected_filename": ".env",
        "kind": "volume_logical",
        "volume": HERMES_HOME_VOLUME,
        "inspect": "docker_exec_metadata_only_if_running",
    },
)

PRODUCTION_SECRET_PATHS_EXCLUDED: tuple[str, ...] = (
    r"%USERPROFILE%\.powerunits\secrets",
    r"%USERPROFILE%\.powerunits\secrets\repo-b.env",
    r"%USERPROFILE%\.powerunits\secrets\app.env",
    r"%USERPROFILE%\.powerunits\secrets\mapbox.env",
    r"%APPDATA%\GitHub CLI",
    r"%LOCALAPPDATA%\GitHub CLI",
    r"%USERPROFILE%\.git-credentials",
    r"\\.\pipe\docker_engine",
    "/var/run/docker.sock",
    r"%USERPROFILE%",
)

PRODUCTION_SECRET_CLASSES_EXCLUDED: tuple[str, ...] = (
    "Railway/Operator credentials",
    "production database credentials",
    "host GitHub credential store",
    "Docker socket",
    "whole Windows profile",
    "Operator Hermes Railway runtime",
)

VOLATILE_MANIFEST_FIELDS: tuple[str, ...] = (
    "created_at",
    "audit_run_id",
    "future_backup.snapshot_id",
    "encrypted_backup.snapshot_id",
    "encrypted_backup.created_at",
    "recovery_staging_pack.verified_at",
)

READINESS_READY = "READY_FOR_RECOVERY_2"
READINESS_BLOCKED = "BLOCKED"
READINESS_BLOCKED_LOCAL_WORK = "BLOCKED_LOCAL_WORK"
BACKUP_BLOCKED_LOCAL_WORK = "BACKUP_BLOCKED_LOCAL_WORK"
USB_SYSTEM_DRIVE = "USB_SYSTEM_DRIVE"
USB_NOT_REMOVABLE = "USB_NOT_REMOVABLE"
USB_AMBIGUOUS = "USB_AMBIGUOUS"
USB_NOT_CONFIRMED = "USB_NOT_CONFIRMED"
USB_INSUFFICIENT_SPACE = "USB_INSUFFICIENT_SPACE"

COVERAGE_REMOTE_SAFE = "REMOTE_SAFE"
COVERAGE_STAGING_COVERED = "LOCAL_ONLY_BUT_RECOVERY_STAGED"
COVERAGE_UNCOVERED = "UNCOVERED"
COVERAGE_EXCLUDED_NOT_SOURCE = "EXCLUDED_NOT_SOURCE"

SLOT_PRESENT = "PRESENT"
SLOT_MISSING = "MISSING"
SLOT_UNEXPECTED = "UNEXPECTED"
SLOT_UNKNOWN = "UNKNOWN"

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "developer-hermes-recovery-manifest.schema.json"
TEMPLATE_PATH = HERE / "developer-hermes-recovery-manifest.template.json"
LIVE_MANIFEST_RELATIVE = Path(".r5-dev") / "recovery" / "developer-hermes-recovery-manifest.json"


def developer_secret_slot_ids() -> tuple[str, ...]:
    return tuple(str(slot["id"]) for slot in DEVELOPER_SECRET_SLOTS)


def developer_secret_slot_filenames() -> frozenset[str]:
    return frozenset(str(slot["expected_filename"]) for slot in DEVELOPER_SECRET_SLOTS)


def host_secret_slot_paths() -> tuple[Path, ...]:
    return tuple(
        Path(slot["path"])
        for slot in DEVELOPER_SECRET_SLOTS
        if slot.get("kind") == "host_file"
    )


def volume_class_by_name() -> dict[str, str]:
    return {item["name"]: item["class"] for item in NAMED_VOLUMES}


def required_volume_names() -> tuple[str, ...]:
    return REQUIRED_NAMED_VOLUMES


def contract_identity() -> dict[str, Any]:
    """Static non-secret identity block used by the template and tests."""
    return {
        "recovery_schema_version": RECOVERY_SCHEMA_VERSION,
        "recovery_architecture": RECOVERY_ARCHITECTURE,
        "off_device_encrypted_backup": OFF_DEVICE_ENCRYPTED_BACKUP,
        "repo_a": {
            "remote": REPO_A_CANONICAL_REMOTE,
            "canonical_branch": REPO_A_CANONICAL_BRANCH,
            "canonical_sha": "<origin-at-generation>",
        },
        "repo_b": {
            "remote": REPO_B_CANONICAL_REMOTE,
            "canonical_branch": REPO_B_CANONICAL_BRANCH,
            "canonical_sha": "<origin-at-generation>",
            "local_name": REPO_B_LOCAL_NAME,
        },
        "runtime": {
            "user": RUNTIME_USER,
            "uid": RUNTIME_UID,
            "gid": RUNTIME_GID,
            "HERMES_HOME": HERMES_HOME,
        },
        "required_named_volumes": list(REQUIRED_NAMED_VOLUMES),
        "named_volumes": [dict(item) for item in NAMED_VOLUMES],
        "required_host_paths": list(REQUIRED_HOST_PATHS),
        "host_path_portability": {
            "current_constraint": HOST_PATH_PORTABILITY,
            "restore_design": RESTORE_HOST_ROOT_DESIGN,
            "later_parameterize": HOST_ROOT_PARAMETERIZATION,
        },
        "profile_names": list(PROFILE_NAMES),
        "desktop": {
            "official_upstream_source_pin": str(DESKTOP_OFFICIAL_SOURCE),
            "expected_packaging_path": DESKTOP_EXPECTED_PACKAGING_PATH,
            "source_of_truth": DESKTOP_SOURCE_OF_TRUTH,
            "built_exe_is_source_of_truth": "NO",
        },
        "developer_secret_slots": [dict(item) for item in DEVELOPER_SECRET_SLOTS],
        "production_secret_paths_excluded": list(PRODUCTION_SECRET_PATHS_EXCLUDED),
        "production_secret_classes_excluded": list(PRODUCTION_SECRET_CLASSES_EXCLUDED),
        "future_backup": {
            "tool": FUTURE_BACKUP_TOOL,
            "status": FUTURE_BACKUP_STATUS,
            "snapshot_id": None,
            "artifact_checksums": {},
        },
        "encrypted_backup": {
            "tool": BACKUP_TOOL,
            "status": FUTURE_BACKUP_STATUS,
            "restic_version": RESTIC_VERSION,
            "snapshot_id": None,
            "created_at": None,
            "artifact_checksums": {},
        },
    }
