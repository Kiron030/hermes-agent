"""Profile-local durable audit ledger for cron execution attempts.

The ledger records what is known about each attempt; it is not a retry queue.
Interrupted attempts become ``unknown`` only after their exact owner process is
proved gone. Terminal states are immutable.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home
from hermes_time import now as _hermes_now

EXECUTIONS_FILE = get_hermes_home().resolve() / "cron" / "executions.db"
MAX_TERMINAL_EXECUTIONS = 1000
HANDOFF_ADOPTION_GRACE_SECONDS = 30.0
_TERMINAL_STATES = ("completed", "failed", "unknown")
_lock = threading.RLock()
_PROCESS_ID = uuid.uuid4().hex


def _connect() -> sqlite3.Connection:
    EXECUTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(EXECUTIONS_FILE, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS executions (
             id TEXT PRIMARY KEY,
             job_id TEXT NOT NULL,
             source TEXT NOT NULL,
             process_id TEXT NOT NULL,
             pid INTEGER NOT NULL,
             process_started_at INTEGER,
             status TEXT NOT NULL CHECK(status IN
               ('claimed','running','completed','failed','unknown')),
             handoff_pending INTEGER NOT NULL DEFAULT 0,
             handoff_started_at REAL,
             claimed_at TEXT NOT NULL,
             started_at TEXT,
             finished_at TEXT,
             error TEXT
           )"""
    )
    from hermes_cli.sqlite_util import add_column_if_missing

    # Additive, idempotent migration for ledgers created before the handoff
    # fence existed; legacy rows read as "not in handoff".
    add_column_if_missing(
        conn, "executions", "handoff_pending",
        "handoff_pending INTEGER NOT NULL DEFAULT 0",
    )
    add_column_if_missing(
        conn, "executions", "handoff_started_at", "handoff_started_at REAL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_executions_job_claimed "
        "ON executions(job_id, claimed_at DESC, id DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_executions_status_claimed "
        "ON executions(status, claimed_at DESC, id DESC)"
    )
    return conn


def _record(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def _process_start_time(pid: int) -> Optional[int]:
    try:
        from gateway.status import get_process_start_time
        return get_process_start_time(pid)
    except Exception:
        return None


def _owner_is_live(pid: int, started_at: Optional[int]) -> bool:
    try:
        from gateway.status import _pid_liveness
        # Fail safe: only proven absence frees the record; an undeterminable
        # probe (None) is treated as alive and the start-time check decides.
        if _pid_liveness(pid) is False:
            return False
    except Exception:
        return True  # fail safe: inability to prove death must not rewrite state
    if started_at is None:
        return pid == os.getpid()
    current = _process_start_time(pid)
    return current is not None and current == started_at


def _prune_unlocked(conn: sqlite3.Connection) -> None:
    limit = max(0, int(MAX_TERMINAL_EXECUTIONS))
    conn.execute(
        """DELETE FROM executions WHERE id IN (
             SELECT id FROM executions
             WHERE status IN ('completed','failed','unknown')
             ORDER BY finished_at DESC, claimed_at DESC, id DESC LIMIT -1 OFFSET ?
           )""",
        (limit,),
    )


def create_execution(job_id: str, *, source: str) -> Dict[str, Any]:
    """Persist a claimed attempt before executor/provider dispatch."""
    now = _hermes_now().isoformat()
    execution_id = uuid.uuid4().hex
    pid = os.getpid()
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO executions
               (id, job_id, source, process_id, pid, process_started_at,
                status, claimed_at)
               VALUES (?, ?, ?, ?, ?, ?, 'claimed', ?)""",
            (execution_id, str(job_id), str(source), _PROCESS_ID, pid,
             _process_start_time(pid), now),
        )
        row = conn.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone()
    return _record(row)  # type: ignore[return-value]


def mark_execution_handoff_pending(execution_id: str) -> Optional[Dict[str, Any]]:
    """Fence restart recovery while an external worker is adopting a claim."""
    with _lock, _connect() as conn:
        cur = conn.execute(
            """UPDATE executions
               SET handoff_pending=1, handoff_started_at=?
               WHERE id=? AND status='claimed'
                 AND process_id=? AND pid=?""",
            (time.time(), execution_id, _PROCESS_ID, os.getpid()),
        )
        if cur.rowcount != 1:
            return None
        return _record(conn.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone())


def adopt_claimed_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """Atomically transfer and start an attempt in its worker process.

    The dispatching process creates the row and fences it with
    ``mark_execution_handoff_pending`` before a worker starts.  Adoption is the
    single ``claimed`` -> ``running`` gate for that handoff: only the winner may
    run side effects.  Recovered (terminal) attempts can never be adopted.
    """
    pid = os.getpid()
    process_started_at = _process_start_time(pid)
    now = _hermes_now().isoformat()
    with _lock, _connect() as conn:
        cur = conn.execute(
            """UPDATE executions
               SET process_id=?, pid=?, process_started_at=?,
                   status='running', started_at=?, handoff_pending=0,
                   handoff_started_at=NULL
               WHERE id=? AND status='claimed' AND handoff_pending=1""",
            (_PROCESS_ID, pid, process_started_at, now, execution_id),
        )
        if cur.rowcount != 1:
            return None
        return _record(conn.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone())


def mark_execution_running(execution_id: str) -> Optional[Dict[str, Any]]:
    """Transition one claimed attempt to running exactly once, by its owner."""
    now = _hermes_now().isoformat()
    with _lock, _connect() as conn:
        cur = conn.execute(
            """UPDATE executions
               SET status='running', started_at=?, handoff_pending=0,
                   handoff_started_at=NULL
               WHERE id=? AND status='claimed' AND handoff_pending=0
                 AND process_id=? AND pid=?""",
            (now, execution_id, _PROCESS_ID, os.getpid()),
        )
        if cur.rowcount != 1:
            return None
        return _record(conn.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone())


def finish_execution(
    execution_id: str, *, success: bool, error: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Write a terminal result once; terminal attempts cannot be rewritten."""
    now = _hermes_now().isoformat()
    status = "completed" if success else "failed"
    detail = None if success else (str(error) if error else "unknown failure")
    with _lock, _connect() as conn:
        cur = conn.execute(
            """UPDATE executions
               SET status=?, finished_at=?, error=?, handoff_pending=0,
                   handoff_started_at=NULL
               WHERE id=? AND status IN ('claimed','running')
                 AND process_id=? AND pid=?""",
            (status, now, detail, execution_id, _PROCESS_ID, os.getpid()),
        )
        if cur.rowcount != 1:
            return None
        _prune_unlocked(conn)
        return _record(conn.execute(
            "SELECT * FROM executions WHERE id=?", (execution_id,)
        ).fetchone())


def recover_interrupted_executions() -> int:
    """Mark provably abandoned attempts unknown without scheduling retries."""
    now = _hermes_now().isoformat()
    changed = 0
    with _lock, _connect() as conn:
        rows = conn.execute(
            """SELECT id, status, process_id, pid, process_started_at,
                      handoff_pending, handoff_started_at
               FROM executions
               WHERE status IN ('claimed','running')"""
        ).fetchall()
        for row in rows:
            if row["process_id"] == _PROCESS_ID:
                continue
            if _owner_is_live(int(row["pid"]), row["process_started_at"]):
                continue
            handoff_started_at = row["handoff_started_at"]
            if (
                row["handoff_pending"]
                and handoff_started_at is not None
                and time.time() - float(handoff_started_at)
                < HANDOFF_ADOPTION_GRACE_SECONDS
            ):
                continue
            # Compare-and-set against the exact observed row: an adoption,
            # start or finish that raced the liveness probe wins.
            cur = conn.execute(
                """UPDATE executions
                   SET status='unknown', finished_at=?, error=?,
                       handoff_pending=0, handoff_started_at=NULL
                   WHERE id=? AND status=? AND process_id=? AND pid=?
                     AND handoff_pending=?
                     AND handoff_started_at IS ?""",
                (now,
                 "Scheduler restarted after this execution's owner exited before a durable "
                 "terminal state; whether side effects ran is unknown.",
                 row["id"], row["status"], row["process_id"], row["pid"],
                 row["handoff_pending"], row["handoff_started_at"]),
            )
            changed += cur.rowcount
        if changed:
            _prune_unlocked(conn)
    return changed


def list_executions(
    *, job_id: Optional[str] = None, limit: int = 50,
    before_claimed_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return indexed, newest-first execution history with cursor pagination."""
    clauses: List[str] = []
    params: List[Any] = []
    if job_id is not None:
        clauses.append("job_id=?")
        params.append(str(job_id))
    if before_claimed_at is not None:
        clauses.append("claimed_at < ?")
        params.append(str(before_claimed_at))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(max(1, min(int(limit), 500)))
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM executions" + where
            + " ORDER BY claimed_at DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """Return one exact execution attempt, or ``None`` when it is absent."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM executions WHERE id=?", (str(execution_id),)
        ).fetchone()
    return _record(row)


def latest_execution(job_id: str) -> Optional[Dict[str, Any]]:
    rows = list_executions(job_id=job_id, limit=1)
    return rows[0] if rows else None


def latest_executions(job_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load latest execution for many jobs in one indexed query."""
    clean = [str(job_id) for job_id in dict.fromkeys(job_ids) if job_id]
    if not clean:
        return {}
    placeholders = ",".join("?" for _ in clean)
    with _lock, _connect() as conn:
        rows = conn.execute(
            f"""SELECT e.* FROM executions e
                WHERE e.job_id IN ({placeholders})
                  AND e.id=(SELECT e2.id FROM executions e2
                            WHERE e2.job_id=e.job_id
                            ORDER BY e2.claimed_at DESC, e2.id DESC LIMIT 1)""",
            clean,
        ).fetchall()
    return {row["job_id"]: dict(row) for row in rows}
