#!/usr/bin/env python3
"""
Build-time bundle: copy allowlisted Powerunits markdown from the monorepo
into docker/powerunits_docs/ and write MANIFEST.json (fail-closed).

No runtime dependency on the monorepo; intended to run on an operator
workstation or in CI before docker build / commit.

Usage:
  python scripts/bundle_powerunits_docs.py --source-root /path/to/EU-PP-Database

Env:
  POWERUNITS_REPO_ROOT — default for --source-root if flag omitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*\.md$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def _git_provenance(repo_root: Path) -> dict[str, str]:
    """Best-effort git metadata; never raises; omits keys if unavailable."""
    out: dict[str, str] = {}
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return out

    def _run_git(*args: str) -> str:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode != 0:
                return ""
            return (proc.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    commit = _run_git("rev-parse", "HEAD")
    if commit and len(commit) >= 7:
        out["source_repo_commit"] = commit
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        out["source_repo_branch"] = branch
    if commit and branch:
        out["source_ref"] = f"{branch}@{commit[:12]}"
    elif commit:
        out["source_ref"] = commit[:12]
    elif branch:
        out["source_ref"] = branch
    return out


def _assert_under_repo_root(repo_root: Path, candidate: Path) -> None:
    repo_r = repo_root.resolve()
    cand_r = candidate.resolve()
    try:
        cand_r.relative_to(repo_r)
    except ValueError as exc:
        raise SystemExit(f"path escapes monorepo root: {candidate}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle allowlisted Powerunits docs.")
    parser.add_argument(
        "--source-root",
        default=os.environ.get("POWERUNITS_REPO_ROOT", ""),
        help="Root of the EU-PP-Database (Powerunits) checkout",
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

        src = (source_root / rel).resolve()
        _assert_under_repo_root(source_root, src)
        if not src.is_file():
            print(f"error: missing allowlisted source file: {src}", file=sys.stderr)
            return 1

        dest = (out_dir / key).resolve()
        try:
            dest.relative_to(out_dir)
        except ValueError as exc:
            raise SystemExit(f"dest escapes out-dir: {key!r}") from exc

        shutil.copy2(src, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        entry: dict = {
            "key": key,
            "source_relative": rel.replace("\\", "/"),
            "sha256": digest,
            "bytes": dest.stat().st_size,
        }
        for opt in ("doc_class", "freshness_tier", "summary"):
            val = raw.get(opt)
            if isinstance(val, str) and val.strip():
                entry[opt] = val.strip()
            elif isinstance(val, (int, float, bool)):
                entry[opt] = val
        entries_out.append(entry)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prov = _git_provenance(source_root)
    repo_name = data.get("source_repo_name")
    if isinstance(repo_name, str) and repo_name.strip():
        prov["source_repo_name"] = repo_name.strip()
    elif "source_repo_name" not in prov:
        prov["source_repo_name"] = source_root.resolve().name or "source"

    manifest: dict = {
        "bundle_version": 2,
        "allowlist_version": data.get("allowlist_version", 1),
        "generated_at": generated_at,
        "source_root_note": "paths are relative to monorepo root at bundle time",
        "entries": sorted(entries_out, key=lambda e: e["key"]),
    }
    manifest.update(prov)
    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(entries_out)} files + MANIFEST.json -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
