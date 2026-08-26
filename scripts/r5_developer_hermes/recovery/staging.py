"""Read-only verification of the Recovery 0B local-git-safety staging pack."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Callable


from r5_developer_hermes.recovery.contract import (
    DEFAULT_STAGING_CREATED_AT,
    DEFAULT_STAGING_PACK,
    STAGING_HASH_MANIFEST_NAME,
    STAGING_INVENTORY_NAME,
)
from r5_developer_hermes.recovery.git_state import default_git_runner


GitRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]


def parse_sha256_manifest(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, relative = line.partition(" ")
        relative = relative.strip().lstrip("*")
        if not digest or not relative:
            raise ValueError("invalid hashes.sha256 line")
        entries.append((digest.lower(), relative.replace("/", "\\")))
    return entries


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum_file(root: Path, name: str = STAGING_HASH_MANIFEST_NAME) -> dict[str, Any]:
    manifest = root / name
    result: dict[str, Any] = {
        "path": str(root),
        "hash_manifest": name,
        "status": "FAIL",
        "checked": 0,
        "missing": [],
        "mismatched": [],
    }
    if not root.is_dir() or not manifest.is_file():
        result["missing"].append(name)
        return result
    entries = parse_sha256_manifest(manifest.read_text(encoding="utf-8"))
    for expected, relative in entries:
        target = root / relative
        result["checked"] += 1
        if not target.is_file():
            result["missing"].append(relative)
            continue
        actual = file_sha256(target)
        if actual != expected:
            result["mismatched"].append(relative)
    if not result["missing"] and not result["mismatched"]:
        result["status"] = "PASS"
    return result


def verify_staging_hashes(root: Path) -> dict[str, Any]:
    return verify_checksum_file(root, STAGING_HASH_MANIFEST_NAME)


def load_staging_index(
    root: Path,
    *,
    bundle_heads: list[str] | None = None,
    git_runner: GitRunner | None = None,
) -> dict[str, Any]:
    inventory_path = root / STAGING_INVENTORY_NAME
    inventory_text = inventory_path.read_text(encoding="utf-8") if inventory_path.is_file() else ""
    artifact_names = [path.name for path in root.rglob("*") if path.is_file()]
    heads = list(bundle_heads or [])
    if bundle_heads is None:
        runner = git_runner or default_git_runner
        seen: set[Path] = set()
        for bundle in (*root.glob("bundles/*.bundle"), *root.glob("bundles/*.bundle")):
            resolved = bundle.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            completed = runner(["bundle", "list-heads", str(bundle)], root)
            if completed.returncode == 0:
                for line in (completed.stdout or "").splitlines():
                    sha = line.split()[0] if line.split() else ""
                    if sha:
                        heads.append(sha)
    return {
        "path": str(root),
        "creation_timestamp": DEFAULT_STAGING_CREATED_AT
        if root.resolve() == DEFAULT_STAGING_PACK.resolve()
        else None,
        "inventory_text": inventory_text,
        "artifact_names": artifact_names,
        "bundle_heads": heads,
        "hash_manifest": STAGING_HASH_MANIFEST_NAME,
    }


def write_sha256_manifest(path: Path, files: list[Path], *, root: Path | None = None) -> Path:
    lines: list[str] = []
    base = root or path.parent
    for item in files:
        if not item.is_file():
            continue
        relative = item.relative_to(base)
        lines.append(f"{file_sha256(item)}  {relative.as_posix()}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def staging_record(root: Path, verification: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": str(root),
        "hash_manifest": STAGING_HASH_MANIFEST_NAME,
        "creation_timestamp": index.get("creation_timestamp") or DEFAULT_STAGING_CREATED_AT,
        "hash_status": verification.get("status"),
        "checked": verification.get("checked"),
        "missing": list(verification.get("missing") or []),
        "mismatched": list(verification.get("mismatched") or []),
    }
