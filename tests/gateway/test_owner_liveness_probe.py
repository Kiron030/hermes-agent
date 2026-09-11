"""MUSTPORT-5A: owner/PID liveness probes never signal what they observe.

On Windows CPython ``os.kill(pid, 0)`` is not a no-op: it maps to
``GenerateConsoleCtrlEvent`` and can Ctrl+C the target's whole console group
(bpo-14484). Owner guards — the delivery ledger, the cron execution ledger and
the compute-host registry — probe through ``gateway.status._pid_liveness``:
psutil first, then a handle-based ``OpenProcess`` check on Windows, and
``os.kill`` only on POSIX.

Fail-safe contract at those guards: proven absence reads dead, an uncertain
probe reads alive (hold), and a live PID whose start time differs from the
recorded one is not the owner.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types

import pytest

from gateway import delivery_ledger, status
from tui_gateway import host_supervisor

_PID = 424242
_OWNER_START = 4242
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87


def _refuse_os_kill(monkeypatch):
    """Record every ``os.kill`` and fail it; a liveness probe must never get here."""
    calls = []

    def _refuse(pid, sig):
        calls.append((pid, sig))
        raise AssertionError(f"liveness probe called os.kill({pid}, {sig})")

    monkeypatch.setattr(os, "kill", _refuse)
    return calls


@pytest.fixture
def kill_calls(monkeypatch):
    return _refuse_os_kill(monkeypatch)


@pytest.fixture
def windows(monkeypatch):
    """Force ``gateway.status`` onto its Windows branch on any host."""
    monkeypatch.setattr(status, "_IS_WINDOWS", True)


class _NoSuchProcess(Exception):
    pass


class _AccessDenied(Exception):
    pass


def _install_psutil(monkeypatch, *, exists=True, gone=False, status_error=None, pid_exists_error=None):
    """Swap in a psutil stub (real POSIX psutil probes via os.kill internally)."""
    psutil = types.ModuleType("psutil")
    psutil.NoSuchProcess = _NoSuchProcess
    psutil.AccessDenied = _AccessDenied
    psutil.STATUS_ZOMBIE = "zombie"

    class Process:
        def __init__(self, pid):
            if gone:
                raise _NoSuchProcess(pid)

        def status(self):
            if status_error is not None:
                raise status_error
            return "running"

    def pid_exists(pid):
        if pid_exists_error is not None:
            raise pid_exists_error
        return exists

    psutil.Process = Process
    psutil.pid_exists = pid_exists
    monkeypatch.setitem(sys.modules, "psutil", psutil)


def _block_psutil(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)  # ``import psutil`` -> ImportError


class _FakeKernel32:
    def __init__(self, *, handle=0x1234, last_error=0, wait_result=_WAIT_TIMEOUT):
        self.handle = handle
        self.last_error = last_error
        self.wait_result = wait_result
        self.opened = []
        self.closed = []

    def OpenProcess(self, access, inherit, pid):
        self.opened.append(pid)
        return self.handle

    def WaitForSingleObject(self, handle, timeout_ms):
        assert timeout_ms == 0  # a probe must never block on its target
        return self.wait_result

    def CloseHandle(self, handle):
        self.closed.append(handle)
        return 1


def _install_kernel32(monkeypatch, fake):
    monkeypatch.setattr(status, "_win32_kernel32", lambda: (fake, lambda: fake.last_error))
    return fake


def _break_ctypes(monkeypatch):
    """kernel32 unreachable through ctypes — both a fresh WinDLL and the shared windll."""
    import ctypes

    def _unavailable(*_args, **_kwargs):
        raise OSError("kernel32 unavailable")

    monkeypatch.setattr(ctypes, "WinDLL", _unavailable, raising=False)
    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(), raising=False)


def _apply_scenario(monkeypatch, scenario):
    if scenario == "alive":
        _install_psutil(monkeypatch, exists=True)
    elif scenario == "dead":
        _install_psutil(monkeypatch, gone=True)
    elif scenario == "uncertain-psutil-error":
        _install_psutil(
            monkeypatch, status_error=_AccessDenied(), pid_exists_error=OSError("psutil failed")
        )
    elif scenario == "uncertain-no-kernel32":
        _block_psutil(monkeypatch)
        _break_ctypes(monkeypatch)
    else:  # pragma: no cover - test typo guard
        raise ValueError(scenario)


_SCENARIOS = ["alive", "dead", "uncertain-psutil-error", "uncertain-no-kernel32"]
_OWNER_EXPECTED = {
    "alive": True,
    "dead": False,
    "uncertain-psutil-error": True,  # fail safe: hold
    "uncertain-no-kernel32": True,  # fail safe: hold
}


class TestWindowsHandleProbe:
    """psutil unavailable on Windows: the ctypes handle check answers, never os.kill."""

    @pytest.mark.parametrize(
        "kernel32, expected",
        [
            ({"wait_result": _WAIT_TIMEOUT}, True),
            ({"wait_result": _WAIT_OBJECT_0}, False),
            ({"handle": None, "last_error": _ERROR_INVALID_PARAMETER}, False),
            ({"handle": None, "last_error": _ERROR_ACCESS_DENIED}, True),
            ({"handle": None, "last_error": 31}, None),
            ({"wait_result": _WAIT_FAILED}, None),
        ],
        ids=["running", "exited", "no-such-pid", "access-denied", "unknown-open-error", "wait-failed"],
    )
    def test_classifies_without_os_kill(self, monkeypatch, windows, kill_calls, kernel32, expected):
        _block_psutil(monkeypatch)
        fake = _install_kernel32(monkeypatch, _FakeKernel32(**kernel32))

        assert status._pid_liveness(_PID) is expected
        # Legacy bool contract for non-owner callers: undeterminable reads False.
        assert status._pid_exists(_PID) is (expected is True)
        assert fake.opened == [_PID, _PID]
        assert fake.closed == ([] if fake.handle is None else [fake.handle, fake.handle])
        assert kill_calls == []

    def test_ctypes_failure_is_uncertain_not_dead(self, monkeypatch, windows, kill_calls):
        _block_psutil(monkeypatch)

        def _no_kernel32():
            raise OSError("kernel32 unavailable")

        monkeypatch.setattr(status, "_win32_kernel32", _no_kernel32)

        assert status._pid_liveness(_PID) is None
        assert status._pid_exists(_PID) is False
        assert kill_calls == []


class TestWindowsPsutilProbe:
    @pytest.mark.parametrize(
        "psutil_kwargs, expected",
        [
            ({"exists": True}, True),
            ({"gone": True}, False),
            ({"status_error": _AccessDenied(), "exists": True}, True),
            ({"status_error": _AccessDenied(), "exists": False}, False),
        ],
        ids=["alive", "no-such-process", "status-access-denied-alive", "status-access-denied-gone"],
    )
    def test_psutil_answers_without_os_kill(self, monkeypatch, windows, kill_calls, psutil_kwargs, expected):
        _install_psutil(monkeypatch, **psutil_kwargs)

        def _fallback_not_expected():
            raise AssertionError("psutil answered; the ctypes fallback must not run")

        monkeypatch.setattr(status, "_win32_kernel32", _fallback_not_expected)

        assert status._pid_liveness(_PID) is expected
        assert kill_calls == []

    def test_psutil_error_propagates_so_owner_guards_can_hold(self, monkeypatch, windows, kill_calls):
        _install_psutil(monkeypatch, status_error=_AccessDenied(), pid_exists_error=OSError("psutil failed"))

        with pytest.raises(OSError):
            status._pid_liveness(_PID)
        assert kill_calls == []


class TestOwnerGuardsOnWindows:
    """Every owner guard: no os.kill, and proven-dead / alive / uncertain map to dead / alive / hold."""

    @pytest.mark.parametrize("scenario", _SCENARIOS)
    def test_delivery_ledger_owner(self, monkeypatch, windows, kill_calls, scenario):
        # Unreadable start time forces the probe fallback that used to call os.kill(pid, 0).
        monkeypatch.setattr(status, "get_process_start_time", lambda pid: None)
        _apply_scenario(monkeypatch, scenario)

        assert delivery_ledger._owner_alive(_PID, _OWNER_START) is _OWNER_EXPECTED[scenario]
        assert kill_calls == []

    def test_delivery_ledger_rejects_recycled_pid(self, monkeypatch, windows, kill_calls):
        monkeypatch.setattr(status, "get_process_start_time", lambda pid: _OWNER_START + 1)
        _apply_scenario(monkeypatch, "alive")

        assert delivery_ledger._owner_alive(_PID, _OWNER_START) is False
        assert kill_calls == []

    @pytest.mark.parametrize("scenario", _SCENARIOS)
    def test_compute_host_registry_owner(self, monkeypatch, windows, kill_calls, scenario):
        _apply_scenario(monkeypatch, scenario)

        assert host_supervisor._pid_alive(_PID) is _OWNER_EXPECTED[scenario]
        assert kill_calls == []

    @pytest.mark.parametrize("scenario", _SCENARIOS)
    def test_cron_execution_owner(self, monkeypatch, windows, kill_calls, scenario):
        from cron import executions

        monkeypatch.setattr(status, "get_process_start_time", lambda pid: _OWNER_START)
        _apply_scenario(monkeypatch, scenario)

        assert executions._owner_is_live(_PID, _OWNER_START) is _OWNER_EXPECTED[scenario]
        assert kill_calls == []

    @pytest.mark.parametrize("scenario", ["alive", "uncertain-no-kernel32"])
    def test_cron_rejects_recycled_pid(self, monkeypatch, windows, kill_calls, scenario):
        from cron import executions

        monkeypatch.setattr(status, "get_process_start_time", lambda pid: _OWNER_START + 1)
        _apply_scenario(monkeypatch, scenario)

        assert executions._owner_is_live(_PID, _OWNER_START) is False
        assert kill_calls == []


class TestRealProcesses:
    def test_probing_own_pid_repeatedly_is_alive_and_harmless(self, monkeypatch):
        from cron import executions

        # POSIX psutil legitimately probes with os.kill; on Windows any call is the bug.
        calls = _refuse_os_kill(monkeypatch) if sys.platform == "win32" else []
        monkeypatch.setattr(status, "get_process_start_time", lambda pid: None)
        pid = os.getpid()

        for _ in range(200):
            assert status._pid_liveness(pid) is True
            assert delivery_ledger._owner_alive(pid, None) is True
            assert host_supervisor._pid_alive(pid) is True
        assert executions._owner_is_live(pid, None) is True
        assert calls == []

    def test_exited_child_pid_reads_dead(self):
        from cron import executions

        # Keep the Popen object alive so its PID is not recycled mid-test.
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        assert proc.wait(timeout=60) == 0

        assert status._pid_liveness(proc.pid) is False
        assert status._pid_exists(proc.pid) is False
        assert host_supervisor._pid_alive(proc.pid) is False
        assert delivery_ledger._owner_alive(proc.pid, 1) is False
        assert executions._owner_is_live(proc.pid, 1) is False


@pytest.mark.skipif(sys.platform != "win32", reason="exercises the real kernel32 handle probe")
class TestRealWindowsHandleProbe:
    def test_handle_probe_without_psutil(self, monkeypatch):
        calls = _refuse_os_kill(monkeypatch)
        _block_psutil(monkeypatch)
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        assert proc.wait(timeout=60) == 0
        pid = os.getpid()

        for _ in range(50):
            assert status._pid_liveness_win32(pid) is True
        assert status._pid_liveness(pid) is True
        assert status._pid_liveness(proc.pid) is False
        assert host_supervisor._pid_alive(pid) is True
        assert host_supervisor._pid_alive(proc.pid) is False
        # PID 4 (System) always exists: access denied or a live handle, both alive.
        assert status._pid_liveness_win32(4) is True
        assert calls == []

    def test_psutil_path_never_signals(self, monkeypatch):
        calls = _refuse_os_kill(monkeypatch)
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        assert proc.wait(timeout=60) == 0

        for _ in range(50):
            assert status._pid_liveness(os.getpid()) is True
        assert status._pid_liveness(proc.pid) is False
        assert calls == []
