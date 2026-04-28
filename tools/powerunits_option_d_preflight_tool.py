#!/usr/bin/env python3
"""
Hermes-facing **preflight only** for Option D bounded `market_features_hourly` slice.

Validates slice parameters and returns operator instructions. **Does not** run the
wrapper, subprocess, or any DB write. Gated by ``HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED``.
"""

from __future__ import annotations

import json
import logging
import os
from tools.powerunits_option_d_bounded_market_features import _validate_slice

logger = logging.getLogger(__name__)

_FEATURE_ENV = "HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED"
_WRAPPER_MODULE = "tools.powerunits_option_d_bounded_market_features"
_SURFACE = "powerunits_option_d_preflight"

_REQUIRED_ENV_DOCS = [
    "DATABASE_URL",
    "DATABASE_URL_TIMESCALE",
    "MARKET_FEATURES_WRITE_TARGET",
    "POWERUNITS_OPTION_D_PRODUCT_ROOT",
]


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def check_powerunits_option_d_preflight_requirements() -> bool:
    return _truthy_env(_FEATURE_ENV)


def _rollback_sql(country: str, version: str, start_z: str, end_z: str) -> str:
    v_esc = version.replace("'", "''")
    c_esc = country.replace("'", "''")
    return (
        "DELETE FROM public.market_features_hourly\n"
        f"WHERE version = '{v_esc}'\n"
        f"  AND country_code = '{c_esc}'\n"
        f"  AND timestamp_utc >= '{start_z}'::timestamptz\n"
        f"  AND timestamp_utc < '{end_z}'::timestamptz;"
    )


def _operator_command(*, country: str, start: str, end: str, version: str) -> str:
    # Single line for copy-paste; operator sets cwd and env separately.
    return (
        "python -m tools.powerunits_option_d_bounded_market_features "
        f"--country {country} --start {start} --end {end} --version {version}"
    )


def preflight_powerunits_option_d_bounded_slice(
    *,
    country: str,
    start: str,
    end: str,
    version: str,
) -> str:
    if not check_powerunits_option_d_preflight_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "message": f"{_FEATURE_ENV} must be truthy for this tool.",
            },
            ensure_ascii=False,
        )

    country_s = (country or "").strip()
    start_s = (start or "").strip()
    end_s = (end or "").strip()
    version_s = (version or "").strip()

    base = {
        "surface": _SURFACE,
        "hermes_executed_write": False,
        "hermes_ran_bounded_wrapper": False,
        "hermes_statement": (
            "Hermes did not execute the bounded wrapper, run shell commands, "
            "or perform any database write."
        ),
        "required_environment_variables": list(_REQUIRED_ENV_DOCS),
    }

    try:
        cc, start_dt, end_dt = _validate_slice(country_s, start_s, end_s, version_s)
    except ValueError as e:
        payload = {
            **base,
            "syntactically_valid": False,
            "normalization_errors": [str(e)],
            "validation_messages": [str(e)],
            "slice": None,
            "operator_wrapper_command": None,
            "rollback_sql_template": None,
        }
        return json.dumps(payload, ensure_ascii=False)

    start_z = start_dt.isoformat().replace("+00:00", "Z")
    end_z = end_dt.isoformat().replace("+00:00", "Z")
    slice_obj = {
        "country": cc,
        "version": version_s,
        "start_utc": start_z,
        "end_utc_exclusive": end_z,
    }
    payload = {
        **base,
        "syntactically_valid": True,
        "normalization_errors": [],
        "validation_messages": [],
        "slice": slice_obj,
        "operator_wrapper_command": _operator_command(
            country=cc, start=start_s, end=end_s, version=version_s
        ),
        "rollback_sql_template": _rollback_sql(cc, version_s, start_z, end_z),
        "operator_notes": (
            "Run from hermes-agent repo root with uv on PATH. Export "
            "`MARKET_FEATURES_WRITE_TARGET=timescale`, set `POWERUNITS_OPTION_D_PRODUCT_ROOT` "
            "to the Powerunits product repo root, and ensure DATABASE_URL / "
            "DATABASE_URL_TIMESCALE match your target before running the wrapper."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


PREFLIGHT_OPTION_D_SCHEMA = {
    "name": "preflight_powerunits_option_d_bounded_slice",
    "description": (
        "**Option D preflight only** — validates a bounded PL / v1 / ≤24h UTC window for "
        "`market_features_hourly` recompute planning. Returns normalized slice, required env "
        "names, exact **manual** wrapper CLI line, and rollback SQL. **Does not** execute the "
        "wrapper, shell, or database writes. Requires "
        f"{_FEATURE_ENV}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {
                "type": "string",
                "description": "Must be PL (first release).",
            },
            "start": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 with Z, e.g. 2024-01-01T00:00:00Z",
            },
            "end": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 with Z (same semantics as market_feature_job).",
            },
            "version": {
                "type": "string",
                "description": "Must be v1 (first release).",
            },
        },
        "required": ["country", "start", "end", "version"],
    },
}


from tools.registry import registry

registry.register(
    name="preflight_powerunits_option_d_bounded_slice",
    toolset="powerunits_option_d_preflight",
    schema=PREFLIGHT_OPTION_D_SCHEMA,
    handler=lambda args, **kw: preflight_powerunits_option_d_bounded_slice(
        country=str((args or {}).get("country", "")),
        start=str((args or {}).get("start", "")),
        end=str((args or {}).get("end", "")),
        version=str((args or {}).get("version", "")),
    ),
    check_fn=check_powerunits_option_d_preflight_requirements,
    requires_env=[_FEATURE_ENV],
    emoji="✅",
)
