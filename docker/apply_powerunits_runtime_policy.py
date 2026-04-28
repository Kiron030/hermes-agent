#!/usr/bin/env python3
"""
Apply Powerunits first-deployment runtime safety policy.

This is intentionally narrow:
- keep Hermes install intact for future phases
- enforce a fail-closed platform/tool surface for first Railway deployment
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


POLICY_ID = "first_safe_v1"

ALLOWED_TELEGRAM_TOOLSETS = [
    "memory",
    "session_search",
    "todo",
    "powerunits_docs",
    "powerunits_github_docs",
    "powerunits_workspace",
    "powerunits_timescale_read",
    "powerunits_repo_b_read",
    "powerunits_option_d_preflight",
    "powerunits_option_d_execute",
    "powerunits_option_d_validate",
]

DISABLED_PLATFORMS = [
    "discord",
    "whatsapp",
    "slack",
    "signal",
    "homeassistant",
    "email",
    "sms",
    "mattermost",
    "matrix",
    "dingtalk",
    "feishu",
    "wecom",
    "wecom_callback",
    "weixin",
    "qqbot",
    "webhook",
    "api_server",
    "bluebubbles",
]

# Deterministic short-term primary LLM route for Powerunits internal spike:
# use direct OpenAI-compatible endpoint instead of implicit OpenRouter fallback.
POWERUNITS_PRIMARY_MODEL_DEFAULT = "gpt-4.1-mini"
POWERUNITS_PRIMARY_PROVIDER = "custom"
POWERUNITS_PRIMARY_BASE_URL = "https://api.openai.com/v1"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _save_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def apply_policy(config_path: Path) -> None:
    cfg = _load_yaml(config_path)

    # Enforce deterministic primary model/provider routing to match
    # OPENAI_API_KEY-only Railway environments.
    model_cfg = cfg.get("model")
    if not isinstance(model_cfg, dict):
        model_cfg = {}
    model_cfg["default"] = POWERUNITS_PRIMARY_MODEL_DEFAULT
    model_cfg["provider"] = POWERUNITS_PRIMARY_PROVIDER
    model_cfg["base_url"] = POWERUNITS_PRIMARY_BASE_URL
    # Pin OpenAI wire mode: GPT-4.x on api.openai.com must not use the
    # Responses path with reasoning.encrypted_content (400 from provider).
    model_cfg["api_mode"] = "chat_completions"
    cfg["model"] = model_cfg

    # Belt-and-suspenders: disable Hermes "reasoning effort" for this phase so
    # auxiliary Responses-shaped calls do not request encrypted reasoning.
    agent_cfg = cfg.get("agent")
    if not isinstance(agent_cfg, dict):
        agent_cfg = {}
    agent_cfg["reasoning_effort"] = "none"
    cfg["agent"] = agent_cfg

    # Enforce narrow, explicit platform toolset policy (fail-closed for gateway usage).
    platform_toolsets = cfg.get("platform_toolsets")
    if not isinstance(platform_toolsets, dict):
        platform_toolsets = {}
    platform_toolsets["telegram"] = list(ALLOWED_TELEGRAM_TOOLSETS)
    for p in DISABLED_PLATFORMS:
        platform_toolsets[p] = []
    cfg["platform_toolsets"] = platform_toolsets

    # Enforce platform exposure defaults: Telegram enabled, all others disabled.
    platforms = cfg.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}
    telegram_cfg = platforms.get("telegram")
    if not isinstance(telegram_cfg, dict):
        telegram_cfg = {}
    telegram_cfg["enabled"] = True
    platforms["telegram"] = telegram_cfg

    for p in DISABLED_PLATFORMS:
        plat_cfg = platforms.get(p)
        if not isinstance(plat_cfg, dict):
            plat_cfg = {}
        plat_cfg["enabled"] = False
        platforms[p] = plat_cfg
    cfg["platforms"] = platforms

    # Keep explicit manual approvals and deny dangerous cron execution in this phase.
    approvals = cfg.get("approvals")
    if not isinstance(approvals, dict):
        approvals = {}
    approvals["mode"] = "manual"
    approvals["cron_mode"] = "deny"
    cfg["approvals"] = approvals

    # Ensure no inherited allowlist bypass exists.
    cfg["command_allowlist"] = []

    # Mark active policy for operator visibility.
    powerunits = cfg.get("powerunits")
    if not isinstance(powerunits, dict):
        powerunits = {}
    runtime_policy = powerunits.get("runtime_policy")
    if not isinstance(runtime_policy, dict):
        runtime_policy = {}
    runtime_policy["id"] = POLICY_ID
    runtime_policy["enforced"] = True
    powerunits["runtime_policy"] = runtime_policy
    cfg["powerunits"] = powerunits

    _save_yaml(config_path, cfg)


def main() -> int:
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    config_path = hermes_home / "config.yaml"
    apply_policy(config_path)
    print(f"[powerunits-policy] applied {POLICY_ID} to {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
