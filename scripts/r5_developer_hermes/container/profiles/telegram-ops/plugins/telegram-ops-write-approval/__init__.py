"""Escalate telegram-ops write/patch calls to the upstream approval gate.

Upstream ``file`` is atomic (read_file + search_files + write_file + patch).
``approvals.mode: manual`` gates dangerous terminal commands, not ordinary
workspace writes. This profile-local plugin uses the documented
``pre_tool_call`` ``{"action": "approve"}`` directive so write/patch share
the same human gate as dangerous commands.

The plugin is opt-in via telegram-ops ``plugins.enabled``. It is not loaded
for the default Developer / Desktop profile.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

WRITE_TOOLS = frozenset({"write_file", "patch"})
PROTECTED_BASENAMES = frozenset({"config.yaml", ".env", ".r5-telegram-ops-seed"})
PLUGIN_MARKER = "telegram-ops-write-approval"
APPROVE_MESSAGE = (
    "telegram-ops requires explicit manual approval before write_file/patch"
)
POLICY_BLOCK_MESSAGE = (
    "telegram-ops refuses writes to profile policy or secret files"
)


def _normalized(path: str) -> str:
    return (path or "").replace("\\", "/").strip()


def is_protected_profile_path(path: str) -> bool:
    """Return True for telegram-ops policy/secret/plugin paths."""
    raw = _normalized(path)
    if not raw:
        return False
    lowered = raw.lower()
    if PLUGIN_MARKER in lowered:
        return True
    try:
        resolved = Path(raw).expanduser()
        if resolved.is_absolute():
            resolved = resolved.resolve()
        resolved_s = str(resolved).replace("\\", "/").lower()
    except Exception:
        resolved_s = lowered
        resolved = Path(raw)
    if PLUGIN_MARKER in resolved_s:
        return True
    name = resolved.name.lower()
    if name in PROTECTED_BASENAMES and "telegram-ops" in resolved_s:
        return True
    try:
        from hermes_constants import get_hermes_home

        home = get_hermes_home().resolve()
        candidate = resolved if resolved.is_absolute() else (home / resolved)
        if name in PROTECTED_BASENAMES:
            try:
                candidate.resolve().relative_to(home)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def pre_tool_call(
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, str] | None:
    if tool_name not in WRITE_TOOLS:
        return None
    payload = args if isinstance(args, dict) else {}
    path = str(payload.get("path") or "")
    if is_protected_profile_path(path):
        return {"action": "block", "message": POLICY_BLOCK_MESSAGE}
    return {
        "action": "approve",
        "message": APPROVE_MESSAGE,
        "rule_key": f"telegram-ops:{tool_name}",
    }


def register(ctx) -> None:
    ctx.register_hook("pre_tool_call", pre_tool_call)
