#!/usr/bin/env python3
"""
Hermes local **preflight** for bounded ENTSO-E market sync (DE / v1 / ≤7d).

No Powerunits HTTP, no job execution. Gated by ``HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED``.
"""

from __future__ import annotations

import json
import os

from tools.powerunits_entsoe_market_bounded_slice import validate_entsoe_bounded_slice

_FEATURE_ENV = "HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_PREFLIGHT_ENABLED"
_SURFACE = "powerunits_entsoe_market_bounded_preflight"


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_entsoe_market_bounded_preflight_requirements() -> bool:
    return _truthy_env(_FEATURE_ENV)


def preflight_powerunits_entsoe_market_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
) -> str:
    if not check_powerunits_entsoe_market_bounded_preflight_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": f"{_FEATURE_ENV} must be truthy for this tool.",
            },
            ensure_ascii=False,
        )

    base = {
        "surface": _SURFACE,
        "hermes_called_powerunits_http": False,
        "hermes_statement": (
            "Hermes did not call Powerunits HTTP or run entsoe_market_job. "
            "Live bounded ingest uses execute_powerunits_entsoe_market_bounded_slice "
            "(POST /internal/hermes/bounded/v1/entsoe-market-sync/recompute) with "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "bounded_http_operator_hint": (
            "Live path: preflight (this tool) → execute_powerunits_entsoe_market_bounded_slice → "
            "validate_powerunits_entsoe_market_bounded_window → summarize_powerunits_entsoe_market_bounded_window. "
            "Repo B runs entsoe_market_job.run for DE only; v1 readiness-window is planned as a follow-up."
        ),
    }

    try:
        cc, start_dt, end_dt = validate_entsoe_bounded_slice(
            (country or "").strip(),
            (start or "").strip(),
            (end or "").strip(),
            (version or "").strip(),
        )
    except ValueError as e:
        return json.dumps(
            {
                **base,
                "syntactically_valid": False,
                "validation_messages": [str(e)],
                "slice": None,
            },
            ensure_ascii=False,
        )

    slice_obj = {
        "country": cc,
        "version": (version or "").strip(),
        "start_utc": start_dt.isoformat().replace("+00:00", "Z"),
        "end_utc_exclusive": end_dt.isoformat().replace("+00:00", "Z"),
    }
    return json.dumps(
        {
            **base,
            "syntactically_valid": True,
            "validation_messages": [],
            "slice": slice_obj,
        },
        ensure_ascii=False,
    )


PREFLIGHT_ENTSOE_SCHEMA = {
    "name": "preflight_powerunits_entsoe_market_bounded_slice",
    "description": (
        "**Bounded ENTSO-E market sync preflight** — local DE / v1 / ≤7d slice check only; "
        f"no HTTP. Requires {_FEATURE_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Must be DE (v1)."},
            "start": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "end": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
            "version": {"type": "string", "description": "Must be v1."},
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="preflight_powerunits_entsoe_market_bounded_slice",
    toolset="powerunits_entsoe_market_bounded_preflight",
    schema=PREFLIGHT_ENTSOE_SCHEMA,
    handler=lambda args, **kw: preflight_powerunits_entsoe_market_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_entsoe_market_bounded_preflight_requirements,
    requires_env=[_FEATURE_ENV],
    emoji="✅",
)
