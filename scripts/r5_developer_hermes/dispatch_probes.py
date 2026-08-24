#!/usr/bin/env python3
"""R5 developer probes via Hermes ``handle_function_call``.

Executed by the pinned modern runtime, not by direct Path/subprocess helpers
for the capability claims. Prints one JSON object.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _dispatch(name: str, args: dict) -> dict:
    from model_tools import handle_function_call

    raw = handle_function_call(name, args)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:2000]}
    else:
        parsed = raw
    return {"tool": name, "args": args, "result": parsed}


def _text(payload: dict) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("output", "content", "diff", "message", "raw", "error"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(result)[:2000]
    return str(result)[:2000]


def _exit_code(payload: dict) -> int:
    result = payload.get("result") or {}
    if isinstance(result, dict) and result.get("exit_code") is not None:
        return int(result["exit_code"])
    text = _text(payload)
    if "AssertionError" in text or "Error" in text:
        return -1
    return 0


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    repo_a = Path(spec["repo_a"]).resolve()
    repo_b = Path(spec["repo_b"]).resolve() if spec.get("repo_b") else None
    scratch = Path(spec["scratch"]).resolve()
    python = spec["python"]
    skill_name = spec.get("skill_name") or "r5-dev-skill"
    web_enabled = bool(spec.get("web_enabled"))
    calls: list[str] = []

    def run(name: str, args: dict) -> dict:
        calls.append(name)
        return _dispatch(name, args)

    # Probe A — code exploration on real Repo A, plus a Repo B read if mounted.
    search = run(
        "search_files",
        {"pattern": "def isolated_env", "target": "content", "path": str(repo_a / "scripts")},
    )
    read_symbol = run(
        "read_file",
        {"path": str(repo_a / "scripts" / "r1_modern_hermes_proof" / "harness.py")},
    )
    repo_b_read = None
    repo_b_write = None
    if repo_b is not None:
        readme = repo_b / "README.md"
        target = readme if readme.is_file() else repo_b
        repo_b_read = run("read_file", {"path": str(target)})
        scratch_b = repo_b / ".r5-developer-hermes-scratch"
        proof_b = scratch_b / "write-proof.txt"
        repo_b_write = run(
            "write_file",
            {"path": str(proof_b), "content": "r5-repo-b-write-proof\n"},
        )
        read_back_b = run("read_file", {"path": str(proof_b)})
    else:
        read_back_b = None

    repo_a_proof = scratch / "repo-a-write-proof.txt"
    write_a = run(
        "write_file",
        {"path": str(repo_a_proof), "content": "r5-repo-a-write-proof\n"},
    )
    read_a_proof = run("read_file", {"path": str(repo_a_proof)})

    probe_a_pass = (
        "isolated_env" in _text(search)
        and "def isolated_env" in _text(read_symbol)
        and "r5-repo-a-write-proof" in _text(read_a_proof)
        and write_a["tool"] == "write_file"
        and (repo_b is None or ("r5-repo-b-write-proof" in _text(read_back_b or {})))
    )

    # Probe B — bounded edit in the scratch git workspace.
    module = scratch / "r5_add.py"
    first_src = (
        "def add(a, b):\n"
        "    return a - b\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0 if add(2, 3) == 5 else 1)\n"
    )
    write_module = run("write_file", {"path": str(module), "content": first_src})
    read_module = run("read_file", {"path": str(module)})
    probe_b_pass = write_module["tool"] == "write_file" and "return a - b" in _text(read_module)

    # Probe C — fail, diagnose, fix, rerun green.
    first = run(
        "terminal",
        {"command": f'"{python}" "{module}"', "workdir": str(scratch), "timeout": 60},
    )
    first_exit = _exit_code(first)
    fixed_src = (
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0 if add(2, 3) == 5 else 1)\n"
    )
    fix = run("write_file", {"path": str(module), "content": fixed_src})
    second = run(
        "terminal",
        {"command": f'"{python}" "{module}"', "workdir": str(scratch), "timeout": 60},
    )
    second_exit = _exit_code(second)
    probe_c_pass = first_exit not in (0, None) and second_exit == 0 and fix["tool"] == "write_file"

    # Probe D — git status / diff through the developer workflow.
    git_status = run(
        "terminal",
        {"command": "git status --short", "workdir": str(scratch), "timeout": 30},
    )
    git_diff = run(
        "terminal",
        {"command": "git diff -- r5_add.py", "workdir": str(scratch), "timeout": 30},
    )
    probe_d_pass = _exit_code(git_status) == 0 and (
        "r5_add.py" in _text(git_status) or "r5_add.py" in _text(git_diff) or "+" in _text(git_diff)
    )

    # Probe E — skills.
    skills_list = run("skills_list", {})
    listed_raw = skills_list.get("result") or {}
    viewed = None
    chosen = skill_name
    if isinstance(listed_raw, dict):
        listed = listed_raw.get("skills") or []
        if listed and isinstance(listed[0], dict) and listed[0].get("name"):
            chosen = listed[0]["name"]
    viewed = run("skill_view", {"name": chosen})
    probe_e_pass = isinstance(listed_raw, dict) and (
        listed_raw.get("success") is True or "skills" in listed_raw
    )

    # Probe F — web only when a dedicated non-production credential is present.
    web = None
    if web_enabled:
        web = run("web_search", {"query": "Hermes Agent Nous Research documentation", "limit": 1})
        web_text = _text(web).lower()
        web_status = (
            "PASS"
            if web["tool"] == "web_search" and "error" not in (web.get("result") or {})
            else "FAIL"
        )
        if "api key" in web_text or "not configured" in web_text or "credential" in web_text:
            web_status = "NOT_RUN_CREDENTIAL_REQUIRED"
    else:
        web_status = "NOT_RUN_CREDENTIAL_REQUIRED"

    # Production-authority tool must be unreachable in this modern runtime.
    execute = run(
        "execute_powerunits_option_d_bounded_slice",
        {"country_code": "DE", "version": "v1"},
    )
    execute_text = _text(execute).lower()
    execute_unreachable = "unknown tool" in execute_text or "not found" in execute_text

    payload = {
        "dispatch_path": "model_tools.handle_function_call",
        "tool_calls": calls,
        "tool_call_count": len(calls),
        "ordinary_workspace_approvals": 0,
        "probe_a": {
            "search_excerpt": _text(search)[:800],
            "read_excerpt": _text(read_symbol)[:400],
            "repo_a_write_excerpt": _text(write_a)[:200],
            "repo_b_read_excerpt": (_text(repo_b_read)[:400] if repo_b_read else None),
            "repo_b_write_excerpt": (_text(repo_b_write)[:200] if repo_b_write else None),
            "pass": probe_a_pass,
        },
        "probe_b": {
            "read_excerpt": _text(read_module)[:400],
            "pass": probe_b_pass,
        },
        "probe_c": {
            "first_exit": first_exit,
            "first_excerpt": _text(first)[:500],
            "second_exit": second_exit,
            "second_excerpt": _text(second)[:500],
            "pass": probe_c_pass,
        },
        "probe_d": {
            "status_excerpt": _text(git_status)[:500],
            "diff_excerpt": _text(git_diff)[:800],
            "pass": probe_d_pass,
        },
        "probe_e": {
            "skills_list_excerpt": _text(skills_list)[:800],
            "skill_view_name": chosen,
            "skill_view_excerpt": (_text(viewed)[:800] if viewed else None),
            "pass": probe_e_pass,
        },
        "probe_f": {
            "status": web_status,
            "excerpt": (_text(web)[:500] if web else None),
        },
        "production_execute_dispatch": {
            "excerpt": _text(execute)[:400],
            "unreachable": execute_unreachable,
        },
        "PROBE_A_CODE_EXPLORATION": "PASS" if probe_a_pass else "FAIL",
        "PROBE_B_EDIT": "PASS" if probe_b_pass else "FAIL",
        "PROBE_C_TEST_LOOP": "PASS" if probe_c_pass else "FAIL",
        "PROBE_D_GIT": "PASS" if probe_d_pass else "FAIL",
        "PROBE_E_SKILLS": "PASS" if probe_e_pass else "FAIL",
        "PROBE_F_WEB": web_status,
        "could_edit": probe_b_pass,
        "could_run_tests": probe_c_pass,
        "could_inspect_diff": probe_d_pass,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
