"""Read-only Git inspection and fail-closed local-work coverage."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from r5_developer_hermes.recovery.contract import (
    COVERAGE_EXCLUDED_NOT_SOURCE,
    COVERAGE_REMOTE_SAFE,
    COVERAGE_STAGING_COVERED,
    COVERAGE_UNCOVERED,
    REPO_A_CANONICAL_BRANCH,
    REPO_A_CANONICAL_REMOTE,
    REPO_B_CANONICAL_BRANCH,
    REPO_B_CANONICAL_REMOTE,
)


GitRunner = Callable[[list[str], Path], subprocess.CompletedProcess[str]]

SECRET_PATH_MARKERS = (
    ".env.pgurl",
    ".env",
    "credentials",
    ".powerunits/secrets",
    "local-env-pgurl",
    "pgurl",
)


def default_git_runner(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _out(completed: subprocess.CompletedProcess[str]) -> str:
    return (completed.stdout or "").strip()


@dataclass
class GitSnapshot:
    root: str
    remote: str
    branch: str
    head: str
    canonical_branch: str
    canonical_sha: str
    canonical_sha_source: str
    dirty: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    stash_count: int = 0
    stash_subjects: list[str] = field(default_factory=list)
    local_only_branches: dict[str, str] = field(default_factory=dict)
    tracking: str | None = None
    dirty_state: str = "clean"

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "remote": self.remote,
            "branch": self.branch,
            "head": self.head,
            "canonical_branch": self.canonical_branch,
            "canonical_sha": self.canonical_sha,
            "canonical_sha_source": self.canonical_sha_source,
            "dirty_state": self.dirty_state,
            "dirty_count": len(self.dirty),
            "untracked_count": len(self.untracked),
            "ahead": self.ahead,
            "behind": self.behind,
            "stash_count": self.stash_count,
            "local_only_branch_count": len(self.local_only_branches),
            "local_only_branches": dict(self.local_only_branches),
            "tracking": self.tracking,
        }


def _git_ok(runner: GitRunner, args: list[str], cwd: Path) -> str:
    completed = runner(args, cwd)
    if completed.returncode != 0:
        return ""
    return _out(completed)


def inspect_git(
    root: Path,
    *,
    canonical_branch: str,
    expected_remote: str,
    runner: GitRunner | None = None,
) -> GitSnapshot:
    git = runner or default_git_runner
    remote = _git_ok(git, ["remote", "get-url", "origin"], root) or expected_remote
    branch = _git_ok(git, ["rev-parse", "--abbrev-ref", "HEAD"], root) or "HEAD"
    head = _git_ok(git, ["rev-parse", "HEAD"], root)
    tracking = _git_ok(git, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], root) or None

    porcelain = _git_ok(git, ["status", "--porcelain"], root)
    dirty: list[str] = []
    untracked: list[str] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        path = line[3:]
        if line.startswith("??"):
            untracked.append(path)
        else:
            dirty.append(path)

    ahead = behind = 0
    if tracking:
        counts = _git_ok(git, ["rev-list", "--left-right", "--count", f"{tracking}...HEAD"], root)
        parts = counts.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            behind, ahead = int(parts[0]), int(parts[1])

    stash_subjects = [
        line
        for line in _git_ok(git, ["stash", "list", "--format=%gs"], root).splitlines()
        if line
    ]

    local_only: dict[str, str] = {}
    refs = _git_ok(
        git,
        ["for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"],
        root,
    )
    unique = {
        line.strip()
        for line in _git_ok(git, ["rev-list", "--all", "--not", "--remotes"], root).splitlines()
        if line.strip()
    }
    for line in refs.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name, sha = parts
        if sha in unique:
            local_only[name] = sha

    ls_remote = git(["ls-remote", "--heads", "origin", canonical_branch], root)
    canonical_sha = ""
    canonical_source = "MISSING"
    if ls_remote.returncode == 0:
        first = (ls_remote.stdout or "").splitlines()
        if first:
            canonical_sha = first[0].split()[0]
            canonical_source = "ORIGIN_LS_REMOTE"
    if not canonical_sha:
        canonical_sha = _git_ok(git, ["rev-parse", f"origin/{canonical_branch}"], root)
        canonical_source = "LOCAL_TRACKING" if canonical_sha else "MISSING"

    dirty_state = "clean"
    if dirty or untracked:
        dirty_state = "dirty"
    return GitSnapshot(
        root=str(root),
        remote=remote,
        branch=branch,
        head=head,
        canonical_branch=canonical_branch,
        canonical_sha=canonical_sha,
        canonical_sha_source=canonical_source,
        dirty=dirty,
        untracked=untracked,
        ahead=ahead,
        behind=behind,
        stash_count=len(stash_subjects),
        stash_subjects=stash_subjects,
        local_only_branches=local_only,
        tracking=tracking,
        dirty_state=dirty_state,
    )


def _looks_secret_path(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(marker in lowered for marker in SECRET_PATH_MARKERS)


@dataclass
class LocalWorkItem:
    repo: str
    kind: str
    identity: str
    coverage: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "repo": self.repo,
            "kind": self.kind,
            "identity": self.identity,
            "coverage": self.coverage,
            "reason": self.reason,
        }


def _stash_artifacts_cover(repo: str, staging_index: Mapping[str, Any] | None) -> bool:
    if not staging_index:
        return False
    names = " ".join(str(name).lower() for name in (staging_index.get("artifact_names") or []))
    inventory = str(staging_index.get("inventory_text") or "").lower()
    prefix = f"repo-{'a' if repo == 'A' else 'b'}-stash"
    return prefix in names or prefix in inventory or f"patches/repo-{'a' if repo == 'A' else 'b'}-stash" in inventory


def _staging_covers(
    identity: str,
    *,
    staging_index: Mapping[str, Any] | None,
) -> bool:
    if not staging_index:
        return False
    haystacks: list[str] = []
    inventory = str(staging_index.get("inventory_text") or "")
    haystacks.append(inventory.lower())
    for sha in staging_index.get("bundle_heads") or []:
        haystacks.append(str(sha).lower())
    for name in staging_index.get("artifact_names") or []:
        haystacks.append(str(name).lower())
    for extra in staging_index.get("covered_identities") or []:
        haystacks.append(str(extra).lower())
    needle = identity.lower()
    short = needle[:12] if len(needle) >= 12 else needle
    return any(needle in blob or (short and short in blob) for blob in haystacks)


def classify_local_work(
    snapshot: GitSnapshot,
    *,
    repo: str,
    staging_index: Mapping[str, Any] | None = None,
) -> list[LocalWorkItem]:
    items: list[LocalWorkItem] = []

    def cover(kind: str, identity: str, *, secret_path: bool = False) -> LocalWorkItem:
        if secret_path:
            return LocalWorkItem(repo, kind, identity, COVERAGE_EXCLUDED_NOT_SOURCE, "secret-path not source")
        if _staging_covers(identity, staging_index=staging_index):
            return LocalWorkItem(repo, kind, identity, COVERAGE_STAGING_COVERED, "recovery-staging artifact")
        return LocalWorkItem(repo, kind, identity, COVERAGE_UNCOVERED, "not remote-safe and not in staging")

    for path in snapshot.dirty:
        items.append(cover("dirty", path, secret_path=_looks_secret_path(path)))
    for path in snapshot.untracked:
        items.append(cover("untracked", path, secret_path=_looks_secret_path(path)))
    if snapshot.ahead > 0:
        identity = f"{snapshot.branch}@{snapshot.head}"
        remote_safe = bool(snapshot.tracking) and snapshot.ahead == 0
        if remote_safe:
            items.append(LocalWorkItem(repo, "unpushed", identity, COVERAGE_REMOTE_SAFE, "tracking"))
        else:
            items.append(cover("unpushed", identity))
            items.append(cover("unpushed", snapshot.head))
    for name, sha in snapshot.local_only_branches.items():
        if name == snapshot.branch and snapshot.tracking and snapshot.ahead == 0 and not snapshot.dirty:
            items.append(LocalWorkItem(repo, "local_only_branch", name, COVERAGE_REMOTE_SAFE, "tracked clean"))
            continue
        covered = cover("local_only_branch", name)
        if covered.coverage == COVERAGE_UNCOVERED:
            covered = cover("local_only_branch", sha)
        if covered.coverage == COVERAGE_UNCOVERED:
            covered = cover("local_only_branch", f"{name}@{sha}")
        items.append(covered)
    for subject in snapshot.stash_subjects:
        if _looks_secret_path(subject):
            items.append(
                LocalWorkItem(repo, "stash", subject, COVERAGE_EXCLUDED_NOT_SOURCE, "secret-path not source")
            )
            continue
        if _stash_artifacts_cover(repo, staging_index) or _staging_covers(subject, staging_index=staging_index):
            items.append(
                LocalWorkItem(repo, "stash", subject, COVERAGE_STAGING_COVERED, "recovery-staging artifact")
            )
            continue
        items.append(cover("stash", subject))

    if (
        not items
        and snapshot.dirty_state == "clean"
        and snapshot.ahead == 0
        and snapshot.stash_count == 0
        and not snapshot.local_only_branches
        and not snapshot.untracked
    ):
        items.append(
            LocalWorkItem(repo, "worktree", snapshot.head or "HEAD", COVERAGE_REMOTE_SAFE, "clean and not ahead")
        )
    return items


def local_git_coverage_status(items: list[LocalWorkItem]) -> str:
    if any(item.coverage == COVERAGE_UNCOVERED for item in items):
        return "BLOCKED"
    return "PASS"


def inspect_repo_a(root: Path, *, runner: GitRunner | None = None) -> GitSnapshot:
    return inspect_git(
        root,
        canonical_branch=REPO_A_CANONICAL_BRANCH,
        expected_remote=REPO_A_CANONICAL_REMOTE,
        runner=runner,
    )


def inspect_repo_b(root: Path | None, *, runner: GitRunner | None = None) -> GitSnapshot | None:
    if root is None or not Path(root).is_dir():
        return None
    return inspect_git(
        Path(root),
        canonical_branch=REPO_B_CANONICAL_BRANCH,
        expected_remote=REPO_B_CANONICAL_REMOTE,
        runner=runner,
    )
