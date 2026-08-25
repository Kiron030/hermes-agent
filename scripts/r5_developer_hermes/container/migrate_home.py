#!/usr/bin/env python3
"""Controlled HERMES_HOME ownership migration for Developer Hermes.

The entire persistent HERMES_HOME tree is intended to be owned by the
Hermes runtime user (uid/gid 10000). Historical root ownership is a
defect, not an exception.

This tool:

- audits owner/group/mode without printing file contents
- chowns only root-owned entries to hermes:hermes
- preserves modes (no chmod, never 777)
- does not follow symlinks out of HERMES_HOME
- refuses workspace binds, egress CA, and Docker sockets
- is safe to rerun
- fails closed on unexpected ownership or path shape
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


INTENDED_USER = "hermes"
INTENDED_UID = 10000
INTENDED_GID = 10000
ALLOWED_UIDS = frozenset({0, INTENDED_UID})
ALLOWED_GIDS = frozenset({0, INTENDED_GID})
DEFAULT_HERMES_HOME = "/opt/data"
SECRET_BASENAMES = frozenset({".env", "auth.json"})

FORBIDDEN_EXACT = frozenset(
    {
        "/workspace",
        "/workspace/hermes-agent",
        "/workspace/EU-PP-Database",
        "/opt/r5-egress-ca",
        "/var/run/docker.sock",
        "/run/docker.sock",
    }
)
FORBIDDEN_PREFIXES = (
    "/workspace/",
    "/opt/r5-egress-ca/",
    "/mnt/",
    "/host/",
    "/host_mnt/",
    "/run/desktop/mnt/host/",
)


class MigrationError(RuntimeError):
    """Fail-closed migration refusal."""


@dataclass(frozen=True)
class EntryAudit:
    relpath: str
    uid: int
    gid: int
    mode: int
    kind: str
    action: str
    reason: str


@dataclass(frozen=True)
class MigrationPlan:
    home: str
    intended_uid: int
    intended_gid: int
    entries: tuple[EntryAudit, ...]
    errors: tuple[str, ...]
    secrets: tuple[dict[str, Any], ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def changes(self) -> tuple[EntryAudit, ...]:
        return tuple(item for item in self.entries if item.action == "chown")

    def as_dict(self) -> dict[str, Any]:
        return {
            "HERMES_HOME": self.home,
            "INTENDED_UID": self.intended_uid,
            "INTENDED_GID": self.intended_gid,
            "INTENDED_USER": INTENDED_USER,
            "OK": "YES" if self.ok else "NO",
            "CHANGE_COUNT": len(self.changes),
            "ERROR_COUNT": len(self.errors),
            "errors": list(self.errors),
            "entries": [asdict(item) for item in self.entries],
            "secrets": list(self.secrets),
            "CONTENTS_PRINTED": "NO",
        }


def _posix(path: Path) -> str:
    return path.as_posix()


def assert_allowed_home(home: Path) -> Path:
    raw = _posix(home)
    if raw in FORBIDDEN_EXACT or any(raw.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        raise MigrationError(f"refusing to migrate forbidden path: {raw}")
    if not home.is_absolute():
        raise MigrationError("HERMES_HOME must be an absolute path")
    if home.is_symlink():
        raise MigrationError("HERMES_HOME must not be a symlink")
    if not home.exists() or not home.is_dir():
        raise MigrationError("HERMES_HOME must be an existing directory")
    return home


def _kind(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def _secret_record(relpath: str, mode: int) -> dict[str, Any]:
    return {
        "relpath": relpath,
        "mode": oct(stat.S_IMODE(mode)),
        "restrictive": "YES" if stat.S_IMODE(mode) == 0o600 else "NO",
        "world_readable": "YES" if mode & stat.S_IROTH else "NO",
        "world_writable": "YES" if mode & stat.S_IWOTH else "NO",
        "contents": "OMITTED",
    }


def audit_home(
    home: Path,
    *,
    intended_uid: int = INTENDED_UID,
    intended_gid: int = INTENDED_GID,
    listdir: Callable[[Path], list[str]] | None = None,
    lstat: Callable[[Path], os.stat_result] | None = None,
    readlink: Callable[[Path], str] | None = None,
) -> MigrationPlan:
    root = assert_allowed_home(home)
    list_fn = listdir or (lambda path: os.listdir(path))
    stat_fn = lstat or os.lstat
    read_fn = readlink or (lambda path: os.readlink(path))

    entries: list[EntryAudit] = []
    errors: list[str] = []
    secrets: list[dict[str, Any]] = []
    stack = [root]
    seen: set[str] = set()

    while stack:
        current = stack.pop()
        key = _posix(current)
        if key in seen:
            continue
        seen.add(key)
        try:
            info = stat_fn(current)
        except OSError as exc:
            errors.append(f"lstat failed: {current.relative_to(root).as_posix()}: {exc}")
            continue

        relpath = "." if current == root else current.relative_to(root).as_posix()
        kind = _kind(info.st_mode)
        if kind == "symlink":
            try:
                target = read_fn(current)
            except OSError as exc:
                errors.append(f"symlink read failed: {relpath}: {exc}")
                continue
            resolved = (current.parent / target).resolve(strict=False)
            try:
                resolved.relative_to(root.resolve(strict=False))
            except ValueError:
                errors.append(f"symlink escapes HERMES_HOME: {relpath}")
                continue

        if info.st_uid not in ALLOWED_UIDS or info.st_gid not in ALLOWED_GIDS:
            errors.append(
                f"unexpected ownership {info.st_uid}:{info.st_gid} at {relpath}"
            )
            action = "fail"
            reason = "UNEXPECTED_OWNER"
        elif info.st_uid == intended_uid and info.st_gid == intended_gid:
            action = "keep"
            reason = "ALREADY_INTENDED"
        else:
            action = "chown"
            reason = "HISTORICAL_ROOT"

        entries.append(
            EntryAudit(
                relpath=relpath,
                uid=info.st_uid,
                gid=info.st_gid,
                mode=stat.S_IMODE(info.st_mode),
                kind=kind,
                action=action,
                reason=reason,
            )
        )
        if current.name in SECRET_BASENAMES and kind == "file":
            secrets.append(_secret_record(relpath, info.st_mode))

        if kind == "directory":
            try:
                names = list_fn(current)
            except OSError as exc:
                errors.append(f"listdir failed: {relpath}: {exc}")
                continue
            for name in names:
                child = current / name
                if name in {".", ".."}:
                    continue
                stack.append(child)

    return MigrationPlan(
        home=_posix(root),
        intended_uid=intended_uid,
        intended_gid=intended_gid,
        entries=tuple(entries),
        errors=tuple(errors),
        secrets=tuple(secrets),
    )


def apply_plan(
    home: Path,
    plan: MigrationPlan,
    *,
    lchown: Callable[[str, int, int], None] | None = None,
    listdir: Callable[[Path], list[str]] | None = None,
    lstat: Callable[[Path], os.stat_result] | None = None,
    readlink: Callable[[Path], str] | None = None,
) -> MigrationPlan:
    if not plan.ok:
        raise MigrationError("refusing to apply a failed migration plan")
    root = assert_allowed_home(home)
    chown_fn = lchown or os.lchown
    for item in sorted(plan.changes, key=lambda entry: entry.relpath):
        target = root if item.relpath == "." else root / item.relpath
        if item.relpath != ".":
            try:
                target.resolve(strict=False).relative_to(root.resolve(strict=False))
            except ValueError as exc:
                raise MigrationError(f"apply path escaped HERMES_HOME: {item.relpath}") from exc
        chown_fn(os.fspath(target), plan.intended_uid, plan.intended_gid)
    return audit_home(
        root,
        intended_uid=plan.intended_uid,
        intended_gid=plan.intended_gid,
        listdir=listdir,
        lstat=lstat,
        readlink=readlink,
    )


def run(
    home: Path,
    *,
    apply: bool,
    intended_uid: int = INTENDED_UID,
    intended_gid: int = INTENDED_GID,
) -> dict[str, Any]:
    planned = audit_home(home, intended_uid=intended_uid, intended_gid=intended_gid)
    payload = planned.as_dict()
    payload["MODE"] = "APPLY" if apply else "DRY_RUN"
    if apply:
        applied = apply_plan(home, planned)
        payload = applied.as_dict()
        payload["MODE"] = "APPLY"
        payload["IDEMPOTENT"] = "YES" if not applied.changes else "NO"
        payload["PRE_CHANGE_COUNT"] = len(planned.changes)
    else:
        payload["IDEMPOTENT"] = "YES" if not planned.changes and planned.ok else "NO"
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate Developer HERMES_HOME ownership")
    parser.add_argument("--home", default=os.environ.get("HERMES_HOME", DEFAULT_HERMES_HOME))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.dry_run:
        print("choose only one of --dry-run or --apply", file=sys.stderr)
        return 2
    apply = bool(args.apply)
    try:
        payload = run(Path(args.home), apply=apply)
    except MigrationError as exc:
        print(json.dumps({"OK": "NO", "error": str(exc), "CONTENTS_PRINTED": "NO"}, indent=2))
        return 78
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if payload.get("OK") == "YES" else 78


if __name__ == "__main__":
    raise SystemExit(main())
