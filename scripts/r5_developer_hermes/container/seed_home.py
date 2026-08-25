#!/usr/bin/env python3
"""Seed isolated persistent HERMES_HOME. No host profile, no production secrets."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data"))
BUNDLED_SKILLS = Path("/opt/hermes/skills")
VERSIONED_SKILL = Path("/opt/r5-developer/skills/r5-dev-skill")
SKILLS_SYNC = Path("/opt/hermes/tools/skills_sync.py")
VENV_PYTHON = Path("/opt/hermes/.venv/bin/python")
SENTINEL = HERMES_HOME / ".r5-dx-sentinel"
GITCONFIG = HERMES_HOME / ".gitconfig"

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
try:
    from r5_developer_hermes.container.telegram_ops import seed_telegram_ops_profile
except ImportError:
    from telegram_ops import seed_telegram_ops_profile  # type: ignore

CONFIG = """model: gpt-5.6-terra
provider: openai-api
security:
  allow_lazy_installs: false
agent:
  reasoning_effort: medium
  disabled_toolsets:
    - delegation
    - browser
    - computer_use
    - cronjob
platform_toolsets:
  cli:
    - file
    - terminal
    - web
    - skills
    - todo
    - memory
approvals:
  mode: off
  cron_mode: deny
"""

SOUL = """# R5 developer Hermes

POWERFUL_IN_WORKSPACE. NOT_POWERFUL_IN_PRODUCTION.
Ordinary workspace edits do not require micro-approvals.
Do not deploy. Do not push to main. Do not merge.
Do not use host credentials. Do not reach production.
"""

GITCONFIG_TEXT = """[user]
    name = R5 Developer Hermes
    email = r5-developer-hermes@local
[credential]
    helper =
[safe]
    directory = /workspace/hermes-agent
    directory = /workspace/EU-PP-Database
"""


def _write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    HERMES_HOME.mkdir(parents=True, exist_ok=True)
    try:
        HERMES_HOME.chmod(0o755)
    except OSError:
        pass
    for name in ("sessions", "skills", "memories", "logs", "plans"):
        (HERMES_HOME / name).mkdir(exist_ok=True)
    _write_if_missing(HERMES_HOME / "config.yaml", CONFIG)
    _write_if_missing(HERMES_HOME / "SOUL.md", SOUL)
    if not GITCONFIG.exists():
        GITCONFIG.write_text(GITCONFIG_TEXT, encoding="utf-8")
    dest_skill = HERMES_HOME / "skills" / "r5-dev-skill"
    if VERSIONED_SKILL.is_dir() and not (dest_skill / "SKILL.md").is_file():
        shutil.copytree(VERSIONED_SKILL, dest_skill, dirs_exist_ok=True)
    if VENV_PYTHON.is_file() and SKILLS_SYNC.is_file() and BUNDLED_SKILLS.is_dir():
        subprocess.run(
            [str(VENV_PYTHON), str(SKILLS_SYNC)],
            check=False,
            env={
                **os.environ,
                "HERMES_HOME": str(HERMES_HOME),
                "HOME": str(HERMES_HOME),
            },
        )
    seed_telegram_ops_profile(HERMES_HOME)
    SENTINEL.write_text("R5_DEVELOPER_DX_PERSISTENCE_SENTINEL\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
