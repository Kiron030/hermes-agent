#!/usr/bin/env python3
"""Probe Hermes runtime provider resolution for R1 model-smoke.

Uses a sentinel key already mapped into the child env. Prints only safe
booleans and URL class fields — never the key, Authorization value, or
query secrets.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
from urllib.parse import urlparse


SENTINEL_ENV = "HERMES_R1_AUTH_PROBE_SENTINEL"


def main() -> int:
    sentinel = os.environ.get(SENTINEL_ENV, "")
    expected_key_env = os.environ.get("HERMES_R1_AUTH_PROBE_KEY_ENV", "OPENAI_API_KEY")
    child_key = os.environ.get(expected_key_env, "")
    requested = os.environ.get("HERMES_INFERENCE_PROVIDER", "openai-api")
    model = os.environ.get("HERMES_INFERENCE_MODEL", "gpt-4.1-mini")

    from hermes_cli.runtime_provider import resolve_runtime_provider

    runtime = resolve_runtime_provider(requested=requested, target_model=model)
    base = str(runtime.get("base_url") or "")
    parsed = urlparse(base)
    resolved_key = str(runtime.get("api_key") or "")
    payload = {
        "provider": runtime.get("provider"),
        "base_url_scheme": parsed.scheme,
        "base_url_host": parsed.hostname,
        "path_class": "/v1/chat/completions",
        "child_key_present": bool(child_key),
        "runtime_key_present": bool(resolved_key),
        "runtime_key_matches_sentinel": bool(sentinel)
        and bool(resolved_key)
        and hmac.compare_digest(resolved_key, sentinel),
        "auth_header_scheme": "Bearer" if resolved_key else None,
        "wrong_host_openrouter": (parsed.hostname or "").endswith("openrouter.ai"),
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    ok = (
        payload["child_key_present"]
        and payload["runtime_key_matches_sentinel"]
        and payload["provider"] == requested
        and not payload["wrong_host_openrouter"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
