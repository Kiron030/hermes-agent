#!/usr/bin/env python3
"""
Build-time bundle: copy allowlisted Powerunits markdown from the monorepo
into docker/powerunits_docs/ and write MANIFEST.json (fail-closed).

File content is read from the git object store at an explicit immutable commit
(--ref, 40 lowercase hex; default: approved_ref from
config/powerunits_github_knowledge.json) — never from the working tree or the
local checkout HEAD. MANIFEST.json records that commit (source_repo_commit) and
its committer time (source_commit_time).

No runtime dependency on the monorepo; intended to run on an operator
workstation or in CI before docker build / commit.

Usage:
  python scripts/bundle_powerunits_docs.py --source-root /path/to/EU-PP-Database [--ref <40-hex>]

Env:
  POWERUNITS_REPO_ROOT — default for --source-root if flag omitted.
  HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG — knowledge config providing the default --ref.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*\.md$")
_SHA40_PATTERN = re.compile(r"[0-9a-f]{40}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _knowledge_config_path() -> Path:
    override = os.environ.get("HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG", "").strip()
    if override:
        return Path(override).resolve()
    return _repo_root() / "config" / "powerunits_github_knowledge.json"


def _approved_ref() -> str:
    """approved_ref from the knowledge config; empty string when unavailable."""
    try:
        data = json.loads(_knowledge_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    ref = data.get("approved_ref") if isinstance(data, dict) else None
    return ref if isinstance(ref, str) else ""


def _load_allowlist(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("allowlist: root must be a JSON object")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("allowlist: 'entries' must be a non-empty list")
    return data


def _assert_key_safe(key: str) -> None:
    if not _KEY_PATTERN.match(key):
        raise SystemExit(f"unsafe or invalid manifest key: {key!r}")


def _git(repo_root: Path, *args: str) -> bytes | None:
    """Run a read-only git command in repo_root; None on any failure (callers fail closed)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _resolve_commit(repo_root: Path, ref: str) -> str:
    """Committer time (ISO-8601 with offset) of the exact local commit ``ref``; exit if absent."""
    out = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    resolved = out.decode("utf-8", errors="replace").strip() if out else ""
    if resolved != ref:
        raise SystemExit(f"error: commit {ref} not found in {repo_root} (fetch it first)")
    # Pin signature output off so user git config (e.g. log.showSignature) cannot pollute %cI.
    out = _git(
        repo_root,
        "-c",
        "log.showSignature=false",
        "show",
        "-s",
        "--no-show-signature",
        "--format=%cI",
        ref,
    )
    commit_time = out.decode("utf-8", errors="replace").strip() if out else ""
    if not commit_time:
        raise SystemExit(f"error: could not read commit time of {ref}")
    return commit_time


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle allowlisted Powerunits docs.")
    parser.add_argument(
        "--source-root",
        default=os.environ.get("POWERUNITS_REPO_ROOT", ""),
        help="Root of the EU-PP-Database (Powerunits) git clone",
    )
    parser.add_argument(
        "--ref",
        default=None,
        help="Immutable 40-hex commit to bundle (default: approved_ref from the knowledge config)",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=_repo_root() / "scripts" / "powerunits_docs_allowlist.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_repo_root() / "docker" / "powerunits_docs",
    )
    args = parser.parse_args()

    if not args.source_root:
        print(
            "error: --source-root or POWERUNITS_REPO_ROOT must point to the Powerunits monorepo",
            file=sys.stderr,
        )
        return 2

    source_root = Path(args.source_root)
    if not source_root.is_dir():
        print(f"error: source root is not a directory: {source_root}", file=sys.stderr)
        return 2

    approved_ref = _approved_ref()
    ref = args.ref if args.ref is not None else approved_ref
    if not _SHA40_PATTERN.fullmatch(ref or ""):
        print(
            f"error: --ref must be a 40 lowercase hex commit SHA (got {ref!r}); "
            "branch names, tags and short SHAs are rejected",
            file=sys.stderr,
        )
        return 2
    if ref != approved_ref:
        print(
            f"warning: --ref {ref} differs from approved_ref {approved_ref or '<unset>'}; "
            "reads from this bundle will report read_is_current_or_approved=false",
            file=sys.stderr,
        )
    commit_time = _resolve_commit(source_root, ref)

    allowlist_path = args.allowlist.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    data = _load_allowlist(allowlist_path)
    entries_out: list[dict] = []

    for raw in data["entries"]:
        if not isinstance(raw, dict):
            raise SystemExit("allowlist: each entry must be an object")
        key = raw.get("key")
        rel = raw.get("source_relative")
        if not isinstance(key, str) or not isinstance(rel, str):
            raise SystemExit("allowlist: key and source_relative must be strings")
        _assert_key_safe(key)
        if ".." in Path(rel).parts or rel.startswith(("/", "\\")):
            raise SystemExit(f"unsafe source_relative: {rel!r}")

        git_rel = rel.replace("\\", "/")
        body = _git(source_root, "cat-file", "blob", f"{ref}:{git_rel}")
        if body is None:
            print(f"error: missing allowlisted source file at {ref}: {git_rel}", file=sys.stderr)
            return 1

        dest = (out_dir / key).resolve()
        try:
            dest.relative_to(out_dir)
        except ValueError as exc:
            raise SystemExit(f"dest escapes out-dir: {key!r}") from exc

        dest.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        entry: dict = {
            "key": key,
            "source_relative": git_rel,
            "sha256": digest,
            "bytes": len(body),
        }
        for opt in ("doc_class", "freshness_tier", "summary"):
            val = raw.get(opt)
            if isinstance(val, str) and val.strip():
                entry[opt] = val.strip()
            elif isinstance(val, (int, float, bool)):
                entry[opt] = val
        entries_out.append(entry)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo_name = data.get("source_repo_name")
    if isinstance(repo_name, str) and repo_name.strip():
        source_repo_name = repo_name.strip()
    else:
        source_repo_name = source_root.resolve().name or "source"

    manifest: dict = {
        "bundle_version": 2,
        "allowlist_version": data.get("allowlist_version", 1),
        "generated_at": generated_at,
        "source_root_note": "paths are relative to monorepo root; content read from git at source_repo_commit",
        "entries": sorted(entries_out, key=lambda e: e["key"]),
        "source_repo_commit": ref,
        "source_commit_time": commit_time,
        "source_ref": ref,
        "source_repo_name": source_repo_name,
    }
    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(entries_out)} files + MANIFEST.json -> {out_dir} (ref {ref})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
