"""Versioned non-secret Developer Hermes recovery manifest."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from r5_developer_hermes.harness import load_pin
from r5_developer_hermes.recovery.contract import (
    FUTURE_BACKUP_STATUS,
    FUTURE_BACKUP_TOOL,
    OFF_DEVICE_ENCRYPTED_BACKUP,
    RECOVERY_ARCHITECTURE,
    RECOVERY_SCHEMA_VERSION,
    SCHEMA_PATH,
    TEMPLATE_PATH,
    VOLATILE_MANIFEST_FIELDS,
    contract_identity,
)
from r5_developer_hermes.recovery.secrets import assert_no_secret_leaks


def utc_now(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_hermes_pins(pin: Mapping[str, Any] | None = None) -> dict[str, str]:
    data = dict(pin) if pin is not None else load_pin()
    return {
        "upstream_release": str(data["upstream_release"]),
        "upstream_project_version": str(data["upstream_project_version"]),
        "upstream_release_sha": str(data["upstream_release_sha"]),
        "upstream_image_digest": str(data["upstream_image_digest"]),
        "developer_image_contract_version": str(data["developer_image_contract_version"]),
        "developer_image": str(data.get("developer_image") or ""),
    }


def strip_volatile(payload: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = copy.deepcopy(dict(payload))
    for field in VOLATILE_MANIFEST_FIELDS:
        cursor: Any = cleaned
        parts = field.split(".")
        for key in parts[:-1]:
            if not isinstance(cursor, dict) or key not in cursor:
                cursor = None
                break
            cursor = cursor[key]
        if isinstance(cursor, dict):
            cursor.pop(parts[-1], None)
    cleaned.pop("created_at", None)
    cleaned.pop("audit_run_id", None)
    return cleaned


def canonicalize(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_template() -> dict[str, Any]:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def validate_schema_version(payload: Mapping[str, Any]) -> None:
    if payload.get("recovery_schema_version") != RECOVERY_SCHEMA_VERSION:
        raise ValueError("recovery_schema_version mismatch")


def required_template_keys() -> tuple[str, ...]:
    return (
        "recovery_schema_version",
        "created_at",
        "repo_a",
        "repo_b",
        "hermes",
        "developer_image_contract_version",
        "runtime",
        "required_named_volumes",
        "required_host_paths",
        "profile_names",
        "desktop",
        "recovery_staging_pack",
        "future_backup",
    )


def build_manifest(
    *,
    repo_a: Mapping[str, Any],
    repo_b: Mapping[str, Any],
    hermes: Mapping[str, Any] | None = None,
    runtime: Mapping[str, Any] | None = None,
    desktop: Mapping[str, Any] | None = None,
    recovery_staging_pack: Mapping[str, Any] | None = None,
    future_backup: Mapping[str, Any] | None = None,
    created_at: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = contract_identity()
    pins = extract_hermes_pins(hermes) if hermes and "upstream_release" in hermes else extract_hermes_pins()
    if hermes:
        pins.update({key: str(value) for key, value in hermes.items() if value is not None})
    payload: dict[str, Any] = {
        "recovery_schema_version": RECOVERY_SCHEMA_VERSION,
        "recovery_architecture": RECOVERY_ARCHITECTURE,
        "created_at": created_at or utc_now(),
        "off_device_encrypted_backup": OFF_DEVICE_ENCRYPTED_BACKUP,
        "repo_a": {
            "remote": repo_a.get("remote") or identity["repo_a"]["remote"],
            "canonical_branch": repo_a.get("canonical_branch") or identity["repo_a"]["canonical_branch"],
            "canonical_sha": repo_a.get("canonical_sha") or "",
        },
        "repo_b": {
            "remote": repo_b.get("remote") or identity["repo_b"]["remote"],
            "canonical_branch": repo_b.get("canonical_branch") or identity["repo_b"]["canonical_branch"],
            "canonical_sha": repo_b.get("canonical_sha") or "",
            "local_name": repo_b.get("local_name") or identity["repo_b"]["local_name"],
        },
        "hermes": {
            "upstream_release": pins["upstream_release"],
            "upstream_project_version": pins["upstream_project_version"],
            "upstream_release_sha": pins["upstream_release_sha"],
            "upstream_image_digest": pins["upstream_image_digest"],
        },
        "developer_image_contract_version": pins["developer_image_contract_version"],
        "runtime": dict(runtime or identity["runtime"]),
        "required_named_volumes": list(identity["required_named_volumes"]),
        "named_volumes": list(identity["named_volumes"]),
        "required_host_paths": list(identity["required_host_paths"]),
        "host_path_portability": dict(identity["host_path_portability"]),
        "profile_names": list(identity["profile_names"]),
        "desktop": dict(desktop or identity["desktop"]),
        "recovery_staging_pack": dict(
            recovery_staging_pack
            or {
                "path": "",
                "hash_manifest": "hashes.sha256",
                "creation_timestamp": "",
            }
        ),
        "future_backup": dict(
            future_backup
            or {
                "tool": FUTURE_BACKUP_TOOL,
                "status": FUTURE_BACKUP_STATUS,
                "snapshot_id": None,
                "artifact_checksums": {},
            }
        ),
        "developer_secret_slots": list(identity["developer_secret_slots"]),
        "production_secret_paths_excluded": list(identity["production_secret_paths_excluded"]),
        "production_secret_classes_excluded": list(identity["production_secret_classes_excluded"]),
    }
    if extra:
        for key, value in extra.items():
            if key in payload and isinstance(payload[key], dict) and isinstance(value, dict):
                payload[key] = {**payload[key], **value}
            else:
                payload[key] = value
    validate_schema_version(payload)
    for key in required_template_keys():
        if key not in payload:
            raise ValueError(f"manifest missing {key}")
    assert_no_secret_leaks(payload, context="developer-hermes-recovery-manifest")
    return payload


def write_manifest(path: Path, payload: Mapping[str, Any]) -> Path:
    assert_no_secret_leaks(payload, context=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonicalize(payload), encoding="utf-8")
    return path
