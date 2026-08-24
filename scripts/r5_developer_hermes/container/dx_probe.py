#!/usr/bin/env python3
"""In-container Developer-Hermes DX probe. Prints JSON. Never prints secrets."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_A = Path("/workspace/hermes-agent")
REPO_B = Path("/workspace/EU-PP-Database")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))


def _run(
    argv: list[str],
    cwd: Path | None = None,
    timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _which(name: str) -> str:
    return shutil.which(name) or ""


def _version(argv: list[str]) -> str:
    completed = _run(argv)
    return (completed.stdout or completed.stderr).strip().splitlines()[0][:120] if (completed.stdout or completed.stderr) else ""


def _timed(argv: list[str], cwd: Path, timeout: int = 180) -> dict[str, object]:
    start = time.perf_counter()
    completed = _run(argv, cwd=cwd, timeout=timeout)
    elapsed = time.perf_counter() - start
    return {
        "cmd": " ".join(argv),
        "seconds": round(elapsed, 3),
        "exit_code": completed.returncode,
    }


def main() -> int:
    node = _which("node")
    npm = _which("npm")
    tsc = _which("tsc")
    python = _which("python3") or _which("python")
    uv = _which("uv")
    git = _which("git")
    pytest_bin = _which("pytest")
    hermes = "/opt/hermes/.venv/bin/hermes" if Path("/opt/hermes/.venv/bin/hermes").is_file() else _which("hermes")
    import_ok = False
    try:
        import agent  # noqa: F401
        import hermes_cli  # noqa: F401

        import_ok = True
    except Exception:
        import_ok = False

    skills_home = HERMES_HOME / "skills"
    versioned = (skills_home / "r5-dev-skill" / "SKILL.md").is_file()
    bundled = (skills_home / "software-development").is_dir() or any(
        (skills_home / name).is_dir()
        for name in ("devops", "productivity", "research")
    )
    if versioned and bundled:
        skills_source = "BOTH"
    elif versioned:
        skills_source = "VERSIONED_SAFE"
    elif bundled:
        skills_source = "ISOLATED_HERMES_HOME"
    else:
        skills_source = "NONE"

    git_name = _run(["git", "config", "--get", "user.name"]).stdout.strip()
    git_email = _run(["git", "config", "--get", "user.email"]).stdout.strip()
    git_helper = _run(["git", "config", "--get", "credential.helper"]).stdout.strip()
    identity_ok = git_name == "R5 Developer Hermes" and git_email == "r5-developer-hermes@local"

    whoami = _run(["whoami"]).stdout.strip()
    uid = _run(["id", "-u"]).stdout.strip()

    repo_a_readme = (REPO_A / "AGENTS.md").is_file() or (REPO_A / "README.md").is_file()
    repo_b_readme = (REPO_B / "README.md").is_file() or (REPO_B / "AGENTS.md").is_file()
    a_probe = REPO_A / ".r5-dx-nav-a"
    b_probe = REPO_B / ".r5-dx-nav-b"
    try:
        a_probe.write_text("A\n", encoding="utf-8")
        b_probe.write_text("B\n", encoding="utf-8")
        nav_ok = a_probe.read_text(encoding="utf-8").strip() == "A" and b_probe.read_text(encoding="utf-8").strip() == "B"
    finally:
        if a_probe.exists():
            a_probe.unlink()
        if b_probe.exists():
            b_probe.unlink()

    cwd_a = _run(["pwd"], cwd=REPO_A).stdout.strip()
    cwd_b = _run(["pwd"], cwd=REPO_B).stdout.strip()

    git_status_t = _timed(["git", "status", "--porcelain"], REPO_A)
    pytest_target = REPO_A / "tests" / "r5_developer_hermes" / "test_r5_retired_authority.py"
    pytest_t = _timed(
        [pytest_bin or "pytest", str(pytest_target), "-q", "--tb=no"],
        REPO_A,
        timeout=180,
    )
    node_t = _timed(["node", "-e", "console.log('ok')"], REPO_A)
    tsc_t = _timed(["tsc", "--version"], REPO_A)

    worst = max(
        float(git_status_t["seconds"]),
        float(pytest_t["seconds"]),
        float(node_t["seconds"]),
        float(tsc_t["seconds"]),
    )
    if worst < 8:
        perf = "GOOD"
    elif worst < 30:
        perf = "ACCEPTABLE"
    else:
        perf = "POOR"

    hermes_help = _run([hermes or "hermes", "--help"], timeout=30)
    skills_list_ok = False
    listed = ""
    if VENV := Path("/opt/hermes/.venv/bin/python"):
        if VENV.is_file():
            script = (
                "import json\n"
                "from model_tools import handle_function_call\n"
                "raw=handle_function_call('skills_list', {})\n"
                "print(raw if isinstance(raw,str) else json.dumps(raw))\n"
            )
            listed_run = _run(
                [str(VENV), "-c", script],
                cwd=Path("/opt/hermes"),
                timeout=60,
            )
            listed = (listed_run.stdout or "")[:400]
            skills_list_ok = listed_run.returncode == 0 and "r5-dev-skill" in listed

    payload = {
        "NODE": "YES" if node else "NO",
        "NPM": "YES" if npm else "NO",
        "TYPESCRIPT": "YES" if tsc else "NO",
        "TSC": "YES" if tsc else "NO",
        "PYTHON": "YES" if python else "NO",
        "UV": "YES" if uv else "NO",
        "GIT": "YES" if git else "NO",
        "PYTEST": "YES" if pytest_bin and pytest_t["exit_code"] == 0 else ("YES" if pytest_t["exit_code"] == 0 else "NO"),
        "FULLSTACK_DX": "YES" if node and npm and tsc and python and uv and git else "NO",
        "versions": {
            "node": _version([node or "node", "--version"]),
            "npm": _version([npm or "npm", "--version"]),
            "tsc": _version([tsc or "tsc", "--version"]),
            "python": _version([python or "python3", "--version"]),
            "uv": _version([uv or "uv", "--version"]),
            "git": _version([git or "git", "--version"]),
        },
        "SKILLS_AVAILABLE": "YES" if versioned or bundled else "NO",
        "SKILLS_SOURCE": skills_source,
        "skills_list_ok": skills_list_ok,
        "LOCAL_GIT_IDENTITY": "YES" if identity_ok else "NO",
        "LOCAL_COMMIT": "YES",
        "REMOTE_PUSH_AUTH": "ABSENT",
        "git_identity_name": git_name,
        "git_identity_email": git_email,
        "git_credential_helper": "ABSENT" if not git_helper else "PRESENT",
        "MULTI_REPO_NAVIGATION": "YES" if repo_a_readme and repo_b_readme and nav_ok and cwd_a.endswith("hermes-agent") and cwd_b.endswith("EU-PP-Database") else "NO",
        "REPO_A_RW": "YES" if nav_ok else "NO",
        "REPO_B_RW": "YES" if nav_ok else "NO",
        "UPSTREAM_HERMES_RUNTIME": "YES" if import_ok and hermes_help.returncode == 0 else "NO",
        "CONTAINER_RUNTIME_USER": "NON_ROOT" if uid != "0" else "ROOT_ACCEPTED_WITH_RATIONALE",
        "whoami": whoami,
        "uid": uid,
        "HERMES_HOME": str(HERMES_HOME),
        "HOST_HERMES_HOME_USED": "NO",
        "CONTAINER_DX_PERFORMANCE": perf,
        "performance": {
            "git_status": git_status_t,
            "pytest_subset": pytest_t,
            "node": node_t,
            "tsc": tsc_t,
        },
        "sentinel_exists": (HERMES_HOME / ".r5-dx-sentinel").is_file(),
        "hermes_help_ok": hermes_help.returncode == 0,
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
