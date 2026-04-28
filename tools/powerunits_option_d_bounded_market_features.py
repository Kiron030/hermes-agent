"""
Bounded Option D wrapper — delegates to Repo B `market_feature_job` (no new SQL).

Operator-only; not a Hermes writer tool. Requires a local checkout of the Powerunits
product repo and `POWERUNITS_OPTION_D_PRODUCT_ROOT` pointing to its root (parent of `backend/`).

Spec: docs/powerunits_option_d_bounded_wrapper_spec_v1.md

IMPORTANT: Do **not** add ``registry.register(...)`` here. Tool discovery imports
``tools/*.py`` modules that register at module level; this file must stay off the
Hermes / Telegram / first_safe tool surface.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

WRAPPER_ID = "option_d_bounded_market_features_v1"
ENV_PRODUCT_ROOT = "POWERUNITS_OPTION_D_PRODUCT_ROOT"


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def _fingerprint_host_db(url: str) -> dict[str, str | None]:
    u = (url or "").strip()
    if not u:
        return {"host": None, "db": None}
    p = urlparse(u)
    db = (p.path or "").strip("/").split("?")[0] or None
    return {"host": p.hostname, "db": db}


def _parse_utc_iso(s: str) -> datetime:
    raw = s.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware (use Z suffix)")
    return dt.astimezone(timezone.utc)


def _validate_slice(country: str, start_s: str, end_s: str, version: str) -> tuple[str, datetime, datetime]:
    cc = country.strip().upper()
    if cc != "PL":
        raise ValueError("country must be PL for this wrapper release")
    if version.strip() != "v1":
        raise ValueError("version must be v1 for this wrapper release")
    start = _parse_utc_iso(start_s)
    end = _parse_utc_iso(end_s)
    if end <= start:
        raise ValueError("end must be strictly after start (exclusive end semantics)")
    delta = end - start
    if delta <= timedelta(0):
        raise ValueError("window must be > 0")
    if delta > timedelta(hours=24):
        raise ValueError("window must be <= 24 hours")
    return cc, start, end


def _check_env() -> tuple[str, str, str]:
    db = os.environ.get("DATABASE_URL", "").strip()
    ts = os.environ.get("DATABASE_URL_TIMESCALE", "").strip()
    wt = os.environ.get("MARKET_FEATURES_WRITE_TARGET", "").strip().lower()
    if not db:
        raise OSError("DATABASE_URL is required")
    if not ts:
        raise OSError("DATABASE_URL_TIMESCALE is required")
    if wt != "timescale":
        raise OSError("MARKET_FEATURES_WRITE_TARGET must be exactly timescale")
    return db, ts, wt


def _parse_job_stdout(text: str) -> dict[str, Any]:
    """Parse `Run: <uuid> status=... rows_written=N` from market_feature_job CLI."""
    out: dict[str, Any] = {"run_id": None, "status": None, "rows_written": None, "error_message": None}
    for line in text.splitlines():
        m = re.search(
            r"Run:\s+(?P<rid>[0-9a-fA-F-]{36})\s+status=(?P<st>\w+)\s+rows_written=(?P<rw>\d+)",
            line,
        )
        if m:
            out["run_id"] = m.group("rid")
            out["status"] = m.group("st")
            out["rows_written"] = int(m.group("rw"))
        if line.startswith("Error:"):
            out["error_message"] = line[len("Error:") :].strip()
    return out


def _delegate_uv(
    *,
    product_root: Path,
    version: str,
    country: str,
    start_s: str,
    end_s: str,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv executable not found on PATH")
    backend = product_root / "backend"
    job_py = backend / "services" / "data_ingestion" / "jobs" / "market_feature_job.py"
    if not job_py.is_file():
        raise FileNotFoundError(f"missing market_feature_job at {job_py}")
    cmd = [
        uv,
        "run",
        "python",
        "-m",
        "services.data_ingestion.jobs.market_feature_job",
        "--version",
        version,
        "--countries",
        country,
        "--start",
        start_s,
        "--end",
        end_s,
    ]
    return subprocess.run(
        cmd,
        cwd=str(backend),
        env=env,
        capture_output=True,
        text=True,
        timeout=3600,
    )


def run_bounded(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
    product_root: Path | None = None,
) -> int:
    """Run validation + delegate. Returns process exit code (0,2,3,4,5)."""
    slice_payload: dict[str, Any] | None = None
    try:
        cc, start_dt, end_dt = _validate_slice(country, start, end, version)
        slice_payload = {
            "country": cc,
            "version": version.strip(),
            "start_utc": start_dt.isoformat().replace("+00:00", "Z"),
            "end_utc_exclusive": end_dt.isoformat().replace("+00:00", "Z"),
        }
    except ValueError as e:
        _emit(
            {
                "ok": False,
                "error_class": "validation",
                "code": 2,
                "message": str(e),
                "slice": None,
            }
        )
        return 2

    try:
        db_url, ts_url, _wt = _check_env()
    except OSError as e:
        _emit(
            {
                "ok": False,
                "error_class": "environment",
                "code": 3,
                "message": str(e),
                "slice": slice_payload,
            }
        )
        return 3

    root = product_root
    if root is None:
        raw_root = os.environ.get(ENV_PRODUCT_ROOT, "").strip()
        if not raw_root:
            _emit(
                {
                    "ok": False,
                    "error_class": "environment",
                    "code": 3,
                    "message": f"{ENV_PRODUCT_ROOT} must point to the Powerunits product repo root (parent of backend/)",
                    "slice": slice_payload,
                }
            )
            return 3
        root = Path(raw_root).expanduser().resolve()
    if not (root / "backend").is_dir():
        _emit(
            {
                "ok": False,
                "error_class": "environment",
                "code": 3,
                "message": f"invalid product root: {root} (expected backend/ directory)",
                "slice": slice_payload,
            }
        )
        return 3

    fp_primary = _fingerprint_host_db(db_url)
    fp_ts = _fingerprint_host_db(ts_url)

    env = os.environ.copy()
    try:
        proc = _delegate_uv(
            product_root=root,
            version=version.strip(),
            country=cc,
            start_s=start.strip(),
            end_s=end.strip(),
            env=env,
        )
    except (FileNotFoundError, RuntimeError) as e:
        _emit(
            {
                "ok": False,
                "error_class": "internal",
                "code": 5,
                "message": str(e),
                "slice": slice_payload,
            }
        )
        return 5
    except Exception as e:  # noqa: BLE001 — wrapper must never leak traceback
        _emit(
            {
                "ok": False,
                "error_class": "internal",
                "code": 5,
                "message": str(e)[:500],
                "slice": slice_payload,
            }
        )
        return 5

    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = _parse_job_stdout(combined)
    job_failed = proc.returncode != 0 or parsed.get("status") != "success" or parsed.get("error_message")

    if job_failed:
        err = (proc.stderr or "").strip() or (proc.stdout or "").strip()
        if parsed.get("error_message"):
            err = str(parsed["error_message"])[:500]
        elif err:
            err = err[:500]
        else:
            err = f"subprocess exit {proc.returncode}"
        _emit(
            {
                "ok": False,
                "error_class": "job_failed",
                "code": 4,
                "message": err,
                "slice": slice_payload,
                "job": {
                    "status": parsed.get("status"),
                    "run_id": parsed.get("run_id"),
                    "rows_written": parsed.get("rows_written"),
                    "returncode": proc.returncode,
                },
            }
        )
        return 4

    _emit(
        {
            "ok": True,
            "wrapper": WRAPPER_ID,
            "slice": slice_payload,
            "write_target": "timescale",
            "db_fingerprint": {
                "primary_host": fp_primary["host"],
                "primary_db": fp_primary["db"],
                "timescale_host": fp_ts["host"],
                "timescale_db": fp_ts["db"],
            },
            "job": {
                "status": parsed.get("status"),
                "run_id": parsed.get("run_id"),
                "rows_written": parsed.get("rows_written"),
                "error_message": None,
            },
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bounded Option D market_features_hourly recompute (operator only).")
    p.add_argument("--country", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--version", required=True)
    args = p.parse_args(argv)
    try:
        return run_bounded(
            country=args.country,
            start=args.start,
            end=args.end,
            version=args.version,
        )
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        _emit(
            {
                "ok": False,
                "error_class": "internal",
                "code": 5,
                "message": str(e)[:500],
                "slice": None,
            }
        )
        return 5


if __name__ == "__main__":
    sys.exit(main())
