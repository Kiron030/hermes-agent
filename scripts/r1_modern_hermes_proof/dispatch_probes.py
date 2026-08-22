#!/usr/bin/env python3
"""Exercise real Hermes handle_function_call dispatch in an isolated scratch tree.

This script is executed by the pinned upstream venv. It must not import the
PowerUnits fork runtime.
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
        for key in ("output", "content", "diff", "message", "raw"):
            value = result.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(result)[:2000]
    return str(result)[:2000]


def main() -> int:
    scratch = Path(sys.argv[1]).resolve()
    python = sys.executable
    alpha = scratch / "alpha.txt"
    beta = scratch / "beta.txt"
    note = scratch / "note.txt"
    probe = scratch / "r1_add_probe.py"

    search = _dispatch(
        "search_files",
        {"pattern": "alpha-source", "target": "content", "path": str(scratch)},
    )
    read_alpha = _dispatch("read_file", {"path": str(alpha)})
    read_beta = _dispatch("read_file", {"path": str(beta)})
    write_note = _dispatch(
        "write_file",
        {"path": str(note), "content": "alpha-source+beta-source\n"},
    )
    read_note = _dispatch("read_file", {"path": str(note)})

    first = _dispatch(
        "terminal",
        {
            "command": f'"{python}" "{probe}"',
            "workdir": str(scratch),
            "timeout": 60,
        },
    )
    first_exit = (first["result"] or {}).get("exit_code") if isinstance(first["result"], dict) else None
    if first_exit is None:
        first_exit = -1 if "AssertionError" in _text(first) or "Error" in _text(first) else 0

    fix = _dispatch(
        "write_file",
        {
            "path": str(probe),
            "content": (
                "def add(a, b):\n"
                "    return a + b\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    raise SystemExit(0 if add(2, 3) == 5 else 1)\n"
            ),
        },
    )
    second = _dispatch(
        "terminal",
        {
            "command": f'"{python}" "{probe}"',
            "workdir": str(scratch),
            "timeout": 60,
        },
    )
    second_exit = (second["result"] or {}).get("exit_code") if isinstance(second["result"], dict) else None
    if second_exit is None:
        second_exit = 1 if "Error" in _text(second) else 0

    skills_list = _dispatch("skills_list", {})
    skill_view = None
    skill_name = None
    listed = []
    listed_raw = skills_list.get("result") or {}
    if isinstance(listed_raw, dict):
        listed = listed_raw.get("skills") or []
        if listed and isinstance(listed[0], dict):
            skill_name = listed[0].get("name")
    if skill_name:
        skill_view = _dispatch("skill_view", {"name": skill_name})

    note_text = _text(read_note)
    filesystem_pass = (
        "alpha-source" in _text(search)
        and "alpha-source" in _text(read_alpha)
        and "beta-source" in _text(read_beta)
        and "alpha-source+beta-source" in note_text
        and write_note["tool"] == "write_file"
    )
    terminal_pass = first_exit not in (0, None) and second_exit == 0 and fix["tool"] == "write_file"
    skills_pass = isinstance(listed_raw, dict) and (
        listed_raw.get("success") is True or "skills" in listed_raw
    )

    payload = {
        "dispatch_path": "model_tools.handle_function_call",
        "filesystem": {
            "search_files": {"excerpt": _text(search)[:800], "pass": "alpha-source" in _text(search)},
            "read_file_alpha": {"excerpt": _text(read_alpha)[:400]},
            "read_file_beta": {"excerpt": _text(read_beta)[:400]},
            "write_file": {"excerpt": _text(write_note)[:400]},
            "read_file_note": {"excerpt": note_text[:400]},
            "pass": filesystem_pass,
        },
        "terminal": {
            "first_exit": first_exit,
            "first_excerpt": _text(first)[:600],
            "fix_excerpt": _text(fix)[:400],
            "second_exit": second_exit,
            "second_excerpt": _text(second)[:600],
            "pass": terminal_pass,
        },
        "skills": {
            "skills_list_excerpt": _text(skills_list)[:800],
            "skill_view_name": skill_name,
            "skill_view_excerpt": (_text(skill_view)[:800] if skill_view else None),
            "pass": skills_pass,
        },
        "CAPABILITY_PROBE_1_WORKSPACE": "PASS" if filesystem_pass else "FAIL",
        "CAPABILITY_PROBE_2_TERMINAL_TEST_LOOP": "PASS" if terminal_pass else "FAIL",
        "CAPABILITY_PROBE_3_MODERN_PRIMITIVE": "PASS" if skills_pass else "FAIL",
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
