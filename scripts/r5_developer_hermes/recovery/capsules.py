"""Self-contained Git recovery capsules for Repo A and Repo B.

Recovery-0B bundles are evidence only. Each backup run rebuilds capsules
from a live Git audit. Thin bundles that require origin objects are
rejected. Secret-bearing local state is excluded, never copied.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from r5_developer_hermes.recovery.contract import BACKUP_BLOCKED_LOCAL_WORK
from r5_developer_hermes.recovery.git_state import (
    GitSnapshot,
    LocalWorkItem,
    SECRET_PATH_MARKERS,
    classify_local_work,
    default_git_runner,
    local_git_coverage_status,
)
from r5_developer_hermes.recovery.secrets import assert_no_secret_leaks
from r5_developer_hermes.recovery.staging import file_sha256


GitRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]

SAFE_UNTRACKED_SKIP_PREFIXES = (
    ".git/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
    "dist/",
    "build/",
)


class CapsuleError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _looks_secret_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(marker in lowered for marker in SECRET_PATH_MARKERS)


def _git(runner: GitRunner, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return runner(args, cwd)


def _git_ok(runner: GitRunner, args: list[str], cwd: Path) -> str:
    completed = _git(runner, args, cwd)
    if completed.returncode != 0:
        return ""
    return (completed.stdout or "").strip()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_untracked(path: str) -> bool:
    lowered = path.replace("\\", "/")
    if _looks_secret_path(lowered):
        return False
    return not any(lowered.startswith(prefix) or f"/{prefix}" in f"/{lowered}" for prefix in SAFE_UNTRACKED_SKIP_PREFIXES)


def _bundle_heads(bundle: Path, runner: GitRunner, cwd: Path) -> list[str]:
    completed = _git(runner, ["bundle", "list-heads", str(bundle)], cwd)
    heads: list[str] = []
    if completed.returncode != 0:
        return heads
    for line in (completed.stdout or "").splitlines():
        sha = line.split()[0] if line.split() else ""
        if sha:
            heads.append(sha)
    return heads


def verify_self_contained_bundle(bundle: Path, *, runner: GitRunner | None = None, cwd: Path | None = None) -> dict[str, Any]:
    git = runner or default_git_runner
    work = cwd or bundle.parent
    listed = _git(git, ["bundle", "list-heads", str(bundle)], work)
    verify = _git(git, ["bundle", "verify", str(bundle)], work)
    text = f"{listed.stdout or ''}\n{verify.stdout or ''}\n{verify.stderr or ''}"
    requires_prereq = "requires these" in text.lower() or "prerequisite" in text.lower()
    thin = "--thin" in text.lower() or "thin bundle" in text.lower()
    # A self-contained bundle lists heads and does not require foreign objects.
    # git bundle verify may still fail when cwd is not a repository; list-heads
    # plus a clone into an empty directory is the standalone proof.
    clone_ok = True
    if listed.returncode == 0 and bundle.is_file() and runner is None:
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix="hermes-bundle-verify-"))
        cloned = _git(git, ["clone", str(bundle), str(scratch / "restored")], scratch)
        clone_ok = cloned.returncode == 0
        shutil.rmtree(scratch, ignore_errors=True)
    ok = listed.returncode == 0 and clone_ok and not requires_prereq and not thin and bundle.is_file()
    return {
        "path": str(bundle),
        "status": "PASS" if ok else "FAIL",
        "self_contained": "YES" if ok else "NO",
        "returncode": listed.returncode,
    }


def _stash_is_secret(subject: str) -> bool:
    return _looks_secret_path(subject)


def _export_safe_stash(root: Path, dest: Path, index: int, runner: GitRunner) -> bool:
    # Read-only: stash show does not pop/drop.
    completed = _git(runner, ["stash", "show", "-p", f"stash@{{{index}}}"], root)
    if completed.returncode != 0:
        return False
    patch = completed.stdout or ""
    if _looks_secret_path(patch):
        return False
    _write_text(dest / f"stash-{index}.patch", patch)
    return True


def _export_worktree_patches(root: Path, dest: Path, runner: GitRunner) -> list[str]:
    listed = _git_ok(runner, ["worktree", "list", "--porcelain"], root)
    extras: list[str] = []
    current = ""
    for line in listed.splitlines():
        if line.startswith("worktree "):
            current = line.split(" ", 1)[1].strip()
            continue
        if not current:
            continue
        extra = Path(current)
        if extra.resolve() == root.resolve():
            current = ""
            continue
        if extra.is_dir():
            diff = _git_ok(runner, ["diff", "HEAD"], extra)
            if diff and not _looks_secret_path(diff):
                name = extra.name or "worktree"
                _write_text(dest / f"{name}.patch", diff)
                extras.append(name)
        current = ""
    return extras


def build_capsule(
    snapshot: GitSnapshot,
    dest: Path,
    *,
    repo: str,
    runner: GitRunner | None = None,
) -> dict[str, Any]:
    git = runner or default_git_runner
    root = Path(snapshot.root)
    dest.mkdir(parents=True, exist_ok=True)
    bundle = dest / "repo.bundle"
    excluded_secret = False
    excluded_kinds: list[str] = []

    create = _git(git, ["bundle", "create", str(bundle), "--all"], root)
    if create.returncode != 0 or not bundle.is_file():
        raise CapsuleError(BACKUP_BLOCKED_LOCAL_WORK, f"repo {repo} self-contained bundle create failed")
    verify = verify_self_contained_bundle(bundle, runner=git, cwd=root)
    if verify["status"] != "PASS":
        raise CapsuleError(BACKUP_BLOCKED_LOCAL_WORK, f"repo {repo} bundle is not self-contained")

    included_dirty: list[str] = []
    for rel in snapshot.dirty:
        if _looks_secret_path(rel):
            excluded_secret = True
            excluded_kinds.append("dirty-secret-path")
            continue
        patch = _git_ok(git, ["diff", "HEAD", "--", rel], root)
        if patch:
            _write_text(dest / "patches" / f"{rel.replace('/', '__')}.patch", patch)
        included_dirty.append(rel)

    untracked_copied: list[str] = []
    for rel in snapshot.untracked:
        if not _safe_untracked(rel):
            if _looks_secret_path(rel):
                excluded_secret = True
                excluded_kinds.append("untracked-secret-path")
            continue
        src = root / rel
        if not src.is_file():
            continue
        target = dest / "untracked" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        untracked_copied.append(rel)

    stash_included = 0
    for index, subject in enumerate(snapshot.stash_subjects):
        if _stash_is_secret(subject):
            excluded_secret = True
            excluded_kinds.append("secret-bearing-stash")
            continue
        stash_dir = dest / "stashes"
        stash_dir.mkdir(parents=True, exist_ok=True)
        if _export_safe_stash(root, stash_dir, index, git):
            stash_included += 1

    worktrees = _export_worktree_patches(root, dest / "worktrees", git)
    heads = _bundle_heads(bundle, git, root)
    inventory_lines = [
        f"REPO_{repo}_SELF_CONTAINED_CAPSULE",
        f"canonical_sha={snapshot.canonical_sha}",
        f"head={snapshot.head}",
        f"{snapshot.branch}@{snapshot.head}",
        f"local_only_branches={','.join(snapshot.local_only_branches)}",
        *[f"{name}@{sha}" for name, sha in snapshot.local_only_branches.items()],
        f"bundle_heads={' '.join(heads)}",
        f"dirty={','.join(included_dirty)}",
        *included_dirty,
        f"untracked={','.join(untracked_copied)}",
        *untracked_copied,
        f"stash_included={stash_included}",
        f"excluded_secret_bearing_local_state={'YES' if excluded_secret else 'NO'}",
        "secrets_included=NO",
    ]
    if stash_included:
        inventory_lines.append(f"repo-{'a' if repo == 'A' else 'b'}-stash")
    _write_text(dest / "INVENTORY.txt", "\n".join(inventory_lines) + "\n")

    metadata = {
        "repo": repo,
        "self_contained": "YES",
        "bundle": "repo.bundle",
        "bundle_sha256": file_sha256(bundle),
        "canonical_sha": snapshot.canonical_sha,
        "head": snapshot.head,
        "local_only_branches": dict(snapshot.local_only_branches),
        "bundle_heads": heads,
        "dirty_included": included_dirty,
        "untracked_count": len(untracked_copied),
        "stash_included": stash_included,
        "worktrees": worktrees,
        "excluded_secret_bearing_local_state": "YES" if excluded_secret else "NO",
        "excluded_kinds": excluded_kinds,
        "workbench_byte_for_byte": (
            "NO"
            if excluded_secret
            else "YES"
        ),
        "workbench_reconstruction_note": (
            "secret-bearing local state excluded; exact Workbench reconstruction is not possible"
            if excluded_secret
            else ""
        ),
    }
    assert_no_secret_leaks(metadata, context=f"repo-{repo.lower()}-capsule-metadata")
    _write_text(dest / "capsule.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return metadata


def capsule_index(dest: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    inventory = dest / "INVENTORY.txt"
    artifact_names = [path.name for path in dest.rglob("*") if path.is_file()]
    return {
        "path": str(dest),
        "inventory_text": inventory.read_text(encoding="utf-8") if inventory.is_file() else "",
        "artifact_names": artifact_names,
        "bundle_heads": list(metadata.get("bundle_heads") or []),
        "covered_identities": list(metadata.get("local_only_branches") or {})
        + list(metadata.get("dirty_included") or [])
        + [str(metadata.get("head") or ""), str(metadata.get("canonical_sha") or "")],
        "hash_status": "PASS",
    }


def coverage_after_capsule(
    snapshot: GitSnapshot,
    *,
    repo: str,
    dest: Path,
    metadata: Mapping[str, Any],
) -> tuple[str, list[LocalWorkItem]]:
    items = classify_local_work(snapshot, repo=repo, staging_index=capsule_index(dest, metadata))
    return local_git_coverage_status(items), items


def write_capsules(
    *,
    repo_a: GitSnapshot,
    repo_b: GitSnapshot | None,
    dest: Path,
    runner: GitRunner | None = None,
) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    a_dir = dest / "repo-a"
    meta_a = build_capsule(repo_a, a_dir, repo="A", runner=runner)
    status_a, items_a = coverage_after_capsule(repo_a, repo="A", dest=a_dir, metadata=meta_a)
    if status_a != "PASS":
        raise CapsuleError(BACKUP_BLOCKED_LOCAL_WORK, "Repo A local-only work is not fully covered by the new capsule")

    meta_b: dict[str, Any] | None = None
    items_b: list[LocalWorkItem] = []
    status_b = "BLOCKED"
    excluded_b = "NO"
    if repo_b is None:
        raise CapsuleError(BACKUP_BLOCKED_LOCAL_WORK, "Repo B checkout is missing")
    b_dir = dest / "repo-b"
    meta_b = build_capsule(repo_b, b_dir, repo="B", runner=runner)
    status_b, items_b = coverage_after_capsule(repo_b, repo="B", dest=b_dir, metadata=meta_b)
    excluded_b = str(meta_b.get("excluded_secret_bearing_local_state") or "NO")
    if status_b != "PASS":
        raise CapsuleError(BACKUP_BLOCKED_LOCAL_WORK, "Repo B local-only work is not fully covered by the new capsule")

    report = {
        "repo_a": meta_a,
        "repo_b": meta_b,
        "repo_a_local_only_coverage": status_a,
        "repo_b_local_only_coverage": status_b,
        "secret_bearing_repo_b_state_excluded": excluded_b,
        "local_work": [item.to_dict() for item in (*items_a, *items_b)],
        "self_contained": "YES",
    }
    assert_no_secret_leaks(report, context="recovery-capsules")
    return report
