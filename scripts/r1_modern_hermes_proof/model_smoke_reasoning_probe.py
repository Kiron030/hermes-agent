#!/usr/bin/env python3
"""Intercept Responses-API kwargs for gpt-4.1-mini. No network, no secrets."""

from __future__ import annotations

import json
import sys

from hermes_cli.config import load_config
from hermes_constants import resolve_reasoning_config
from agent.transports.codex import ResponsesApiTransport


def _effort(kwargs: dict) -> str | None:
    reasoning = kwargs.get("reasoning")
    if isinstance(reasoning, dict):
        effort = reasoning.get("effort")
        return str(effort) if effort is not None else None
    return None


def main() -> int:
    cfg = load_config()
    model = "gpt-4.1-mini"
    resolved = resolve_reasoning_config(cfg, model)
    transport = ResponsesApiTransport()
    messages = [{"role": "user", "content": "R1 reasoning probe"}]
    disabled = transport.build_kwargs(
        model=model,
        messages=messages,
        tools=None,
        reasoning_config=resolved,
        instructions="r1-probe",
        provider="openai-api",
        base_url="https://api.openai.com/v1",
    )
    upstream_default = transport.build_kwargs(
        model=model,
        messages=messages,
        tools=None,
        reasoning_config=None,
        instructions="r1-probe",
        provider="openai-api",
        base_url="https://api.openai.com/v1",
    )
    payload = {
        "provider": "openai-api",
        "model": model,
        "resolved_reasoning_enabled": bool(resolved and resolved.get("enabled") is not False)
        if resolved
        else None,
        "resolved_omits_reasoning_effort": _effort(disabled) is None,
        "upstream_default_effort": _effort(upstream_default),
        "upstream_default_emits_reasoning_effort": _effort(upstream_default) is not None,
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    ok = (
        payload["resolved_omits_reasoning_effort"] is True
        and payload["upstream_default_effort"] == "medium"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
