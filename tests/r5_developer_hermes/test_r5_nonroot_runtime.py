"""Focused proofs for the Developer Hermes non-root runtime repair."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from r5_developer_hermes.container.contract import (
    ENV_ALLOWLIST,
    IMAGE_CONTRACT_VERSION,
    RUNTIME_GID,
    RUNTIME_UID,
    RUNTIME_USER,
    docker_run_argv,
)
from r5_developer_hermes.container.image_identity import IMAGE_INPUT_RELATIVE_PATHS
from r5_developer_hermes.container.launch import migrate_home_argv
from r5_developer_hermes.container.migrate_home import (
    INTENDED_GID,
    INTENDED_UID,
    MigrationError,
    apply_plan,
    audit_home,
    run,
)
from r5_developer_hermes.container.seed_home import main as seed_home_main
from r5_developer_hermes.harness import REPO_ROOT


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"


def _stat(uid: int, gid: int, mode: int, *, kind: str = "file") -> os.stat_result:
    extra = {
        "file": stat.S_IFREG,
        "directory": stat.S_IFDIR,
        "symlink": stat.S_IFLNK,
    }[kind]
    return SimpleNamespace(st_uid=uid, st_gid=gid, st_mode=extra | mode)  # type: ignore[return-value]


class FakeTree:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.meta: dict[str, os.stat_result] = {}
        self.links: dict[str, str] = {}
        self.children: dict[str, list[str]] = {}
        self.chowns: list[tuple[str, int, int]] = []

    def add(self, relpath: str, uid: int, gid: int, mode: int, kind: str = "file") -> None:
        path = self.home if relpath == "." else self.home / relpath
        key = path.as_posix()
        self.meta[key] = _stat(uid, gid, mode, kind=kind)
        if kind == "directory":
            self.children.setdefault(key, [])
        parent = self.home if relpath == "." else path.parent
        parent_key = parent.as_posix()
        name = path.name if relpath != "." else "."
        self.children.setdefault(parent_key, [])
        if relpath != "." and name not in self.children[parent_key]:
            self.children[parent_key].append(name)

    def add_link(self, relpath: str, target: str, uid: int = 0, gid: int = 0) -> None:
        self.add(relpath, uid, gid, 0o777, kind="symlink")
        self.links[(self.home / relpath).as_posix()] = target

    def listdir(self, path: Path) -> list[str]:
        return list(self.children.get(path.as_posix(), []))

    def lstat(self, path: Path) -> os.stat_result:
        return self.meta[path.as_posix()]

    def readlink(self, path: Path) -> str:
        return self.links[path.as_posix()]

    def lchown(self, raw: str, uid: int, gid: int) -> None:
        self.chowns.append((Path(raw).name if Path(raw) != self.home else ".", uid, gid))
        current = self.meta[Path(raw).as_posix()]
        kind = "symlink" if stat.S_ISLNK(current.st_mode) else (
            "directory" if stat.S_ISDIR(current.st_mode) else "file"
        )
        self.meta[Path(raw).as_posix()] = _stat(uid, gid, stat.S_IMODE(current.st_mode), kind=kind)


def test_runtime_identity_is_pure_nonroot() -> None:
    assert RUNTIME_USER == "hermes"
    assert RUNTIME_UID == 10000 == INTENDED_UID
    assert RUNTIME_GID == 10000 == INTENDED_GID
    assert IMAGE_CONTRACT_VERSION == "r5-dx-image-v2"
    argv = docker_run_argv()
    assert argv[argv.index("--user") + 1] == "10000:10000"
    joined = " ".join(argv)
    assert "HERMES_DOCKER_EXEC_AS_ROOT" not in joined
    assert "HERMES_ALLOW_ROOT_GATEWAY" not in joined
    assert "HERMES_DOCKER_EXEC_AS_ROOT" not in ENV_ALLOWLIST
    assert "HERMES_ALLOW_ROOT_GATEWAY" not in ENV_ALLOWLIST
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    last_user = [line for line in dockerfile.splitlines() if line.startswith("USER ")][-1]
    assert last_user == "USER hermes"


def test_migration_is_in_image_inputs_and_volume_only() -> None:
    assert "migrate_home.py" in IMAGE_INPUT_RELATIVE_PATHS
    argv = migrate_home_argv(apply=False)
    joined = " ".join(argv)
    assert "--user" in argv and argv[argv.index("--user") + 1] == "0:0"
    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
    assert "--privileged=false" in argv
    assert "type=volume,src=r5-developer-hermes-home,dst=/opt/data" in argv
    assert "type=bind," not in joined
    assert "/workspace" not in joined
    assert "r5-egress-ca" not in joined
    assert "docker.sock" not in joined
    assert "--apply" not in argv
    assert migrate_home_argv(apply=True)[-1] == "--apply"


def test_mixed_ownership_migration_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    home = tmp_path / "opt" / "data"
    home.mkdir(parents=True)
    tree = FakeTree(home)
    tree.add(".", 0, 0, 0o755, kind="directory")
    tree.add("config.yaml", 0, 0, 0o644)
    tree.add("profiles", 0, 0, 0o755, kind="directory")
    tree.add("profiles/telegram-ops", 10000, 10000, 0o700, kind="directory")
    tree.add("profiles/telegram-ops/.env", 10000, 10000, 0o600)
    tree.add("auth.json", 0, 0, 0o600)
    plan = audit_home(
        home,
        listdir=tree.listdir,
        lstat=tree.lstat,
        readlink=tree.readlink,
    )
    assert plan.ok is True
    changed = {item.relpath for item in plan.changes}
    assert changed == {".", "config.yaml", "profiles", "auth.json"}
    assert all(item.relpath != "profiles/telegram-ops/.env" for item in plan.changes)
    secrets = {item["relpath"]: item for item in plan.secrets}
    assert secrets["profiles/telegram-ops/.env"]["mode"] == "0o600"
    assert secrets["profiles/telegram-ops/.env"]["restrictive"] == "YES"
    assert secrets["auth.json"]["mode"] == "0o600"
    assert all(item["contents"] == "OMITTED" for item in plan.secrets)
    applied = apply_plan(
        home,
        plan,
        lchown=tree.lchown,
        listdir=tree.listdir,
        lstat=tree.lstat,
        readlink=tree.readlink,
    )
    assert applied.ok is True
    assert applied.changes == ()
    second = apply_plan(
        home,
        applied,
        lchown=tree.lchown,
        listdir=tree.listdir,
        lstat=tree.lstat,
        readlink=tree.readlink,
    )
    assert second.changes == ()
    assert sorted(tree.chowns) == sorted(
        [
            (".", 10000, 10000),
            ("auth.json", 10000, 10000),
            ("config.yaml", 10000, 10000),
            ("profiles", 10000, 10000),
        ]
    )


def test_unexpected_owner_and_escape_symlink_fail_closed(tmp_path: Path) -> None:
    home = tmp_path / "opt" / "data"
    home.mkdir(parents=True)
    tree = FakeTree(home)
    tree.add(".", 0, 0, 0o755, kind="directory")
    tree.add("odd", 1, 1, 0o644)
    tree.add_link("out", "/workspace/hermes-agent")
    plan = audit_home(home, listdir=tree.listdir, lstat=tree.lstat, readlink=tree.readlink)
    assert plan.ok is False
    assert any("unexpected ownership" in item for item in plan.errors)
    assert any("symlink escapes HERMES_HOME" in item for item in plan.errors)
    with pytest.raises(MigrationError, match="failed migration plan"):
        apply_plan(home, plan, lchown=tree.lchown)
    with pytest.raises(MigrationError, match="forbidden path"):
        audit_home(Path("/workspace/hermes-agent"))
    with pytest.raises(MigrationError, match="forbidden path"):
        audit_home(Path("/opt/r5-egress-ca"))


def test_seed_home_refuses_unwritable_or_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "data"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr("r5_developer_hermes.container.seed_home.HERMES_HOME", home)
    monkeypatch.setattr("os.access", lambda *_args, **_kwargs: False)
    assert seed_home_main() == 78
    monkeypatch.setattr("os.access", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("os.geteuid", lambda: 0, raising=False)
    assert seed_home_main() == 78


def test_fresh_home_seeds_without_human_chown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "fresh-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr("r5_developer_hermes.container.seed_home.HERMES_HOME", home)
    monkeypatch.setattr("os.geteuid", lambda: 10000, raising=False)
    assert seed_home_main() == 0
    assert (home / "config.yaml").is_file()
    assert (home / ".r5-dx-sentinel").is_file()
    env_path = home / "profiles" / "telegram-ops" / ".env"
    assert env_path.is_file()
    if os.name != "nt":
        assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
        assert stat.S_IMODE((home / "profiles" / "telegram-ops").stat().st_mode) == 0o700
    payload = run(home, apply=False, intended_uid=home.stat().st_uid, intended_gid=home.stat().st_gid)
    assert payload["OK"] == "YES"
    assert payload["CONTENTS_PRINTED"] == "NO"
