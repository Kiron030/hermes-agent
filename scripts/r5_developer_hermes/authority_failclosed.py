#!/usr/bin/env python3
"""Prove production write/deploy authority is absent in the developer process.

Prints one JSON object. Never prints secret values.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


PRODUCTION_AUTHORITY_NAMES = [
    "DATABASE_URL_TIMESCALE",
    "DATABASE_URL",
    "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET",
    "RAILWAY_TOKEN",
    "RAILWAY_API_TOKEN",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_ENVIRONMENT_ID",
    "RAILWAY_PUBLIC_DOMAIN",
    "RAILWAY_STATIC_URL",
    "VERCEL_TOKEN",
    "VERCEL_ORG_ID",
    "VERCEL_PROJECT_ID",
    "VERCEL_DEPLOY_HOOK",
]


def _present(names: list[str]) -> list[str]:
    return [name for name in names if (os.environ.get(name) or "").strip()]


def _check_fn_closed() -> dict:
    try:
        from tools.powerunits_option_d_execute_tool import (
            check_powerunits_option_d_execute_requirements,
        )
    except Exception as exc:
        return {
            "importable": False,
            "available": False,
            "reason": type(exc).__name__,
            "fail_closed": True,
        }
    available = bool(check_powerunits_option_d_execute_requirements())
    return {
        "importable": True,
        "available": available,
        "fail_closed": not available,
        "tool": "execute_powerunits_option_d_bounded_slice",
    }


def _looks_authenticated(cli: str, returncode: int, output: str) -> bool:
    text = output.lower()
    login_markers = (
        "login",
        "not logged",
        "unauthorized",
        "unauthenticated",
        "no token",
        "missing token",
        "please run",
        "auth required",
        "not authenticated",
    )
    if any(marker in text for marker in login_markers):
        return False
    if returncode != 0:
        return False
    if "no production authority" in text or "deploy cli shadowed" in text:
        return False
    if cli == "railway" and ("logged in" in text or "email" in text or "@" in text):
        return True
    if cli == "vercel" and ("@" in text or "username" in text):
        return True
    return False


def _deploy_clis() -> dict:
    found = {name: bool(shutil.which(name)) for name in ("railway", "vercel")}
    attempts = []
    for cli in ("railway", "vercel"):
        path = shutil.which(cli)
        if not path:
            attempts.append(
                {
                    "cli": cli,
                    "present": False,
                    "authenticated": False,
                    "reason": "binary_absent",
                }
            )
            continue
        probe = subprocess.run(
            [path, "whoami"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        combined = (probe.stdout or "") + (probe.stderr or "")
        authenticated = _looks_authenticated(cli, probe.returncode, combined)
        attempts.append(
            {
                "cli": cli,
                "present": True,
                "returncode": probe.returncode,
                "authenticated": authenticated,
                "reason": (
                    "cli_present_but_unauthenticated"
                    if not authenticated
                    else "host_cli_login_visible"
                ),
            }
        )
    return {
        "which": found,
        "attempts": attempts,
        "deploy_reachable": any(item.get("authenticated") for item in attempts),
        "note": (
            "A host CLI binary on PATH is not deploy authority. "
            "Deploy is reachable only if that CLI is authenticated inside "
            "the constructed child environment."
        ),
    }


def main() -> int:
    authority_present = _present(PRODUCTION_AUTHORITY_NAMES)
    target_present = _present(["POWERUNITS_INTERNAL_EXECUTE_BASE_URL"])
    check_fn = _check_fn_closed()
    deploy = _deploy_clis()
    payload = {
        "process_authority_present": authority_present,
        "production_target_present": target_present,
        "PRODUCTION_DB_CREDENTIAL_PRESENT": any(
            name in authority_present for name in ("DATABASE_URL_TIMESCALE", "DATABASE_URL")
        ),
        "POWERUNITS_EXECUTE_SECRET_PRESENT": "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
        in authority_present,
        "DEPLOYMENT_CREDENTIAL_PRESENT": any(
            name.startswith("RAILWAY_") or name.startswith("VERCEL_") for name in authority_present
        ),
        "execute_check_fn": check_fn,
        "deploy": deploy,
        "PRODUCTION_WRITE_REACHABLE": bool(check_fn.get("available")),
        "PRODUCTION_DEPLOY_REACHABLE": bool(deploy.get("deploy_reachable")),
        "pass": (
            not authority_present
            and check_fn.get("fail_closed") is True
            and deploy.get("deploy_reachable") is False
        ),
    }
    print(json.dumps(payload))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
