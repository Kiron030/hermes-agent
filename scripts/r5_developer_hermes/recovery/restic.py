"""Pinned restic bootstrap and password-safe invocation.

The recovery password is read only from RESTIC_PASSWORD. It is never placed
on a process command line and never written into logs or reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import urlopen

from r5_developer_hermes.recovery.contract import (
    RESTIC_CANONICAL_EXE,
    RESTIC_RELEASE_BASE,
    RESTIC_VERSION,
    RESTIC_WINDOWS_AMD64_MEMBER,
    RESTIC_WINDOWS_AMD64_NAME,
    RESTIC_WINDOWS_AMD64_SHA256,
)


ResticRunner = Callable[[list[str], Mapping[str, str] | None], subprocess.CompletedProcess[str]]
IterablePath = list[Path]

PASSWORD_ENV = "RESTIC_PASSWORD"
FORBIDDEN_PASSWORD_FLAGS = ("-p", "--password", "--password-command")
PINNED_VERSION_RE = re.compile(rf"^restic\s+{re.escape(RESTIC_VERSION)}(?:\s|$)")
EXPECTED_ZIP_MEMBERS = frozenset(
    {
        RESTIC_CANONICAL_EXE.lower(),
        RESTIC_WINDOWS_AMD64_MEMBER.lower(),
    }
)


class ResticError(RuntimeError):
    def __init__(self, message: str, *, argv: list[str] | None = None):
        super().__init__(message)
        self.argv = list(argv or [])


def restic_zip_url() -> str:
    return f"{RESTIC_RELEASE_BASE}/{RESTIC_WINDOWS_AMD64_NAME}"


def restic_sha256sums_url() -> str:
    return f"{RESTIC_RELEASE_BASE}/SHA256SUMS"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256sums(text: str, filename: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, name = line.partition(" ")
        name = name.strip()
        if name == filename:
            return digest.lower()
    raise ResticError(f"SHA256SUMS missing {filename}")


def assert_checksum(path: Path, expected: str) -> str:
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        raise ResticError("restic checksum mismatch; refusing unverified binary")
    return actual


def write_checksum_sidecar(binary: Path) -> Path:
    sidecar = Path(str(binary) + ".sha256")
    sidecar.write_text(sha256_file(binary) + "\n", encoding="utf-8")
    return sidecar


def verify_checksum_sidecar(binary: Path) -> str:
    sidecar = Path(str(binary) + ".sha256")
    if not sidecar.is_file():
        raise ResticError("cached restic checksum sidecar missing; refusing reuse")
    expected = sidecar.read_text(encoding="utf-8").strip().split()[0]
    return assert_checksum(binary, expected)


def redact_command(argv: list[str]) -> list[str]:
    redacted: list[str] = []
    skip_next = False
    for item in argv:
        if skip_next:
            redacted.append("<redacted>")
            skip_next = False
            continue
        if item in FORBIDDEN_PASSWORD_FLAGS:
            raise ResticError("restic password must not be passed as a command-line argument")
        if item.startswith("--password="):
            raise ResticError("restic password must not be passed as a command-line argument")
        redacted.append(item)
    return redacted


def default_restic_runner(argv: list[str], env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    redact_command(argv)
    merged = dict(os.environ)
    if env:
        merged.update(env)
    if not merged.get(PASSWORD_ENV):
        merged.pop(PASSWORD_ENV, None)
    return subprocess.run(argv, text=True, capture_output=True, check=False, env=merged)


def restic_version_text(binary: Path, *, runner: ResticRunner | None = None) -> str:
    restic = runner or default_restic_runner
    completed = restic([str(binary), "version"], None)
    if completed.returncode != 0:
        raise ResticError("restic version failed")
    return (completed.stdout or "").strip()


def version_matches_pin(version_text: str) -> bool:
    first = (version_text or "").strip().splitlines()[0] if version_text else ""
    return bool(PINNED_VERSION_RE.match(first))


def assert_pinned_version(binary: Path, *, runner: ResticRunner | None = None) -> str:
    text = restic_version_text(binary, runner=runner)
    if not version_matches_pin(text):
        raise ResticError("restic version mismatch; refusing unpinned binary")
    return text


def locate_existing_restic(*, extra_paths: IterablePath | None = None) -> Path | None:
    candidates: list[Path] = []
    if extra_paths:
        candidates.extend(Path(item) for item in extra_paths)
    which = shutil.which("restic")
    if which:
        candidates.append(Path(which))
    seen: set[Path] = set()
    for path in candidates:
        resolved = path
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        return resolved
    return None


def download_bytes(url: str, *, opener: Callable[[str], bytes] | None = None) -> bytes:
    if opener is not None:
        return opener(url)
    with urlopen(url, timeout=60) as handle:  # noqa: S310 — pinned GitHub release URL
        return handle.read()


def zip_member_is_safe(name: str) -> bool:
    raw = name.replace("\\", "/")
    if raw.startswith("/") or raw.startswith("../") or "/../" in f"/{raw}/":
        return False
    if raw in {".", ".."} or raw.endswith("/"):
        return False
    if Path(raw).is_absolute():
        return False
    return True


def select_restic_zip_member(names: list[str]) -> str:
    """Return the single official restic executable member. Fail closed otherwise."""
    safe: list[str] = []
    for name in names:
        if not zip_member_is_safe(name):
            raise ResticError("restic zip member rejected (zip-slip or unexpected path)")
        base = Path(name.replace("\\", "/")).name.lower()
        if base in EXPECTED_ZIP_MEMBERS:
            if "/" in name.replace("\\", "/") or "\\" in name:
                raise ResticError("restic zip member rejected (unexpected nested path)")
            safe.append(name)
    if not safe:
        raise ResticError("restic zip did not contain the expected restic executable")
    unique = list(dict.fromkeys(safe))
    if len(unique) != 1:
        raise ResticError("restic zip contained multiple restic executables")
    return unique[0]


def extract_pinned_restic_exe(archive: Path, dest_exe: Path) -> str:
    """Extract the official member to dest_exe. Archive checksum must already be verified."""
    scratch = Path(tempfile.mkdtemp(prefix="hermes-restic-extract-"))
    try:
        with zipfile.ZipFile(archive) as zipped:
            member = select_restic_zip_member(zipped.namelist())
            info = zipped.getinfo(member)
            if info.is_dir():
                raise ResticError("restic zip member is a directory")
            extracted = scratch / Path(member).name
            with zipped.open(member) as src, extracted.open("wb") as out:
                shutil.copyfileobj(src, out)
        dest_exe.parent.mkdir(parents=True, exist_ok=True)
        if dest_exe.exists():
            dest_exe.unlink()
        shutil.copy2(extracted, dest_exe)
        return member
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def host_restic_cache_dir(*, repo_root: Path | None = None) -> Path:
    root = Path(repo_root) if repo_root is not None else Path(".")
    return root / ".r5-dev" / "restic" / RESTIC_VERSION


def inspect_pinned_restic(
    dest_dir: Path,
    *,
    existing: Path | None = None,
    extra_paths: IterablePath | None = None,
    runner: ResticRunner | None = None,
) -> dict[str, Any]:
    """Read-only: is a verified pinned restic already available? Never downloads.

    PATH restic is ignored. Only a sidecar-verified binary is executed.
    """
    del extra_paths
    binary = dest_dir / RESTIC_CANONICAL_EXE
    candidates: list[Path] = []
    if existing and existing.is_file():
        candidates.append(existing)
    if binary.is_file():
        candidates.append(binary)
    for path in candidates:
        try:
            verify_checksum_sidecar(path)
            text = assert_pinned_version(path, runner=runner)
            return {
                "available": True,
                "binary": str(path),
                "version": RESTIC_VERSION,
                "version_text": text,
                "download": "NOT_NEEDED",
                "asset": RESTIC_WINDOWS_AMD64_NAME,
                "member": RESTIC_WINDOWS_AMD64_MEMBER,
                "sha256": RESTIC_WINDOWS_AMD64_SHA256,
            }
        except ResticError:
            continue
    return {
        "available": False,
        "binary": None,
        "version": RESTIC_VERSION,
        "download": "WOULD_DOWNLOAD",
        "asset": RESTIC_WINDOWS_AMD64_NAME,
        "member": RESTIC_WINDOWS_AMD64_MEMBER,
        "sha256": RESTIC_WINDOWS_AMD64_SHA256,
    }


def _trust_existing(path: Path, dest_exe: Path, *, runner: ResticRunner | None) -> dict[str, Any]:
    verify_checksum_sidecar(path)
    text = assert_pinned_version(path, runner=runner)
    dest_exe.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != dest_exe.resolve():
        shutil.copy2(path, dest_exe)
        write_checksum_sidecar(dest_exe)
    return {
        "binary": str(dest_exe if dest_exe.is_file() else path),
        "version": RESTIC_VERSION,
        "version_text": text,
        "source": "existing-pinned",
        "checksum_verified": "SIDECAR+VERSION_PIN",
    }


def bootstrap_restic(
    dest_dir: Path,
    *,
    existing: Path | None = None,
    allow_download: bool = True,
    opener: Callable[[str], bytes] | None = None,
    runner: ResticRunner | None = None,
    extra_paths: IterablePath | None = None,
) -> dict[str, Any]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_exe = dest_dir / RESTIC_CANONICAL_EXE
    if dest_exe.is_file():
        try:
            verify_checksum_sidecar(dest_exe)
            text = assert_pinned_version(dest_exe, runner=runner)
            return {
                "binary": str(dest_exe),
                "version": RESTIC_VERSION,
                "version_text": text,
                "source": "bootstrap-cache",
                "checksum_verified": "SIDECAR+VERSION_PIN",
            }
        except ResticError:
            dest_exe.unlink(missing_ok=True)
            Path(str(dest_exe) + ".sha256").unlink(missing_ok=True)

    if existing and existing.is_file():
        try:
            return _trust_existing(existing, dest_exe, runner=runner)
        except ResticError:
            pass

    del extra_paths

    if not allow_download:
        raise ResticError("pinned restic binary is not available and download is disabled")

    scratch = Path(tempfile.mkdtemp(prefix="hermes-restic-dl-"))
    try:
        sums = download_bytes(restic_sha256sums_url(), opener=opener)
        expected = parse_sha256sums(sums.decode("utf-8"), RESTIC_WINDOWS_AMD64_NAME)
        if expected != RESTIC_WINDOWS_AMD64_SHA256:
            raise ResticError("upstream SHA256SUMS does not match the pinned Windows restic checksum")
        payload = download_bytes(restic_zip_url(), opener=opener)
        if sha256_bytes(payload) != RESTIC_WINDOWS_AMD64_SHA256:
            raise ResticError("downloaded restic zip checksum mismatch; refusing unverified binary")
        archive = scratch / RESTIC_WINDOWS_AMD64_NAME
        archive.write_bytes(payload)
        (dest_dir / "SHA256SUMS").write_bytes(sums)
        member = extract_pinned_restic_exe(archive, dest_exe)
        text = assert_pinned_version(dest_exe, runner=runner)
        write_checksum_sidecar(dest_exe)
        return {
            "binary": str(dest_exe),
            "version": RESTIC_VERSION,
            "version_text": text,
            "source": "verified-download",
            "checksum_verified": "SHA256SUMS+PIN+VERSION",
            "sha256": RESTIC_WINDOWS_AMD64_SHA256,
            "member": member,
        }
    except Exception:
        dest_exe.unlink(missing_ok=True)
        Path(str(dest_exe) + ".sha256").unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def repository_exists(repo: Path) -> bool:
    return (repo / "config").is_file()


def restic_env(password: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    value = password if password is not None else env.get(PASSWORD_ENV, "")
    if not value:
        raise ResticError("RESTIC_PASSWORD is missing; refusing to invoke restic")
    env[PASSWORD_ENV] = value
    return env


def run_restic(
    binary: Path,
    args: list[str],
    *,
    repo: Path,
    password: str | None = None,
    runner: ResticRunner | None = None,
) -> subprocess.CompletedProcess[str]:
    restic = runner or default_restic_runner
    argv = [str(binary), "--repo", str(repo), *args]
    redact_command(argv)
    env = restic_env(password)
    return restic(argv, env)


def init_or_existing(
    binary: Path,
    repo: Path,
    *,
    password: str | None = None,
    runner: ResticRunner | None = None,
) -> dict[str, Any]:
    repo.mkdir(parents=True, exist_ok=True)
    if repository_exists(repo):
        return {"action": "existing", "repo": str(repo), "restic_version": RESTIC_VERSION}
    completed = run_restic(binary, ["init"], repo=repo, password=password, runner=runner)
    if completed.returncode != 0:
        raise ResticError("restic init failed")
    return {"action": "init", "repo": str(repo), "restic_version": RESTIC_VERSION}


def backup_path(
    binary: Path,
    repo: Path,
    source: Path,
    *,
    password: str | None = None,
    runner: ResticRunner | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    args = ["backup", "--json"]
    if tags:
        for tag in tags:
            args.extend(["--tag", tag])
    args.append(str(source))
    completed = run_restic(binary, args, repo=repo, password=password, runner=runner)
    if completed.returncode != 0:
        raise ResticError("restic backup failed")
    snapshot_id = None
    for line in (completed.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("message_type") == "summary" or payload.get("snapshot_id"):
            snapshot_id = payload.get("snapshot_id") or payload.get("id")
    return {"snapshot_id": snapshot_id, "repo": str(repo)}


def restic_check(
    binary: Path,
    repo: Path,
    *,
    password: str | None = None,
    runner: ResticRunner | None = None,
) -> dict[str, Any]:
    completed = run_restic(binary, ["check"], repo=repo, password=password, runner=runner)
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
    }


def list_snapshots(
    binary: Path,
    repo: Path,
    *,
    password: str | None = None,
    runner: ResticRunner | None = None,
) -> list[dict[str, Any]]:
    completed = run_restic(binary, ["snapshots", "--json"], repo=repo, password=password, runner=runner)
    if completed.returncode != 0:
        raise ResticError("restic snapshots failed")
    text = (completed.stdout or "").strip() or "[]"
    payload = json.loads(text)
    if isinstance(payload, dict):
        return [payload]
    return list(payload)


def restore_include(
    binary: Path,
    repo: Path,
    target: Path,
    *,
    snapshot: str = "latest",
    include: list[str],
    password: str | None = None,
    runner: ResticRunner | None = None,
) -> dict[str, Any]:
    args = ["restore", snapshot, "--target", str(target)]
    for item in include:
        args.extend(["--include", item])
    completed = run_restic(binary, args, repo=repo, password=password, runner=runner)
    if completed.returncode != 0:
        raise ResticError("restic metadata restore failed")
    return {"status": "PASS", "target": str(target)}
