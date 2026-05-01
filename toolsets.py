#!/usr/bin/env python3
"""
Toolsets Module

This module provides a flexible system for defining and managing tool aliases/toolsets.
Toolsets allow you to group tools together for specific scenarios and can be composed
from individual tools or other toolsets.

Features:
- Define custom toolsets with specific tools
- Compose toolsets from other toolsets
- Built-in common toolsets for typical use cases
- Easy extension for new toolsets
- Support for dynamic toolset resolution

Usage:
    from toolsets import get_toolset, resolve_toolset, get_all_toolsets
    
    # Get tools for a specific toolset
    tools = get_toolset("research")
    
    # Resolve a toolset to get all tool names (including from composed toolsets)
    all_tools = resolve_toolset("full_stack")
"""

from typing import List, Dict, Any, Set, Optional


# Shared tool list for CLI and all messaging platform toolsets.
# Edit this once to update all platforms simultaneously.
_HERMES_CORE_TOOLS = [
    # Web
    "web_search", "web_extract",
    # Terminal + process management
    "terminal", "process",
    # File manipulation
    "read_file", "write_file", "patch", "search_files",
    # Vision + image generation
    "vision_analyze", "image_generate",
    # Skills
    "skills_list", "skill_view", "skill_manage",
    # Browser automation
    "browser_navigate", "browser_snapshot", "browser_click",
    "browser_type", "browser_scroll", "browser_back",
    "browser_press", "browser_get_images",
    "browser_vision", "browser_console", "browser_cdp",
    # Text-to-speech
    "text_to_speech",
    # Planning & memory
    "todo", "memory",
    # Session history search
    "session_search",
    # Clarifying questions
    "clarify",
    # Code execution + delegation
    "execute_code", "delegate_task",
    # Cronjob management
    "cronjob",
    # Cross-platform messaging (gated on gateway running via check_fn)
    "send_message",
    # Home Assistant smart home control (gated on HASS_TOKEN via check_fn)
    "ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service",
]


# Core toolset definitions
# These can include individual tools or reference other toolsets
TOOLSETS = {
    # Basic toolsets - individual tool categories
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_extract"],
        "includes": []  # No other toolsets included
    },
    
    "search": {
        "description": "Web search only (no content extraction/scraping)",
        "tools": ["web_search"],
        "includes": []
    },
    
    "vision": {
        "description": "Image analysis and vision tools",
        "tools": ["vision_analyze"],
        "includes": []
    },
    
    "image_gen": {
        "description": "Creative generation tools (images)",
        "tools": ["image_generate"],
        "includes": []
    },
    
    "terminal": {
        "description": "Terminal/command execution and process management tools",
        "tools": ["terminal", "process"],
        "includes": []
    },
    
    "moa": {
        "description": "Advanced reasoning and problem-solving tools",
        "tools": ["mixture_of_agents"],
        "includes": []
    },
    
    "skills": {
        "description": "Access, create, edit, and manage skill documents with specialized instructions and knowledge",
        "tools": ["skills_list", "skill_view", "skill_manage"],
        "includes": []
    },
    
    "browser": {
        "description": "Browser automation for web interaction (navigate, click, type, scroll, iframes, hold-click) with web search for finding URLs",
        "tools": [
            "browser_navigate", "browser_snapshot", "browser_click",
            "browser_type", "browser_scroll", "browser_back",
            "browser_press", "browser_get_images",
            "browser_vision", "browser_console", "browser_cdp", "web_search"
        ],
        "includes": []
    },
    
    "cronjob": {
        "description": "Cronjob management tool - create, list, update, pause, resume, remove, and trigger scheduled tasks",
        "tools": ["cronjob"],
        "includes": []
    },
    
    "messaging": {
        "description": "Cross-platform messaging: send messages to Telegram, Discord, Slack, SMS, etc.",
        "tools": ["send_message"],
        "includes": []
    },
    
    "rl": {
        "description": "RL training tools for running reinforcement learning on Tinker-Atropos",
        "tools": [
            "rl_list_environments", "rl_select_environment",
            "rl_get_current_config", "rl_edit_config",
            "rl_start_training", "rl_check_status",
            "rl_stop_training", "rl_get_results",
            "rl_list_runs", "rl_test_inference"
        ],
        "includes": []
    },
    
    "file": {
        "description": "File manipulation tools: read, write, patch (with fuzzy matching), and search (content + files)",
        "tools": ["read_file", "write_file", "patch", "search_files"],
        "includes": []
    },
    
    "tts": {
        "description": "Text-to-speech: convert text to audio with Edge TTS (free), ElevenLabs, OpenAI, or xAI",
        "tools": ["text_to_speech"],
        "includes": []
    },
    
    "todo": {
        "description": "Task planning and tracking for multi-step work",
        "tools": ["todo"],
        "includes": []
    },
    
    "memory": {
        "description": "Persistent memory across sessions (personal notes + user profile)",
        "tools": ["memory"],
        "includes": []
    },
    
    "session_search": {
        "description": "Search and recall past conversations with summarization",
        "tools": ["session_search"],
        "includes": []
    },
    
    "clarify": {
        "description": "Ask the user clarifying questions (multiple-choice or open-ended)",
        "tools": ["clarify"],
        "includes": []
    },

    "powerunits_docs": {
        "description": (
            "Read-only Powerunits documentation bundled with Hermes; "
            "manifest keys only (no arbitrary filesystem paths)."
        ),
        "tools": ["read_powerunits_doc"],
        "includes": [],
    },

    "powerunits_github_docs": {
        "description": (
            "Read-only GitHub docs access, hard-allowlisted to "
            "Kiron030/Powerunits.io docs/roadmap on branch starting_the_seven_phases."
        ),
        "tools": ["list_powerunits_roadmap_dir", "read_powerunits_roadmap_file"],
        "includes": [],
    },

    "powerunits_workspace": {
        "description": (
            "Bounded persistent workspace at /opt/data/hermes_workspace "
            "(analysis/notes/drafts/exports), no delete/rename, text files only."
        ),
        "tools": [
            "list_hermes_workspace",
            "read_hermes_workspace_file",
            "save_hermes_workspace_note",
        ],
        "includes": [],
    },

    "powerunits_timescale_read": {
        "description": (
            "Staged operator-only bounded read against Timescale "
            "(DATABASE_URL_TIMESCALE, feature-flagged); single view, fixed patterns."
        ),
        "tools": ["read_powerunits_timescale_dataset"],
        "includes": [],
    },

    "powerunits_repo_b_read": {
        "description": (
            "Allowlisted Repo B file read via GitHub API only "
            "(HERMES_POWERUNITS_REPO_B_READ_ENABLED + GitHub read token); "
            "keys from config/powerunits_repo_b_read_allowlist.json."
        ),
        "tools": ["read_powerunits_repo_b_allowlisted"],
        "includes": [],
    },

    "powerunits_option_d_preflight": {
        "description": (
            "Option D bounded slice **preflight only** (PL / v1 / ≤24h UTC): validates "
            "arguments locally and returns slice, rollback SQL, optional legacy wrapper CLI, "
            "and bounded HTTP operator hint. **No** Powerunits HTTP, **no** wrapper execution, "
            "**no** DB writes from Hermes. Gated by HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED."
        ),
        "tools": ["preflight_powerunits_option_d_bounded_slice"],
        "includes": [],
    },

    "powerunits_option_d_execute": {
        "description": (
            "Option D **bounded execute**: one HTTP POST to the Powerunits internal "
            "`/internal/hermes/bounded/v1/market-features-hourly/recompute` API (PL / v1 / ≤24h UTC). "
            "Requires HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED, POWERUNITS_INTERNAL_EXECUTE_BASE_URL, "
            "and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET. Not a general SQL writer."
        ),
        "tools": ["execute_powerunits_option_d_bounded_slice"],
        "includes": [],
    },

    "powerunits_option_d_validate": {
        "description": (
            "Option D **bounded validate-window**: one HTTP POST to Powerunits internal read-only "
            "`/internal/hermes/bounded/v1/market-features-hourly/validate-window` (PL / v1 / ≤24h UTC). "
            "Requires HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED, POWERUNITS_INTERNAL_EXECUTE_BASE_URL, "
            "and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["validate_powerunits_option_d_bounded_window"],
        "includes": [],
    },

    "powerunits_option_d_readiness": {
        "description": (
            "Option D **bounded readiness-window**: one HTTP POST to Powerunits internal read-only "
            "`/internal/hermes/bounded/v1/market-features-hourly/readiness-window` (PL / v1 / ≤24h UTC). "
            "Requires HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED, POWERUNITS_INTERNAL_EXECUTE_BASE_URL, "
            "and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["readiness_powerunits_option_d_bounded_window"],
        "includes": [],
    },

    "powerunits_option_d_summary": {
        "description": (
            "Option D **bounded summary-window**: one HTTP POST to Powerunits internal read-only "
            "`/internal/hermes/bounded/v1/market-features-hourly/summary-window` (PL / v1 / ≤24h UTC). "
            "Requires HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED, POWERUNITS_INTERNAL_EXECUTE_BASE_URL, "
            "and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["summarize_powerunits_option_d_bounded_window"],
        "includes": [],
    },

    "powerunits_entsoe_market_bounded_preflight": {
        "description": (
            "Bounded ENTSO-E market sync **preflight** (DE / v1 / ≤7d UTC): local slice check only; "
            "bounded HTTP operator hint. **No** Powerunits HTTP. "
            "Gated by HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED."
        ),
        "tools": ["preflight_powerunits_entsoe_market_bounded_slice"],
        "includes": [],
    },

    "powerunits_entsoe_market_bounded_execute": {
        "description": (
            "Bounded ENTSO-E market sync **execute**: one HTTP POST to "
            "`/internal/hermes/bounded/v1/entsoe-market-sync/recompute` (DE / v1 / ≤7d). "
            "Requires HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_EXECUTE_ENABLED, "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL, POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["execute_powerunits_entsoe_market_bounded_slice"],
        "includes": [],
    },

    "powerunits_entsoe_market_bounded_validate": {
        "description": (
            "Bounded ENTSO-E market sync **validate-window**: one HTTP POST to read-only "
            "`/internal/hermes/bounded/v1/entsoe-market-sync/validate-window` (DE / v1 / ≤7d). "
            "Counts are on **normalized UTC hour-bucket** tables; generation is long-format by "
            "technology_group (see Repo B `semantics_notes`). "
            "Requires HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED + same base URL and bearer."
        ),
        "tools": ["validate_powerunits_entsoe_market_bounded_window"],
        "includes": [],
    },

    "powerunits_entsoe_market_bounded_summary": {
        "description": (
            "Bounded ENTSO-E market sync **summary-window**: one HTTP POST to read-only "
            "`/internal/hermes/bounded/v1/entsoe-market-sync/summary-window` (DE / v1 / ≤7d). "
            "Same hourly-normalized semantics as validate (compact validation subset). "
            "Requires HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED + same base URL and bearer."
        ),
        "tools": ["summarize_powerunits_entsoe_market_bounded_window"],
        "includes": [],
    },

    "powerunits_entsoe_market_bounded_campaign": {
        "description": (
            "Bounded ENTSO-E market sync **campaign (v1 DE)**: sequential execute + summary over "
            "contiguous ≤7d sub-windows (campaign span ≤31d, ≤5 windows), fail-fast. "
            "Requires HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED plus ENTSO-E bounded "
            "execute + summary flags, POWERUNITS_INTERNAL_EXECUTE_BASE_URL, "
            "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET. Does not run market_feature_job "
            "or expand_market_data."
        ),
        "tools": ["campaign_powerunits_entsoe_market_bounded_de"],
        "includes": [],
    },

    "powerunits_entsoe_market_bounded_coverage_scan": {
        "description": (
            "Bounded ENTSO-E market sync **coverage-scan** (read-only, v1 DE): one HTTP POST to "
            "`/internal/hermes/bounded/v1/entsoe-market-sync/coverage-scan` — multi-subwindow rollup "
            "on normalized hourly ENTSO-E tables (**no** recompute / **no** job triggers). "
            "Span ≤31d partitioned like campaign (≤5 × ≤7d). "
            "Requires HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED plus "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL, POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["scan_powerunits_entsoe_market_bounded_coverage_de"],
        "includes": [],
    },

    "powerunits_era5_weather_bounded_preflight": {
        "description": (
            "Bounded ERA5 weather sync **preflight** (DE / v1 / ≤7d UTC): local slice check only; "
            "bounded HTTP operator hint. **No** Powerunits HTTP. "
            "Gated by HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED."
        ),
        "tools": ["preflight_powerunits_era5_weather_bounded_slice"],
        "includes": [],
    },

    "powerunits_era5_weather_bounded_execute": {
        "description": (
            "Bounded ERA5 weather sync **execute**: one HTTP POST to "
            "`/internal/hermes/bounded/v1/era5-weather/recompute` (DE / v1 / ≤7d). "
            "Requires HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_EXECUTE_ENABLED, "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL, POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET. "
            "Does not auto-run market_feature_job or market_driver_feature_job."
        ),
        "tools": ["execute_powerunits_era5_weather_bounded_slice"],
        "includes": [],
    },

    "powerunits_era5_weather_bounded_validate": {
        "description": (
            "Bounded ERA5 weather sync **validate-window**: one HTTP POST to read-only "
            "`/internal/hermes/bounded/v1/era5-weather/validate-window` (DE / v1 / ≤7d). "
            "Requires HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED + same base URL and bearer."
        ),
        "tools": ["validate_powerunits_era5_weather_bounded_window"],
        "includes": [],
    },

    "powerunits_era5_weather_bounded_summary": {
        "description": (
            "Bounded ERA5 weather sync **summary-window**: one HTTP POST to read-only "
            "`/internal/hermes/bounded/v1/era5-weather/summary-window` (DE / v1 / ≤7d). "
            "Requires HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED + same base URL and bearer."
        ),
        "tools": ["summarize_powerunits_era5_weather_bounded_window"],
        "includes": [],
    },

    "powerunits_era5_weather_bounded_campaign": {
        "description": (
            "Bounded ERA5 weather sync **campaign (v1 DE)**: sequential execute + summary over "
            "contiguous ≤7d sub-windows (campaign span ≤31d, ≤5 windows), fail-fast. "
            "Requires HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED plus ERA5 bounded "
            "execute + summary flags, POWERUNITS_INTERNAL_EXECUTE_BASE_URL, "
            "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET. Does not run market_feature_job "
            "or expand_market_data."
        ),
        "tools": ["campaign_powerunits_era5_weather_bounded_de"],
        "includes": [],
    },

    "powerunits_era5_weather_bounded_coverage_scan": {
        "description": (
            "Bounded ERA5 weather sync **coverage-scan** (read-only, v1 DE): one HTTP POST to "
            "`/internal/hermes/bounded/v1/era5-weather/coverage-scan` — multi-subwindow rollup on "
            "`weather_country_hourly` (**no** execute, **no** era5_weather_job, **no** feature jobs). "
            "Span ≤31d partitioned like campaign (≤5 × ≤7d). "
            "Requires HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED plus "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL, POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["scan_powerunits_era5_weather_bounded_coverage_de"],
        "includes": [],
    },

    "powerunits_baseline_layer_preview": {
        "description": (
            "Bounded **baseline layer-coverage preview** (read-only, v1 DE): one HTTP POST to "
            "`/internal/hermes/bounded/v1/baseline/layer-coverage-preview` — expand-aligned layer "
            "aggregates and baseline gate preview (**no** jobs, **no** campaigns, **no** "
            "`expand_market_data`). Span ≤31d single window. "
            "Requires HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED plus "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL, POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "tools": ["preview_powerunits_baseline_layer_coverage_de"],
        "includes": [],
    },

    "code_execution": {
        "description": "Run Python scripts that call tools programmatically (reduces LLM round trips)",
        "tools": ["execute_code"],
        "includes": []
    },
    
    "delegation": {
        "description": "Spawn subagents with isolated context for complex subtasks",
        "tools": ["delegate_task"],
        "includes": []
    },

    # "honcho" toolset removed — Honcho is now a memory provider plugin.
    # Tools are injected via MemoryManager, not the toolset system.

    "homeassistant": {
        "description": "Home Assistant smart home control and monitoring",
        "tools": ["ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service"],
        "includes": []
    },

    "feishu_doc": {
        "description": "Read Feishu/Lark document content",
        "tools": ["feishu_doc_read"],
        "includes": []
    },

    "feishu_drive": {
        "description": "Feishu/Lark document comment operations (list, reply, add)",
        "tools": [
            "feishu_drive_list_comments", "feishu_drive_list_comment_replies",
            "feishu_drive_reply_comment", "feishu_drive_add_comment",
        ],
        "includes": []
    },


    # Scenario-specific toolsets
    
    "debugging": {
        "description": "Debugging and troubleshooting toolkit",
        "tools": ["terminal", "process"],
        "includes": ["web", "file"]  # For searching error messages and solutions, and file operations
    },
    
    "safe": {
        "description": "Safe toolkit without terminal access",
        "tools": [],
        "includes": ["web", "vision", "image_gen"]
    },
    
    # ==========================================================================
    # Full Hermes toolsets (CLI + messaging platforms)
    #
    # All platforms share the same core tools (including send_message,
    # which is gated on gateway running via its check_fn).
    # ==========================================================================

    "hermes-acp": {
        "description": "Editor integration (VS Code, Zed, JetBrains) — coding-focused tools without messaging, audio, or clarify UI",
        "tools": [
            "web_search", "web_extract",
            "terminal", "process",
            "read_file", "write_file", "patch", "search_files",
            "vision_analyze",
            "skills_list", "skill_view", "skill_manage",
            "browser_navigate", "browser_snapshot", "browser_click",
            "browser_type", "browser_scroll", "browser_back",
            "browser_press", "browser_get_images",
            "browser_vision", "browser_console", "browser_cdp",
            "todo", "memory",
            "session_search",
            "execute_code", "delegate_task",
        ],
        "includes": []
    },

    "hermes-api-server": {
        "description": "OpenAI-compatible API server — full agent tools accessible via HTTP (no interactive UI tools like clarify or send_message)",
        "tools": [
            # Web
            "web_search", "web_extract",
            # Terminal + process management
            "terminal", "process",
            # File manipulation
            "read_file", "write_file", "patch", "search_files",
            # Vision + image generation
            "vision_analyze", "image_generate",
            # Skills
            "skills_list", "skill_view", "skill_manage",
            # Browser automation
            "browser_navigate", "browser_snapshot", "browser_click",
            "browser_type", "browser_scroll", "browser_back",
            "browser_press", "browser_get_images",
            "browser_vision", "browser_console", "browser_cdp",
            # Planning & memory
            "todo", "memory",
            # Session history search
            "session_search",
            # Code execution + delegation
            "execute_code", "delegate_task",
            # Cronjob management
            "cronjob",
            # Home Assistant smart home control (gated on HASS_TOKEN via check_fn)
            "ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service",

        ],
        "includes": []
    },
    
    "hermes-cli": {
        "description": "Full interactive CLI toolset - all default tools plus cronjob management",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "hermes-telegram": {
        "description": "Telegram bot toolset - full access for personal use (terminal has safety checks)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "hermes-discord": {
        "description": "Discord bot toolset - full access (terminal has safety checks via dangerous command approval)",
        "tools": _HERMES_CORE_TOOLS + [
            # Discord server introspection & management (gated on DISCORD_BOT_TOKEN via check_fn)
            "discord_server",
        ],
        "includes": []
    },
    
    "hermes-whatsapp": {
        "description": "WhatsApp bot toolset - similar to Telegram (personal messaging, more trusted)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "hermes-slack": {
        "description": "Slack bot toolset - full access for workspace use (terminal has safety checks)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },
    
    "hermes-signal": {
        "description": "Signal bot toolset - encrypted messaging platform (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-bluebubbles": {
        "description": "BlueBubbles iMessage bot toolset - Apple iMessage via local BlueBubbles server",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-homeassistant": {
        "description": "Home Assistant bot toolset - smart home event monitoring and control",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-email": {
        "description": "Email bot toolset - interact with Hermes via email (IMAP/SMTP)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-mattermost": {
        "description": "Mattermost bot toolset - self-hosted team messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-matrix": {
        "description": "Matrix bot toolset - decentralized encrypted messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-dingtalk": {
        "description": "DingTalk bot toolset - enterprise messaging platform (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-feishu": {
        "description": "Feishu/Lark bot toolset - enterprise messaging via Feishu/Lark (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-weixin": {
        "description": "Weixin bot toolset - personal WeChat messaging via iLink (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-qqbot": {
        "description": "QQBot toolset - QQ messaging via Official Bot API v2 (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-wecom": {
        "description": "WeCom bot toolset - enterprise WeChat messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-wecom-callback": {
        "description": "WeCom callback toolset - enterprise self-built app messaging (full access)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-sms": {
        "description": "SMS bot toolset - interact with Hermes via SMS (Twilio)",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-webhook": {
        "description": "Webhook toolset - receive and process external webhook events",
        "tools": _HERMES_CORE_TOOLS,
        "includes": []
    },

    "hermes-gateway": {
        "description": "Gateway toolset - union of all messaging platform tools",
        "tools": [],
        "includes": ["hermes-telegram", "hermes-discord", "hermes-whatsapp", "hermes-slack", "hermes-signal", "hermes-bluebubbles", "hermes-homeassistant", "hermes-email", "hermes-sms", "hermes-mattermost", "hermes-matrix", "hermes-dingtalk", "hermes-feishu", "hermes-wecom", "hermes-wecom-callback", "hermes-weixin", "hermes-qqbot", "hermes-webhook"]
    }
}



def get_toolset(name: str) -> Optional[Dict[str, Any]]:
    """
    Get a toolset definition by name.
    
    Args:
        name (str): Name of the toolset
        
    Returns:
        Dict: Toolset definition with description, tools, and includes
        None: If toolset not found
    """
    toolset = TOOLSETS.get(name)
    if toolset:
        return toolset

    try:
        from tools.registry import registry
    except Exception:
        return None

    registry_toolset = name
    description = f"Plugin toolset: {name}"
    alias_target = registry.get_toolset_alias_target(name)

    if name not in _get_plugin_toolset_names():
        registry_toolset = alias_target
        if not registry_toolset:
            return None
        description = f"MCP server '{name}' tools"
    else:
        reverse_aliases = {
            canonical: alias
            for alias, canonical in _get_registry_toolset_aliases().items()
            if alias not in TOOLSETS
        }
        alias = reverse_aliases.get(name)
        if alias:
            description = f"MCP server '{alias}' tools"

    return {
        "description": description,
        "tools": registry.get_tool_names_for_toolset(registry_toolset),
        "includes": [],
    }


def resolve_toolset(name: str, visited: Set[str] = None) -> List[str]:
    """
    Recursively resolve a toolset to get all tool names.
    
    This function handles toolset composition by recursively resolving
    included toolsets and combining all tools.
    
    Args:
        name (str): Name of the toolset to resolve
        visited (Set[str]): Set of already visited toolsets (for cycle detection)
        
    Returns:
        List[str]: List of all tool names in the toolset
    """
    if visited is None:
        visited = set()
    
    # Special aliases that represent all tools across every toolset
    # This ensures future toolsets are automatically included without changes.
    if name in {"all", "*"}:
        all_tools: Set[str] = set()
        for toolset_name in get_toolset_names():
            # Use a fresh visited set per branch to avoid cross-branch contamination
            resolved = resolve_toolset(toolset_name, visited.copy())
            all_tools.update(resolved)
        return sorted(all_tools)

    # Check for cycles / already-resolved (diamond deps).
    # Silently return [] — either this is a diamond (not a bug, tools already
    # collected via another path) or a genuine cycle (safe to skip).
    if name in visited:
        return []

    visited.add(name)

    # Get toolset definition
    toolset = get_toolset(name)
    if not toolset:
        return []

    # Collect direct tools
    tools = set(toolset.get("tools", []))

    # Recursively resolve included toolsets, sharing the visited set across
    # sibling includes so diamond dependencies are only resolved once and
    # cycle warnings don't fire multiple times for the same cycle.
    for included_name in toolset.get("includes", []):
        included_tools = resolve_toolset(included_name, visited)
        tools.update(included_tools)
    
    return sorted(tools)


def resolve_multiple_toolsets(toolset_names: List[str]) -> List[str]:
    """
    Resolve multiple toolsets and combine their tools.
    
    Args:
        toolset_names (List[str]): List of toolset names to resolve
        
    Returns:
        List[str]: Combined list of all tool names (deduplicated)
    """
    all_tools = set()
    
    for name in toolset_names:
        tools = resolve_toolset(name)
        all_tools.update(tools)
    
    return sorted(all_tools)


def _get_plugin_toolset_names() -> Set[str]:
    """Return toolset names registered by plugins (from the tool registry).

    These are toolsets that exist in the registry but not in the static
    ``TOOLSETS`` dict — i.e. they were added by plugins at load time.
    """
    try:
        from tools.registry import registry
        return {
            toolset_name
            for toolset_name in registry.get_registered_toolset_names()
            if toolset_name not in TOOLSETS
        }
    except Exception:
        return set()


def _get_registry_toolset_aliases() -> Dict[str, str]:
    """Return explicit toolset aliases registered in the live registry."""
    try:
        from tools.registry import registry
        return registry.get_registered_toolset_aliases()
    except Exception:
        return {}


def get_all_toolsets() -> Dict[str, Dict[str, Any]]:
    """
    Get all available toolsets with their definitions.

    Includes both statically-defined toolsets and plugin-registered ones.
    
    Returns:
        Dict: All toolset definitions
    """
    result = dict(TOOLSETS)
    aliases = _get_registry_toolset_aliases()
    for ts_name in _get_plugin_toolset_names():
        display_name = ts_name
        for alias, canonical in aliases.items():
            if canonical == ts_name and alias not in TOOLSETS:
                display_name = alias
                break
        if display_name in result:
            continue
        toolset = get_toolset(display_name)
        if toolset:
            result[display_name] = toolset
    return result


def get_toolset_names() -> List[str]:
    """
    Get names of all available toolsets (excluding aliases).

    Includes plugin-registered toolset names.
    
    Returns:
        List[str]: List of toolset names
    """
    names = set(TOOLSETS.keys())
    aliases = _get_registry_toolset_aliases()
    for ts_name in _get_plugin_toolset_names():
        for alias, canonical in aliases.items():
            if canonical == ts_name and alias not in TOOLSETS:
                names.add(alias)
                break
        else:
            names.add(ts_name)
    return sorted(names)




def validate_toolset(name: str) -> bool:
    """
    Check if a toolset name is valid.
    
    Args:
        name (str): Toolset name to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Accept special alias names for convenience
    if name in {"all", "*"}:
        return True
    if name in TOOLSETS:
        return True
    if name in _get_plugin_toolset_names():
        return True
    return name in _get_registry_toolset_aliases()


def create_custom_toolset(
    name: str,
    description: str,
    tools: List[str] = None,
    includes: List[str] = None
) -> None:
    """
    Create a custom toolset at runtime.
    
    Args:
        name (str): Name for the new toolset
        description (str): Description of the toolset
        tools (List[str]): Direct tools to include
        includes (List[str]): Other toolsets to include
    """
    TOOLSETS[name] = {
        "description": description,
        "tools": tools or [],
        "includes": includes or []
    }




def get_toolset_info(name: str) -> Dict[str, Any]:
    """
    Get detailed information about a toolset including resolved tools.
    
    Args:
        name (str): Toolset name
        
    Returns:
        Dict: Detailed toolset information
    """
    toolset = get_toolset(name)
    if not toolset:
        return None
    
    resolved_tools = resolve_toolset(name)
    
    return {
        "name": name,
        "description": toolset["description"],
        "direct_tools": toolset["tools"],
        "includes": toolset["includes"],
        "resolved_tools": resolved_tools,
        "tool_count": len(resolved_tools),
        "is_composite": bool(toolset["includes"])
    }




if __name__ == "__main__":
    print("Toolsets System Demo")
    print("=" * 60)
    
    print("\nAvailable Toolsets:")
    print("-" * 40)
    for name, toolset in get_all_toolsets().items():
        info = get_toolset_info(name)
        composite = "[composite]" if info["is_composite"] else "[leaf]"
        print(f"  {composite} {name:20} - {toolset['description']}")
        print(f"     Tools: {len(info['resolved_tools'])} total")
    
    print("\nToolset Resolution Examples:")
    print("-" * 40)
    for name in ["web", "terminal", "safe", "debugging"]:
        tools = resolve_toolset(name)
        print(f"\n  {name}:")
        print(f"    Resolved to {len(tools)} tools: {', '.join(sorted(tools))}")
    
    print("\nMultiple Toolset Resolution:")
    print("-" * 40)
    combined = resolve_multiple_toolsets(["web", "vision", "terminal"])
    print("  Combining ['web', 'vision', 'terminal']:")
    print(f"    Result: {', '.join(sorted(combined))}")
    
    print("\nCustom Toolset Creation:")
    print("-" * 40)
    create_custom_toolset(
        name="my_custom",
        description="My custom toolset for specific tasks",
        tools=["web_search"],
        includes=["terminal", "vision"]
    )
    custom_info = get_toolset_info("my_custom")
    print("  Created 'my_custom' toolset:")
    print(f"    Description: {custom_info['description']}")
    print(f"    Resolved tools: {', '.join(custom_info['resolved_tools'])}")
