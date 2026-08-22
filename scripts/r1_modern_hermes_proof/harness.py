#!/usr/bin/env python3
"""R1 isolated modern-Hermes proof harness.

Proofs the pinned upstream release in a reconstructable, non-production
environment. Does not read ``.env``, does not start public listeners, and
does not patch upstream core.

    python scripts/r1_modern_hermes_proof/harness.py <command>

Commands:
    verify-pin
    prepare-source
    frozen-install
    inspect-lazy-install
    isolate-env
    boot-smoke
    enumerate-tools
    clamp-operator
    capability-inventory
    capability-probes
    model-smoke
    all
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
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PIN_PATH = HERE / "pin.json"

PROOF_ROOT_ENV = "HERMES_R1_PROOF_ROOT"
MODEL_KEY_ENV = "HERMES_R1_MODEL_API_KEY"
MODEL_PROVIDER_ENV = "HERMES_R1_MODEL_PROVIDER"
MODEL_NAME_ENV = "HERMES_R1_MODEL"
DEFAULT_SMOKE_MODEL = "gpt-4.1-mini"
SMOKE_PROMPT = "Reply with exactly: R1_MODEL_SMOKE_OK"

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
    "USERPROFILE",
    "USERNAME",
    "HOMEDRIVE",
    "HOMEPATH",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "LANG",
    "LC_ALL",
    "TZ",
    "TERM",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "XDG_RUNTIME_DIR",
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


def load_pin() -> dict[str, Any]:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def proof_root() -> Path:
    override = os.environ.get(PROOF_ROOT_ENV, "").strip()
    return Path(override) if override else REPO_ROOT / ".r1-proof"


def upstream_src() -> Path:
    return proof_root() / "upstream-src"


def operator_home() -> Path:
    return proof_root() / "homes" / "operator"


def developer_home() -> Path:
    return proof_root() / "homes" / "developer"


def scratch_workspace() -> Path:
    return proof_root() / "scratch" / "capability_workspace"


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


def resolve_model_smoke_target(
    r1_provider: str | None = None,
    model: str | None = None,
) -> dict[str, str]:
    """Map the R1 human provider alias onto the Hermes runtime identity.

    Hermes ``auto`` treats ``OPENAI_API_KEY`` as OpenRouter. The smoke path
    must pin ``openai-api`` (api.openai.com) explicitly.
    """
    raw = (
        r1_provider
        if r1_provider is not None
        else os.environ.get(MODEL_PROVIDER_ENV, "openai")
    ).strip().lower() or "openai"
    model_name = (
        model if model is not None else os.environ.get(MODEL_NAME_ENV, DEFAULT_SMOKE_MODEL)
    ).strip() or DEFAULT_SMOKE_MODEL
    if raw in {"openai", "openai-api"}:
        return {
            "r1_provider": "openai",
            "hermes_provider": "openai-api",
            "key_env": "OPENAI_API_KEY",
            "model": model_name,
            "base_url_scheme": "https",
            "base_url_host": "api.openai.com",
            "path_class": "/v1/chat/completions",
        }
    if raw == "openrouter":
        return {
            "r1_provider": "openrouter",
            "hermes_provider": "openrouter",
            "key_env": "OPENROUTER_API_KEY",
            "model": model_name,
            "base_url_scheme": "https",
            "base_url_host": "openrouter.ai",
            "path_class": "/api/v1/chat/completions",
        }
    raise ValueError(f"unsupported R1 model-smoke provider {raw!r}")


def map_model_key_into_env(env: dict[str, str], model_key: str) -> dict[str, str]:
    """Map the R1 key into the child provider env only. Never persist it."""
    target = resolve_model_smoke_target()
    env[target["key_env"]] = model_key
    env["HERMES_INFERENCE_PROVIDER"] = target["hermes_provider"]
    env["HERMES_INFERENCE_MODEL"] = target["model"]
    return env


def isolated_env(
    hermes_home: Path,
    *,
    extra: dict[str, str] | None = None,
    include_model_key: bool = False,
) -> dict[str, str]:
    """Build a process env with production authority structurally absent."""
    pin = load_pin()
    blocked = set(production_authority_names(pin))
    env: dict[str, str] = {}
    for key in SAFE_ENV_PASSTHROUGH:
        value = os.environ.get(key)
        if value is not None and key not in blocked:
            env[key] = value
    env["HERMES_HOME"] = str(hermes_home)
    env["HERMES_DISABLE_LAZY_INSTALLS"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    if include_model_key:
        model_key = os.environ.get(MODEL_KEY_ENV, "").strip()
        if model_key:
            map_model_key_into_env(env, model_key)
    if extra:
        for key, value in extra.items():
            if key in blocked:
                raise ValueError(f"refusing to inject production-authority name {key}")
            env[key] = value
    present = sorted(name for name in blocked if env.get(name))
    if present:
        raise RuntimeError(f"isolated env leaked production-authority names: {present}")
    return env


def model_smoke_cli_args() -> list[str]:
    """Pinned CLI argv after the executable.

    ``-z/--oneshot`` takes PROMPT as its immediate argument. Placing
    ``--provider`` after ``-z`` makes argparse report
    ``argument -z/--oneshot: expected one argument`` before any HTTP call.
    """
    target = resolve_model_smoke_target()
    return [
        "--provider",
        target["hermes_provider"],
        "--model",
        target["model"],
        "-z",
        SMOKE_PROMPT,
    ]


def model_smoke_command(hermes: Path, python: Path) -> list[str]:
    """Run the R1 oneshot shim, not raw ``hermes -z``.

    Pinned ``hermes -z`` builds ``AIAgent`` without
    ``resolve_reasoning_config``. The Responses transport then defaults
    ``reasoning.effort=medium``, which ``gpt-4.1-mini`` rejects with HTTP 400.
    The shim is oneshot-equivalent and applies isolated
    ``agent.reasoning_effort: none``.
    """
    return [str(python), str(HERE / "model_smoke_run.py")]


def write_model_smoke_operator_config(home: Path) -> dict[str, str]:
    """Pin provider/model in isolated config. Never persist the API key."""
    pin = load_pin()
    target = resolve_model_smoke_target()
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        _operator_config(
            pin,
            model_provider=target["hermes_provider"],
            model_name=target["model"],
            omit_reasoning=True,
        ),
        encoding="utf-8",
    )
    return target


def assert_authority_absent(env: dict[str, str], pin: dict[str, Any] | None = None) -> dict[str, Any]:
    names = production_authority_names(pin)
    present = [name for name in names if env.get(name)]
    return {
        "asserted_absent": list(names),
        "present": present,
        "pass": not present,
    }


def verify_pin(*, live: bool = True) -> dict[str, Any]:
    pin = load_pin()
    result: dict[str, Any] = {
        "pin": {
            "release": pin["upstream_release"],
            "project_version": pin["upstream_project_version"],
            "release_sha": pin["upstream_release_sha"],
            "tag_object": pin["upstream_tag_object"],
            "image_digest": pin["upstream_image_digest"],
        },
        "checks": {},
    }
    if not live:
        result["live"] = False
        result["pass"] = True
        return result

    tag_url = "https://api.github.com/repos/NousResearch/hermes-agent/git/refs/tags/v2026.8.19"
    tag_ref = _http_json(tag_url)
    tag_object = tag_ref["object"]["sha"]
    tag_meta = _http_json(
        f"https://api.github.com/repos/NousResearch/hermes-agent/git/tags/{tag_object}"
    )
    release_sha = tag_meta["object"]["sha"]
    release = _http_json(
        "https://api.github.com/repos/NousResearch/hermes-agent/releases/tags/v2026.8.19"
    )
    image = _http_json(
        "https://hub.docker.com/v2/repositories/nousresearch/hermes-agent/tags/v2026.8.19"
    )
    pyproject_b64 = _http_json(
        "https://api.github.com/repos/NousResearch/hermes-agent/contents/pyproject.toml"
        f"?ref={pin['upstream_release_sha']}"
    )["content"]
    import base64

    pyproject = base64.b64decode(pyproject_b64).decode("utf-8")
    version_ok = 'version = "0.20.5"' in pyproject.splitlines()[2] or 'version = "0.20.5"' in pyproject

    checks = {
        "release_tag": release.get("tagName") == pin["upstream_release"]
        or release.get("tag_name") == pin["upstream_release"],
        "tag_object": tag_object == pin["upstream_tag_object"],
        "release_sha": release_sha == pin["upstream_release_sha"],
        "project_version": version_ok,
        "image_digest": image.get("digest") == pin["upstream_image_digest"],
    }
    result["checks"] = checks
    result["observed"] = {
        "tag_object": tag_object,
        "release_sha": release_sha,
        "release_name": release.get("name"),
        "image_digest": image.get("digest"),
        "image_last_pushed": image.get("tag_last_pushed"),
    }
    result["pass"] = all(checks.values())
    return result


def _http_json(url: str) -> dict[str, Any]:
    headers = {"User-Agent": "hermes-r1-proof", "Accept": "application/json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def prepare_source() -> dict[str, Any]:
    pin = load_pin()
    dest = upstream_src()
    dest.parent.mkdir(parents=True, exist_ok=True)
    sha = pin["upstream_release_sha"]
    if dest.exists():
        observed = _git(["rev-parse", "HEAD"], cwd=dest).strip()
        if observed == sha:
            return {"path": str(dest), "sha": observed, "already_present": True}
        raise RuntimeError(f"existing source at {dest} is {observed}, expected {sha}")

    _git(["fetch", "upstream", sha], cwd=REPO_ROOT)
    _git(["worktree", "add", "--detach", str(dest), sha], cwd=REPO_ROOT)
    observed = _git(["rev-parse", "HEAD"], cwd=dest).strip()
    if observed != sha:
        raise RuntimeError(f"worktree HEAD {observed} != pin {sha}")
    return {"path": str(dest), "sha": observed, "already_present": False}


def frozen_install() -> dict[str, Any]:
    src = _require_source()
    cmd = ["uv", "sync", "--frozen"]
    completed = subprocess.run(
        cmd,
        cwd=src,
        capture_output=True,
        text=True,
        check=False,
    )
    result = {
        "command": cmd,
        "cwd": str(src),
        "returncode": completed.returncode,
        "pass": completed.returncode == 0,
    }
    write_json(
        artifacts_dir() / "frozen_install.json",
        {**result, "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]},
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "uv sync --frozen failed:\n"
            f"{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}"
        )
    return result


def inspect_lazy_install() -> dict[str, Any]:
    src = _require_source()
    lazy_deps = (src / "tools" / "lazy_deps.py").read_text(encoding="utf-8")
    config_docs = ""
    security_md = src / "website" / "docs" / "user-guide" / "security.md"
    if security_md.exists():
        config_docs = security_md.read_text(encoding="utf-8")
    boot_hits = []
    for rel in (
        "hermes_cli/main.py",
        "hermes_cli/oneshot.py",
        "run_agent.py",
        "agent/agent_init.py",
    ):
        text = (src / rel).read_text(encoding="utf-8")
        if "lazy_deps.ensure" in text or "from tools.lazy_deps import ensure" in text:
            boot_hits.append(rel)
    present = "def ensure(" in lazy_deps
    disable_env = "HERMES_DISABLE_LAZY_INSTALLS" in lazy_deps
    config_gate = "allow_lazy_installs" in lazy_deps
    verdict = "ABSENT_OR_DISABLED"
    if boot_hits:
        verdict = "PRESENT_AND_BLOCKING"
    result = {
        "lazy_deps_module_present": present,
        "disable_env_supported": disable_env,
        "config_gate_supported": config_gate,
        "startup_direct_ensure_hits": boot_hits,
        "proof_disables": {
            "HERMES_DISABLE_LAZY_INSTALLS": "1",
            "security.allow_lazy_installs": False,
        },
        "RUNTIME_LAZY_INSTALL": verdict,
        "notes": (
            "Upstream exposes opt-in lazy installs for optional backends. "
            "The inspected CLI/agent startup files do not call ensure() themselves. "
            "The proof process sets HERMES_DISABLE_LAZY_INSTALLS=1 and "
            "security.allow_lazy_installs=false. No upstream patch applied."
        ),
        "docs_mention_allow_lazy_installs": "allow_lazy_installs" in config_docs,
    }
    write_json(artifacts_dir() / "lazy_install.json", result)
    return result


def write_proof_homes() -> dict[str, Any]:
    pin = load_pin()
    homes = {
        "operator": operator_home(),
        "developer": developer_home(),
    }
    for name, home in homes.items():
        home.mkdir(parents=True, exist_ok=True)
        (home / "sessions").mkdir(exist_ok=True)
        if name == "operator":
            config = _operator_config(pin)
        else:
            config = _developer_config()
        (home / "config.yaml").write_text(config, encoding="utf-8")
        (home / "SOUL.md").write_text(
            f"# R1 {name} proof soul\n\nIsolated non-production proof context.\n",
            encoding="utf-8",
        )
    scratch_workspace().mkdir(parents=True, exist_ok=True)
    return {name: str(path) for name, path in homes.items()}


def _operator_config(
    pin: dict[str, Any],
    *,
    model_provider: str | None = None,
    model_name: str | None = None,
    omit_reasoning: bool = False,
) -> str:
    allowed = "\n".join(f"    - {name}" for name in pin["operator_allowed_toolsets"])
    disabled = "\n".join(f"    - {name}" for name in pin["operator_forbidden_toolsets"])
    reasoning = ""
    if omit_reasoning:
        reasoning = "  reasoning_effort: none\n"
        if model_name:
            reasoning += (
                "  reasoning_overrides:\n"
                f"    {model_name}: none\n"
            )
    text = (
        "security:\n"
        "  allow_lazy_installs: false\n"
        "agent:\n"
        f"{reasoning}"
        f"  disabled_toolsets:\n{disabled}\n"
        "platform_toolsets:\n"
        "  cli:\n"
        f"{allowed}\n"
        "approvals:\n"
        "  mode: manual\n"
        "  cron_mode: deny\n"
    )
    if model_provider and model_name:
        text += (
            "model:\n"
            f"  provider: {model_provider}\n"
            f"  default: {model_name}\n"
        )
    return text


def _developer_config() -> str:
    return (
        "security:\n"
        "  allow_lazy_installs: false\n"
        "agent:\n"
        "  disabled_toolsets: []\n"
        "platform_toolsets:\n"
        "  cli:\n"
        "    - file\n"
        "    - terminal\n"
        "    - web\n"
        "    - skills\n"
        "    - todo\n"
        "    - memory\n"
        "approvals:\n"
        "  mode: manual\n"
    )


def boot_smoke() -> dict[str, Any]:
    src = _require_source()
    python = _upstream_python(src)
    write_proof_homes()
    env = isolated_env(operator_home())
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
        "help_cmd": help_cmd,
        "help_returncode": help_run.returncode,
        "help_has_usage": "Usage" in help_run.stdout or "usage" in help_run.stdout.lower(),
        "production_credential_assertions": assertion,
        "LISTEN_ADDRESS": "none",
        "PUBLIC_INGRESS": "NO",
        "pass": completed.returncode == 0 and help_run.returncode == 0 and assertion["pass"],
    }
    write_json(artifacts_dir() / "boot_smoke.json", result)
    if not result["pass"]:
        raise RuntimeError(f"boot smoke failed: {completed.stderr[-2000:]}\n{help_run.stderr[-2000:]}")
    return result


def enumerate_tools(context: str = "operator") -> dict[str, Any]:
    pin = load_pin()
    src = _require_source()
    python = _upstream_python(src)
    write_proof_homes()
    home = operator_home() if context == "operator" else developer_home()
    env = isolated_env(home)
    if context == "operator":
        enabled = pin["operator_allowed_toolsets"]
        disabled = pin["operator_forbidden_toolsets"]
    else:
        enabled = ["file", "terminal", "web", "skills", "todo", "memory"]
        disabled = []
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
        "context": context,
        "enabled_toolsets": enabled,
        "disabled_toolsets": disabled,
        "callable_tools": names,
        "inspectable": True,
    }
    write_json(artifacts_dir() / f"tools_{context}.json", result)
    return result


def clamp_operator() -> dict[str, Any]:
    pin = load_pin()
    src = _require_source()
    python = _upstream_python(src)
    write_proof_homes()
    env = isolated_env(operator_home())
    allowed = pin["operator_allowed_toolsets"]
    forbidden = pin["operator_forbidden_toolsets"]
    cases = []

    def run_case(name: str, enabled: list[str] | None, disabled: list[str] | None) -> dict[str, Any]:
        script = (
            "import json,sys\n"
            "from model_tools import get_tool_definitions\n"
            "enabled=json.loads(sys.argv[1])\n"
            "disabled=json.loads(sys.argv[2])\n"
            "en=None if enabled==[] and sys.argv[3]=='none' else enabled\n"
            "dis=None if disabled==[] and sys.argv[4]=='none' else disabled\n"
            "if sys.argv[3]=='none':\n"
            "    en=None\n"
            "if sys.argv[4]=='none':\n"
            "    dis=None\n"
            "defs=get_tool_definitions(enabled_toolsets=en, disabled_toolsets=dis, quiet_mode=True)\n"
            "print(json.dumps(sorted(d['function']['name'] for d in defs)))\n"
        )
        enabled_flag = "none" if enabled is None else "set"
        disabled_flag = "none" if disabled is None else "set"
        completed = subprocess.run(
            [
                str(python),
                "-c",
                script,
                json.dumps(enabled or []),
                json.dumps(disabled or []),
                enabled_flag,
                disabled_flag,
            ],
            cwd=src,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"clamp case {name} failed: {completed.stderr[-4000:]}")
        names = json.loads(completed.stdout.strip().splitlines()[-1])
        return {"name": name, "enabled": enabled, "disabled": disabled, "callable": names}

    cases.append(run_case("normal_allowed_set", allowed, forbidden))
    cases.append(run_case("disabled_family_terminal", allowed, ["terminal"]))
    cases.append(run_case("explicit_caller_requests_terminal", allowed + ["terminal"], None))
    cases.append(run_case("explicit_caller_plus_disabled_arg", allowed + ["terminal"], forbidden))
    cases.append(run_case("unknown_toolset_does_not_widen", allowed + ["not_a_real_toolset"], forbidden))
    cases.append(run_case("toolsets_all_bypass", None, None))

    oneshot = (src / "hermes_cli" / "oneshot.py").read_text(encoding="utf-8")
    model_tools = (src / "model_tools.py").read_text(encoding="utf-8")
    tools_config = (src / "hermes_cli" / "tools_config.py").read_text(encoding="utf-8")
    oneshot_passes_disabled = "disabled_toolsets=" in oneshot
    has_final_policy_intersection = "first_safe" in model_tools or "POWERUNITS" in model_tools
    platform_tools_subtracts_disabled = "enabled_toolsets -= disabled_set" in tools_config
    plugin_default_enabled = "New plugin not yet seen by hermes tools — default enabled" in tools_config

    all_resolution = _run_upstream_json(
        python,
        src,
        env,
        (
            "import json\n"
            "from hermes_cli.oneshot import _validate_explicit_toolsets\n"
            "from model_tools import get_tool_definitions\n"
            "resolved, err = _validate_explicit_toolsets('all')\n"
            "defs = get_tool_definitions(enabled_toolsets=resolved, disabled_toolsets=None, quiet_mode=True)\n"
            "names = sorted(d['function']['name'] for d in defs)\n"
            "print(json.dumps({'resolved_enabled': resolved, 'error': err, 'callable': names}))\n"
        ),
    )
    high_authority = [
        "execute_code",
        "browser_exec",
        "browser_navigate",
        "session_search",
        "delegate_task",
        "write_file",
        "terminal",
        "read_file",
    ]
    restored = [name for name in high_authority if name in all_resolution.get("callable", [])]
    plugin_expansion = _run_upstream_json(
        python,
        src,
        env,
        (
            "import json\n"
            "from unittest.mock import patch\n"
            "from hermes_cli.tools_config import _get_platform_tools\n"
            "declared = ['memory', 'todo', 'web']\n"
            "config = {'platform_toolsets': {'cli': list(declared)}, "
            "'agent': {'disabled_toolsets': ['terminal', 'file']}, "
            "'known_plugin_toolsets': {}}\n"
            "with patch('hermes_cli.tools_config._get_plugin_toolset_keys', "
            "return_value={'r1_undeclared_plugin'}):\n"
            "    enabled = sorted(_get_platform_tools(config, 'cli'))\n"
            "print(json.dumps({'declared': declared, 'enabled': enabled, "
            "'undeclared_plugin_present': 'r1_undeclared_plugin' in enabled}))\n"
        ),
    )

    explicit = next(case for case in cases if case["name"] == "explicit_caller_requests_terminal")
    forbidden_tools_from_terminal = {"terminal", "process"}
    caller_restored_forbidden = bool(set(explicit["callable"]) & forbidden_tools_from_terminal)
    toolsets_all_bypass = bool(restored) and all_resolution.get("resolved_enabled") is None
    plugin_self_expansion = bool(plugin_expansion.get("undeclared_plugin_present"))

    equivalence = "PATCH_REQUIRED"
    seam = (
        "MINIMUM_ENFORCEMENT_SEAM = model_tools._compute_tool_definitions "
        "using a FINAL POSITIVE INTERSECTION against a declared operator "
        "allowlist after normal enabled/disabled resolution and before "
        "registry definitions. Domain-agnostic; no PowerUnits/Telegram/"
        "capability-tier/Repo-B logic. CLAMP_IMPLEMENTATION_CLASS = "
        "THIN_CORE_PATCH. R1 does not implement this patch."
    )

    result = {
        "cases": [
            {
                **case,
                "forbidden_present": sorted(
                    name
                    for name in case["callable"]
                    if name
                    in {
                        "terminal",
                        "process",
                        "read_file",
                        "write_file",
                        "delegate_task",
                        "session_search",
                        "execute_code",
                        "browser_navigate",
                        "browser_exec",
                    }
                ),
            }
            for case in cases
        ],
        "paths": {
            "get_tool_definitions": "disabled subtraction exists; no final policy intersection",
            "oneshot_explicit_toolsets": (
                "passes enabled_toolsets only; does not pass disabled_toolsets"
                if not oneshot_passes_disabled
                else "passes disabled_toolsets"
            ),
            "oneshot_toolsets_all": "hermes -z --toolsets all -> enabled=None, disabled=None",
            "tools_config._get_platform_tools": (
                "subtracts agent.disabled_toolsets from enabled"
                if platform_tools_subtracts_disabled
                else "does not subtract disabled"
            ),
            "plugin_default_enabled_comment_present": plugin_default_enabled,
            "multiplex": "not used in this proof",
        },
        "oneshot_passes_disabled_toolsets": oneshot_passes_disabled,
        "upstream_has_final_policy_intersection": has_final_policy_intersection,
        "caller_can_restore_forbidden_tool": caller_restored_forbidden,
        "CALLER_BYPASS": "VERIFIED" if caller_restored_forbidden else "NOT_PROVEN",
        "TOOLSETS_ALL_BYPASS": {
            "resolved_enabled": all_resolution.get("resolved_enabled"),
            "restored_high_authority": restored,
            "pass": toolsets_all_bypass,
        },
        "PLUGIN_SELF_EXPANSION": plugin_expansion,
        "CONFIG_ONLY": "INSUFFICIENT",
        "CORE_PATCH_NEEDED": "YES",
        "CLAMP_IMPLEMENTATION_CLASS": "THIN_CORE_PATCH",
        "CLAMP_EQUIVALENCE": equivalence,
        "PATCH_SEAM_IF_REQUIRED": seam,
        "FUTURE_CORE_PATCH_IMPLEMENTED": "NO",
    }
    if not (toolsets_all_bypass and plugin_self_expansion and caller_restored_forbidden):
        raise RuntimeError(
            "expected both caller bypass and plugin self-expansion evidence; "
            f"got toolsets_all={toolsets_all_bypass} plugin={plugin_self_expansion} "
            f"caller={caller_restored_forbidden}"
        )
    write_json(artifacts_dir() / "clamp_operator.json", result)
    return result


def _run_upstream_json(python: Path, src: Path, env: dict[str, str], script: str) -> dict[str, Any]:
    completed = subprocess.run(
        [str(python), "-c", script],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"upstream probe failed: {completed.stderr[-4000:]}\n{completed.stdout[-2000:]}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def capability_inventory() -> dict[str, Any]:
    src = _require_source()
    toolsets_text = (src / "toolsets.py").read_text(encoding="utf-8")
    inventory = {
        "filesystem_read": "file / read_file" if '"file"' in toolsets_text else "absent",
        "filesystem_write": "file / write_file, patch" if "write_file" in toolsets_text else "absent",
        "terminal_command_execution": "terminal / terminal, process" if '"terminal"' in toolsets_text else "absent",
        "git_oriented_work": "terminal + file (no dedicated git toolset; git via terminal)",
        "tests_subprocess_workflow": "terminal",
        "web_research": "web / web_search, web_extract" if '"web"' in toolsets_text else "absent",
        "browser": "browser" if '"browser"' in toolsets_text else "absent",
        "skills": "skills / skills_list, skill_view, skill_manage" if '"skills"' in toolsets_text else "absent",
        "delegation_subagents": "delegation / delegate_task" if '"delegation"' in toolsets_text else "absent",
        "profiles": "present in docs/user-guide/profiles.md" if (src / "website/docs/user-guide/profiles.md").exists() else "unknown",
        "bot_mode": "present in docs/user-guide/bot-mode.md" if (src / "website/docs/user-guide/bot-mode.md").exists() else "unknown",
        "observability": "present in docs/observability" if (src / "docs/observability").exists() else "unknown",
    }
    write_json(artifacts_dir() / "capability_inventory.json", inventory)
    return inventory


def capability_probes() -> dict[str, Any]:
    src = _require_source()
    python = _upstream_python(src)
    write_proof_homes()
    scratch = scratch_workspace()
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    (scratch / "alpha.txt").write_text("alpha-source\n", encoding="utf-8")
    (scratch / "beta.txt").write_text("beta-source\n", encoding="utf-8")
    (scratch / "r1_add_probe.py").write_text(
        "def add(a, b):\n    return a - b\n\nif __name__ == '__main__':\n    raise SystemExit(0 if add(2, 3) == 5 else 1)\n",
        encoding="utf-8",
    )
    skill_dir = developer_home() / "skills" / "r1-proof-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: r1-proof-skill\ndescription: Local isolated R1 fixture. Not networked.\n---\n\nRead-only proof skill.\n",
        encoding="utf-8",
    )
    env = isolated_env(
        developer_home(),
        extra={
            "PWD": str(scratch),
            "HERMES_YOLO_MODE": "1",
            "HERMES_ACCEPT_HOOKS": "1",
        },
    )
    probe_script = HERE / "dispatch_probes.py"
    completed = subprocess.run(
        [str(python), str(probe_script), str(scratch)],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"capability probes failed: {completed.stderr[-4000:]}\n{completed.stdout[-2000:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    payload["CAPABILITY_TOOL_DISPATCH"] = {
        "FILESYSTEM": payload.get("CAPABILITY_PROBE_1_WORKSPACE"),
        "TERMINAL": payload.get("CAPABILITY_PROBE_2_TERMINAL_TEST_LOOP"),
        "SKILLS": payload.get("CAPABILITY_PROBE_3_MODERN_PRIMITIVE"),
        "path": "model_tools.handle_function_call",
    }
    all_pass = (
        payload.get("CAPABILITY_PROBE_1_WORKSPACE") == "PASS"
        and payload.get("CAPABILITY_PROBE_2_TERMINAL_TEST_LOOP") == "PASS"
        and payload.get("CAPABILITY_PROBE_3_MODERN_PRIMITIVE") == "PASS"
    )
    payload["CAPABILITY_UPLIFT"] = "STRONG" if all_pass else "MODERATE"
    write_json(artifacts_dir() / "capability_probes.json", payload)
    return payload


def model_smoke() -> dict[str, Any]:
    key = os.environ.get(MODEL_KEY_ENV, "").strip()
    warning = (
        "DO NOT ATTACH RAW MODEL-SMOKE ARTIFACT TO PR WITHOUT REVIEW/REDACTION. "
        "stdout/stderr tails may contain provider-error material."
    )
    if not key:
        command = f"{sys.executable} scripts/r1_modern_hermes_proof/harness.py model-smoke"
        result = {
            "MODEL_SMOKE": "HUMAN_CREDENTIAL_REQUIRED",
            "MODEL_SMOKE_HARNESS": "READY",
            "human_command": (
                f"set {MODEL_KEY_ENV}=<non-production-ephemeral-key>\n"
                f"set {MODEL_PROVIDER_ENV}=openai\n"
                f"set {MODEL_NAME_ENV}=gpt-4.1-mini\n"
                f"{command}"
            ),
            "notes": (
                "Do not source the key from production .env or secret stores. "
                "Use a dedicated non-production provider key only. "
                + warning
            ),
        }
        write_json(artifacts_dir() / "model_smoke.json", result)
        return result

    src = _require_source()
    python = _upstream_python(src)
    hermes = python.with_name("hermes.exe" if python.suffix == ".exe" else "hermes")
    write_proof_homes()
    target = write_model_smoke_operator_config(operator_home())
    env = isolated_env(operator_home(), include_model_key=True)
    assertion = assert_authority_absent(env)
    cmd = model_smoke_command(hermes, python)
    completed = subprocess.run(
        cmd,
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    result = {
        "MODEL_SMOKE": "PASS" if completed.returncode == 0 and "R1_MODEL_SMOKE_OK" in output else "FAIL",
        "MODEL_SMOKE_HARNESS": "READY",
        "returncode": completed.returncode,
        "production_credential_assertions": assertion,
        "wiring": {
            "provider": target["hermes_provider"],
            "model": target["model"],
            "child_key_env": target["key_env"],
            "child_key_present": bool(env.get(target["key_env"])),
            "intended_host": target["base_url_host"],
            "intended_path_class": target["path_class"],
            "ambient_openai_key_passthrough": False,
            "reasoning_effort": "none",
        },
        "stdout_tail": completed.stdout[-400:],
        "stderr_tail": completed.stderr[-400:],
        "warning": warning,
    }
    write_json(artifacts_dir() / "model_smoke.json", result)
    return result


def probe_model_smoke_auth_path(sentinel: str) -> dict[str, Any]:
    """Resolve the Hermes provider path with a sentinel key. No live model call."""
    if not sentinel or sentinel.startswith("sk-"):
        raise ValueError("probe sentinel must be a non-secret test token")
    src = _require_source()
    python = _upstream_python(src)
    write_proof_homes()
    target = write_model_smoke_operator_config(operator_home())
    env = isolated_env(operator_home())
    map_model_key_into_env(env, sentinel)
    env["HERMES_R1_AUTH_PROBE_SENTINEL"] = sentinel
    env["HERMES_R1_AUTH_PROBE_KEY_ENV"] = target["key_env"]
    completed = subprocess.run(
        [str(python), str(HERE / "model_smoke_auth_probe.py")],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(f"auth probe produced no JSON: {completed.stderr[-2000:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    payload["returncode"] = completed.returncode
    payload["intended_host"] = target["base_url_host"]
    payload["intended_provider"] = target["hermes_provider"]
    return payload


def probe_model_smoke_reasoning_kwargs() -> dict[str, Any]:
    """Prove gpt-4.1-mini Responses kwargs omit reasoning.effort. No live call."""
    src = _require_source()
    python = _upstream_python(src)
    write_proof_homes()
    write_model_smoke_operator_config(operator_home())
    env = isolated_env(operator_home())
    completed = subprocess.run(
        [str(python), str(HERE / "model_smoke_reasoning_probe.py")],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(
            f"reasoning probe produced no JSON: {completed.stderr[-2000:]}"
        )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    payload["returncode"] = completed.returncode
    return payload


def _require_source() -> Path:
    src = upstream_src()
    if not src.exists():
        raise RuntimeError("upstream source missing; run prepare-source first")
    return src


def _upstream_python(src: Path) -> Path:
    windows = src / ".venv" / "Scripts" / "python.exe"
    posix = src / ".venv" / "bin" / "python"
    if windows.exists():
        return windows
    if posix.exists():
        return posix
    raise RuntimeError("upstream venv missing; run frozen-install first")


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
    parser = argparse.ArgumentParser(description="R1 modern Hermes proof harness")
    parser.add_argument(
        "command",
        choices=[
            "verify-pin",
            "prepare-source",
            "frozen-install",
            "inspect-lazy-install",
            "isolate-env",
            "boot-smoke",
            "enumerate-tools",
            "clamp-operator",
            "capability-inventory",
            "capability-probes",
            "model-smoke",
            "all",
        ],
    )
    parser.add_argument("--offline-pin", action="store_true")
    parser.add_argument("--context", choices=["operator", "developer"], default="operator")
    args = parser.parse_args(argv)

    dispatch = {
        "verify-pin": lambda: verify_pin(live=not args.offline_pin),
        "prepare-source": prepare_source,
        "frozen-install": frozen_install,
        "inspect-lazy-install": inspect_lazy_install,
        "isolate-env": lambda: {
            "homes": write_proof_homes(),
            "operator": assert_authority_absent(isolated_env(operator_home())),
            "developer": assert_authority_absent(isolated_env(developer_home())),
        },
        "boot-smoke": boot_smoke,
        "enumerate-tools": lambda: enumerate_tools(args.context),
        "clamp-operator": clamp_operator,
        "capability-inventory": capability_inventory,
        "capability-probes": capability_probes,
        "model-smoke": model_smoke,
    }
    if args.command == "all":
        payload = {}
        for name in (
            "verify-pin",
            "prepare-source",
            "frozen-install",
            "inspect-lazy-install",
            "isolate-env",
            "boot-smoke",
            "enumerate-tools",
            "clamp-operator",
            "capability-inventory",
            "capability-probes",
            "model-smoke",
        ):
            payload[name] = dispatch[name]()
        write_json(artifacts_dir() / "all.json", {k: v for k, v in payload.items() if k != "verify-pin" or True})
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    result = dispatch[args.command]()
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
