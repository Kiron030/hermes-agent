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
    assert tg.DISPLAY_NAME == "Developer Remote"
    assert tg.PROFILE_ROLE == "DEVELOPER_TELEGRAM"
    assert tg.ARCHITECTURE == "TWO_BOT"
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
    assert "telegram-ops-write-approval" not in default


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
    # Upstream `file` is atomic. write_file/patch are callable schema members.
    # They are approval-gated by the profile plugin, not structurally absent.
    assert tg.FILE_TOOLSET_ATOMIC_WRITE_TOOLS <= tools
    invariants = tg.profile_invariants()
    assert invariants["APPROVALS_MODE"] == "manual"
    assert invariants["PROFILE_POLICY"] == "READ_FIRST_WITH_APPROVAL_GATED_WRITES"
    assert invariants["WRITE_APPROVAL_PLUGIN_ENABLED"] is True


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
    live_ok, live_reason = tg.may_start_live_gateway(
        "LIVE_SHAPED",
        live_activation=True,
        allowed_users_present="YES",
    )
    assert live_ok is True
    assert live_reason == "LIVE_ACTIVATION_OK"
    assert tg.may_start_live_gateway(
        "LIVE_SHAPED",
        live_activation=False,
        allowed_users_present="YES",
    ) == (False, "REFUSE_LIVE_TOKEN")
    assert tg.may_start_live_gateway(
        "LIVE_SHAPED",
        live_activation=True,
        allowed_users_present="NO",
    ) == (False, "REFUSE_MISSING_ALLOWED_USER")
    assert tg.may_start_live_gateway(
        "LIVE_SHAPED",
        live_activation=True,
        allowed_users_present="YES",
        allow_all_set="YES",
    ) == (False, "REFUSE_ALLOW_ALL")
    assert tg.may_start_live_gateway(
        "LIVE_SHAPED",
        live_activation=True,
        allowed_users_present="YES",
        webhook_set="YES",
    ) == (False, "REFUSE_WEBHOOK")


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
    soul = (home / "SOUL.md").read_text(encoding="utf-8").lower()
    assert "not an os or container sandbox" in soul
    assert "developer remote" in soul
    assert "railway operator" in soul
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
    assert {"telegram_up", "telegram_status", "telegram_down", "telegram_activate"} <= names
    assert "telegram-activate" in text
    assert "--i-understand-this-starts-the-developer-telegram-bot" in launch_src
    assert "ACTIVATE-DEVELOPER-TELEGRAM" in text
    assert "Read-Host 'Developer Telegram bot token' -AsSecureString" in text
    assert "telegram_bot_token" in text
    assert "--token" not in text


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
    plugin_dir = SEED_DIR / "plugins" / "telegram-ops-write-approval"
    for path in (
        SEED_DIR / "config.yaml",
        SEED_DIR / "SOUL.md",
        SEED_DIR / "env.template",
        plugin_dir / "plugin.yaml",
        plugin_dir / "__init__.py",
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


def _reset_hermes_config_caches() -> None:
    from hermes_cli import config as config_mod
    from model_tools import _clear_tool_defs_cache

    config_mod._LOAD_CONFIG_CACHE.clear()
    config_mod._RAW_CONFIG_CACHE.clear()
    _clear_tool_defs_cache()


def _dispatch_gated_file_action(
    monkeypatch,
    tool_name: str,
    args: dict,
    *,
    approved: bool | None,
) -> tuple[str, str]:
    """Same gate as tool_executor: plugin directive, then execute only if clear."""
    plugin = tg.load_write_approval_plugin()

    def fake_invoke(hook_name, **kwargs):
        if hook_name != "pre_tool_call":
            return []
        result = plugin.pre_tool_call(
            tool_name=kwargs.get("tool_name", ""),
            args=kwargs.get("args") or {},
        )
        return [result] if result else []

    monkeypatch.setattr("hermes_cli.plugins.invoke_hook", fake_invoke)
    if approved is None:
        monkeypatch.setattr(
            "tools.approval.request_tool_approval",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no approval presented")),
        )
    else:
        monkeypatch.setattr(
            "tools.approval.request_tool_approval",
            lambda *a, **k: {
                "approved": approved,
                "message": None if approved else "denied",
            },
        )
    from hermes_cli.plugins import resolve_pre_tool_block

    block = resolve_pre_tool_block(tool_name, args)
    if block is not None:
        return "blocked", block
    from tools.file_tools import patch_tool, write_file_tool

    if tool_name == "write_file":
        return "executed", write_file_tool(args["path"], args["content"])
    return "executed", patch_tool(
        mode="replace",
        path=args["path"],
        old_string=args.get("old_string"),
        new_string=args.get("new_string"),
    )


def test_seed_installs_write_approval_plugin(tmp_path: Path) -> None:
    tg.seed_telegram_ops_profile(tmp_path)
    home = tmp_path / "profiles" / "telegram-ops"
    plugin = home / "plugins" / tg.WRITE_APPROVAL_PLUGIN
    assert (plugin / "plugin.yaml").is_file()
    assert (plugin / "__init__.py").is_file()
    seeded = (home / "config.yaml").read_text(encoding="utf-8")
    assert tg.WRITE_APPROVAL_PLUGIN in seeded
    assert "READ_FIRST_WITH_APPROVAL_GATED_WRITES" in (SEED_DIR / "config.yaml").read_text(
        encoding="utf-8"
    )


def test_write_without_approval_does_not_mutate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    fixture = tmp_path / "disposable-approval-fixture.txt"
    original = b"keep-original-bytes\n"
    fixture.write_bytes(original)
    status, detail = _dispatch_gated_file_action(
        monkeypatch,
        "write_file",
        {"path": str(fixture), "content": "mutated-without-approval\n"},
        approved=None,
    )
    assert status == "blocked"
    assert "approval" in detail.lower() or "blocked" in detail.lower()
    assert fixture.read_bytes() == original


def test_write_denied_produces_zero_mutation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    fixture = tmp_path / "disposable-deny-fixture.txt"
    original = b"deny-must-keep\n"
    fixture.write_bytes(original)
    status, detail = _dispatch_gated_file_action(
        monkeypatch,
        "write_file",
        {"path": str(fixture), "content": "should-not-land\n"},
        approved=False,
    )
    assert status == "blocked"
    assert "denied" in detail.lower() or "blocked" in detail.lower()
    assert fixture.read_bytes() == original


def test_patch_denied_produces_zero_mutation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    fixture = tmp_path / "disposable-patch-fixture.txt"
    original = b"alpha-line\n"
    fixture.write_bytes(original)
    status, _detail = _dispatch_gated_file_action(
        monkeypatch,
        "patch",
        {
            "path": str(fixture),
            "old_string": "alpha-line",
            "new_string": "beta-line",
        },
        approved=False,
    )
    assert status == "blocked"
    assert fixture.read_bytes() == original


def test_write_executes_only_after_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    fixture = tmp_path / "disposable-approve-fixture.txt"
    fixture.write_bytes(b"before-approval\n")
    status, _detail = _dispatch_gated_file_action(
        monkeypatch,
        "write_file",
        {"path": str(fixture), "content": "after-approval\n"},
        approved=True,
    )
    assert status == "executed"
    assert fixture.read_text(encoding="utf-8") == "after-approval\n"


def test_profile_policy_files_are_blocked_even_if_approved(
    tmp_path: Path, monkeypatch
) -> None:
    tg.seed_telegram_ops_profile(tmp_path)
    home = tmp_path / "profiles" / "telegram-ops"
    monkeypatch.setenv("HERMES_HOME", str(home))
    target = home / "config.yaml"
    original = target.read_bytes()
    status, detail = _dispatch_gated_file_action(
        monkeypatch,
        "write_file",
        {"path": str(target), "content": "approvals:\n  mode: off\n"},
        approved=True,
    )
    assert status == "blocked"
    assert "policy" in detail.lower() or "refuses" in detail.lower()
    assert target.read_bytes() == original


def test_yolo_and_allowed_commands_cannot_relax_approval_posture() -> None:
    from gateway.slash_access import policy_from_extra

    seed = tg.load_seed_config()
    telegram = seed["platforms"]["telegram"]
    policy = policy_from_extra(telegram, "dm")
    assert policy.enabled is True
    assert policy.can_run("123456789", "yolo") is False
    assert policy.can_run("123456789", "tools") is False
    assert policy.can_run("123456789", "toolsets") is False
    assert policy.can_run("123456789", "model") is False
    assert policy.can_run("123456789", "cron") is False
    assert policy.can_run("123456789", "approve") is True
    assert policy.can_run("123456789", "deny") is True
    assert policy.is_admin("123456789") is False
    assert telegram["allow_admin_from"] == ["0"]
    assert seed["approvals"]["cron_mode"] == "deny"
    handler_src = (REPO_ROOT / "gateway" / "slash_commands.py").read_text(encoding="utf-8")
    for fn_name in (
        "_handle_profile_command",
        "_handle_status_command",
        "_handle_stop_command",
        "_handle_approve_command",
    ):
        start = handler_src.index(f"async def {fn_name}")
        nxt = handler_src.find("\n    async def ", start + 1)
        body = handler_src[start:nxt]
        assert "approvals.mode" not in body
        assert "cron_mode" not in body
    yolo_start = handler_src.index("async def _handle_yolo_command")
    yolo_body = handler_src[yolo_start : handler_src.find("\n    async def ", yolo_start + 1)]
    assert "enable_session_yolo" in yolo_body
    assert "yolo" not in {
        str(item).lstrip("/").lower() for item in telegram["user_allowed_commands"]
    }


def test_callable_schema_exposes_file_writes_and_hides_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    tg.seed_telegram_ops_profile(tmp_path)
    home = tmp_path / "profiles" / "telegram-ops"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_POWERUNITS_RUNTIME_POLICY", raising=False)
    _reset_hermes_config_caches()
    try:
        from model_tools import get_tool_definitions

        seed = tg.load_seed_config()
        defs = get_tool_definitions(
            enabled_toolsets=list(seed["platform_toolsets"]["telegram"]),
            disabled_toolsets=list(seed["agent"]["disabled_toolsets"]),
            quiet_mode=True,
        )
        names = {item["function"]["name"] for item in defs}
    finally:
        _reset_hermes_config_caches()
    assert "read_file" in names
    assert "search_files" in names
    assert "write_file" in names
    assert "patch" in names
    assert "terminal" not in names
    assert "process" not in names
    assert "execute_code" not in names
    assert "git_commit" not in names
    assert "git_push" not in names
    assert "delegate_task" not in names
    assert "computer_use" not in names
    assert not any(name.startswith("browser_") for name in names)


def test_repo_a_and_repo_b_are_readable_through_file_tools(
    tmp_path: Path, monkeypatch
) -> None:
    import json

    from r5_developer_hermes.container.contract import (
        BIND_MOUNTS,
        ENV_ALLOWLIST,
        HOST_REPO_A,
        HOST_REPO_B,
        REPO_A_CONTAINER,
        REPO_B_CONTAINER,
    )
    from tools.file_tools import read_file_tool

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    (tmp_path / "hermes-home").mkdir()
    tools = _resolved_telegram_tools()
    assert "read_file" in tools
    assert "search_files" in tools
    destinations = {dest for _src, dest in BIND_MOUNTS}
    assert REPO_A_CONTAINER in destinations
    assert REPO_B_CONTAINER in destinations
    assert "/workspace" in ENV_ALLOWLIST["HERMES_WRITE_SAFE_ROOT"]
    repo_a = REPO_ROOT if (REPO_ROOT / "AGENTS.md").is_file() else HOST_REPO_A
    result_a = json.loads(read_file_tool(str(repo_a / "AGENTS.md"), offset=1, limit=8))
    assert not result_a.get("error")
    text_a = str(result_a.get("content") or result_a)
    assert "hermes" in text_a.lower()
    repo_b_candidates = (
        HOST_REPO_B,
        REPO_ROOT.parent / "EU-PP-Database",
    )
    repo_b = next((path for path in repo_b_candidates if path.is_dir()), None)
    if repo_b is None:
        # CI and other hosts without the dedicated clone still prove the
        # same file-tool path against a disposable Repo B stand-in. The
        # live bind target remains /workspace/EU-PP-Database.
        repo_b = tmp_path / "EU-PP-Database"
        repo_b.mkdir()
        (repo_b / "README.md").write_text(
            "EU-PP-Database stand-in for telegram-ops read proof\n",
            encoding="utf-8",
        )
    marker = next(repo_b.glob("README*"))
    result_b = json.loads(read_file_tool(str(marker), offset=1, limit=8))
    assert not result_b.get("error")
    assert result_b.get("content") or result_b.get("lines")


def test_dotenv_flags_detect_allow_all_and_webhook(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "TELEGRAM_BOT_TOKEN=123456789:AAHfakeLiveShapedTokenValueXXX\n"
        "TELEGRAM_ALLOWED_USERS=123456789\n"
        "TELEGRAM_ALLOW_ALL_USERS=true\n"
        "TELEGRAM_WEBHOOK_URL=https://example.invalid/hook\n",
        encoding="utf-8",
    )
    state = tg.read_dotenv_names_and_token_class(path)
    assert state["token_class"] == "LIVE_SHAPED"
    assert state["allowed_users_present"] == "YES"
    assert state["allowed_users_class"] == "NUMERIC_SINGLE"
    assert state["allow_all_set"] == "YES"
    assert state["webhook_set"] == "YES"
    dumped = str(state)
    assert "AAHfake" not in dumped
    assert "example.invalid" not in dumped


def test_apply_live_secrets_writes_restricted_env_without_returning_values(
    tmp_path: Path,
) -> None:
    token = "123456789:AAHfakeLiveShapedTokenValueXXX"
    user = "123456789"
    result = tg.apply_live_secrets(
        tmp_path,
        {
            tg.ACTIVATION_STDIN_TOKEN_KEY: token,
            tg.ACTIVATION_STDIN_USER_KEY: user,
        },
    )
    assert result["APPLIED"] == "YES"
    assert result["token_class"] == "LIVE_SHAPED"
    assert result["allowed_users_present"] == "YES"
    assert result["allowed_users_class"] == "NUMERIC_SINGLE"
    assert result["allow_all_set"] == "NO"
    assert result["webhook_set"] == "NO"
    assert token not in str(result)
    assert user not in str(result)
    env_text = (tmp_path / "profiles" / "telegram-ops" / ".env").read_text(encoding="utf-8")
    assert f"TELEGRAM_BOT_TOKEN={token}" in env_text
    assert f"TELEGRAM_ALLOWED_USERS={user}" in env_text
    assert "TELEGRAM_ALLOW_ALL_USERS=" in env_text
    assert not any(
        line.startswith("TELEGRAM_ALLOW_ALL_USERS=") and line.split("=", 1)[1].strip()
        for line in env_text.splitlines()
        if not line.startswith("#")
    )
    again = tg.apply_live_secrets(
        tmp_path,
        {
            tg.ACTIVATION_STDIN_TOKEN_KEY: "999999999:AAHanotherLiveShapedTokenXXX",
            tg.ACTIVATION_STDIN_USER_KEY: "999999999",
        },
    )
    assert again["APPLIED"] == "NO"
    assert again["REASON"] == "REFUSE_OVERWRITE_EXISTING_LIVE_SECRET"
    assert "999999999" not in (tmp_path / "profiles" / "telegram-ops" / ".env").read_text(
        encoding="utf-8"
    )


def test_apply_live_secrets_refuses_non_live_and_non_numeric(tmp_path: Path) -> None:
    missing = tg.apply_live_secrets(
        tmp_path,
        {
            tg.ACTIVATION_STDIN_TOKEN_KEY: "",
            tg.ACTIVATION_STDIN_USER_KEY: "123456789",
        },
    )
    assert missing["APPLIED"] == "NO"
    assert missing["REASON"] == "REFUSE_NON_LIVE_TOKEN"
    invalid_user = tg.apply_live_secrets(
        tmp_path,
        {
            tg.ACTIVATION_STDIN_TOKEN_KEY: "123456789:AAHfakeLiveShapedTokenValueXXX",
            tg.ACTIVATION_STDIN_USER_KEY: "@not-numeric,2",
        },
    )
    assert invalid_user["APPLIED"] == "NO"
    assert invalid_user["REASON"] == "REFUSE_NON_NUMERIC_USER"
    assert invalid_user["allowed_users_class"] == "INVALID"


def test_activation_payload_parser_is_strict() -> None:
    parsed = tg.parse_activation_payload(
        {
            "telegram_bot_token": "123456789:AAHfakeLiveShapedTokenValueXXX",
            "telegram_allowed_users": "123456789",
        }
    )
    assert set(parsed) == {
        tg.ACTIVATION_STDIN_TOKEN_KEY,
        tg.ACTIVATION_STDIN_USER_KEY,
    }
    try:
        tg.parse_activation_payload({"telegram_bot_token": "x"})
        raise AssertionError("expected missing-user reject")
    except ValueError as exc:
        assert "REFUSE_ACTIVATION_PAYLOAD" in str(exc)
    try:
        tg.parse_activation_payload(
            {
                "telegram_bot_token": "x",
                "telegram_allowed_users": "1",
                "extra": "nope",
            }
        )
        raise AssertionError("expected extra-field reject")
    except ValueError as exc:
        assert "REFUSE_ACTIVATION_EXTRA_FIELDS" in str(exc)


def test_telegram_activate_without_intent_does_not_start() -> None:
    from r5_developer_hermes.container.launch import telegram_activate

    result = telegram_activate(confirmed=False)
    assert result["START_PERMITTED"] == "NO"
    assert result["START_REASON"] == "REFUSE_MISSING_ACTIVATION_INTENT"
    assert result["GATEWAY"] == "NOT_STARTED"
    assert result["OPERATOR_TELEGRAM_CHANGED"] == "NO"
    assert result["RAILWAY_CHANGED"] == "NO"
    assert result["TOKEN_VALUES_RECORDED"] == "NO"
