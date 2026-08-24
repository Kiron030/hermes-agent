#!/usr/bin/env python3
"""In-container Developer-Hermes boundary probe.

Prints JSON to stdout. Never prints secret values. Cleans throwaway git
mutations before exit.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_A = Path("/workspace/hermes-agent")
REPO_B = Path("/workspace/EU-PP-Database")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/tmp/r5-hermes-home"))

NEGATIVE_PATHS = (
    "/mnt/c",
    "/mnt/d",
    "/mnt/w",
    "/mnt/host",
    "/host",
    "/host_mnt",
    "/run/desktop/mnt/host",
    "/run/desktop/mnt/host/c",
    "/run/desktop/mnt/host/d",
    "/run/desktop/mnt/host/w",
    "/run/desktop/mnt/host/w/Workbench",
    "/run/desktop/mnt/host/w/dataset",
    "/run/desktop/mnt/host/c/Users",
    "/run/desktop/mnt/host/c/Users/User",
    "/run/desktop/mnt/host/c/Users/User/.powerunits",
    "/run/desktop/mnt/host/c/Users/User/.powerunits/secrets",
    "/var/run/docker.sock",
    "/run/docker.sock",
)

AUTHORITY_ENV_NAMES = (
    "RAILWAY_TOKEN",
    "RAILWAY_API_TOKEN",
    "RAILWAY_SERVICE_ID",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_ENVIRONMENT_ID",
    "VERCEL_TOKEN",
    "VERCEL_ORG_ID",
    "VERCEL_PROJECT_ID",
    "VERCEL_DEPLOY_HOOK",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "DATABASE_URL",
    "DATABASE_URL_TIMESCALE",
    "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET",
    "POWERUNITS_INTERNAL_EXECUTE_BASE_URL",
    "SSH_AUTH_SOCK",
    "GIT_ASKPASS",
    "GITHUB_USER",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "r5-container-probe",
    "GIT_AUTHOR_EMAIL": "r5-container-probe@local",
    "GIT_COMMITTER_NAME": "r5-container-probe",
    "GIT_COMMITTER_EMAIL": "r5-container-probe@local",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/tmp/r5-hermes-home/.gitconfig-absent",
    "GIT_OPTIONAL_LOCKS": "0",
}

PROBE_RELATIVE = Path(".r5-container-boundary-probe")


def _run(
    argv: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 90,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def _which(name: str) -> str:
    path = shutil.which(name)
    return path or ""


def _tooling() -> dict[str, object]:
    python = _which("python3") or _which("python")
    uv = _which("uv")
    git = _which("git")
    hermes = _which("hermes")
    node = _which("node")
    versions = {}
    for label, argv in (
        ("python", [python or "python3", "--version"]),
        ("uv", [uv or "uv", "--version"]),
        ("git", [git or "git", "--version"]),
    ):
        if argv[0]:
            completed = _run(argv)
            versions[label] = (completed.stdout or completed.stderr).strip()
        else:
            versions[label] = ""
    import_ok = False
    import_error = ""
    try:
        import agent  # noqa: F401
        import hermes_cli  # noqa: F401

        import_ok = True
    except Exception as exc:  # pragma: no cover - empirical runtime path
        import_error = type(exc).__name__
    pytest_ok = False
    pytest_version = ""
    try:
        import pytest

        pytest_ok = True
        pytest_version = pytest.__version__
    except Exception:
        pytest_ok = False
    return {
        "PYTHON": "YES" if python else "NO",
        "UV": "YES" if uv else "NO",
        "GIT": "YES" if git else "NO",
        "HERMES_CLI": "YES" if hermes else "NO",
        "NODE": "YES" if node else "NO",
        "PYTEST": "YES" if pytest_ok else "NO",
        "UPSTREAM_HERMES_RUNTIME_PRESENT": "YES" if import_ok else "NO",
        "versions": versions,
        "pytest_version": pytest_version,
        "hermes_import_error": import_error,
        "shell": os.environ.get("SHELL") or "/bin/bash",
        "whoami": (_run(["whoami"]).stdout or "").strip(),
    }


def _rw_cycle(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {"readable": "NO", "writable": "NO", "create": "NO", "modify": "NO", "delete": "NO"}
    readable = "YES" if os.access(root, os.R_OK) else "NO"
    probe = root / PROBE_RELATIVE
    create = modify = delete = "NO"
    try:
        probe.write_text("R5_CONTAINER_PROBE_CREATE\n", encoding="utf-8")
        create = "YES" if probe.is_file() else "NO"
        probe.write_text("R5_CONTAINER_PROBE_MODIFY\n", encoding="utf-8")
        modify = "YES" if "MODIFY" in probe.read_text(encoding="utf-8") else "NO"
        probe.unlink()
        delete = "YES" if not probe.exists() else "NO"
    except OSError:
        pass
    writable = "YES" if create == "YES" and modify == "YES" and delete == "YES" else "NO"
    return {
        "readable": readable,
        "writable": writable,
        "create": create,
        "modify": modify,
        "delete": delete,
    }


def _git_cycle(root: Path) -> dict[str, str]:
    result = {
        "status": "NO",
        "diff": "NO",
        "local_commit": "NO",
        "cleaned": "NO",
    }
    if not (root / ".git").exists():
        return result
    lock = root / ".git" / "index.lock"
    if lock.exists():
        lock.unlink()
    before = _run(["git", "rev-parse", "HEAD"], cwd=root, env=GIT_ENV)
    before_sha = (before.stdout or "").strip()
    status = _run(["git", "status", "--porcelain"], cwd=root, env=GIT_ENV)
    result["status"] = "YES" if status.returncode == 0 else "NO"
    probe = root / PROBE_RELATIVE
    try:
        probe.write_text("R5_CONTAINER_GIT_PROBE\n", encoding="utf-8")
        unstaged = _run(["git", "status", "--porcelain", "--", str(PROBE_RELATIVE)], cwd=root, env=GIT_ENV)
        result["diff"] = "YES" if unstaged.returncode == 0 and (unstaged.stdout or "").strip() else "NO"
        add = _run(["git", "add", "--", str(PROBE_RELATIVE)], cwd=root, env=GIT_ENV)
        commit = _run(
            ["git", "commit", "--no-verify", "-m", "tmp: r5 container boundary probe"],
            cwd=root,
            env=GIT_ENV,
        )
        after = _run(["git", "rev-parse", "HEAD"], cwd=root, env=GIT_ENV)
        after_sha = (after.stdout or "").strip()
        result["local_commit"] = "YES" if commit.returncode == 0 and after_sha and after_sha != before_sha else "NO"
        if commit.returncode != 0:
            result["commit_error"] = (commit.stderr or commit.stdout).strip()[:240]
        if add.returncode != 0:
            result["add_error"] = (add.stderr or add.stdout).strip()[:240]
    except subprocess.TimeoutExpired as exc:
        result["timeout"] = " ".join(exc.cmd) if isinstance(exc.cmd, list) else str(exc.cmd)
    finally:
        if before_sha:
            reset = _run(["git", "reset", "--hard", before_sha], cwd=root, env=GIT_ENV)
            if reset.returncode != 0:
                result["reset_error"] = (reset.stderr or reset.stdout).strip()[:240]
        if probe.exists():
            probe.unlink()
        clean = _run(["git", "status", "--porcelain"], cwd=root, env=GIT_ENV)
        result["cleaned"] = "YES" if clean.returncode == 0 and not (clean.stdout or "").strip() else "NO"
    return result


def _pytest_subset() -> dict[str, str]:
    target = REPO_A / "tests" / "r5_developer_hermes" / "test_r5_retired_authority.py"
    if not target.is_file():
        return {"TEST_LOOP": "NO", "PYTEST": "NO", "reason": "target-missing"}
    uvx = shutil.which("uvx") or "uvx"
    completed = _run(
        [uvx, "--from", "pytest", "pytest", str(target), "-q", "--tb=no"],
        cwd=REPO_A,
        timeout=180,
    )
    return {
        "TEST_LOOP": "YES" if completed.returncode == 0 else "NO",
        "PYTEST": "YES" if completed.returncode == 0 else "NO",
        "runner": "uvx-pytest",
        "exit_code": str(completed.returncode),
        "summary": ((completed.stdout or completed.stderr).strip().splitlines() or [""])[-1][:240],
    }


def _negative_paths() -> dict[str, str]:
    found = [path for path in NEGATIVE_PATHS if Path(path).exists()]
    return {
        "reachable": found,
        "HOST_PROFILE_REACHABLE": "YES" if any("Users/User" in path for path in found) else "NO",
        "HOST_SECRET_ROOT_REACHABLE": "YES"
        if any(".powerunits/secrets" in path for path in found)
        else "NO",
        "WORKBENCH_REACHABLE": "YES" if any(path.endswith("Workbench") for path in found) else "NO",
        "DATASET_REACHABLE": "YES" if any(path.endswith("dataset") for path in found) else "NO",
        "DOCKER_SOCKET": "PRESENT" if any(path.endswith("docker.sock") for path in found) else "ABSENT",
    }


def _authority_env() -> dict[str, str]:
    present = [name for name in AUTHORITY_ENV_NAMES if os.environ.get(name)]
    return {
        "present_names": present,
        "RAILWAY_AUTH": "PRESENT" if any(name.startswith("RAILWAY_") for name in present) else "ABSENT",
        "VERCEL_AUTH": "PRESENT" if any(name.startswith("VERCEL_") for name in present) else "ABSENT",
        "GH_HOST_AUTH": "PRESENT" if any(name in {"GH_TOKEN", "GITHUB_TOKEN", "GITHUB_USER"} for name in present) else "ABSENT",
        "PRODUCTION_DB_AUTH": "PRESENT"
        if any(name in {"DATABASE_URL", "DATABASE_URL_TIMESCALE"} for name in present)
        else "ABSENT",
        "POWERUNITS_EXECUTE_AUTH": "PRESENT"
        if any("EXECUTE" in name or name == "POWERUNITS_INTERNAL_EXECUTE_BASE_URL" for name in present)
        else "ABSENT",
    }


def _home_authority() -> dict[str, str]:
    markers = {
        "HOST_SSH_KEYS": HERMES_HOME / ".ssh",
        "ssh_root": Path("/root/.ssh"),
        "ssh_home": Path.home() / ".ssh",
        "gitconfig_home": Path.home() / ".gitconfig",
        "railway": Path.home() / ".railway",
        "vercel": Path.home() / ".vercel",
        "config_gh": Path.home() / ".config" / "gh",
        "docker_config": Path.home() / ".docker",
    }
    existing = {key: str(path) for key, path in markers.items() if path.exists()}
    helper = _run(["git", "config", "--get", "credential.helper"], env=GIT_ENV)
    helper_value = (helper.stdout or "").strip()
    return {
        "HOME": str(Path.home()),
        "HERMES_HOME": str(HERMES_HOME),
        "existing_marker_names": sorted(existing),
        "HOST_SSH_KEYS": "PRESENT" if any("ssh" in key for key in existing) else "ABSENT",
        "HOST_GIT_CREDENTIAL_HELPER": "PRESENT" if helper_value else "ABSENT",
        "RAILWAY_CONFIG": "PRESENT" if "railway" in existing else "ABSENT",
        "VERCEL_CONFIG": "PRESENT" if "vercel" in existing else "ABSENT",
        "GH_CONFIG": "PRESENT" if "config_gh" in existing else "ABSENT",
        "DOCKER_CONFIG": "PRESENT" if "docker_config" in existing else "ABSENT",
    }


def _mount_table() -> list[str]:
    mounts = Path("/proc/self/mountinfo")
    if not mounts.is_file():
        return []
    return mounts.read_text(encoding="utf-8", errors="replace").splitlines()


def main() -> int:
    tooling = _tooling()
    repo_a = _rw_cycle(REPO_A)
    repo_b = _rw_cycle(REPO_B)
    git_a = _git_cycle(REPO_A)
    git_b = _git_cycle(REPO_B)
    payload = {
        "workspace_exists": Path("/workspace").is_dir(),
        "cwd": os.getcwd(),
        "tooling": tooling,
        "repo_a": repo_a,
        "repo_b": repo_b,
        "git_a": git_a,
        "git_b": git_b,
        "pytest": _pytest_subset(),
        "negative_paths": _negative_paths(),
        "authority_env": _authority_env(),
        "home_authority": _home_authority(),
        "mountinfo": _mount_table(),
        "model_auth_required_for_boundary_proof": "NO",
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
