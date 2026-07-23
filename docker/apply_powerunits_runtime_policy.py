#!/usr/bin/env python3
"""
Apply Powerunits first-deployment runtime safety policy.

This is intentionally narrow:
- keep Hermes install intact for future phases
- enforce a fail-closed platform/tool surface for first Railway deployment
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# This script is invoked as a standalone file (not via `python -m` / package
# import), both from docker/stage2-hook.sh (s6-overlay cont-init, or a manual
# call from docker/railway_gateway_with_dashboard.sh) and potentially by hand.
# `python /path/to/script.py` only puts the SCRIPT's own directory
# (.../docker/) on sys.path[0] -- never the repo root one level up, where the
# fork's top-level `powerunits_*.py` modules actually live. Normally those
# modules are also reachable via the editable/wheel install's site-packages
# (see `py-modules` in pyproject.toml), but that has already broken once
# (2026-07-02 incident: powerunits_telegram_overlays was missing from
# py-modules and ModuleNotFoundError'd here). Insert the repo root explicitly
# so this script keeps working even if a future top-level module is again
# forgotten from py-modules, regardless of caller/CWD/PYTHONPATH context.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import yaml

from powerunits_capability_tier import read_powerunits_capability_tier
from powerunits_bounded_profiles_v1 import (
    active_bounded_profile_id,
    apply_bounded_profile_to_process_env,
    persist_bounded_profile_to_hermes_env,
    _explicit_env_keys_at_boot,
)
from powerunits_telegram_overlays import (
    TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1,
    merge_capability_overlays_into_telegram,
)

POLICY_ID = "first_safe_v1"

ALLOWED_TELEGRAM_TOOLSETS = list(TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1)

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
# Override with HERMES_POWERUNITS_PRIMARY_MODEL (e.g. gpt-4.1 rollback).
POWERUNITS_PRIMARY_MODEL_FALLBACK = "gpt-5.4"
POWERUNITS_PRIMARY_PROVIDER = "custom"
POWERUNITS_PRIMARY_BASE_URL = "https://api.openai.com/v1"

# GPT-5.4 Responses trial: reasoning on by default (medium). Rollback via
# HERMES_POWERUNITS_REASONING_EFFORT=none (or model rollback to gpt-4.1).
POWERUNITS_REASONING_EFFORT_FALLBACK = "medium"
_ALLOWED_REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
)


def _resolve_primary_model() -> str:
    raw = (os.getenv("HERMES_POWERUNITS_PRIMARY_MODEL") or "").strip()
    return raw or POWERUNITS_PRIMARY_MODEL_FALLBACK


def _canonical_model_id(model: str) -> str:
    m = (model or "").strip().lower()
    if "/" in m:
        m = m.rsplit("/", 1)[-1]
    return m


def _api_mode_for_primary_model(model: str) -> str:
    """GPT-5.x on api.openai.com needs Responses; GPT-4.x stays on chat completions."""
    if _canonical_model_id(model).startswith("gpt-5"):
        return "codex_responses"
    return "chat_completions"


def _resolve_reasoning_effort(primary_model: str) -> str:
    """Resolve agent.reasoning_effort for Powerunits first_safe_v1.

    - GPT-5*: default ``medium`` (Responses + ``reasoning.effort``).
    - Non-GPT-5: force ``none`` (GPT-4.x rejects encrypted reasoning include).
    - Env ``HERMES_POWERUNITS_REASONING_EFFORT`` overrides on GPT-5* only
      (invalid values fall back to ``none`` fail-closed).
    """
    if not _canonical_model_id(primary_model).startswith("gpt-5"):
        return "none"
    raw = (os.getenv("HERMES_POWERUNITS_REASONING_EFFORT") or "").strip().lower()
    if not raw:
        return POWERUNITS_REASONING_EFFORT_FALLBACK
    if raw not in _ALLOWED_REASONING_EFFORTS:
        return "none"
    return raw


# Back-compat alias for docs/tests that import the constant name.
POWERUNITS_PRIMARY_MODEL_DEFAULT = _resolve_primary_model()


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
    primary_model = _resolve_primary_model()
    model_cfg = cfg.get("model")
    if not isinstance(model_cfg, dict):
        model_cfg = {}
    model_cfg["default"] = primary_model
    model_cfg["provider"] = POWERUNITS_PRIMARY_PROVIDER
    model_cfg["base_url"] = POWERUNITS_PRIMARY_BASE_URL
    # GPT-4.x: chat_completions (Responses encrypted_content → 400).
    # GPT-5.x: codex_responses (tools + reasoning require /v1/responses).
    model_cfg["api_mode"] = _api_mode_for_primary_model(primary_model)
    cfg["model"] = model_cfg

    # Reasoning dial (GPT-5 Responses only). Default medium for the 5.4 trial;
    # set HERMES_POWERUNITS_REASONING_EFFORT=none to roll back without model change.
    # Non-GPT-5 primary always pins none (encrypted include unsafe on GPT-4.x).
    agent_cfg = cfg.get("agent")
    if not isinstance(agent_cfg, dict):
        agent_cfg = {}
    agent_cfg["reasoning_effort"] = _resolve_reasoning_effort(primary_model)
    cfg["agent"] = agent_cfg

    # Enforce narrow, explicit platform toolset policy (fail-closed for gateway usage).
    platform_toolsets = cfg.get("platform_toolsets")
    if not isinstance(platform_toolsets, dict):
        platform_toolsets = {}
    platform_toolsets["telegram"] = merge_capability_overlays_into_telegram(
        list(ALLOWED_TELEGRAM_TOOLSETS), read_powerunits_capability_tier()
    )
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
    profile_id = active_bounded_profile_id()
    if profile_id:
        powerunits["bounded_profile_v1"] = profile_id
    cfg["powerunits"] = powerunits

    auxiliary = cfg.get("auxiliary")
    if not isinstance(auxiliary, dict):
        auxiliary = {}
    curator = auxiliary.get("curator")
    if not isinstance(curator, dict):
        curator = {}
    curator.setdefault("enabled", False)
    auxiliary["curator"] = curator
    cfg["auxiliary"] = auxiliary

    redaction = cfg.get("redaction")
    if not isinstance(redaction, dict):
        redaction = {}
    redaction.setdefault("enabled", False)
    cfg["redaction"] = redaction

    _save_yaml(config_path, cfg)


def _sync_powerunits_soul_md(hermes_home: Path) -> bool:
    """Refresh ``$HERMES_HOME/SOUL.md`` from the image on every policy boot (operator contract)."""
    src = Path(__file__).resolve().parent / "SOUL.md"
    dest = hermes_home / "SOUL.md"
    if not src.is_file():
        return False
    hermes_home.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def main() -> int:
    hermes_home = Path(os.getenv("HERMES_HOME", "/opt/data"))
    config_path = hermes_home / "config.yaml"
    env_path = hermes_home / ".env"
    explicit_at_boot = _explicit_env_keys_at_boot()
    persist_result = persist_bounded_profile_to_hermes_env(
        env_path, explicit_env_keys=explicit_at_boot
    )
    profile_result = apply_bounded_profile_to_process_env()
    apply_policy(config_path)
    soul_synced = _sync_powerunits_soul_md(hermes_home)
    msg = f"[powerunits-policy] applied {POLICY_ID} to {config_path}"
    if profile_result.get("profile"):
        msg += (
            f" (bounded_profile_v1={profile_result['profile']}, "
            f"applied={len(profile_result.get('applied') or [])}, "
            f"persisted={len(persist_result.get('persisted') or [])}, "
            f"explicit_overrides={len(profile_result.get('skipped_explicit') or [])})"
        )
    if soul_synced:
        msg += f" (SOUL.md synced to {hermes_home / 'SOUL.md'})"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
