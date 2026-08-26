"""Dedicated telegram-ops profile contract for Developer Hermes.

Internal profile name stays ``telegram-ops``. Display and role are
Developer Remote: a second BotFather identity for local Developer Hermes.
The Railway Operator Telegram bot is a different identity and is not
modified here.

Ordinary ``telegram-up`` stays fail-closed for LIVE_SHAPED tokens.
Live polling requires an explicit activation intent.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any


PROFILE_NAME = "telegram-ops"
DISPLAY_NAME = "Developer Remote"
PROFILE_ROLE = "DEVELOPER_TELEGRAM"
ARCHITECTURE = "TWO_BOT"
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
SEED_VERSION = "telegram-ops-0c-v1"
PROFILE_POLICY = "READ_FIRST_WITH_APPROVAL_GATED_WRITES"
WRITE_APPROVAL_PLUGIN = "telegram-ops-write-approval"
NUMERIC_USER_RE = re.compile(r"^\d{5,20}$")
TRUTHY_ENV = frozenset({"1", "true", "yes", "on"})
ACTIVATION_STDIN_TOKEN_KEY = "telegram_bot_token"
ACTIVATION_STDIN_USER_KEY = "telegram_allowed_users"

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
LIVE_TOKEN_SHAPE_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")
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
CONTAINER_GATEWAY_LOG = f"{CONTAINER_PROFILE_HOME}/logs/gateway.log"
INTENDED_GATEWAY_USER = "hermes"
INTENDED_GATEWAY_UID = 10000
INTENDED_GATEWAY_GID = 10000
SEED_DIR = Path(__file__).resolve().parent / "profiles" / PROFILE_NAME

# Docker-native primitive. Do not use ``gateway start`` (systemd/launchd).
GATEWAY_RUN_ARGV = (HERMES_BIN, "-p", PROFILE_NAME, "gateway", "run")
GATEWAY_STATUS_ARGV = (HERMES_BIN, "-p", PROFILE_NAME, "gateway", "status")
DOWN_MECHANISM = "PROFILE_PID_STOP"


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


def _dotenv_value(value: str) -> str:
    return str(value).strip().strip('"').strip("'")


def _is_truthy_env(value: str) -> bool:
    return _dotenv_value(value).lower() in TRUTHY_ENV


def classify_allowed_users(value: str | None) -> str:
    """Return PRESENT shape only. Never echoes the identifier."""
    raw = _dotenv_value("" if value is None else str(value))
    if not raw:
        return "MISSING"
    if "," in raw or not NUMERIC_USER_RE.match(raw):
        return "INVALID"
    return "NUMERIC_SINGLE"


def read_dotenv_names_and_token_class(path: Path) -> dict[str, str]:
    """Read a dotenv file. Returns names and token class, never the token."""
    names: list[str] = []
    token_class = "MISSING"
    if not path.is_file():
        return {
            "env_names": "",
            "token_class": token_class,
            "allowed_users_present": "NO",
            "allowed_users_class": "MISSING",
            "allow_all_set": "NO",
            "webhook_set": "NO",
        }
    allowed_users_present = "NO"
    allowed_users_class = "MISSING"
    allow_all_set = "NO"
    webhook_set = "NO"
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
        if key == "TELEGRAM_ALLOWED_USERS":
            allowed_users_class = classify_allowed_users(value)
            if allowed_users_class == "NUMERIC_SINGLE":
                allowed_users_present = "YES"
        if key in {"TELEGRAM_ALLOW_ALL_USERS", "GATEWAY_ALLOW_ALL_USERS"} and _is_truthy_env(value):
            allow_all_set = "YES"
        if key == "TELEGRAM_WEBHOOK_URL" and _dotenv_value(value):
            webhook_set = "YES"
    return {
        "env_names": ",".join(sorted(names)),
        "token_class": token_class,
        "allowed_users_present": allowed_users_present,
        "allowed_users_class": allowed_users_class,
        "allow_all_set": allow_all_set,
        "webhook_set": webhook_set,
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
    try:
        dest.chmod(0o700)
    except OSError:
        pass
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
    if action == "up":
        return GATEWAY_RUN_ARGV
    if action == "status":
        return GATEWAY_STATUS_ARGV
    if action == "down":
        raise ValueError("telegram-down uses profile-specific PID stop, not gateway stop")
    raise ValueError(f"unknown telegram lifecycle action {action!r}")


def looks_like_hermes_serve_command(command: str | None) -> bool:
    lowered = "" if command is None else str(command).lower()
    return "hermes serve" in lowered or "hermes_cli.main serve" in lowered


def looks_like_telegram_ops_gateway_command(command: str | None) -> bool:
    """True only for ``hermes -p telegram-ops gateway run``. Never hermes serve."""
    lowered = "" if command is None else str(command).lower().replace("\x00", " ")
    if looks_like_hermes_serve_command(lowered):
        return False
    if any(
        token in lowered
        for token in (
            "gateway start",
            "gateway status",
            "gateway stop",
            "gateway install",
            "gateway uninstall",
        )
    ):
        return False
    has_profile = (
        f"-p {PROFILE_NAME}" in lowered or f"--profile {PROFILE_NAME}" in lowered
    )
    return has_profile and "gateway run" in lowered


def parse_upstream_gateway_status(status_text: str | None) -> str:
    """Interpret ``hermes gateway status`` text. Exit code 0 is not evidence."""
    lowered = "" if status_text is None else str(status_text).lower()
    if "gateway is not running" in lowered:
        return "STOPPED"
    if "gateway is running" in lowered:
        return "RUNNING"
    return "STOPPED"


def classify_live_token(token_class: str | None) -> str:
    return "PRESENT" if token_class == "LIVE_SHAPED" else "MISSING"


def classify_gateway_user(uid: int | None, user: str | None = None) -> str:
    if uid == INTENDED_GATEWAY_UID or user == INTENDED_GATEWAY_USER:
        return INTENDED_GATEWAY_USER
    if uid is None and not user:
        return "NONE"
    return "other"


def classify_live_polling(
    *,
    token_class: str,
    process_running: bool,
    upstream_status: str | None = None,
) -> str:
    """YES only with a live telegram-ops gateway process. Token alone is not enough."""
    if token_class != "LIVE_SHAPED":
        return "NO"
    if not process_running:
        return "NO"
    if upstream_status is not None and upstream_status != "RUNNING":
        return "NO"
    return "YES"


def status_agreement(process_status: str, upstream_status: str) -> str:
    return "YES" if process_status == upstream_status else "NO"


def redact_sensitive_text(text: str | None) -> str:
    """Strip token-shaped values and allowlist user ids from helper output."""
    raw = "" if text is None else str(text)
    redacted = LIVE_TOKEN_SHAPE_RE.sub("[REDACTED_TOKEN]", raw)
    redacted = re.sub(
        r"(TELEGRAM_ALLOWED_USERS\s*=\s*)\d{5,20}",
        r"\1[REDACTED_USER]",
        redacted,
        flags=re.IGNORECASE,
    )
    return redacted


def may_start_gateway(token_class: str) -> tuple[bool, str]:
    """Ordinary telegram-up stays fail-closed for live-shaped tokens."""
    if token_class == "LIVE_SHAPED":
        return False, "REFUSE_LIVE_TOKEN"
    if token_class == "SYNTHETIC":
        return True, "SYNTHETIC_OK"
    if token_class == "MISSING":
        return True, "NO_TOKEN_NO_POLL"
    return False, "REFUSE_UNKNOWN_TOKEN"


def may_start_live_gateway(
    token_class: str,
    *,
    live_activation: bool,
    allowed_users_present: str = "NO",
    allow_all_set: str = "NO",
    webhook_set: str = "NO",
) -> tuple[bool, str]:
    """Start live polling only with explicit human intent and a closed allowlist."""
    if allow_all_set == "YES":
        return False, "REFUSE_ALLOW_ALL"
    if webhook_set == "YES":
        return False, "REFUSE_WEBHOOK"
    if token_class == "LIVE_SHAPED":
        if not live_activation:
            return False, "REFUSE_LIVE_TOKEN"
        if allowed_users_present != "YES":
            return False, "REFUSE_MISSING_ALLOWED_USER"
        return True, "LIVE_ACTIVATION_OK"
    if live_activation:
        return False, "REFUSE_NON_LIVE_FOR_ACTIVATION"
    return may_start_gateway(token_class)


def parse_activation_payload(payload: Any) -> dict[str, str]:
    """Accept only the two secret fields. Never return them in status output."""
    if not isinstance(payload, dict):
        raise ValueError("REFUSE_ACTIVATION_PAYLOAD")
    token = payload.get(ACTIVATION_STDIN_TOKEN_KEY)
    user = payload.get(ACTIVATION_STDIN_USER_KEY)
    if token is None or user is None:
        raise ValueError("REFUSE_ACTIVATION_PAYLOAD")
    extra = sorted(
        str(key)
        for key in payload
        if key not in {ACTIVATION_STDIN_TOKEN_KEY, ACTIVATION_STDIN_USER_KEY}
    )
    if extra:
        raise ValueError("REFUSE_ACTIVATION_EXTRA_FIELDS")
    return {
        ACTIVATION_STDIN_TOKEN_KEY: str(token),
        ACTIVATION_STDIN_USER_KEY: str(user),
    }


def apply_live_secrets(hermes_home: Path, payload: dict[str, Any]) -> dict[str, str]:
    """Write the Developer token and one numeric user into the profile .env.

    Values are accepted only from a parsed stdin payload. The return value
    never includes the token or the user identifier.
    """
    dest = profile_home(hermes_home)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        dest.chmod(0o700)
    except OSError:
        pass
    env_target = dest / ".env"
    existing = read_dotenv_names_and_token_class(env_target)
    if (
        existing["token_class"] == "LIVE_SHAPED"
        and existing["allowed_users_present"] == "YES"
    ):
        return {
            "APPLIED": "NO",
            "REASON": "REFUSE_OVERWRITE_EXISTING_LIVE_SECRET",
            **{key: existing[key] for key in (
                "token_class",
                "allowed_users_present",
                "allowed_users_class",
                "allow_all_set",
                "webhook_set",
            )},
        }
    parsed = parse_activation_payload(payload)
    token_class = classify_telegram_token(parsed[ACTIVATION_STDIN_TOKEN_KEY])
    users_class = classify_allowed_users(parsed[ACTIVATION_STDIN_USER_KEY])
    if token_class != "LIVE_SHAPED":
        return {
            "APPLIED": "NO",
            "REASON": "REFUSE_NON_LIVE_TOKEN",
            "token_class": token_class,
            "allowed_users_present": "NO",
            "allowed_users_class": users_class,
            "allow_all_set": "NO",
            "webhook_set": "NO",
        }
    if users_class != "NUMERIC_SINGLE":
        return {
            "APPLIED": "NO",
            "REASON": "REFUSE_NON_NUMERIC_USER",
            "token_class": token_class,
            "allowed_users_present": "NO",
            "allowed_users_class": users_class,
            "allow_all_set": "NO",
            "webhook_set": "NO",
        }
    text = (
        "# Developer Remote Telegram secrets. Never commit this file.\n"
        "# Operator Railway token is a different identity and is not stored here.\n"
        f"TELEGRAM_BOT_TOKEN={parsed[ACTIVATION_STDIN_TOKEN_KEY]}\n"
        f"TELEGRAM_ALLOWED_USERS={_dotenv_value(parsed[ACTIVATION_STDIN_USER_KEY])}\n"
        "# TELEGRAM_ALLOW_ALL_USERS=\n"
        "# GATEWAY_ALLOW_ALL_USERS=\n"
        "# TELEGRAM_WEBHOOK_URL=\n"
        "# TELEGRAM_GROUP_ALLOWED_USERS=\n"
        "# TELEGRAM_GROUP_ALLOWED_CHATS=\n"
    )
    env_target.write_text(text, encoding="utf-8")
    try:
        os.chmod(env_target, 0o600)
    except OSError:
        pass
    state = read_dotenv_names_and_token_class(env_target)
    return {
        "APPLIED": "YES",
        "REASON": "LIVE_SECRET_STORED",
        "TOKEN_STORAGE": TOKEN_STORAGE_TARGET,
        **{key: state[key] for key in (
            "token_class",
            "allowed_users_present",
            "allowed_users_class",
            "allow_all_set",
            "webhook_set",
        )},
    }


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
        "DISPLAY_NAME": DISPLAY_NAME,
        "PROFILE_ROLE": PROFILE_ROLE,
        "ARCHITECTURE": ARCHITECTURE,
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
