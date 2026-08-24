#!/usr/bin/env python3
"""R5 Powerful Developer Hermes harness.

A separate modern-Hermes developer instance that is powerful in the mounted
workspace and possesses no production authority. Isolation is a constructed
child-process environment — not in-process env redaction.

    python scripts/r5_developer_hermes/harness.py <command>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PIN_PATH = HERE / "pin.json"

PROOF_ROOT_ENV = "HERMES_R5_PROOF_ROOT"
REPO_B_ENV = "HERMES_R5_REPO_B_ROOT"
UPSTREAM_SRC_ENV = "HERMES_R5_UPSTREAM_SRC"
WEB_KEY_ENV = "HERMES_R5_WEB_API_KEY"
MODEL_KEY_ENV = "HERMES_R5_MODEL_API_KEY"
R1_MODEL_KEY_ENV = "HERMES_R1_MODEL_API_KEY"

SAFE_ENV_PASSTHROUGH = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERNAME",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "LANG",
    "LC_ALL",
    "TZ",
    "TERM",
    "USER",
    "LOGNAME",
    "SHELL",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "GIT_SSL_CAINFO",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)

# The deploy-CLI stubs are a convenience nudge, not a security control.
# The independent isolation review showed a PATH shadow is defeated by an
# absolute path, a shell indirection or a subprocess call, so no part of the
# authority proof may depend on them. Keeping them is a UX choice only.
DEPLOY_CLI_STUB_SECURITY_CONTROL = False

PRINCIPAL_ISOLATION_ARTIFACT = "principal_isolation.json"
CONTAINER_ISOLATION_ARTIFACT = "container_boundary.json"


def load_pin() -> dict[str, Any]:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def proof_root() -> Path:
    override = os.environ.get(PROOF_ROOT_ENV, "").strip()
    return Path(override) if override else REPO_ROOT / ".r5-dev"


def developer_home() -> Path:
    return proof_root() / "home"


def process_home() -> Path:
    """Synthetic HOME so host CLI logins (Railway/Vercel) cannot leak in."""
    return proof_root() / "process-home"


def scratch_workspace() -> Path:
    return proof_root() / "scratch" / "git-probe"


def artifacts_dir() -> Path:
    path = proof_root() / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def production_authority_names(pin: dict[str, Any] | None = None) -> tuple[str, ...]:
    data = pin or load_pin()
    return tuple(data["production_authority_names"])


def production_target_names(pin: dict[str, Any] | None = None) -> tuple[str, ...]:
    data = pin or load_pin()
    return tuple(data.get("production_target_names") or ())


def blocked_names(pin: dict[str, Any] | None = None) -> set[str]:
    data = pin or load_pin()
    return set(production_authority_names(data)) | set(production_target_names(data))


def repo_a_root() -> Path:
    return REPO_ROOT


def repo_b_root() -> Path | None:
    override = os.environ.get(REPO_B_ENV, "").strip()
    if override:
        path = Path(override)
        return path if path.is_dir() else None
    sibling = REPO_ROOT.parent / "EU-PP-Database"
    return sibling if sibling.is_dir() else None


def upstream_src() -> Path:
    override = os.environ.get(UPSTREAM_SRC_ENV, "").strip()
    if override:
        return Path(override)
    local = proof_root() / "upstream-src"
    if (local / "model_tools.py").is_file():
        return local
    r1 = REPO_ROOT / ".r1-proof" / "upstream-src"
    if (r1 / "model_tools.py").is_file():
        return r1
    return local


def _path_with_deploy_cli_stubs(raw_path: str, isolated_home: Path) -> str:
    """Put a visible "don't deploy from here" nudge in front of the deploy CLIs.

    SECURITY_CONTROL = NO. This changes what ``railway`` resolves to for a
    careless PATH lookup and nothing else. It does not remove the host login,
    it does not survive an absolute path, and the stub files themselves sit in
    a directory the developer instance can write to. Isolation comes from the
    OS principal (see :func:`os_principal_status`), never from this function.
    """
    stub_dir = isolated_home / "bin"
    stub_dir.mkdir(parents=True, exist_ok=True)
    unix = (
        "#!/bin/sh\n"
        "echo 'R5 developer instance: deploy CLI shadowed (no production authority)' >&2\n"
        "exit 1\n"
    )
    windows = (
        "@echo off\r\n"
        "echo R5 developer instance: deploy CLI shadowed (no production authority)\r\n"
        "exit /b 1\r\n"
    )
    for name in ("railway", "vercel"):
        script = stub_dir / name
        script.write_text(unix, encoding="utf-8")
        try:
            script.chmod(0o755)
        except OSError:
            pass
        (stub_dir / f"{name}.cmd").write_text(windows, encoding="utf-8")
        (stub_dir / f"{name}.bat").write_text(windows, encoding="utf-8")
    return str(stub_dir) + os.pathsep + raw_path


def isolated_env(
    hermes_home: Path,
    *,
    extra: dict[str, str] | None = None,
    include_web_key: bool = False,
) -> dict[str, str]:
    """Build a child env by constructing it. Production names are never copied."""
    pin = load_pin()
    blocked = blocked_names(pin)
    env: dict[str, str] = {}
    for key in SAFE_ENV_PASSTHROUGH:
        value = os.environ.get(key)
        if value is not None and key not in blocked:
            env[key] = value
    env["HERMES_HOME"] = str(hermes_home)
    env["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["HERMES_R5_CONTEXT"] = "developer"
    isolated_home = Path(hermes_home).resolve().parent / "process-home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(isolated_home)
    env["USERPROFILE"] = str(isolated_home)
    drive, tail = os.path.splitdrive(str(isolated_home))
    if drive:
        env["HOMEDRIVE"] = drive
        env["HOMEPATH"] = tail or "\\"
    env["PATH"] = _path_with_deploy_cli_stubs(env.get("PATH", ""), isolated_home)
    if include_web_key:
        web_key = os.environ.get(WEB_KEY_ENV, "").strip()
        if web_key:
            env["TAVILY_API_KEY"] = web_key
    if extra:
        for key, value in extra.items():
            if key in blocked:
                raise ValueError(f"refusing to inject production-authority name {key}")
            env[key] = value
    leaked = sorted(name for name in blocked if env.get(name))
    if leaked:
        raise RuntimeError(f"isolated env leaked production-authority names: {leaked}")
    return env


def assert_authority_absent(env: dict[str, str], pin: dict[str, Any] | None = None) -> dict[str, Any]:
    names = production_authority_names(pin)
    present = [name for name in names if env.get(name)]
    return {
        "asserted_absent": list(names),
        "present": present,
        "pass": not present,
    }


def _developer_config() -> str:
    pin = load_pin()
    enabled = "\n".join(f"    - {name}" for name in pin["developer_enabled_toolsets"])
    deferred = "\n".join(f"    - {name}" for name in pin["developer_deferred_toolsets"])
    return (
        "security:\n"
        "  allow_lazy_installs: false\n"
        "agent:\n"
        f"  disabled_toolsets:\n{deferred}\n"
        "platform_toolsets:\n"
        "  cli:\n"
        f"{enabled}\n"
        "approvals:\n"
        "  mode: off\n"
        "  cron_mode: deny\n"
    )


def write_developer_home() -> Path:
    home = developer_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "sessions").mkdir(exist_ok=True)
    (home / "config.yaml").write_text(_developer_config(), encoding="utf-8")
    (home / "SOUL.md").write_text(
        "# R5 developer Hermes\n\n"
        "POWERFUL_IN_WORKSPACE. NOT_POWERFUL_IN_PRODUCTION.\n"
        "Ordinary workspace edits do not require micro-approvals.\n"
        "Do not deploy. Do not push to main. Do not merge.\n",
        encoding="utf-8",
    )
    skill_dir = home / "skills" / "r5-dev-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: r5-dev-skill\n"
        "description: Local isolated R5 developer fixture. Not networked.\n"
        "---\n\n"
        "Harmless developer-instance skill used only for skills_list / skill_view.\n",
        encoding="utf-8",
    )
    return home


def prepare_scratch() -> Path:
    scratch = scratch_workspace()
    scratch.mkdir(parents=True, exist_ok=True)
    git_dir = scratch / ".git"
    if git_dir.is_dir():
        _git(["reset", "--hard"], cwd=scratch)
        _git(["clean", "-fd"], cwd=scratch)
    else:
        _git(["init"], cwd=scratch)
        _git(["config", "user.email", "r5-developer@localhost"], cwd=scratch)
        _git(["config", "user.name", "R5 Developer Hermes"], cwd=scratch)
    (scratch / "README.md").write_text(
        "R5 scratch git workspace. Not production.\n",
        encoding="utf-8",
    )
    (scratch / "r5_add.py").write_text(
        "def add(a, b):\n    return 0\n",
        encoding="utf-8",
    )
    status = _git(["status", "--porcelain"], cwd=scratch)
    if status.strip():
        _git(["add", "README.md", "r5_add.py"], cwd=scratch)
        _git(["commit", "-m", "R5 scratch baseline"], cwd=scratch)
    return scratch


def prepare_runtime() -> dict[str, Any]:
    pin = load_pin()
    src = upstream_src()
    expected = pin["upstream_release_sha"]
    if src.exists() and (src / "model_tools.py").is_file():
        observed = _git(["rev-parse", "HEAD"], cwd=src).strip()
        if observed != expected:
            raise RuntimeError(f"upstream source at {src} is {observed}, expected {expected}")
        python = _upstream_python(src)
        return {
            "path": str(src),
            "sha": observed,
            "reused": True,
            "python": str(python),
        }

    dest = proof_root() / "upstream-src"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(["fetch", "upstream", expected], cwd=REPO_ROOT)
    _git(["worktree", "add", "--detach", str(dest), expected], cwd=REPO_ROOT)
    completed = subprocess.run(
        ["uv", "sync", "--frozen"],
        cwd=dest,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "uv sync --frozen failed:\n"
            f"{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}"
        )
    return {
        "path": str(dest),
        "sha": expected,
        "reused": False,
        "python": str(_upstream_python(dest)),
    }


def os_principal_status() -> dict[str, Any]:
    """Identify the OS security principal this process actually runs as.

    The constructed environment is not a boundary; the logon token is. On
    Windows that means the account SID, which no environment variable can
    change.
    """
    if os.name != "nt":
        return {
            "platform": os.name,
            "principal_id": str(os.getuid()),  # type: ignore[attr-defined]  # windows-footgun: ok — POSIX branch behind os.name != "nt"
            "is_administrator": os.getuid() == 0,  # type: ignore[attr-defined]  # windows-footgun: ok — POSIX branch behind os.name != "nt"
        }
    account = sid = None
    completed = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        parts = [field.strip('" ') for field in completed.stdout.strip().split('","')]
        if len(parts) >= 2:
            account, sid = parts[0].strip('"'), parts[1].strip('"')
    groups = subprocess.run(
        ["whoami.exe", "/groups", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "platform": "nt",
        "account": account,
        "principal_id": sid,
        "is_administrator": "S-1-5-32-544" in (groups.stdout or ""),
    }


def principal_isolation_evidence() -> dict[str, Any] | None:
    """Load the Phase C proof produced under the dedicated principal, if any."""
    path = artifacts_dir() / PRINCIPAL_ISOLATION_ARTIFACT
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def container_boundary_evidence() -> dict[str, Any] | None:
    """Load the empirical Linux-container boundary proof, if any."""
    path = artifacts_dir() / CONTAINER_ISOLATION_ARTIFACT
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def isolation_boundary_status() -> dict[str, Any]:
    """Describe the boundary honestly, and fail closed when it is unproven."""
    docker = shutil.which("docker")
    principal = os_principal_status()
    container = container_boundary_evidence()
    evidence = principal_isolation_evidence()
    container_proven = bool(
        container
        and container.get("ISOLATION_BOUNDARY") == "CONTAINER"
        and container.get("ISOLATION_ACCEPTANCE") == "PASS"
    )
    principal_proven = bool(
        evidence
        and evidence.get("CHILD_OS_PRINCIPAL") == "SEPARATE_PRINCIPAL"
        and evidence.get("ISOLATION_ACCEPTANCE") == "PASS"
    )
    if container_proven:
        boundary = "CONTAINER"
    elif principal_proven:
        boundary = "DEDICATED_OS_PRINCIPAL"
    else:
        boundary = "PROCESS_CONSTRUCTED_ENV"
    return {
        "ISOLATION_BOUNDARY": boundary,
        "BOUNDARY_SUFFICIENT": "YES" if container_proven or principal_proven else "NO",
        "PATH_STUB_SECURITY_ROLE": "NONE",
        "workspace_acl_script_role": "FALLBACK_ONLY",
        "docker_binary": docker,
        "docker_available": bool(docker),
        "container_used": container_proven,
        "container_evidence_present": container is not None,
        "os_principal": principal,
        "principal_evidence_present": evidence is not None,
        "note": (
            "The canonical R5 isolation boundary is a Linux container with an "
            "explicit two-repository bind-mount allowlist. A constructed child "
            "environment is not an authority boundary. The dedicated Windows "
            "principal and scope-workspace-authority.ps1 remain defense in "
            "depth / FALLBACK_ONLY."
        ),
    }


def isolate_env() -> dict[str, Any]:
    home = write_developer_home()
    scratch = prepare_scratch()
    env = isolated_env(home)
    assertion = assert_authority_absent(env)
    child = _run_child_env_dump(env)
    parent_has_blocked = any(os.environ.get(name) for name in blocked_names())
    result = {
        "homes": {"developer": str(home)},
        "scratch": str(scratch),
        "workspace_repo_a": str(repo_a_root()),
        "workspace_repo_b": str(repo_b_root()) if repo_b_root() else None,
        "production_credential_assertions": assertion,
        "child_env_authority_present": child["present"],
        "parent_may_contain_blocked_names": parent_has_blocked,
        "child_did_not_inherit_blocked_names": not child["present"],
        "isolation_boundary": isolation_boundary_status(),
        "os_principal": os_principal_status(),
        "approvals_mode": "off",
        # Env hygiene only. This says nothing about authority: see
        # isolation_boundary["BOUNDARY_SUFFICIENT"] for that.
        "pass": assertion["pass"] and not child["present"],
    }
    write_json(artifacts_dir() / "isolate_env.json", result)
    return result


def _run_child_env_dump(env: dict[str, str]) -> dict[str, Any]:
    names = list(blocked_names())
    script = (
        "import json,os,sys\n"
        "names=json.loads(sys.argv[1])\n"
        "print(json.dumps([n for n in names if os.environ.get(n)]))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, json.dumps(names)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"child env dump failed: {completed.stderr[-2000:]}")
    present = json.loads(completed.stdout.strip().splitlines()[-1])
    return {"present": present, "returncode": completed.returncode}


def boot_smoke() -> dict[str, Any]:
    src = _require_source()
    python = _upstream_python(src)
    write_developer_home()
    env = isolated_env(developer_home())
    assertion = assert_authority_absent(env)
    completed = subprocess.run(
        [str(python), "-c", "import hermes_cli, model_tools, toolsets; print('boot-ok')"],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    hermes = python.with_name("hermes.exe" if python.suffix == ".exe" else "hermes")
    help_cmd = [str(hermes), "--help"] if hermes.exists() else [
        str(python),
        "-c",
        "from hermes_cli.main import main; import sys; sys.argv=['hermes','--help']; main()",
    ]
    help_run = subprocess.run(
        help_cmd,
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    result = {
        "import_returncode": completed.returncode,
        "import_stdout": completed.stdout.strip(),
        "help_returncode": help_run.returncode,
        "help_has_usage": "Usage" in help_run.stdout or "usage" in help_run.stdout.lower(),
        "production_credential_assertions": assertion,
        "LISTEN_ADDRESS": "none",
        "PUBLIC_INGRESS": "NO",
        "pass": completed.returncode == 0 and help_run.returncode == 0 and assertion["pass"],
    }
    write_json(artifacts_dir() / "boot_smoke.json", result)
    if not result["pass"]:
        raise RuntimeError(
            f"boot smoke failed: {completed.stderr[-2000:]}\n{help_run.stderr[-2000:]}"
        )
    return result


def enumerate_tools() -> dict[str, Any]:
    pin = load_pin()
    src = _require_source()
    python = _upstream_python(src)
    write_developer_home()
    env = isolated_env(developer_home())
    enabled = pin["developer_enabled_toolsets"]
    disabled = pin["developer_deferred_toolsets"]
    script = (
        "import json,sys\n"
        "from model_tools import get_tool_definitions\n"
        "enabled=json.loads(sys.argv[1])\n"
        "disabled=json.loads(sys.argv[2]) or None\n"
        "defs=get_tool_definitions(enabled_toolsets=enabled, disabled_toolsets=disabled, quiet_mode=True)\n"
        "print(json.dumps(sorted(d['function']['name'] for d in defs)))\n"
    )
    completed = subprocess.run(
        [str(python), "-c", script, json.dumps(enabled), json.dumps(disabled)],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"enumerate-tools failed: {completed.stderr[-4000:]}")
    names = json.loads(completed.stdout.strip().splitlines()[-1])
    result = {
        "enabled_toolsets": enabled,
        "disabled_toolsets": disabled,
        "callable_tools": names,
        "inspectable": True,
        "has_filesystem": {"read_file", "write_file"} <= set(names),
        "has_terminal": "terminal" in names,
        "has_skills": {"skills_list", "skill_view"} <= set(names),
        "has_operator_execute": pin["fail_closed_execute_tool"] in names,
    }
    write_json(artifacts_dir() / "tools_developer.json", result)
    return result


def sqlite_probe() -> dict[str, Any]:
    src = _require_source()
    python = _upstream_python(src)
    env = isolated_env(write_developer_home())
    completed = subprocess.run(
        [str(python), str(HERE / "sqlite_probe.py")],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"sqlite probe failed: {completed.stderr[-2000:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    write_json(artifacts_dir() / "sqlite_probe.json", payload)
    return payload


def authority_proof() -> dict[str, Any]:
    write_developer_home()
    env = isolated_env(developer_home())
    assertion = assert_authority_absent(env)

    fork_run = subprocess.run(
        [sys.executable, str(HERE / "authority_failclosed.py")],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if not fork_run.stdout.strip():
        raise RuntimeError(f"authority fail-closed produced no JSON: {fork_run.stderr[-2000:]}")
    fork_payload = json.loads(fork_run.stdout.strip().splitlines()[-1])

    src = _require_source()
    python = _upstream_python(src)
    modern_script = (
        "import json\n"
        "from model_tools import handle_function_call\n"
        "raw=handle_function_call('execute_powerunits_option_d_bounded_slice', "
        "{'country_code':'DE','version':'v1'})\n"
        "print(raw if isinstance(raw,str) else json.dumps(raw))\n"
    )
    modern_run = subprocess.run(
        [str(python), "-c", modern_script],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    modern_text = (modern_run.stdout or "") + (modern_run.stderr or "")
    modern_unreachable = "unknown tool" in modern_text.lower()

    # Deployment reachability is a property of the OS principal, not of the
    # environment. Absence of RAILWAY_TOKEN says nothing while the process still
    # runs as a user whose file-backed Railway session is discoverable, so this
    # value is sourced from the Phase C principal proof and defaults to unproven.
    evidence = principal_isolation_evidence()
    boundary = isolation_boundary_status()
    deploy_reachable = (
        evidence.get("PRODUCTION_DEPLOY_REACHABLE") if evidence else "NOT_PROVEN"
    )
    secret_files_reachable = (
        evidence.get("PRODUCTION_SECRET_FILES_REACHABLE") if evidence else "NOT_PROVEN"
    )

    result = {
        "isolation": assertion,
        "fork_fail_closed": fork_payload,
        "modern_dispatch_excerpt": modern_text[-800:],
        "modern_execute_unreachable": modern_unreachable,
        "isolation_boundary": boundary,
        "principal_evidence": evidence,
        "PRODUCTION_DB_CREDENTIAL_PRESENT": fork_payload.get(
            "PRODUCTION_DB_CREDENTIAL_PRESENT"
        ),
        "POWERUNITS_EXECUTE_SECRET_PRESENT": fork_payload.get(
            "POWERUNITS_EXECUTE_SECRET_PRESENT"
        ),
        "DEPLOYMENT_CREDENTIAL_PRESENT": fork_payload.get("DEPLOYMENT_CREDENTIAL_PRESENT"),
        "PRODUCTION_WRITE_REACHABLE": bool(fork_payload.get("PRODUCTION_WRITE_REACHABLE"))
        or not modern_unreachable,
        "PRODUCTION_DEPLOY_REACHABLE": deploy_reachable,
        "PRODUCTION_SECRET_FILES_REACHABLE": secret_files_reachable,
        "PATH_STUB_SECURITY_ROLE": "NONE",
        "pass": (
            assertion["pass"]
            and fork_payload.get("pass") is True
            and modern_unreachable
            and deploy_reachable == "NO"
            and secret_files_reachable == "NO"
        ),
    }
    write_json(artifacts_dir() / "authority_proof.json", result)
    return result


def developer_probes() -> dict[str, Any]:
    src = _require_source()
    python = _upstream_python(src)
    write_developer_home()
    scratch = prepare_scratch()
    repo_b = repo_b_root()
    web_key = os.environ.get(WEB_KEY_ENV, "").strip()
    spec = {
        "repo_a": str(repo_a_root()),
        "repo_b": str(repo_b) if repo_b else None,
        "scratch": str(scratch),
        "python": str(python),
        "skill_name": "r5-dev-skill",
        "web_enabled": bool(web_key),
    }
    spec_path = artifacts_dir() / "probe_spec.json"
    write_json(spec_path, spec)
    env = isolated_env(
        developer_home(),
        extra={"PWD": str(scratch)},
        include_web_key=True,
    )
    completed = subprocess.run(
        [str(python), str(HERE / "dispatch_probes.py"), str(spec_path)],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(
            f"developer probes failed: {completed.stderr[-4000:]}\n{completed.stdout[-2000:]}"
        )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    payload["workspace_repo_a_rw"] = payload.get("PROBE_A_CODE_EXPLORATION") == "PASS"
    payload["workspace_repo_b_rw"] = bool(repo_b) and payload.get("PROBE_A_CODE_EXPLORATION") == "PASS"
    payload["WEB"] = payload.get("PROBE_F_WEB")
    if repo_b:
        leftover = repo_b / ".r5-developer-hermes-scratch"
        if leftover.exists():
            shutil.rmtree(leftover, ignore_errors=True)
    write_json(artifacts_dir() / "developer_probes.json", payload)
    return payload


def capability_inventory() -> dict[str, Any]:
    tools = enumerate_tools()
    names = set(tools["callable_tools"])
    probes = {}
    probe_path = artifacts_dir() / "developer_probes.json"
    if probe_path.is_file():
        probes = json.loads(probe_path.read_text(encoding="utf-8"))

    def status(proven: bool, available: bool, deferred: bool = False) -> str:
        if proven:
            return "PROVEN_NOW"
        if deferred:
            return "DEFERRED"
        if available:
            return "AVAILABLE_NOT_YET_PROVEN"
        return "DEFERRED"

    inventory = {
        "filesystem": status(
            probes.get("PROBE_A_CODE_EXPLORATION") == "PASS"
            and probes.get("PROBE_B_EDIT") == "PASS",
            {"read_file", "write_file"} <= names,
        ),
        "terminal": status(probes.get("PROBE_C_TEST_LOOP") == "PASS", "terminal" in names),
        "git": status(probes.get("PROBE_D_GIT") == "PASS", "terminal" in names),
        "tests": status(probes.get("PROBE_C_TEST_LOOP") == "PASS", "terminal" in names),
        "web": (
            "PROVEN_NOW"
            if probes.get("PROBE_F_WEB") == "PASS"
            else "AVAILABLE_NOT_YET_PROVEN"
            if "web_search" in names
            else "DEFERRED"
        ),
        "browser": status(False, "browser_navigate" in names or "browser" in names, deferred=True),
        "skills": status(probes.get("PROBE_E_SKILLS") == "PASS", "skills_list" in names),
        "delegation": status(False, "delegate_task" in names, deferred=True),
        "profiles": "AVAILABLE_NOT_YET_PROVEN",
        "bot_mode": "DEFERRED",
        "observability": "AVAILABLE_NOT_YET_PROVEN",
        "callable_tools": tools["callable_tools"],
    }
    if probes.get("PROBE_F_WEB") == "NOT_RUN_CREDENTIAL_REQUIRED":
        inventory["web"] = "AVAILABLE_NOT_YET_PROVEN"
        inventory["web_note"] = "WEB_PROBE = NOT_RUN_CREDENTIAL_REQUIRED"
    write_json(artifacts_dir() / "capability_inventory.json", inventory)
    return inventory


def deletion_has_zero_production_effect() -> dict[str, Any]:
    """The developer instance is local scratch. Deleting it cannot reach production."""
    root = proof_root()
    return {
        "developer_root": str(root),
        "is_local_scratch": root == REPO_ROOT / ".r5-dev" or os.environ.get(PROOF_ROOT_ENV),
        "contains_production_secrets_file": (root / ".env").exists(),
        "rollback": "Delete .r5-dev/ (or HERMES_R5_PROOF_ROOT). Production is untouched.",
        "pass": not (root / ".env").exists(),
    }


def preflight() -> dict[str, Any]:
    pin = load_pin()
    r1_docs = REPO_ROOT / "docs" / "architecture" / "hermes_r1_proof_report_v1.md"
    r1_present = r1_docs.is_file() and "GATE_1_STATUS = CLOSED" in r1_docs.read_text(
        encoding="utf-8"
    )
    expected = [
        "scripts/r5_developer_hermes/harness.py",
        "scripts/r5_developer_hermes/dispatch_probes.py",
        "scripts/r5_developer_hermes/authority_failclosed.py",
        "scripts/r5_developer_hermes/sqlite_probe.py",
        "scripts/r5_developer_hermes/pin.json",
        "scripts/r5_developer_hermes/principal/preflight-principal.ps1",
        "scripts/r5_developer_hermes/principal/provision-principal.ps1",
        "scripts/r5_developer_hermes/principal/launch-developer-hermes.ps1",
        "scripts/r5_developer_hermes/principal/verify-principal-isolation.ps1",
        "tests/r5_developer_hermes/test_r5_contracts.py",
        "tests/r5_developer_hermes/test_r5_runtime.py",
        "docs/architecture/hermes_r5_developer_hermes_v1.md",
        "docs/architecture/hermes_r5_proof_report_v1.md",
    ]
    missing = [rel for rel in expected if not (REPO_ROOT / rel).is_file()]
    result = {
        "SLICE": "R5",
        "BASE_SHA": _git(["rev-parse", "HEAD"], cwd=REPO_ROOT).strip(),
        "GATE_1_CLOSED": r1_present,
        "R1_PRESENT": r1_present,
        "SCOPE_CONFIRMED": missing == [],
        "BLOCKERS": [] if not missing else [f"missing:{path}" for path in missing],
        "EXPECTED_FILES": expected,
        "pin": {
            "release": pin["upstream_release"],
            "sha": pin["upstream_release_sha"],
        },
        "workspace_repo_a": str(repo_a_root()),
        "workspace_repo_b": str(repo_b_root()) if repo_b_root() else None,
        "isolation_boundary": isolation_boundary_status(),
    }
    write_json(artifacts_dir() / "preflight.json", result)
    return result


def run_all() -> dict[str, Any]:
    result = {
        "preflight": preflight(),
        "runtime": prepare_runtime(),
        "isolate": isolate_env(),
        "boot": boot_smoke(),
        "tools": enumerate_tools(),
        "sqlite": sqlite_probe(),
        "authority": authority_proof(),
        "probes": developer_probes(),
        "inventory": capability_inventory(),
        "deletion": deletion_has_zero_production_effect(),
    }
    write_json(artifacts_dir() / "all.json", result)
    return result


def _require_source() -> Path:
    src = upstream_src()
    if not (src / "model_tools.py").is_file():
        raise RuntimeError("upstream source missing; run prepare-runtime first")
    return src


def _upstream_python(src: Path) -> Path:
    windows = src / ".venv" / "Scripts" / "python.exe"
    posix = src / ".venv" / "bin" / "python"
    if windows.exists():
        return windows
    if posix.exists():
        return posix
    raise RuntimeError("upstream venv missing; run prepare-runtime first")


def _git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R5 developer Hermes harness")
    parser.add_argument(
        "command",
        choices=[
            "preflight",
            "prepare-runtime",
            "isolate-env",
            "boot-smoke",
            "enumerate-tools",
            "sqlite-probe",
            "authority-proof",
            "developer-probes",
            "capability-inventory",
            "all",
        ],
    )
    args = parser.parse_args(argv)
    dispatch = {
        "preflight": preflight,
        "prepare-runtime": prepare_runtime,
        "isolate-env": isolate_env,
        "boot-smoke": boot_smoke,
        "enumerate-tools": enumerate_tools,
        "sqlite-probe": sqlite_probe,
        "authority-proof": authority_proof,
        "developer-probes": developer_probes,
        "capability-inventory": capability_inventory,
        "all": run_all,
    }
    payload = dispatch[args.command]()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if isinstance(payload, dict) and payload.get("pass") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
