"""Secret-slot metadata and fail-closed leak scanning.

Reports PRESENT / MISSING / UNEXPECTED / UNKNOWN. Never reads or emits
credential values.
"""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from typing import Any, Iterable

from r5_developer_hermes.recovery.contract import (
    DEVELOPER_CREDENTIALS_DIR,
    DEVELOPER_SECRET_SLOTS,
    PRODUCTION_SECRET_PATHS_EXCLUDED,
    SLOT_MISSING,
    SLOT_PRESENT,
    SLOT_UNEXPECTED,
    SLOT_UNKNOWN,
    developer_secret_slot_filenames,
)


SECRET_SHAPED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{10,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+=/]{8,}"),
    re.compile(r"(?i)postgres(?:ql)?://\S+"),
    re.compile(r"(?i)mysql://\S+"),
    re.compile(r"(?i)mongodb(?:\+srv)?://\S+"),
    re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)railway[_-]?token\s*[:=]\s*\S+"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S{8,}"),
)


def iter_strings(payload: Any) -> Iterable[str]:
    if payload is None:
        return
    if isinstance(payload, str):
        yield payload
        return
    if isinstance(payload, (int, float, bool)):
        yield str(payload)
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield str(key)
            yield from iter_strings(value)
        return
    if isinstance(payload, (list, tuple, set)):
        for item in payload:
            yield from iter_strings(item)


def find_secret_shaped_leaks(payload: Any) -> list[str]:
    """Return pattern names that matched. Never return the matched text."""
    hits: list[str] = []
    blob = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    for pattern in SECRET_SHAPED_PATTERNS:
        if pattern.search(blob):
            hits.append(pattern.pattern)
    return hits


def assert_no_secret_leaks(payload: Any, *, context: str) -> None:
    hits = find_secret_shaped_leaks(payload)
    if hits:
        raise RuntimeError(f"secret-shaped value leaked into {context}")


def production_paths_are_excluded(required_paths: Iterable[str], slot_paths: Iterable[str]) -> bool:
    required = {normalize_compare_path(path) for path in required_paths}
    slots = {normalize_compare_path(path) for path in slot_paths}
    forbidden = {normalize_compare_path(path) for path in PRODUCTION_SECRET_PATHS_EXCLUDED}
    return required.isdisjoint(forbidden) and slots.isdisjoint(forbidden)


def normalize_compare_path(path: str) -> str:
    raw = path.replace("/", "\\").strip()
    return raw.lower()


def _stat_metadata(path: Path) -> dict[str, Any]:
    info = path.stat()
    is_file = path.is_file()
    is_dir = path.is_dir()
    kind = "file" if is_file else "directory" if is_dir else "other"
    return {
        "exists": True,
        "type": kind,
        "size": int(info.st_size) if is_file else None,
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "expected_filename": path.name,
    }


def inspect_host_slot(slot: dict[str, str], *, root: Path | None = None) -> dict[str, Any]:
    """Metadata only. The file is never opened for reading."""
    declared = Path(slot["path"])
    target = (root / declared.name) if root is not None else declared
    record: dict[str, Any] = {
        "id": slot["id"],
        "purpose": slot["purpose"],
        "path": slot["path"] if root is None else str(target),
        "expected_filename": slot["expected_filename"],
        "kind": slot["kind"],
        "status": SLOT_MISSING,
        "exists": False,
        "type": None,
        "size": None,
        "owner_acl": None,
    }
    if not target.exists():
        return record
    meta = _stat_metadata(target)
    record.update(meta)
    record["status"] = SLOT_PRESENT
    if target.name != slot["expected_filename"]:
        record["status"] = SLOT_UNEXPECTED
    return record


def inspect_credentials_dir_unexpected(
    directory: Path | None = None,
    *,
    allow_filenames: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Flag extra files under the Developer credentials directory."""
    root = directory if directory is not None else DEVELOPER_CREDENTIALS_DIR
    allowed = allow_filenames if allow_filenames is not None else developer_secret_slot_filenames()
    unexpected: list[dict[str, Any]] = []
    if not root.is_dir():
        return unexpected
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_file():
            continue
        if child.name in allowed:
            continue
        unexpected.append(
            {
                "id": f"unexpected:{child.name}",
                "purpose": "not on Developer recovery secret-slot allowlist",
                "path": str(child),
                "expected_filename": child.name,
                "kind": "host_file",
                "status": SLOT_UNEXPECTED,
                "exists": True,
                "type": "file",
                "size": int(child.stat().st_size),
                "owner_acl": None,
            }
        )
    return unexpected


def inspect_developer_secret_slots(
    *,
    credentials_dir: Path | None = None,
    telegram_meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for slot in DEVELOPER_SECRET_SLOTS:
        if slot.get("kind") == "host_file":
            root = credentials_dir if credentials_dir is not None else None
            if root is not None:
                records.append(inspect_host_slot(slot, root=root))
            else:
                records.append(inspect_host_slot(slot))
            continue
        record = {
            "id": slot["id"],
            "purpose": slot["purpose"],
            "path": slot["path"],
            "expected_filename": slot["expected_filename"],
            "kind": slot["kind"],
            "volume": slot.get("volume"),
            "status": SLOT_UNKNOWN,
            "exists": None,
            "type": None,
            "size": None,
            "owner_acl": None,
        }
        if telegram_meta is not None:
            exists = bool(telegram_meta.get("exists"))
            record["exists"] = exists
            record["status"] = SLOT_PRESENT if exists else SLOT_MISSING
            record["type"] = "file" if exists else None
            if "size" in telegram_meta:
                record["size"] = telegram_meta.get("size")
            if "uid" in telegram_meta and "gid" in telegram_meta:
                record["owner_acl"] = f"{telegram_meta.get('uid')}:{telegram_meta.get('gid')}"
            if telegram_meta.get("mode"):
                record["mode"] = telegram_meta.get("mode")
        records.append(record)
    if credentials_dir is not None or DEVELOPER_CREDENTIALS_DIR.is_dir():
        scan_dir = credentials_dir if credentials_dir is not None else DEVELOPER_CREDENTIALS_DIR
        records.extend(inspect_credentials_dir_unexpected(scan_dir))
    return records


def slot_summaries(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Purpose/path/status only — the public audit surface."""
    return [
        {
            "id": str(item["id"]),
            "purpose": str(item["purpose"]),
            "path": str(item["path"]),
            "status": str(item["status"]),
        }
        for item in records
    ]


def unexpected_slots(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in records if item.get("status") == SLOT_UNEXPECTED]


def missing_host_slots(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in records
        if item.get("kind") == "host_file" and item.get("status") == SLOT_MISSING
    ]
