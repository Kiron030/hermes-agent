"""Durable cron execution-ledger behavior."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _point_ledger(monkeypatch, tmp_path):
    import cron.executions as executions

    monkeypatch.setattr(executions, "EXECUTIONS_FILE", tmp_path / "cron" / "executions.db")
    return executions


def test_execution_transitions_are_durable(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)

    claimed = executions.create_execution("job-1", source="builtin")
    assert claimed["status"] == "claimed"
    assert claimed["claimed_at"]
    assert claimed["started_at"] is None
    assert claimed["finished_at"] is None

    running = executions.mark_execution_running(claimed["id"])
    assert running["status"] == "running"
    assert running["started_at"]

    completed = executions.finish_execution(claimed["id"], success=True)
    assert completed["status"] == "completed"
    assert completed["finished_at"]
    assert completed["error"] is None

    persisted = executions.list_executions(job_id="job-1")
    assert persisted == [completed]


def test_execution_can_be_loaded_by_exact_attempt_id(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    first = executions.create_execution("same-job", source="builtin")
    second = executions.create_execution("same-job", source="builtin")

    assert executions.get_execution(first["id"]) == first
    assert executions.get_execution(second["id"]) == second
    assert executions.get_execution("missing") is None


def test_fresh_external_handoff_is_not_recovered_before_worker_adopts(
    monkeypatch, tmp_path
):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("handoff-job", source="builtin")
    assert executions.mark_execution_handoff_pending(record["id"]) is not None

    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")
    monkeypatch.setattr(executions, "_owner_is_live", lambda _pid, _started: False)

    assert executions.recover_interrupted_executions() == 0
    assert executions.get_execution(record["id"])["status"] == "claimed"
    adopted = executions.adopt_claimed_execution(record["id"])
    assert adopted["status"] == "running"
    assert adopted["handoff_pending"] == 0


def test_stale_external_handoff_is_recovered_unknown(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("handoff-job", source="builtin")
    pending = executions.mark_execution_handoff_pending(record["id"])

    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")
    monkeypatch.setattr(executions, "_owner_is_live", lambda _pid, _started: False)
    monkeypatch.setattr(
        executions.time,
        "time",
        lambda: pending["handoff_started_at"]
        + executions.HANDOFF_ADOPTION_GRACE_SECONDS
        + 1,
    )

    assert executions.recover_interrupted_executions() == 1
    recovered = executions.get_execution(record["id"])
    assert recovered["status"] == "unknown"
    assert recovered["handoff_pending"] == 0


def test_recovery_does_not_overwrite_concurrent_worker_adoption(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("adoption-race", source="builtin")
    pending = executions.mark_execution_handoff_pending(record["id"])
    assert pending is not None
    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-scheduler")
    monkeypatch.setattr(
        executions.time,
        "time",
        lambda: pending["handoff_started_at"]
        + executions.HANDOFF_ADOPTION_GRACE_SECONDS
        + 1,
    )

    def adopt_while_liveness_is_checked(_pid, _started_at):
        monkeypatch.setattr(executions, "_PROCESS_ID", "external-worker")
        monkeypatch.setattr(executions.os, "getpid", lambda: 4242)
        monkeypatch.setattr(executions, "_process_start_time", lambda _pid: 9876)
        assert executions.adopt_claimed_execution(record["id"]) is not None
        return False

    monkeypatch.setattr(executions, "_owner_is_live", adopt_while_liveness_is_checked)

    assert executions.recover_interrupted_executions() == 0
    current = executions.get_execution(record["id"])
    assert current is not None
    assert current["status"] == "running"
    assert current["process_id"] == "external-worker"
    assert current["pid"] == 4242


def test_foreign_process_cannot_start_or_finish_execution(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("owner-fence", source="builtin")
    original_process_id = executions._PROCESS_ID
    original_pid = record["pid"]

    monkeypatch.setattr(executions, "_PROCESS_ID", "foreign-process")
    monkeypatch.setattr(executions.os, "getpid", lambda: original_pid + 1)
    assert executions.mark_execution_running(record["id"]) is None
    assert executions.finish_execution(record["id"], success=True) is None

    monkeypatch.setattr(executions, "_PROCESS_ID", original_process_id)
    monkeypatch.setattr(executions.os, "getpid", lambda: original_pid)
    assert executions.mark_execution_running(record["id"]) is not None
    assert executions.finish_execution(record["id"], success=True) is not None


def test_terminal_execution_cannot_be_rewritten(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("immutable", source="builtin")
    executions.mark_execution_running(record["id"])
    executions.finish_execution(record["id"], success=True)

    assert executions.finish_execution(
        record["id"], success=False, error="late writer"
    ) is None
    assert executions.latest_execution("immutable")["status"] == "completed"


def test_retention_bounds_terminal_history_but_preserves_inflight(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    monkeypatch.setattr(executions, "MAX_TERMINAL_EXECUTIONS", 3)
    inflight = executions.create_execution("live", source="builtin")
    executions.mark_execution_running(inflight["id"])
    for index in range(8):
        row = executions.create_execution(f"done-{index}", source="builtin")
        executions.finish_execution(row["id"], success=True)

    records = executions.list_executions(limit=100)
    assert len([row for row in records if row["status"] == "completed"]) == 3
    assert executions.latest_execution("live")["status"] == "running"


def test_recently_finished_long_running_execution_survives_retention(
    monkeypatch, tmp_path
):
    executions = _point_ledger(monkeypatch, tmp_path)
    monkeypatch.setattr(executions, "MAX_TERMINAL_EXECUTIONS", 1)
    long_running = executions.create_execution("long-running", source="builtin")
    assert executions.mark_execution_running(long_running["id"]) is not None
    newer = executions.create_execution("newer", source="builtin")
    assert executions.finish_execution(newer["id"], success=True) is not None

    finished = executions.finish_execution(long_running["id"], success=True)

    assert finished is not None
    assert finished["status"] == "completed"
    assert executions.get_execution(long_running["id"])["status"] == "completed"
    assert executions.get_execution(newer["id"]) is None


def test_corrupt_store_fails_closed_without_overwrite(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    executions.EXECUTIONS_FILE.parent.mkdir(parents=True)
    executions.EXECUTIONS_FILE.write_bytes(b"not a sqlite database")

    with __import__("pytest").raises(sqlite3.DatabaseError):
        executions.create_execution("new", source="builtin")
    assert executions.EXECUTIONS_FILE.read_bytes() == b"not a sqlite database"


def test_execution_history_is_paginated(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    ids = []
    for _index in range(5):
        row = executions.create_execution("paged", source="builtin")
        executions.finish_execution(row["id"], success=True)
        ids.append(row["id"])

    first = executions.list_executions(job_id="paged", limit=2)
    second = executions.list_executions(
        job_id="paged", limit=2, before_claimed_at=first[-1]["claimed_at"]
    )
    assert [row["id"] for row in first] == list(reversed(ids))[:2]
    assert set(row["id"] for row in first).isdisjoint(row["id"] for row in second)


def test_cron_runs_cli_prints_execution_history(monkeypatch, tmp_path, capsys):
    executions = _point_ledger(monkeypatch, tmp_path)
    row = executions.create_execution("cli-job", source="builtin")
    executions.finish_execution(row["id"], success=False, error="boom")
    from hermes_cli.cron import cron_runs

    cron_runs("cli-job", limit=10)

    output = capsys.readouterr().out
    assert row["id"] in output
    assert "failed" in output
    assert "boom" in output


def test_quick_backup_includes_execution_ledger():
    from hermes_cli.backup import _QUICK_STATE_FILES

    assert "cron/executions.db" in _QUICK_STATE_FILES


def test_failed_execution_keeps_error(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)

    record = executions.create_execution("job-2", source="external")
    failed = executions.finish_execution(record["id"], success=False, error="provider exploded")

    assert failed["status"] == "failed"
    assert failed["error"] == "provider exploded"


def test_recovery_does_not_mark_live_process_execution_unknown(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("still-live", source="builtin")
    executions.mark_execution_running(record["id"])

    assert executions.recover_interrupted_executions() == 0
    assert executions.latest_execution("still-live")["status"] == "running"


def test_recovery_does_not_mark_other_live_owner_unknown(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("other-live", source="builtin")
    with sqlite3.connect(executions.EXECUTIONS_FILE) as conn:
        conn.execute(
            "UPDATE executions SET process_id=?, pid=? WHERE id=?",
            ("another-import", os.getpid(), record["id"]),
        )

    assert executions.recover_interrupted_executions() == 0
    assert executions.latest_execution("other-live")["status"] == "claimed"


def test_recovery_rejects_recycled_pid(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("recycled", source="builtin")
    with sqlite3.connect(executions.EXECUTIONS_FILE) as conn:
        conn.execute(
            "UPDATE executions SET process_id=?, process_started_at=? WHERE id=?",
            ("old-import", -1, record["id"]),
        )

    assert executions.recover_interrupted_executions() == 1
    assert executions.latest_execution("recycled")["status"] == "unknown"


def test_restart_marks_interrupted_execution_unknown_without_requeue(tmp_path):
    """Real temp-HERMES_HOME subprocess restart: in-flight is audit-only unknown."""
    home = tmp_path / "home"
    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["PYTHONPATH"] = str(repo)

    create = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cron.executions import create_execution, mark_execution_running; "
            "r=create_execution('restart-job', source='builtin'); "
            "mark_execution_running(r['id']); print(r['id'])",
        ],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    execution_id = create.stdout.strip()

    recover = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from cron.executions import recover_interrupted_executions, list_executions; "
            "print(recover_interrupted_executions()); "
            "print(json.dumps(list_executions(job_id='restart-job'))) ",
        ],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    lines = recover.stdout.strip().splitlines()
    assert lines[0] == "1"
    records = json.loads(lines[1])
    assert len(records) == 1
    assert records[0]["id"] == execution_id
    assert records[0]["status"] == "unknown"
    assert records[0]["finished_at"]
    assert "restart" in records[0]["error"].lower()
    # Recovery only classifies the old attempt. It must not manufacture a new
    # claimed record (which would imply an automatic retry).
    assert [r["status"] for r in records] == ["unknown"]


def test_generic_submit_failure_finishes_attempt_and_releases_guard(monkeypatch):
    import cron.scheduler as scheduler

    class BrokenPool:
        def submit(self, _callable):
            raise ValueError("executor rejected")

    finished = []
    monkeypatch.setattr(
        scheduler, "create_execution",
        lambda *_args, **_kwargs: {"id": "exec-submit-fail"},
    )
    monkeypatch.setattr(
        scheduler, "finish_execution",
        lambda execution_id, **kwargs: finished.append((execution_id, kwargs)),
    )
    monkeypatch.setattr(scheduler, "get_due_jobs", lambda: [{"id": "submit-fail"}])
    monkeypatch.setattr(scheduler, "advance_next_run", lambda _job_id: None)
    monkeypatch.setattr(scheduler, "_get_parallel_pool", lambda _workers: BrokenPool())

    assert scheduler.tick(verbose=False, sync=False) == 0
    assert finished == [
        ("exec-submit-fail", {
            "success": False,
            "error": "Executor dispatch failed: executor rejected",
        })
    ]
    assert "submit-fail" not in scheduler.get_running_job_ids()


def test_run_one_job_records_running_then_terminal(monkeypatch):
    import cron.scheduler as scheduler

    events = []
    monkeypatch.setattr(
        scheduler,
        "mark_execution_running",
        lambda execution_id: events.append(("running", execution_id)) or {},
        raising=False,
    )
    monkeypatch.setattr(
        scheduler,
        "finish_execution",
        lambda execution_id, **kwargs: events.append(("finish", execution_id, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(scheduler, "claim_dispatch", lambda _job_id: True)
    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda job, *, defer_agent_teardown=None: (True, "output", "response", None),
    )
    monkeypatch.setattr(scheduler, "save_job_output", lambda *_args: None)
    monkeypatch.setattr(scheduler, "_deliver_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scheduler, "mark_job_run", lambda *_args, **_kwargs: None)

    assert scheduler.run_one_job({"id": "job-3", "execution_id": "exec-3"}) is True
    assert events[0] == ("running", "exec-3")
    assert events[-1][0:2] == ("finish", "exec-3")
    assert events[-1][2]["success"] is True


def test_provider_start_recovers_interrupted_records_before_tick(monkeypatch):
    import cron.scheduler_provider as provider

    events = []
    stop = __import__("threading").Event()
    stop.set()
    monkeypatch.setattr(
        "cron.executions.recover_interrupted_executions",
        lambda: events.append("recover") or 0,
        raising=False,
    )
    monkeypatch.setattr("cron.jobs.record_ticker_heartbeat", lambda **_kwargs: events.append("heartbeat"))

    provider.InProcessCronScheduler().start(stop, interval=1)

    assert events[:2] == ["recover", "heartbeat"]


def test_external_provider_start_recovers_interrupted_records(monkeypatch):
    from plugins.cron_providers.chronos import ChronosCronScheduler

    provider = ChronosCronScheduler()
    provider._client = type("Client", (), {"arm": lambda self, **kwargs: None})()
    events = []
    monkeypatch.setattr(
        "cron.executions.recover_interrupted_executions",
        lambda: events.append("recover") or 0,
    )
    monkeypatch.setattr(provider, "reconcile", lambda: events.append("reconcile"))

    provider.start(__import__("threading").Event())

    assert events == ["recover", "reconcile"]


def test_job_listing_exposes_latest_execution(monkeypatch, tmp_path):
    import cron.jobs as jobs

    monkeypatch.setattr(jobs, "CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr(jobs, "JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr(jobs, "OUTPUT_DIR", tmp_path / "cron" / "output")
    executions = _point_ledger(monkeypatch, tmp_path)

    job = jobs.create_job(prompt="audit me", schedule="every 1h", name="audit")
    record = executions.create_execution(job["id"], source="builtin")
    executions.mark_execution_running(record["id"])

    listed = jobs.list_jobs(include_disabled=True)
    assert listed[0]["latest_execution"]["id"] == record["id"]
    assert listed[0]["latest_execution"]["status"] == "running"


# --- compare-and-set transitions, non-retrying recovery, additive migration --------------------

_BASE_EXECUTIONS_COLUMNS = [
    "id", "job_id", "source", "process_id", "pid", "process_started_at", "status",
    "claimed_at", "started_at", "finished_at", "error",
]

# Exact ledger DDL shipped before the handoff fence columns existed.
_BASE_EXECUTIONS_DDL = """CREATE TABLE IF NOT EXISTS executions (
     id TEXT PRIMARY KEY,
     job_id TEXT NOT NULL,
     source TEXT NOT NULL,
     process_id TEXT NOT NULL,
     pid INTEGER NOT NULL,
     process_started_at INTEGER,
     status TEXT NOT NULL CHECK(status IN
       ('claimed','running','completed','failed','unknown')),
     claimed_at TEXT NOT NULL,
     started_at TEXT,
     finished_at TEXT,
     error TEXT
   )"""


def _raw_row(executions, execution_id):
    conn = sqlite3.connect(executions.EXECUTIONS_FILE)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM executions WHERE id=?", (execution_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _stub_run_body(monkeypatch, scheduler, ran):
    monkeypatch.setattr(scheduler, "claim_dispatch", lambda _job_id: True)
    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda job, **_kwargs: ran.append(job["id"]) or (True, "output", "response", None),
    )
    monkeypatch.setattr(scheduler, "save_job_output", lambda *_args: None)
    monkeypatch.setattr(scheduler, "_deliver_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scheduler, "mark_job_run", lambda *args, **_kwargs: ran.append(("mark_job_run", args))
    )


def test_stale_owner_cannot_rewrite_recovered_attempt(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("stale-owner", source="builtin")
    assert executions.mark_execution_running(record["id"]) is not None
    owner_process_id = executions._PROCESS_ID

    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")
    monkeypatch.setattr(executions, "_owner_is_live", lambda _pid, _started: False)
    assert executions.recover_interrupted_executions() == 1
    recovered = _raw_row(executions, record["id"])
    assert recovered["status"] == "unknown"

    # The original owner resurfaces holding its stale view of the attempt.
    monkeypatch.setattr(executions, "_PROCESS_ID", owner_process_id)
    assert executions.finish_execution(record["id"], success=True) is None
    assert executions.finish_execution(record["id"], success=False, error="late") is None
    assert executions.mark_execution_running(record["id"]) is None
    assert _raw_row(executions, record["id"]) == recovered


def test_duplicate_running_transition_changes_nothing(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("duplicate-start", source="builtin")

    first = executions.mark_execution_running(record["id"])

    assert first is not None
    assert executions.mark_execution_running(record["id"]) is None
    assert _raw_row(executions, record["id"]) == first


def test_recovery_snapshot_does_not_overwrite_newer_owner_transition(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("probe-race", source="builtin")
    owner_process_id = executions._PROCESS_ID
    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")

    def owner_starts_while_probe_runs(_pid, _started_at):
        monkeypatch.setattr(executions, "_PROCESS_ID", owner_process_id)
        assert executions.mark_execution_running(record["id"]) is not None
        monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")
        return False

    monkeypatch.setattr(executions, "_owner_is_live", owner_starts_while_probe_runs)

    # Recovery observed ``claimed``; the owner's newer ``running`` must survive.
    assert executions.recover_interrupted_executions() == 0
    current = executions.get_execution(record["id"])
    assert current["status"] == "running"
    assert current["error"] is None


_ADOPT_IN_CHILD = (
    "import json, os, sys\n"
    "from cron.executions import adopt_claimed_execution\n"
    "won = adopt_claimed_execution(sys.argv[1])\n"
    "print(json.dumps({'pid': os.getpid(), 'won': won is not None}))\n"
)


def test_concurrent_adoption_across_processes_has_exactly_one_winner(monkeypatch, tmp_path):
    """Real processes race the claimed -> running gate for one handed-off attempt."""
    import cron.executions as executions

    home = tmp_path / "home"
    monkeypatch.setattr(
        executions, "EXECUTIONS_FILE", home.resolve() / "cron" / "executions.db"
    )
    record = executions.create_execution("adopt-race", source="builtin")
    assert executions.mark_execution_handoff_pending(record["id"]) is not None

    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["PYTHONPATH"] = str(repo)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _ADOPT_IN_CHILD, record["id"]],
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    results = []
    try:
        for proc in procs:
            out, err = proc.communicate(timeout=120)
            assert proc.returncode == 0, err
            results.append(json.loads(out.strip().splitlines()[-1]))
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.kill()

    winners = [result for result in results if result["won"]]
    assert len(winners) == 1
    current = executions.get_execution(record["id"])
    assert current["status"] == "running"
    assert current["pid"] == winners[0]["pid"]
    assert current["handoff_pending"] == 0
    assert len(executions.list_executions(job_id="adopt-race")) == 1


def test_run_one_job_does_not_start_an_attempt_it_did_not_win(monkeypatch, tmp_path):
    import cron.scheduler as scheduler

    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("duplicate-dispatch", source="builtin")
    winner = executions.mark_execution_running(record["id"])
    assert winner is not None
    ran = []
    _stub_run_body(monkeypatch, scheduler, ran)

    # A duplicate dispatch of the same attempt loses the claimed -> running CAS.
    assert scheduler.run_one_job(
        {"id": "duplicate-dispatch", "execution_id": record["id"]}
    ) is True

    assert ran == []
    assert _raw_row(executions, record["id"]) == winner


def test_dead_owner_recovery_is_terminal_and_never_reruns(monkeypatch, tmp_path):
    import cron.scheduler as scheduler

    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("dead-owner", source="builtin")
    assert executions.mark_execution_running(record["id"]) is not None
    owner_process_id = executions._PROCESS_ID
    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")
    monkeypatch.setattr(executions, "_owner_is_live", lambda _pid, _started: False)

    assert executions.recover_interrupted_executions() == 1
    recovered = executions.get_execution(record["id"])
    assert recovered["status"] == "unknown"
    assert recovered["finished_at"]
    assert executions.recover_interrupted_executions() == 0

    # No transition can revive the recovered attempt, from either process identity.
    for process_id in ("replacement-gateway", owner_process_id):
        monkeypatch.setattr(executions, "_PROCESS_ID", process_id)
        assert executions.mark_execution_running(record["id"]) is None
        assert executions.mark_execution_handoff_pending(record["id"]) is None
        assert executions.adopt_claimed_execution(record["id"]) is None
        assert executions.finish_execution(record["id"], success=True) is None

    # Feeding the recovered attempt back through the shared run body does not run it.
    ran = []
    _stub_run_body(monkeypatch, scheduler, ran)
    assert scheduler.run_one_job({"id": "dead-owner", "execution_id": record["id"]}) is True
    assert ran == []
    assert executions.list_executions(job_id="dead-owner") == [recovered]


def test_live_adopted_run_survives_simulated_gateway_restart(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    record = executions.create_execution("restart-live", source="builtin")
    assert executions.mark_execution_handoff_pending(record["id"]) is not None
    dispatcher_process_id = executions._PROCESS_ID

    # A live worker (this process under its own import identity) adopts the handoff.
    monkeypatch.setattr(executions, "_PROCESS_ID", "detached-worker")
    adopted = executions.adopt_claimed_execution(record["id"])
    assert adopted is not None
    assert adopted["status"] == "running"

    # Replacement gateway starts: the real liveness probe sees the worker alive.
    monkeypatch.setattr(executions, "_PROCESS_ID", "replacement-gateway")
    assert executions.recover_interrupted_executions() == 0
    assert executions.adopt_claimed_execution(record["id"]) is None
    assert executions.mark_execution_running(record["id"]) is None
    assert executions.get_execution(record["id"]) == adopted

    # The departed dispatcher's identity cannot terminalize the adopted run.
    monkeypatch.setattr(executions, "_PROCESS_ID", dispatcher_process_id)
    assert executions.finish_execution(record["id"], success=False, error="stale") is None

    monkeypatch.setattr(executions, "_PROCESS_ID", "detached-worker")
    finished = executions.finish_execution(record["id"], success=True)
    assert finished["status"] == "completed"
    assert executions.list_executions(job_id="restart-live") == [finished]


def test_base_schema_ledger_is_migrated_additively(monkeypatch, tmp_path):
    executions = _point_ledger(monkeypatch, tmp_path)
    executions.EXECUTIONS_FILE.parent.mkdir(parents=True)
    legacy_rows = [
        ("legacy-done", "job-a", "builtin", "old-import", 111, 222, "completed",
         "2026-09-01T00:00:00+00:00", "2026-09-01T00:00:01+00:00",
         "2026-09-01T00:00:02+00:00", None),
        ("legacy-live", "job-b", "builtin", "old-import", 333, 444, "running",
         "2026-09-01T00:01:00+00:00", "2026-09-01T00:01:01+00:00", None, None),
    ]
    conn = sqlite3.connect(executions.EXECUTIONS_FILE)
    try:
        conn.execute(_BASE_EXECUTIONS_DDL)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_executions_job_claimed "
            "ON executions(job_id, claimed_at DESC, id DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_executions_status_claimed "
            "ON executions(status, claimed_at DESC, id DESC)"
        )
        conn.executemany(
            "INSERT INTO executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", legacy_rows
        )
        conn.commit()
    finally:
        conn.close()

    # Opening the ledger repeatedly proves the migration is idempotent.
    first_open = executions.list_executions(limit=10)
    assert executions.list_executions(limit=10) == first_open

    conn = sqlite3.connect(executions.EXECUTIONS_FILE)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(executions)")]
        migrated = conn.execute(
            "SELECT " + ", ".join(_BASE_EXECUTIONS_COLUMNS) + " FROM executions ORDER BY id"
        ).fetchall()
        fence = conn.execute(
            "SELECT id, handoff_pending, handoff_started_at FROM executions ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    assert columns[:len(_BASE_EXECUTIONS_COLUMNS)] == _BASE_EXECUTIONS_COLUMNS
    assert columns[len(_BASE_EXECUTIONS_COLUMNS):] == ["handoff_pending", "handoff_started_at"]
    assert migrated == legacy_rows
    assert fence == [("legacy-done", 0, None), ("legacy-live", 0, None)]

    # A legacy in-flight row with a dead owner still recovers under the CAS predicate.
    monkeypatch.setattr(executions, "_owner_is_live", lambda _pid, _started: False)
    assert executions.recover_interrupted_executions() == 1
    assert executions.get_execution("legacy-live")["status"] == "unknown"
    assert executions.get_execution("legacy-done") == dict(
        zip(_BASE_EXECUTIONS_COLUMNS, legacy_rows[0]),
        handoff_pending=0,
        handoff_started_at=None,
    )


def test_execution_ledger_schema_carries_no_replayable_authority(monkeypatch, tmp_path):
    """Attempts record audit facts only: no approval, grant or capability can be replayed."""
    executions = _point_ledger(monkeypatch, tmp_path)
    executions.create_execution("schema-guard", source="builtin")

    conn = sqlite3.connect(executions.EXECUTIONS_FILE)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(executions)")}
    finally:
        conn.close()

    assert columns == set(_BASE_EXECUTIONS_COLUMNS) | {"handoff_pending", "handoff_started_at"}
