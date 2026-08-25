"""Dedicated telegram-ops profile contract for Developer Hermes.

Preparation only. This module does not start a live Telegram poller and
does not move the Railway token. The profile is a capability/configuration
boundary, not an OS or container sandbox.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any


PROFILE_NAME = "telegram-ops"
PROFILE_IS_OS_SANDBOX = False
TELEGRAM_PROFILE_IS_DEDICATED = True
APPROVALS_MODE = "manual"
CRON_MODE = "deny"
EGRESS_CLASS = "MESSAGING_PLATFORM"
EGRESS_ALLOWED_HOSTS = ("api.telegram.org",)
MEDIA_DOWNLOAD_SCOPE = "OUT_OF_SCOPE"
TRANSPORT = "LONG_POLLING"
PUBLIC_INBOUND_PORT = False
SENTINEL_NAME = ".r5-telegram-ops-seed"
SEED_VERSION = "telegram-ops-0b-v2"
PROFILE_POLICY = "READ_FIRST_WITH_APPROVAL_GATED_WRITES"
WRITE_APPROVAL_PLUGIN = "telegram-ops-write-approval"

# Upstream `file` is atomic. These schema members arrive with read_file.
FILE_TOOLSET_ATOMIC_WRITE_TOOLS = frozenset({"write_file", "patch"})
EXPLICIT_TOOLSETS = ("file",)
FORBIDDEN_TOOLSETS = frozenset(
    {
        "terminal",
        "delegation",
        "browser",
        "computer_use",
        "cronjob",
        "web",
        "skills",
        "memory",
        "hermes-telegram",
    }
)
DENIED_SLASH_COMMANDS = frozenset(
    {
        "yolo",
        "model",
        "reasoning",
        "cron",
        "tools",
        "toolsets",
        "skills",
        "learn",
        "memory",
        "restart",
        "platform",
        "sethome",
        "update",
        "reload",
        "reload-mcp",
        "reload-skills",
        "browser",
        "kanban",
        "curator",
        "blueprint",
        "suggestions",
        "background",
    }
)
USER_ALLOWED_COMMANDS = (
    "help",
    "whoami",
    "status",
    "profile",
    "approve",
    "deny",
    "new",
    "stop",
)
SLASH_ADMIN_SENTINEL = "0"
DM_ONLY_ALLOWED_CHATS = ("__dm_only__",)
SYNTHETIC_TOKEN_MARKERS = (
    "SYNTHETIC",
    "TEST_TOKEN",
    "DO_NOT_POLL",
    "000000000:",
)
LIVE_TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{20,}$")
PLACEHOLDER_TOKENS = frozenset(
    {
        "",
        "changeme",
        "your_token_here",
        "replace-me",
        "todo",
        "xxx",
    }
)

HERMES_BIN = "/opt/hermes/.venv/bin/hermes"
CONTAINER_PROFILE_HOME = "/opt/data/profiles/telegram-ops"
TOKEN_STORAGE_TARGET = f"{CONTAINER_PROFILE_HOME}/.env"
SEED_DIR = Path(__file__).resolve().parent / "profiles" / PROFILE_NAME

GATEWAY_START_ARGV = (HERMES_BIN, "-p", PROFILE_NAME, "gateway", "start")
GATEWAY_STATUS_ARGV = (HERMES_BIN, "-p", PROFILE_NAME, "gateway", "status")
GATEWAY_STOP_ARGV = (HERMES_BIN, "-p", PROFILE_NAME, "gateway", "stop")


def seed_paths() -> dict[str, Path]:
    return {
        "config": SEED_DIR / "config.yaml",
        "soul": SEED_DIR / "SOUL.md",
        "env_template": SEED_DIR / "env.template",
        "write_approval_plugin": SEED_DIR / "plugins" / WRITE_APPROVAL_PLUGIN,
    }


def load_write_approval_plugin():
    """Load the versioned profile plugin without installing it globally."""
    import importlib.util

    path = seed_paths()["write_approval_plugin"] / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "telegram_ops_write_approval_seed",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("telegram-ops write-approval plugin is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_seed_config_text() -> str:
    return seed_paths()["config"].read_text(encoding="utf-8")


def load_seed_config() -> dict[str, Any]:
    import yaml

    payload = yaml.safe_load(load_seed_config_text())
    if not isinstance(payload, dict):
        raise RuntimeError("telegram-ops config.yaml must be a mapping")
    return payload


def profile_home(hermes_home: Path) -> Path:
    return Path(hermes_home) / "profiles" / PROFILE_NAME


def token_env_path(hermes_home: Path) -> Path:
    return profile_home(hermes_home) / ".env"


def classify_telegram_token(value: str | None) -> str:
    """Classify a token without logging or returning the value."""
    raw = "" if value is None else str(value).strip().strip('"').strip("'")
    if raw.lower() in PLACEHOLDER_TOKENS:
        return "MISSING"
    if any(marker in raw for marker in SYNTHETIC_TOKEN_MARKERS):
        return "SYNTHETIC"
    if LIVE_TOKEN_RE.match(raw):
        return "LIVE_SHAPED"
    return "PLACEHOLDER"


def read_dotenv_names_and_token_class(path: Path) -> dict[str, str]:
    """Read a dotenv file. Returns names and token class, never the token."""
    names: list[str] = []
    token_class = "MISSING"
    if not path.is_file():
        return {"env_names": "", "token_class": token_class, "allowed_users_present": "NO"}
    allowed_users_present = "NO"
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        names.append(key)
        if key == "TELEGRAM_BOT_TOKEN":
            token_class = classify_telegram_token(value)
        if key == "TELEGRAM_ALLOWED_USERS" and value.strip().strip('"').strip("'"):
            allowed_users_present = "YES"
    return {
        "env_names": ",".join(sorted(names)),
        "token_class": token_class,
        "allowed_users_present": allowed_users_present,
    }


def _refresh_text_file(target: Path, text: str) -> bool:
    if target.exists() and target.read_text(encoding="utf-8") == text:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return True


def seed_telegram_ops_profile(hermes_home: Path) -> dict[str, str]:
    """Create or refresh the dedicated profile. Never overwrite a live .env."""
    dest = profile_home(hermes_home)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("sessions", "memories", "logs", "skills", "plugins"):
        (dest / name).mkdir(exist_ok=True)
    paths = seed_paths()
    wrote = []
    for source_key, dest_name in (
        ("config", "config.yaml"),
        ("soul", "SOUL.md"),
    ):
        if _refresh_text_file(dest / dest_name, paths[source_key].read_text(encoding="utf-8")):
            wrote.append(dest_name)
    plugin_src = paths["write_approval_plugin"]
    plugin_dest = dest / "plugins" / WRITE_APPROVAL_PLUGIN
    if plugin_src.is_dir():
        shutil.copytree(plugin_src, plugin_dest, dirs_exist_ok=True)
        wrote.append(f"plugins/{WRITE_APPROVAL_PLUGIN}")
    env_target = dest / ".env"
    if not env_target.exists():
        env_target.write_text(paths["env_template"].read_text(encoding="utf-8"), encoding="utf-8")
        try:
            os.chmod(env_target, 0o600)
        except OSError:
            pass
        wrote.append(".env")
    sentinel = dest / SENTINEL_NAME
    if _refresh_text_file(sentinel, SEED_VERSION + "\n"):
        wrote.append(SENTINEL_NAME)
    return {
        "PROFILE_NAME": PROFILE_NAME,
        "PROFILE_HOME": str(dest),
        "SEEDED": "YES",
        "WROTE": ",".join(wrote) if wrote else "NONE",
        "TOKEN_CLASS": read_dotenv_names_and_token_class(env_target)["token_class"],
        "PROFILE_POLICY": PROFILE_POLICY,
    }


def gateway_lifecycle_argv(action: str) -> tuple[str, ...]:
    mapping = {
        "up": GATEWAY_START_ARGV,
        "status": GATEWAY_STATUS_ARGV,
        "down": GATEWAY_STOP_ARGV,
    }
    if action not in mapping:
        raise ValueError(f"unknown telegram lifecycle action {action!r}")
    return mapping[action]


def may_start_gateway(token_class: str) -> tuple[bool, str]:
    """PREP may start only when polling cannot steal the live identity."""
    if token_class == "LIVE_SHAPED":
        return False, "REFUSE_LIVE_TOKEN"
    if token_class == "SYNTHETIC":
        return True, "SYNTHETIC_OK"
    if token_class == "MISSING":
        return True, "NO_TOKEN_NO_POLL"
    return False, "REFUSE_UNKNOWN_TOKEN"


def profile_invariants(config: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = config if config is not None else load_seed_config()
    approvals = payload.get("approvals") or {}
    agent = payload.get("agent") or {}
    platforms = payload.get("platforms") or {}
    telegram = platforms.get("telegram") or {}
    platform_toolsets = payload.get("platform_toolsets") or {}
    disabled = list(agent.get("disabled_toolsets") or [])
    final_cap = list(agent.get("final_allowed_toolsets") or [])
    telegram_tools = list(platform_toolsets.get("telegram") or [])
    return {
        "PROFILE_NAME": PROFILE_NAME,
        "PROFILE_IS_OS_SANDBOX": PROFILE_IS_OS_SANDBOX,
        "TELEGRAM_PROFILE_IS_DEDICATED": TELEGRAM_PROFILE_IS_DEDICATED,
        "APPROVALS_MODE": approvals.get("mode"),
        "CRON_MODE": approvals.get("cron_mode"),
        "EXPLICIT_TOOLSETS": tuple(telegram_tools),
        "FINAL_ALLOWED_TOOLSETS": tuple(final_cap),
        "DISABLED_TOOLSETS": tuple(disabled),
        "YOLO_IN_USER_COMMANDS": "yolo" in {
            str(item).lstrip("/").lower()
            for item in (telegram.get("user_allowed_commands") or [])
        },
        "ALLOW_ADMIN_FROM": tuple(str(item) for item in (telegram.get("allow_admin_from") or [])),
        "USER_ALLOWED_COMMANDS": tuple(telegram.get("user_allowed_commands") or []),
        "ALLOWED_CHATS": tuple(telegram.get("allowed_chats") or []),
        "GROUP_ALLOWED_CHATS": tuple(telegram.get("group_allowed_chats") or []),
        "UNAUTHORIZED_DM_BEHAVIOR": telegram.get("unauthorized_dm_behavior"),
        "GUEST_MODE": bool(telegram.get("guest_mode")),
        "REQUIRE_MENTION": bool(telegram.get("require_mention")),
        "PROFILE_POLICY": PROFILE_POLICY,
        "WRITE_APPROVAL_PLUGIN": WRITE_APPROVAL_PLUGIN,
        "WRITE_APPROVAL_PLUGIN_ENABLED": WRITE_APPROVAL_PLUGIN
        in list((payload.get("plugins") or {}).get("enabled") or []),
    }
