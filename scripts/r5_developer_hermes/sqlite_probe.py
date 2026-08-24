#!/usr/bin/env python3
"""Record the developer-runtime SQLite version and journal-mode choice.

Does not enable WAL on a known-vulnerable build. Prints one JSON object.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path


# Hermes warns below 3.51.3 (backports 3.50.7 / 3.44.6). Keep DELETE on older
# linked builds. Do not force WAL on 3.38.x.
WAL_SAFE_MIN = (3, 51, 3)


def _parse(version: str) -> tuple[int, ...]:
    parts = []
    for item in version.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            break
    return tuple(parts)


def main() -> int:
    version = sqlite3.sqlite_version
    parsed = _parse(version)
    safe = parsed >= WAL_SAFE_MIN
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "r5-sqlite-probe.db"
        conn = sqlite3.connect(str(path))
        try:
            if safe:
                conn.execute("PRAGMA journal_mode=WAL")
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                status = "SAFE_WAL_AVAILABLE"
            else:
                conn.execute("PRAGMA journal_mode=DELETE")
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                status = "KNOWN_RUNTIME_DEPENDENCY_DEBT"
        finally:
            conn.close()
    payload = {
        "sqlite_version": version,
        "wal_safe_min": ".".join(str(part) for part in WAL_SAFE_MIN),
        "SQLITE_RUNTIME_STATUS": status,
        "SQLITE_WAL_MODE": mode.lower(),
        "upgrade_path": (
            "Rebuild the developer venv or use `hermes update` so the "
            "linked SQLite is 3.51.3+ (or backports 3.50.7 / 3.44.6). "
            "Do not force WAL on this vulnerable 3.38.x build."
        ),
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
