#!/usr/bin/env python3
"""
Hermes-facing **bounded Option D execute** — exactly one subprocess to the operator wrapper.

Delegates only to ``sys.executable -m tools.powerunits_option_d_bounded_market_features``.
No direct SQL, no other shell commands, no follow-up jobs. Gated by
``HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.powerunits_option_d_bounded_market_features import _validate_slice

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED"
_SURFACE = "powerunits_option_d_execute"
_HERMES_REPO_ROOT = Path(__file__).resolve().parent.parent
_WRAPPER_MODULE = "tools.powerunits_option_d_bounded_market_features"
_MAX_IO_SUMMARY_CHARS = 6000
_SUBPROCESS_TIMEOUT_S = 3600

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_option_d_execute_requirements() -> bool:
    return _truthy_env(_FEATURE_ENV)


def _redact_secrets(text: str) -> str:
    if not text:
        return ""
    redacted = _SECRET_URL_RE.sub("[REDACTED_URL]", text)
    if len(redacted) > _MAX_IO_SUMMARY_CHARS:
        return redacted[:_MAX_IO_SUMMARY_CHARS] + "\n...[truncated]"
    return redacted


def _run_bounded_subprocess(
    cmd: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout_s: int = _SUBPROCESS_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def execute_powerunits_option_d_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    _run_wrapper: Any = None,
) -> str:
    runner = _run_wrapper or _run_bounded_subprocess

    if not check_powerunits_option_d_execute_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": f"{_FEATURE_ENV} must be truthy for this tool.",
                "slice": None,
                "execution_attempted": False,
                "success": False,
                "delegated_wrapper_exit_code": None,
            },
            ensure_ascii=False,
        )

    country_s = (country or "").strip()
    start_s = (start or "").strip()
    end_s = (end or "").strip()
    version_s = (version or "").strip()

    base_statement = (
        "Hermes performed no direct SQL. The only execution path was a single subprocess "
        f"invoking `{_WRAPPER_MODULE}` via `python -m` (interpreter: Hermes `sys.executable`). "
        "No other jobs, shells, or fallback paths were started by this tool."
    )

    try:
        cc, start_dt, end_dt = _validate_slice(country_s, start_s, end_s, version_s)
    except ValueError as e:
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": None,
                "validation_messages": [str(e)],
                "execution_attempted": False,
                "success": False,
                "delegated_wrapper_exit_code": None,
                "wrapper_stdout_summary": "",
                "wrapper_stderr_summary": "",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    slice_obj = {
        "country": cc,
        "version": version_s,
        "start_utc": start_dt.isoformat().replace("+00:00", "Z"),
        "end_utc_exclusive": end_dt.isoformat().replace("+00:00", "Z"),
    }

    cmd = [
        sys.executable,
        "-m",
        _WRAPPER_MODULE,
        "--country",
        cc,
        "--start",
        start_s,
        "--end",
        end_s,
        "--version",
        version_s,
    ]

    try:
        proc = runner(
            cmd,
            cwd=str(_HERMES_REPO_ROOT),
            env=dict(os.environ),
            timeout_s=_SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        err = (e.stderr or "") if isinstance(e.stderr, str) else ""
        logger.warning("option_d execute: wrapper timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": True,
                "success": False,
                "delegated_wrapper_exit_code": None,
                "error_class": "timeout",
                "wrapper_stdout_summary": _redact_secrets(out),
                "wrapper_stderr_summary": _redact_secrets(err),
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("option_d execute: subprocess error: %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "slice": slice_obj,
                "execution_attempted": True,
                "success": False,
                "delegated_wrapper_exit_code": None,
                "error_class": "subprocess_error",
                "message": f"{type(e).__name__}: {e}"[:500],
                "wrapper_stdout_summary": "",
                "wrapper_stderr_summary": "",
                "hermes_statement": base_statement,
            },
            ensure_ascii=False,
        )

    rc = int(proc.returncode)
    ok = rc == 0
    return json.dumps(
        {
            "surface": _SURFACE,
            "slice": slice_obj,
            "execution_attempted": True,
            "success": ok,
            "delegated_wrapper_exit_code": rc,
            "wrapper_stdout_summary": _redact_secrets(proc.stdout or ""),
            "wrapper_stderr_summary": _redact_secrets(proc.stderr or ""),
            "hermes_statement": base_statement,
        },
        ensure_ascii=False,
    )


EXECUTE_OPTION_D_SCHEMA = {
    "name": "execute_powerunits_option_d_bounded_slice",
    "description": (
        "**Option D bounded execute (first Hermes write test)** — validates PL / v1 / ≤24h UTC "
        "slice, then runs **exactly one** subprocess: `python -m tools.powerunits_option_d_bounded_market_features` "
        "with the same arguments (no direct SQL, no other commands). Requires "
        f"{_FEATURE_ENV}. Not a general-purpose database writer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Must be PL (first release)."},
            "start": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z.",
            },
            "end": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z.",
            },
            "version": {"type": "string", "description": "Must be v1 (first release)."},
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="execute_powerunits_option_d_bounded_slice",
    toolset="powerunits_option_d_execute",
    schema=EXECUTE_OPTION_D_SCHEMA,
    handler=lambda args, **kw: execute_powerunits_option_d_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_option_d_execute_requirements,
    requires_env=[_FEATURE_ENV],
    emoji="⚡",
)
