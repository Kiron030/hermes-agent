#!/usr/bin/env python3
"""Prove production write/deploy authority is absent in the developer process.

Prints one JSON object. Never prints secret values.
"""

from __future__ import annotations

import json
import os
import subprocess


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


def _stub_dir() -> str:
    """The R5 deploy-CLI stub directory, which must never be measured as a CLI."""
    home = os.environ.get("HOME") or ""
    return os.path.normcase(os.path.join(home, "bin")) if home else ""


def _resolve_real_cli(cli: str) -> list[str]:
    """Find genuine CLI binaries, deliberately ignoring the R5 PATH stubs.

    The previous implementation called ``shutil.which`` while the stub directory
    was prepended to PATH, so it measured the stub's own exit code and concluded
    "unauthenticated" no matter what the host CLI could do. A PATH shadow is not
    a boundary, so the proof must resolve past it.
    """
    stub = _stub_dir()
    found: list[str] = []
    extensions = os.environ.get("PATHEXT", ".EXE;.CMD;.BAT").split(os.pathsep)
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        if stub and os.path.normcase(os.path.abspath(directory)) == stub:
            continue
        for suffix in [""] + extensions:
            candidate = os.path.join(directory, f"{cli}{suffix.lower()}")
            if os.path.isfile(candidate) and candidate not in found:
                found.append(candidate)
    return found


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
    found = {name: _resolve_real_cli(name) for name in ("railway", "vercel")}
    attempts = []
    for cli in ("railway", "vercel"):
        paths = found[cli]
        if not paths:
            attempts.append(
                {
                    "cli": cli,
                    "present": False,
                    "authenticated": False,
                    "reason": "binary_not_reachable_by_this_principal",
                }
            )
            continue
        for path in paths:
            try:
                probe = subprocess.run(
                    [path, "whoami"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except OSError as exc:
                attempts.append(
                    {
                        "cli": cli,
                        "path": path,
                        "present": True,
                        "authenticated": False,
                        "reason": f"not_executable:{type(exc).__name__}",
                    }
                )
                continue
            combined = (probe.stdout or "") + (probe.stderr or "")
            authenticated = _looks_authenticated(cli, probe.returncode, combined)
            attempts.append(
                {
                    "cli": cli,
                    "path": path,
                    "present": True,
                    "returncode": probe.returncode,
                    "authenticated": authenticated,
                    "reason": (
                        "host_cli_login_visible"
                        if authenticated
                        else "reachable_but_unauthenticated"
                    ),
                }
            )
    return {
        "resolved_paths": found,
        "attempts": attempts,
        "deploy_reachable": any(item.get("authenticated") for item in attempts),
        "PATH_STUB_SECURITY_ROLE": "NONE",
        "note": (
            "Resolution deliberately skips the R5 stub directory. A PATH shadow "
            "is defeated by any absolute path, so measuring the stub would only "
            "prove that the stub answers. Deploy authority is a property of the "
            "OS principal: it is absent when the principal cannot execute or "
            "authenticate the real CLI."
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
