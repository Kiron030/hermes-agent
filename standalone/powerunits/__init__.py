"""PowerUnits standalone plugin — official Hermes register(ctx) entry."""

from __future__ import annotations

from .operations import BASE_URL_ENV, SECRET_ENV, TOOLSET_NAME, get_operation
from . import schemas, tools


def register(ctx) -> None:
    """Wire four read-only tools through the official plugin API."""

    for operation_id, schema in schemas.SCHEMAS.items():
        spec = get_operation(operation_id)
        ctx.register_tool(
            name=spec.tool_name,
            toolset=TOOLSET_NAME,
            schema=schema,
            handler=tools.HANDLERS[operation_id],
            check_fn=tools.CHECK_FNS[operation_id],
            requires_env=[spec.gate_env, BASE_URL_ENV, SECRET_ENV],
            description=schema["description"],
            emoji="🔌",
        )
