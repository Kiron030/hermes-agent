"""Narrow typed schemas. No URL, host, route, path, or SQL parameter."""

from __future__ import annotations

from .operations import OPERATIONS, TOOLSET_NAME

_NO_TRANSPORT = (
    "The model cannot choose a host, URL, route, path, or SQL statement. "
    "Repo B remains authoritative for domain rules."
)


def _object_schema(
    *,
    name: str,
    description: str,
    properties: dict,
    required: list[str],
) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


READ_COVERAGE_SNAPSHOT = _object_schema(
    name="read_powerunits_coverage_snapshot_v1",
    description=(
        "Read-only coverage + pipeline freshness snapshot via one bounded "
        "Repo-B POST. " + _NO_TRANSPORT
    ),
    properties={
        "country_codes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "ISO2 list (e.g. DE, PL). Required.",
        },
        "window_start_utc": {
            "type": "string",
            "description": "Inclusive UTC ISO-8601 (Z).",
        },
        "window_end_utc": {
            "type": "string",
            "description": "Exclusive UTC ISO-8601 (Z).",
        },
        "version": {
            "type": "string",
            "description": "Dataset version; default v1.",
            "default": "v1",
        },
    },
    required=["country_codes", "window_start_utc", "window_end_utc"],
)

INVENTORY_BOUNDED_COVERAGE = _object_schema(
    name="inventory_powerunits_bounded_coverage_v1",
    description=(
        "Read-only multi-country coverage inventory via one bounded Repo-B POST. "
        "No workspace CSV persist, no writes. " + _NO_TRANSPORT
    ),
    properties={
        "window_start_utc": {
            "type": "string",
            "description": "Inclusive UTC ISO-8601 with Z.",
        },
        "window_end_utc": {
            "type": "string",
            "description": "Exclusive UTC ISO-8601 with Z.",
        },
        "country_codes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "ISO2 list. Required.",
        },
        "families": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional Repo-B family id subset.",
        },
        "version": {
            "type": "string",
            "description": "v1.",
            "default": "v1",
        },
    },
    required=["window_start_utc", "window_end_utc", "country_codes"],
)

READ_ENTSOE_BZN_PRICE_READINESS = _object_schema(
    name="read_powerunits_entsoe_bzn_price_readiness_v1",
    description=(
        "Read-only BZN day-ahead price readiness via one bounded Repo-B POST. "
        + _NO_TRANSPORT
    ),
    properties={
        "country_codes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Advisory ISO2 list. Omit for the Repo-B default batch.",
        },
        "window_start_utc": {
            "type": "string",
            "description": "Inclusive UTC ISO-8601 (Z).",
        },
        "window_end_utc": {
            "type": "string",
            "description": "Exclusive UTC ISO-8601 (Z).",
        },
        "table_version": {
            "type": "string",
            "description": "BZN logical table version; default bzn_advisory_v1.",
            "default": "bzn_advisory_v1",
        },
    },
    required=["window_start_utc", "window_end_utc"],
)

READINESS_OPTION_D = _object_schema(
    name="readiness_powerunits_option_d_bounded_window",
    description=(
        "Read-only Option D readiness-window via one bounded Repo-B POST. "
        "Plugin-side checks may fail early on empty fields only; Repo B is "
        "authoritative for country/window rules. " + _NO_TRANSPORT
    ),
    properties={
        "country": {"type": "string", "description": "ISO2 country code."},
        "start": {"type": "string", "description": "Inclusive UTC ISO-8601 with Z."},
        "end": {"type": "string", "description": "Exclusive UTC ISO-8601 with Z."},
        "version": {"type": "string", "description": "Dataset version."},
        "pipeline_run_id": {
            "type": "string",
            "description": "Optional; forwarded, may be ignored by Repo B.",
        },
    },
    required=["country", "start", "end", "version"],
)


SCHEMAS = {
    "read_powerunits_coverage_snapshot_v1": READ_COVERAGE_SNAPSHOT,
    "inventory_powerunits_bounded_coverage_v1": INVENTORY_BOUNDED_COVERAGE,
    "read_powerunits_entsoe_bzn_price_readiness_v1": READ_ENTSOE_BZN_PRICE_READINESS,
    "readiness_powerunits_option_d_bounded_window": READINESS_OPTION_D,
}

assert set(SCHEMAS) == set(OPERATIONS)
assert TOOLSET_NAME == "powerunits_bounded_reads"
