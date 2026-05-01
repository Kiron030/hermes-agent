#!/usr/bin/env python3
"""
Hermes local **preflight** for bounded ERA5 weather sync (DE/FR slices / v1 / ≤7d).

No Powerunits HTTP, no job execution. Gated by ``HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED``
(optional allowlist) or legacy ``HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_PREFLIGHT_ENABLED``.
"""

from __future__ import annotations

import json

from tools.powerunits_bounded_family_gates import (
    ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
    ERA5_WEATHER_BOUNDED_LEGACY_ENV,
    ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
    era5_weather_bounded_core_step_enabled,
    era5_weather_bounded_gate_requirement_text,
    era5_weather_bounded_request_country_permitted,
)
from tools.powerunits_era5_weather_bounded_slice import validate_era5_bounded_slice

_STEP = "preflight"
_LEGACY_ENV = ERA5_WEATHER_BOUNDED_LEGACY_ENV[_STEP]
_SURFACE = "powerunits_era5_weather_bounded_preflight"

_NOT_AUTO = (
    "After a successful bounded ERA5 execute, Repo B runs only era5_weather_job — "
    "market_feature_job was NOT auto-run and market_driver_feature_job was NOT auto-run. "
    "Bounded Hermes Option D executes DE/PL market-feature slices separately; refresh "
    "DE market_features_hourly via Repo B worker/runbook/CLI when needed."
)


def check_powerunits_era5_weather_bounded_preflight_requirements() -> bool:
    return era5_weather_bounded_core_step_enabled(_STEP)


def preflight_powerunits_era5_weather_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
) -> str:
    if not check_powerunits_era5_weather_bounded_preflight_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": f"{era5_weather_bounded_gate_requirement_text(_STEP)}.",
            },
            ensure_ascii=False,
        )

    base = {
        "surface": _SURFACE,
        "hermes_called_powerunits_http": False,
        "hermes_statement": (
            "Hermes did not call Powerunits HTTP or run era5_weather_job. "
            "Live bounded ingest uses execute_powerunits_era5_weather_bounded_slice "
            "(POST /internal/hermes/bounded/v1/era5-weather/recompute) with "
            "POWERUNITS_INTERNAL_EXECUTE_BASE_URL and POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET."
        ),
        "bounded_http_operator_hint": (
            "Live path: preflight (this tool) → execute_powerunits_era5_weather_bounded_slice → "
            "validate_powerunits_era5_weather_bounded_window → summarize_powerunits_era5_weather_bounded_window. "
            f"{_NOT_AUTO}"
        ),
    }

    try:
        cc, start_dt, end_dt = validate_era5_bounded_slice(
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

    if not era5_weather_bounded_request_country_permitted(cc):
        slim = {
            "country": cc,
            "version": (version or "").strip(),
            "start_utc": start_dt.isoformat().replace("+00:00", "Z"),
            "end_utc_exclusive": end_dt.isoformat().replace("+00:00", "Z"),
        }
        return json.dumps(
            {
                **base,
                "error_code": "country_not_permitted",
                "syntactically_valid": False,
                "validation_messages": [
                    f"`{cc}` is not permitted: set `{ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV}` "
                    f"when `{ERA5_WEATHER_BOUNDED_PRIMARY_ENV}` is enabled (unset ⇒ DE only)."
                ],
                "slice": slim,
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


PREFLIGHT_ERA5_SCHEMA = {
    "name": "preflight_powerunits_era5_weather_bounded_slice",
    "description": (
        "**Bounded ERA5 weather sync preflight** — local DE / v1 / ≤7d slice check only; "
        f"no HTTP. Gate `{ERA5_WEATHER_BOUNDED_PRIMARY_ENV}` or `{_LEGACY_ENV}`; optional "
        f"`{ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV}`. "
        "Execute path does not auto-run market_feature_job or market_driver_feature_job."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {
                "type": "string",
                "description": "Bounded ERA5 v1 ISO2 (DE or FR; same set as Repo B bounded ERA5 allowlist).",
            },
            "start": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
            "end": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
            "version": {"type": "string", "description": "Must be v1."},
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="preflight_powerunits_era5_weather_bounded_slice",
    toolset="powerunits_era5_weather_bounded_preflight",
    schema=PREFLIGHT_ERA5_SCHEMA,
    handler=lambda args, **kw: preflight_powerunits_era5_weather_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_era5_weather_bounded_preflight_requirements,
    requires_env=[
        ERA5_WEATHER_BOUNDED_PRIMARY_ENV,
        ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES_ENV,
        _LEGACY_ENV,
    ],
    emoji="✅",
)
