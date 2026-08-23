"""Measure the upgrade-conflict surface between the fork and pinned modern upstream.

Read-only. Emits JSON on stdout.

    python scripts/r3_shadow_comparison/measure_upstream_proximity.py
"""

from __future__ import annotations

import json
import subprocess
import sys

MERGE_BASE = "3ef6bbd201263d354fd83ec55b3c306ded2eb72a"  # upstream v0.19.0 (2026.7.20)
UPSTREAM_PINNED = "fcbd1076a93841fa88855acce810e342a5b78101"  # upstream v0.20.5 (2026.8.19)
FORK_HEAD = "d7dbb7e64072659d3ebd27aaaee197c91ce3fa6c"

# Files whose churn says nothing about maintenance burden.
NOISE_SUFFIXES = (".lock", "package-lock.json", ".po", ".mo")
NOISE_PREFIXES = ("website/", "locales/", "assets/", "infographic/")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def numstat(a: str, b: str) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for line in git("diff", "--numstat", a, b).splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if added == "-" or removed == "-":  # binary
            continue
        out[path] = (int(added), int(removed))
    return out


def is_noise(path: str) -> bool:
    return path.endswith(NOISE_SUFFIXES) or path.startswith(NOISE_PREFIXES)


def tracked_at(rev: str) -> set[str]:
    return set(git("ls-tree", "-r", "--name-only", rev).splitlines())


def main() -> int:
    base_files = tracked_at(MERGE_BASE)

    fork_delta = numstat(MERGE_BASE, FORK_HEAD)
    upstream_delta = numstat(MERGE_BASE, UPSTREAM_PINNED)

    fork_signal = {p: v for p, v in fork_delta.items() if not is_noise(p)}
    upstream_signal = {p: v for p, v in upstream_delta.items() if not is_noise(p)}

    fork_shared = {p: v for p, v in fork_signal.items() if p in base_files}
    fork_new = {p: v for p, v in fork_signal.items() if p not in base_files}

    collision = sorted(set(fork_shared) & set(upstream_signal))

    def total(d: dict[str, tuple[int, int]]) -> dict[str, int]:
        return {
            "files": len(d),
            "added": sum(a for a, _ in d.values()),
            "removed": sum(r for _, r in d.values()),
        }

    report = {
        "merge_base": MERGE_BASE,
        "upstream_pinned": UPSTREAM_PINNED,
        "fork_head": FORK_HEAD,
        "fork_delta_all": total(fork_delta),
        "fork_delta_signal": total(fork_signal),
        "fork_modifies_shared_upstream_files": total(fork_shared),
        "fork_only_new_files": total(fork_new),
        "upstream_delta_signal": total(upstream_signal),
        "upgrade_conflict_surface": {
            "files": len(collision),
            "fork_lines_in_those_files": sum(
                fork_shared[p][0] + fork_shared[p][1] for p in collision
            ),
            "paths": collision,
        },
        "top_fork_touched_shared_files": sorted(
            (
                {"path": p, "added": a, "removed": r, "also_changed_upstream": p in upstream_signal}
                for p, (a, r) in fork_shared.items()
            ),
            key=lambda d: d["added"] + d["removed"],
            reverse=True,
        )[:25],
    }
    json.dump(report, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
