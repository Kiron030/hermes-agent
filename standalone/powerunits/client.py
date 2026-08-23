"""One generic bounded HTTP client.

Caller contract: ``operation_id`` + typed JSON body.
Not: arbitrary URL, path, SQL, or filesystem path.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Callable, Mapping

import httpx

from .host import apply_target_refusal, resolve_target
from .operations import (
    FORBIDDEN_TRANSPORT_KEYS,
    SECRET_ENV,
    TIMEOUT_ENV,
    get_operation,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 120.0
MIN_TIMEOUT_S = 30.0
MAX_RESPONSE_CHARS = 200000
CONNECT_TIMEOUT_S = 15.0

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)

HttpPost = Callable[[str, dict[str, str], dict[str, Any], float], Any]


def redact_secrets(text: str, *, limit: int = MAX_RESPONSE_CHARS) -> str:
    if not text:
        return ""
    redacted = _SECRET_URL_RE.sub("[REDACTED_URL]", text)
    if len(redacted) > limit:
        return redacted[:limit] + "\n...[truncated]"
    return redacted


def _timeout_s() -> float:
    raw = (os.getenv(TIMEOUT_ENV) or "").strip()
    if not raw:
        return float(DEFAULT_TIMEOUT_S)
    try:
        return max(MIN_TIMEOUT_S, float(raw))
    except ValueError:
        return float(DEFAULT_TIMEOUT_S)


def default_http_post(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout_s: float,
) -> httpx.Response:
    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT_S, read=timeout_s, write=60.0, pool=15.0)
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, headers=headers, json=json_body)


# Tests replace this. Production uses default_http_post.
http_post: HttpPost = default_http_post


def _structured_error(
    *,
    error_code: str,
    message: str,
    surface: str,
    read_attempted: bool = False,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "success": False,
        "error_code": error_code,
        "message": message,
        "surface": surface,
        "read_attempted": read_attempted,
        "http_status_from_repo_b": None,
    }
    if extra:
        out.update(extra)
    return out


def invoke(operation_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
    """POST a typed body to the frozen route for ``operation_id``."""

    try:
        spec = get_operation(operation_id)
    except KeyError:
        return _structured_error(
            error_code="unknown_operation_id",
            message=f"operation_id {operation_id!r} is not in the bounded registry.",
            surface="powerunits_bounded_reads",
        )

    surface = spec.operation_id
    transport_hits = sorted(set(body) & FORBIDDEN_TRANSPORT_KEYS)
    if transport_hits:
        return _structured_error(
            error_code="unexpected_field",
            message=f"transport fields are not accepted: {transport_hits}",
            surface=surface,
            extra={"rejected_fields": transport_hits},
        )

    secret = (os.getenv(SECRET_ENV) or "").strip()
    resolved = resolve_target()
    if resolved.refused or not resolved.base_url or not secret:
        payload = {
            "error_code": "read_config_incomplete",
            "surface": surface,
            "read_attempted": False,
            "inventory_attempted": False,
            "readiness_attempted": False,
            "http_status_from_repo_b": None,
            "success": False,
            "message": "Base URL, allowlisted host, and bearer secret are required.",
        }
        return apply_target_refusal(payload)

    # Route is a compile-time suffix. Caller cannot choose a path.
    url = f"{resolved.base_url}{spec.route_suffix}"
    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    json_body = dict(body)
    timeout_s = _timeout_s()

    try:
        resp = http_post(url, headers, json_body, timeout_s)
    except httpx.TimeoutException:
        logger.warning("powerunits plugin: HTTP timeout operation=%s", operation_id)
        return _structured_error(
            error_code="timeout",
            message="bounded read timed out",
            surface=surface,
            read_attempted=True,
            extra={"error_class": "timeout", "correlation_id": correlation_id},
        )
    except httpx.RequestError as exc:
        logger.warning("powerunits plugin: HTTP error operation=%s", operation_id)
        return _structured_error(
            error_code="http_client_error",
            message="bounded read transport failed",
            surface=surface,
            read_attempted=True,
            extra={
                "error_class": "http_client_error",
                "response_body_summary": redact_secrets(str(exc), limit=500),
                "correlation_id": correlation_id,
            },
        )

    status = int(resp.status_code)
    raw_text = redact_secrets(getattr(resp, "text", "") or "")
    try:
        parsed = resp.json() if getattr(resp, "content", None) else {}
        if not isinstance(parsed, dict):
            parsed = {"repo_b_non_object_json": parsed}
    except (ValueError, TypeError, json.JSONDecodeError):
        parsed = {"parse_error": True, "response_body_summary": raw_text[:8000]}

    merged: dict[str, Any] = dict(parsed)
    merged["http_status_from_repo_b"] = status
    merged["http_status"] = status
    merged["read_attempted"] = True
    merged.setdefault("correlation_id", correlation_id)
    merged["surface"] = surface
    merged["effect_class"] = spec.effect_class
    if status != 200 or merged.get("success") is False:
        merged.setdefault("response_body_summary", raw_text)
        merged.setdefault("success", False)
    return merged
