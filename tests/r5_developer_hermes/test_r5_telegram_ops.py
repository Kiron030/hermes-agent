"""Focused 0B PREP invariants for the dedicated telegram-ops profile."""

from __future__ import annotations

import ast
from pathlib import Path

from r5_developer_hermes.container.contract import (
    AUTHORITY_ENV_NAMES,
    ENV_ALLOWLIST,
    MODEL_KEY_ALLOWLIST,
    docker_run_argv,
)
from r5_developer_hermes.container.egress import host as egress
from r5_developer_hermes.container import telegram_ops as tg
from r5_developer_hermes.harness import REPO_ROOT
from toolsets import resolve_toolset


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"
LAUNCHER = CONTAINER_DIR / "launch-developer-hermes.ps1"
SEED_DIR = CONTAINER_DIR / "profiles" / "telegram-ops"


def _resolved_telegram_tools() -> set[str]:
    tools: set[str] = set()
    for name in tg.EXPLICIT_TOOLSETS:
        tools.update(resolve_toolset(name))
    return tools


def test_telegram_profile_is_dedicated_and_not_default() -> None:
    default = (CONTAINER_DIR / "seed_home.py").read_text(encoding="utf-8")
    seed = tg.load_seed_config()
    assert tg.PROFILE_NAME == "telegram-ops"
    assert tg.TELEGRAM_PROFILE_IS_DEDICATED is True
    assert tg.PROFILE_IS_OS_SANDBOX is False
    assert 'mode: off' in default
    assert seed["approvals"]["mode"] == "manual"
    assert seed["approvals"]["mode"] != "off"
    assert "profiles/telegram-ops" in tg.TOKEN_STORAGE_TARGET
    assert tg.token_env_path(Path("/opt/data")) == Path("/opt/data/profiles/telegram-ops/.env")


def test_default_developer_profile_policy_is_unchanged() -> None:
    default = (CONTAINER_DIR / "seed_home.py").read_text(encoding="utf-8")
    assert "mode: off" in default
    assert "cron_mode: deny" in default
    assert "- terminal" in default
    assert "- file" in default
    assert "TELEGRAM_BOT_TOKEN" not in default
    assert 'PROFILE_NAME = "telegram-ops"' not in default


def test_approvals_manual_and_cron_denied() -> None:
    invariants = tg.profile_invariants()
    assert invariants["APPROVALS_MODE"] == "manual"
    assert invariants["CRON_MODE"] == "deny"
    assert invariants["APPROVALS_MODE"] != "off"


def test_toolset_is_explicit_file_only_and_excludes_dangerous_sets() -> None:
    invariants = tg.profile_invariants()
    assert invariants["EXPLICIT_TOOLSETS"] == ("file",)
    assert invariants["FINAL_ALLOWED_TOOLSETS"] == ("file",)
    disabled = set(invariants["DISABLED_TOOLSETS"])
    for name in tg.FORBIDDEN_TOOLSETS:
        assert name in disabled or name == "hermes-telegram"
    assert "hermes-telegram" not in invariants["EXPLICIT_TOOLSETS"]
    tools = _resolved_telegram_tools()
    assert "read_file" in tools
    assert "search_files" in tools
    assert "terminal" not in tools
    assert "browser_navigate" not in tools
    assert "computer_use" not in tools
    assert "cronjob" not in tools
    assert "delegate_task" not in tools or "delegation" in disabled


def test_terminal_write_git_and_browser_surfaces() -> None:
    tools = _resolved_telegram_tools()
    assert "terminal" not in tools
    assert "execute_code" not in tools
    assert "git_commit" not in tools
    assert "git_push" not in tools
    assert not any(name.startswith("browser_") for name in tools)
    assert "computer_use" not in tools
    assert "cronjob" not in tools
    # Upstream `file` is atomic. write_file/patch are schema members, not a
    # separate write toolset, and cannot run autonomously under manual approvals.
    assert tg.FILE_TOOLSET_ATOMIC_WRITE_TOOLS <= tools
    assert tg.profile_invariants()["APPROVALS_MODE"] == "manual"


def test_yolo_and_posture_commands_are_unavailable() -> None:
    invariants = tg.profile_invariants()
    allowed = {str(item).lstrip("/").lower() for item in invariants["USER_ALLOWED_COMMANDS"]}
    assert "yolo" not in allowed
    assert invariants["YOLO_IN_USER_COMMANDS"] is False
    for command in tg.DENIED_SLASH_COMMANDS:
        assert command not in allowed
    assert invariants["ALLOW_ADMIN_FROM"] == (tg.SLASH_ADMIN_SENTINEL,)
    assert "approve" in allowed
    assert "deny" in allowed


def test_authorization_defaults_deny_and_is_dm_only() -> None:
    invariants = tg.profile_invariants()
    template = (SEED_DIR / "env.template").read_text(encoding="utf-8")
    assert invariants["ALLOWED_CHATS"] == tg.DM_ONLY_ALLOWED_CHATS
    assert invariants["GROUP_ALLOWED_CHATS"] == ()
    assert invariants["GUEST_MODE"] is False
    assert invariants["UNAUTHORIZED_DM_BEHAVIOR"] == "ignore"
    assert "TELEGRAM_ALLOW_ALL_USERS=" in template
    assert "GATEWAY_ALLOW_ALL_USERS=" in template
    assert "must remain unset" in template.lower() or "Must remain unset" in template
    assert "TELEGRAM_WEBHOOK_URL=" in template
    assert "TELEGRAM_GROUP_ALLOWED_USERS=" in template
    classify = tg.read_dotenv_names_and_token_class(SEED_DIR / "env.template")
    assert classify["token_class"] == "MISSING"
    assert classify["allowed_users_present"] == "NO"


def test_empty_or_missing_allowed_users_fails_closed() -> None:
    assert tg.classify_telegram_token(None) == "MISSING"
    assert tg.classify_telegram_token("") == "MISSING"
    assert tg.classify_telegram_token("   ") == "MISSING"
    seeded = tg.read_dotenv_names_and_token_class(SEED_DIR / "env.template")
    assert seeded["allowed_users_present"] == "NO"
    assert seeded["token_class"] == "MISSING"


def test_token_is_not_committed_or_forwarded() -> None:
    raw_tree = (SEED_DIR / "env.template").read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN=" in raw_tree
    assert not any(
        line.split("=", 1)[1].strip()
        for line in raw_tree.splitlines()
        if line.startswith("TELEGRAM_BOT_TOKEN=")
    )
    assert "TELEGRAM_BOT_TOKEN" not in ENV_ALLOWLIST
    assert "TELEGRAM_BOT_TOKEN" not in MODEL_KEY_ALLOWLIST
    assert "TELEGRAM_BOT_TOKEN" not in AUTHORITY_ENV_NAMES
    argv = " ".join(docker_run_argv())
    assert "TELEGRAM_BOT_TOKEN" not in argv
    repo_hits = list(REPO_ROOT.glob("**/.env"))
    assert not any("telegram-ops" in str(path) for path in repo_hits)


def test_token_classification_never_starts_live_polling() -> None:
    assert tg.classify_telegram_token("000000000:SYNTHETIC_TEST_TOKEN_DO_NOT_POLL") == "SYNTHETIC"
    assert tg.classify_telegram_token("123456789:AAHfakeLiveShapedTokenValueXXX") == "LIVE_SHAPED"
    allowed, reason = tg.may_start_gateway("LIVE_SHAPED")
    assert allowed is False
    assert reason == "REFUSE_LIVE_TOKEN"
    assert tg.may_start_gateway("MISSING") == (True, "NO_TOKEN_NO_POLL")
    assert tg.may_start_gateway("SYNTHETIC") == (True, "SYNTHETIC_OK")


def test_seed_writes_profile_without_a_live_token(tmp_path: Path) -> None:
    result = tg.seed_telegram_ops_profile(tmp_path)
    home = tmp_path / "profiles" / "telegram-ops"
    assert result["SEEDED"] == "YES"
    assert result["TOKEN_CLASS"] == "MISSING"
    assert (home / "config.yaml").is_file()
    assert (home / "SOUL.md").is_file()
    assert (home / ".env").is_file()
    assert (home / "sessions").is_dir()
    assert (home / "memories").is_dir()
    assert "not an os or container sandbox" in (home / "SOUL.md").read_text(encoding="utf-8").lower()
    existing = home / ".env"
    existing.write_text("TELEGRAM_BOT_TOKEN=000000000:SYNTHETIC_TEST_TOKEN_DO_NOT_POLL\n", encoding="utf-8")
    again = tg.seed_telegram_ops_profile(tmp_path)
    assert again["TOKEN_CLASS"] == "SYNTHETIC"
    assert "keep" in existing.read_text(encoding="utf-8") or "SYNTHETIC" in existing.read_text(encoding="utf-8")


def test_lifecycle_commands_are_deterministic_and_profile_scoped() -> None:
    assert tg.gateway_lifecycle_argv("up") == tg.GATEWAY_START_ARGV
    assert tg.gateway_lifecycle_argv("status") == tg.GATEWAY_STATUS_ARGV
    assert tg.gateway_lifecycle_argv("down") == tg.GATEWAY_STOP_ARGV
    for argv in (tg.GATEWAY_START_ARGV, tg.GATEWAY_STATUS_ARGV, tg.GATEWAY_STOP_ARGV):
        assert argv[0] == tg.HERMES_BIN
        assert argv[1:3] == ("-p", "telegram-ops")
        assert argv[3] == "gateway"
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "telegram-up" in text
    assert "telegram-status" in text
    assert "telegram-down" in text
    launch_src = (CONTAINER_DIR / "launch.py").read_text(encoding="utf-8")
    tree = ast.parse(launch_src)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"telegram_up", "telegram_status", "telegram_down"} <= names


def test_messaging_platform_is_the_only_new_named_host() -> None:
    classes = egress.load_policy()["classes"]
    assert "MESSAGING_PLATFORM" in classes
    entry = classes["MESSAGING_PLATFORM"]
    assert entry["decision"] == "ALLOW"
    assert entry["hosts"] == ["api.telegram.org"]
    assert "*" not in "".join(entry["hosts"])
    approved = {
        host
        for name, hosts in egress.approved_destinations().items()
        for host in hosts
        if name == "MESSAGING_PLATFORM"
    }
    assert approved == {"api.telegram.org"}
    assert classes["OTHER_ARBITRARY_NETWORK"]["decision"] == "DENY"
    assert classes["OTHER_ARBITRARY_NETWORK"]["hosts"] == []


def test_developer_launch_stays_internal_with_no_public_inbound() -> None:
    argv = docker_run_argv()
    joined = " ".join(argv)
    assert "--publish" not in argv
    assert "-p" not in argv
    assert argv[argv.index("--network") + 1] == egress.INTERNAL_NETWORK
    assert argv[argv.index("--network") + 1] != "host"
    assert "r5-desktop-ingress" not in joined
    assert "--network" in argv
    assert joined.count("--network") == 1


def test_token_never_appears_in_seed_or_docs_as_a_value() -> None:
    for path in (
        SEED_DIR / "config.yaml",
        SEED_DIR / "SOUL.md",
        SEED_DIR / "env.template",
        CONTAINER_DIR / "telegram_ops.py",
        CONTAINER_DIR / "seed_home.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert not tg.LIVE_TOKEN_RE.search(text)


def test_operator_and_railway_sources_are_untouched_by_this_module() -> None:
    assert not (CONTAINER_DIR / "telegram_ops.py").read_text(encoding="utf-8").count(
        "powerunits_telegram_overlays"
    )
    assert "first_safe_v1" not in (SEED_DIR / "config.yaml").read_text(encoding="utf-8")
    railway = REPO_ROOT / "docker" / "railway_gateway.sh"
    overlays = REPO_ROOT / "powerunits_telegram_overlays.py"
    assert railway.is_file()
    assert overlays.is_file()
