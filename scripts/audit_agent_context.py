#!/usr/bin/env python3
"""Read-only agent-context size profile for a Git repository.

Uses only the Python standard library. Prints paths, counts, and sizes —
never file bodies. Suitable for Windows and POSIX.

Token implications are proxies only (bytes / rough char estimates), not
Cursor-reported token counts.

Usage:
  python scripts/audit_agent_context.py
  python scripts/audit_agent_context.py --root W:\\Workbench\\hermes-agent
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import subprocess
import sys
from pathlib import Path

# Rough UTF-8 chars/token proxy for English/prose-heavy text. Not a tokenizer.
CHARS_PER_TOKEN_PROXY = 4


def _git_ls_files(root: Path) -> list[str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=root,
        stderr=subprocess.DEVNULL,
    )
    return [p.decode("utf-8", "replace") for p in raw.split(b"\0") if p]


def _file_size(root: Path, rel: str) -> int:
    path = root / rel
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return 0
    return 0


def _top_level(rel: str) -> str:
    normalized = rel.replace("\\", "/")
    if "/" not in normalized:
        return normalized
    return normalized.split("/", 1)[0]


def _read_text_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def _instruction_inventory(root: Path) -> dict[str, int]:
    candidates = [
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        ".cursorrules",
        ".cursorignore",
        ".cursorindexingignore",
        "README.md",
    ]
    found: dict[str, int] = {}
    for name in candidates:
        size = _read_text_size(root / name)
        if size:
            found[name] = size
    cursor_rules = root / ".cursor" / "rules"
    if cursor_rules.is_dir():
        for path in sorted(cursor_rules.rglob("*.mdc")):
            rel = path.relative_to(root).as_posix()
            found[rel] = _read_text_size(path)
    for path in sorted(root.rglob("AGENTS.md")):
        rel = path.relative_to(root).as_posix()
        if rel not in found:
            found[rel] = _read_text_size(path)
    return found


def profile(root: Path) -> dict:
    files = _git_ls_files(root)
    by_top_count: collections.Counter[str] = collections.Counter()
    by_top_bytes: collections.Counter[str] = collections.Counter()
    md_count = 0
    md_bytes = 0
    largest: list[tuple[int, str]] = []
    ext_bytes: collections.Counter[str] = collections.Counter()
    ext_count: collections.Counter[str] = collections.Counter()

    for rel in files:
        size = _file_size(root, rel)
        top = _top_level(rel)
        by_top_count[top] += 1
        by_top_bytes[top] += size
        largest.append((size, rel.replace("\\", "/")))
        lower = rel.replace("\\", "/").lower()
        if lower.endswith(".md"):
            md_count += 1
            md_bytes += size
        ext = Path(lower).suffix or "(none)"
        ext_count[ext] += 1
        ext_bytes[ext] += size

    largest.sort(reverse=True)
    instructions = _instruction_inventory(root)
    always_on_bytes = instructions.get("AGENTS.md", 0)
    # Nested AGENTS.md are path-scoped in Cursor; root is always-on proxy.
    nested_agents = {
        k: v for k, v in instructions.items() if k.endswith("AGENTS.md") and k != "AGENTS.md"
    }

    return {
        "root": str(root.resolve()),
        "tracked_files": len(files),
        "top_level": [
            {
                "name": name,
                "files": by_top_count[name],
                "bytes": by_top_bytes[name],
            }
            for name, _ in by_top_count.most_common(25)
        ],
        "markdown": {
            "files": md_count,
            "bytes": md_bytes,
            "token_proxy_estimate": md_bytes // CHARS_PER_TOKEN_PROXY,
        },
        "largest_tracked": [
            {"bytes": size, "path": path} for size, path in largest[:30]
        ],
        "extensions_by_bytes": [
            {"ext": ext, "files": ext_count[ext], "bytes": ext_bytes[ext]}
            for ext, _ in ext_bytes.most_common(15)
        ],
        "instruction_files": [
            {"path": path, "bytes": size} for path, size in sorted(instructions.items())
        ],
        "always_on_proxy": {
            "root_agents_md_bytes": always_on_bytes,
            "root_agents_token_proxy_estimate": always_on_bytes // CHARS_PER_TOKEN_PROXY,
            "nested_agents_md": [
                {"path": path, "bytes": size}
                for path, size in sorted(nested_agents.items())
            ],
            "note": (
                "Token estimates are byte/4 proxies for text, not Cursor usage. "
                "Root AGENTS.md is the primary always-on instruction burden proxy."
            ),
        },
    }


def _print_human(report: dict) -> None:
    print(f"root={report['root']}")
    print(f"tracked_files={report['tracked_files']}")
    print("top_level:")
    for row in report["top_level"]:
        print(f"  {row['name']}: files={row['files']} bytes={row['bytes']}")
    md = report["markdown"]
    print(
        f"markdown: files={md['files']} bytes={md['bytes']} "
        f"token_proxy_estimate~={md['token_proxy_estimate']}"
    )
    print("largest_tracked:")
    for row in report["largest_tracked"]:
        print(f"  {row['bytes']}\t{row['path']}")
    print("extensions_by_bytes:")
    for row in report["extensions_by_bytes"]:
        print(f"  {row['ext']}: files={row['files']} bytes={row['bytes']}")
    print("instruction_files:")
    for row in report["instruction_files"]:
        print(f"  {row['bytes']}\t{row['path']}")
    ao = report["always_on_proxy"]
    print(
        f"always_on_proxy: root_AGENTS.md_bytes={ao['root_agents_md_bytes']} "
        f"token_proxy_estimate~={ao['root_agents_token_proxy_estimate']}"
    )
    for row in ao["nested_agents_md"]:
        print(f"  nested {row['bytes']}\t{row['path']}")
    print(ao["note"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=None,
        help="Git repository root (default: parent of scripts/ or cwd)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text",
    )
    args = parser.parse_args()
    if args.root:
        root = Path(args.root)
    else:
        script_dir = Path(__file__).resolve().parent
        candidate = script_dir.parent
        root = candidate if (candidate / ".git").exists() else Path.cwd()
    if not (root / ".git").exists():
        print(f"error: not a git repository: {root}", file=sys.stderr)
        return 2
    report = profile(root)
    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    # Stable stdout encoding on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    raise SystemExit(main())
