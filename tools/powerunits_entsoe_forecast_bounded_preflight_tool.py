#!/usr/bin/env python3
"""
Hermes local **preflight** for bounded ENTSO-E **forecast** sync (DE / v1 / ≤7d).

No Powerunits HTTP, no job execution. Gated by ``HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED``
(optional allowlist) or legacy ``HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_PREFLIGHT_ENABLED``.
"""

from __future__ import annotations

import json

from tools.powerunits_bounded_family_gates import (
    ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ENTSOE_FORECAST_BOUNDED_LEGACY_ENV,
    ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV,
    entsoe_forecast_bounded_core_step_enabled,
    entsoe_forecast_bounded_gate_requirement_text,
)
from tools.powerunits_entsoe_forecast_bounded_slice import validate_entsoe_forecast_bounded_slice

_STEP = "preflight"
_LEGACY_ENV = ENTSOE_FORECAST_BOUNDED_LEGACY_ENV[_STEP]
_SURFACE = "powerunits_entsoe_forecast_bounded_preflight"


def check_powerunits_entsoe_forecast_bounded_preflight_requirements() -> bool:
    return entsoe_forecast_bounded_core_step_enabled(_STEP)


def preflight_powerunits_entsoe_forecast_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
) -> str:
    if not check_powerunits_entsoe_forecast_bounded_preflight_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": f"{entsoe_forecast_bounded_gate_requirement_text(_STEP)}.",
            },
            ensure_ascii=False,
        )

    base = {
        "surface": _SURFACE,
        "hermes_called_powerunits_http": False,
        "hermes_statement": (
            "Hermes did not call Powerunits HTTP or run entsoe_forecast_job. "
            "Live bounded ingest uses execute_powerunits_entsoe_forecast_bounded_slice "
            "(POST /internal/hermes/bounded/v1/entsoe-forecast/recompute) with "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET. "
            "This family is **forecast only** (F3b load + F4 wind/solar day-ahead), not realized market."
        ),
        "bounded_http_operator_hint": (
            "Live path: preflight (this tool) → execute_powerunits_entsoe_forecast_bounded_slice → "
            "validate_powerunits_entsoe_forecast_bounded_window → "
            "summarize_powerunits_entsoe_forecast_bounded_window. "
            "Repo B runs entsoe_forecast_job for DE; market_feature_job / market_driver_feature_job "
            "were NOT run."
        ),
    }

    try:
        cc, start_dt, end_dt = validate_entsoe_forecast_bounded_slice(
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


PREFLIGHT_ENTSOE_FORECAST_SCHEMA = {
    "name": "preflight_powerunits_entsoe_forecast_bounded_slice",
    "description": (
        "**Bounded ENTSO-E forecast preflight** — local DE / v1 / ≤7d slice check only; no HTTP. "
        f"Gate: `{ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV}` or `{_LEGACY_ENV}`; optional "
        f"`{ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV}`."
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
    name="preflight_powerunits_entsoe_forecast_bounded_slice",
    toolset="powerunits_entsoe_forecast_bounded_preflight",
    schema=PREFLIGHT_ENTSOE_FORECAST_SCHEMA,
    handler=lambda args, **kw: preflight_powerunits_entsoe_forecast_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_entsoe_forecast_bounded_preflight_requirements,
    requires_env=[
        ENTSOE_FORECAST_BOUNDED_PRIMARY_ENV,
        ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
    ],
    emoji="✅",
)
