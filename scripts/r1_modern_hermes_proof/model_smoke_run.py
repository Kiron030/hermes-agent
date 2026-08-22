#!/usr/bin/env python3
"""R1 oneshot-equivalent that honors isolated reasoning config.

Pinned ``hermes -z`` constructs AIAgent without resolve_reasoning_config.
agent.transports.codex.ResponsesApiTransport.build_kwargs then defaults
reasoning.effort=medium, which gpt-4.1-mini rejects (HTTP 400).

This runner keeps provider=openai-api and model=gpt-4.1-mini and applies
agent.reasoning_effort from the isolated HERMES_HOME config. It does not
patch Hermes core.
"""

from __future__ import annotations

import logging
import os
import sys


SMOKE_PROMPT = "Reply with exactly: R1_MODEL_SMOKE_OK"


def main() -> int:
    os.environ["HERMES_YOLO_MODE"] = "1"
    os.environ["HERMES_ACCEPT_HOOKS"] = "1"

    from hermes_cli.config import load_config
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from hermes_cli.tools_config import _get_platform_tools
    from hermes_constants import resolve_reasoning_config
    from gateway.session_context import declare_stateless_channel
    from run_agent import AIAgent

    try:
        from hermes_cli.oneshot import _create_session_db_for_oneshot
    except Exception:
        _create_session_db_for_oneshot = None

    declare_stateless_channel()
    cfg = load_config()
    model = os.environ.get("HERMES_INFERENCE_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    provider = os.environ.get("HERMES_INFERENCE_PROVIDER", "openai-api").strip() or "openai-api"
    runtime = resolve_runtime_provider(requested=provider, target_model=model)
    reasoning_config = resolve_reasoning_config(cfg, model)
    toolsets = sorted(_get_platform_tools(cfg, "cli"))
    session_db = _create_session_db_for_oneshot() if _create_session_db_for_oneshot else None
    agent = None
    try:
        agent = AIAgent(
            api_key=runtime.get("api_key"),
            base_url=runtime.get("base_url"),
            provider=runtime.get("provider"),
            requested_provider=runtime.get("requested_provider"),
            api_mode=runtime.get("api_mode"),
            model=model,
            enabled_toolsets=toolsets,
            quiet_mode=True,
            platform="cli",
            session_db=session_db,
            credential_pool=runtime.get("credential_pool"),
            reasoning_config=reasoning_config,
        )
        agent.suppress_status_output = True
        agent.stream_delta_callback = None
        agent.tool_gen_callback = None
        result = agent.run_conversation(SMOKE_PROMPT)
        text = result.get("final_response") or ""
        if result.get("failed") or result.get("partial"):
            err = result.get("error") or result.get("final_response") or "agent failed"
            sys.stderr.write(f"{err}\n")
            return 1
        if not str(text).strip():
            sys.stderr.write("r1 model-smoke: no final response\n")
            return 1
        sys.stdout.write(text if str(text).endswith("\n") else f"{text}\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"r1 model-smoke: agent failed: {exc}\n")
        logging.debug("model smoke failed", exc_info=True)
        return 1
    finally:
        if agent is not None:
            try:
                agent.close()
            except Exception:
                pass
        if session_db is not None:
            try:
                session_db.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
