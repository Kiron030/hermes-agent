"""Frozen operation_id → route-suffix registry.

The model never sees a URL, host, path, or SQL field. The client may only
POST to ``base + route_suffix`` for a known operation_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


EFFECT_READ = "READ"
TOOLSET_NAME = "powerunits_bounded_reads"

BASE_URL_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
ALLOWED_HOSTS_ENV = "POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS"
HOST_PIN_MODE_ENV = "POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE"
SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"

# Transport keys the model/client must never treat as routing input.
FORBIDDEN_TRANSPORT_KEYS: FrozenSet[str] = frozenset(
    {
        "url",
        "host",
        "hostname",
        "base_url",
        "path",
        "route",
        "sql",
        "query",
        "file_path",
        "filepath",
    }
)


@dataclass(frozen=True)
class OperationSpec:
    operation_id: str
    tool_name: str
    route_suffix: str
    effect_class: str
    gate_env: str
    r0_wrapper_module: str
    allowed_request_fields: FrozenSet[str]
    required_request_fields: FrozenSet[str]


OPERATIONS: dict[str, OperationSpec] = {
    "read_powerunits_coverage_snapshot_v1": OperationSpec(
        operation_id="read_powerunits_coverage_snapshot_v1",
        tool_name="read_powerunits_coverage_snapshot_v1",
        route_suffix="/internal/hermes/bounded/v1/coverage-snapshot",
        effect_class=EFFECT_READ,
        gate_env="HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED",
        r0_wrapper_module="tools.powerunits_bounded_coverage_snapshot_tool",
        allowed_request_fields=frozenset(
            {"country_codes", "window_start_utc", "window_end_utc", "version"}
        ),
        required_request_fields=frozenset(
            {"country_codes", "window_start_utc", "window_end_utc"}
        ),
    ),
    "inventory_powerunits_bounded_coverage_v1": OperationSpec(
        operation_id="inventory_powerunits_bounded_coverage_v1",
        tool_name="inventory_powerunits_bounded_coverage_v1",
        route_suffix="/internal/hermes/bounded/v1/coverage-inventory",
        effect_class=EFFECT_READ,
        gate_env="HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED",
        r0_wrapper_module="tools.powerunits_bounded_coverage_inventory_tool",
        allowed_request_fields=frozenset(
            {"country_codes", "window_start_utc", "window_end_utc", "families", "version"}
        ),
        required_request_fields=frozenset(
            {"country_codes", "window_start_utc", "window_end_utc"}
        ),
    ),
    "read_powerunits_entsoe_bzn_price_readiness_v1": OperationSpec(
        operation_id="read_powerunits_entsoe_bzn_price_readiness_v1",
        tool_name="read_powerunits_entsoe_bzn_price_readiness_v1",
        route_suffix="/internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read",
        effect_class=EFFECT_READ,
        gate_env="HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED",
        r0_wrapper_module="tools.powerunits_entsoe_bzn_price_readiness_tool",
        allowed_request_fields=frozenset(
            {"country_codes", "window_start_utc", "window_end_utc", "table_version"}
        ),
        required_request_fields=frozenset({"window_start_utc", "window_end_utc"}),
    ),
    "readiness_powerunits_option_d_bounded_window": OperationSpec(
        operation_id="readiness_powerunits_option_d_bounded_window",
        tool_name="readiness_powerunits_option_d_bounded_window",
        route_suffix="/internal/hermes/bounded/v1/market-features-hourly/readiness-window",
        effect_class=EFFECT_READ,
        gate_env="HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED",
        r0_wrapper_module="tools.powerunits_option_d_readiness_tool",
        allowed_request_fields=frozenset(
            {"country", "start", "end", "version", "pipeline_run_id"}
        ),
        required_request_fields=frozenset({"country", "start", "end", "version"}),
    ),
}


def get_operation(operation_id: str) -> OperationSpec:
    spec = OPERATIONS.get(operation_id)
    if spec is None:
        raise KeyError(operation_id)
    return spec
