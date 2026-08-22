#!/usr/bin/env python3
"""PowerUnits write-approval helper (S0-B).

Reuses ``tools.approval.request_tool_approval``. Does not copy approval logic.

Automatic bypass modes (YOLO, ``approvals.mode=off``, cron ``cron_mode=approve``)
cannot authorize a PowerUnits bounded write by themselves. A prior explicit
human allowlist entry for the same rule key may still pass.
"""

from __future__ import annotations

from typing import Any, Mapping

from tools.powerunits_bounded_effects_v1 import (
    UnclassifiedPowerUnitsOperation,
    effect_class_for,
    is_write_effect,
)

_EMPTY = "-"


def _canon_token(value: str | None) -> str:
    text = " ".join((value or "").strip().split())
    return text if text else _EMPTY


def _canon_country(value: str | None) -> str:
    token = _canon_token(value)
    if token == _EMPTY:
        return _EMPTY
    return token.upper()


def _canon_window_token(value: str | None) -> str:
    token = _canon_token(value)
    if token == _EMPTY:
        return _EMPTY
    return token.replace(" ", "").replace("z", "Z")


def _canon_resource(value: str | None) -> str:
    """Preserve resource/path identity. Do not case-fold or apply z→Z."""

    text = (value or "").strip()
    return text if text else _EMPTY


def canonical_window(start: str | None = None, end: str | None = None) -> str:
    left = _canon_window_token(start)
    right = _canon_window_token(end)
    if left == _EMPTY and right == _EMPTY:
        return _EMPTY
    return f"{left}/{right}"


def canonical_write_rule_key(
    operation: str,
    country: str | None = None,
    window: str | None = None,
    *,
    resource: str | None = None,
) -> str:
    """Deterministic write identity with typed slots.

    Temporal slices use ``window:`` (ISO z→Z). Resource/path identities use
    ``resource:`` and keep case so ``notes/az.md`` ≠ ``notes/aZ.md``.
    """

    op = _canon_token(operation)
    cc = _canon_country(country)
    if resource is not None and str(resource).strip():
        return f"{op}:{cc}:resource:{_canon_resource(resource)}"
    return f"{op}:{cc}:window:{_canon_window_token(window)}"


def write_approval_error_fields(decision: Mapping[str, Any]) -> dict[str, Any]:
    """Structured, model-readable refusal fields for write wrappers."""

    status = str(decision.get("status") or "").strip()
    if status == "approval_required":
        error_code = "approval_required"
    else:
        error_code = str(decision.get("error_code") or "approval_denied")
        if not status:
            status = error_code
    return {
        "error_code": error_code,
        "status": status,
        "message": decision.get("message"),
        "rule_key": decision.get("rule_key"),
        "execution_attempted": False,
        "success": False,
        "http_status": None,
        "error_class": error_code,
    }


def _automatic_bypass_refusal(rule_key: str, operation: str) -> dict[str, Any]:
    return {
        "approved": False,
        "error_code": "approval_denied",
        "status": "approval_denied",
        "rule_key": rule_key,
        "message": (
            f"BLOCKED: PowerUnits bounded write '{operation}' cannot be authorized by "
            "YOLO, approvals.mode=off, or cron_mode=approve. An explicit human "
            f"approval for this exact action ({rule_key}) is required."
        ),
    }


def write_approval_tool_error(decision: Mapping[str, Any]) -> str:
    """Structured tool_error JSON for local durable writers."""

    from tools.registry import tool_error

    fields = write_approval_error_fields(decision)
    return tool_error(
        str(fields.get("message") or "PowerUnits write not approved"),
        error_code=fields["error_code"],
        status=fields["status"],
        success=False,
        rule_key=fields.get("rule_key"),
    )


def _cron_auto_approve_active() -> bool:
    from tools.approval import env_var_enabled, _get_cron_approval_mode

    return bool(env_var_enabled("HERMES_CRON_SESSION") and _get_cron_approval_mode() == "approve")


def _automatic_write_bypass_active() -> bool:
    from tools.approval import is_approval_bypass_active

    return bool(is_approval_bypass_active() or _cron_auto_approve_active())


def _unclassified_refusal(operation: str) -> dict[str, Any]:
    return {
        "approved": False,
        "error_code": "effect_unclassified",
        "status": "approval_denied",
        "rule_key": None,
        "message": (
            f"BLOCKED: PowerUnits operation '{operation}' has no effect classification. "
            "Unclassified writes fail closed."
        ),
    }


def require_powerunits_write_approval(
    *,
    operation: str,
    country: str | None = None,
    window: str | None = None,
    resource: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Gate a PowerUnits write. Call before any HTTP POST or local overwrite.

    Returns ``{"approved": True, ...}`` or a structured refusal
    (``approved`` is False). Never raises for a normal deny.
    """

    from tools.approval import (
        get_current_session_key,
        is_approved,
        request_tool_approval,
    )

    op = (operation or "").strip()
    try:
        effect = effect_class_for(op)
    except UnclassifiedPowerUnitsOperation:
        return _unclassified_refusal(op or "<empty>")

    if not is_write_effect(effect):
        return {"approved": True, "message": None, "rule_key": None, "effect_class": effect}

    rule_key = canonical_write_rule_key(op, country, window, resource=resource)
    pattern_key = f"plugin_rule:{rule_key}"
    description = reason or (
        f"PowerUnits {effect} requires explicit human approval for {rule_key}"
    )

    if _automatic_write_bypass_active():
        session_key = get_current_session_key()
        if is_approved(session_key, pattern_key):
            return {
                "approved": True,
                "message": None,
                "rule_key": rule_key,
                "effect_class": effect,
            }
        return _automatic_bypass_refusal(rule_key, op)

    result = request_tool_approval(op, description, rule_key=rule_key)
    approved = bool(result.get("approved"))
    out: dict[str, Any] = dict(result)
    out["approved"] = approved
    out["rule_key"] = rule_key
    out["effect_class"] = effect
    if approved:
        return out

    status = str(out.get("status") or "").strip()
    if status == "approval_required":
        out["error_code"] = "approval_required"
    else:
        out.setdefault("error_code", "approval_denied")
        out.setdefault("status", "approval_denied")
        if not out.get("message"):
            out["message"] = (
                f"BLOCKED: PowerUnits bounded write '{op}' was not approved "
                f"({rule_key})."
            )
    return out
