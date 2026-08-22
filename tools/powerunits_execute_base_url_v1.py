#!/usr/bin/env python3
"""Single PowerUnits-owned resolver for the bounded execute Base URL (S0-C).

Bounded HTTP wrappers obtain their execute origin here. The model still cannot
choose host, path, or URL; each wrapper keeps its compile-time route suffix.

This is not a general Hermes url_safety / egress framework.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV = "POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS"
POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV = "POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE"

PIN_MODE_WARN = "warn"
PIN_MODE_ENFORCE = "enforce"
DEFAULT_HOST_PIN_MODE = PIN_MODE_WARN

ERROR_HTTPS_REQUIRED = "execute_target_https_required"
ERROR_URL_INVALID = "execute_target_url_invalid"
ERROR_HOST_REFUSED = "execute_target_host_refused"
ERROR_ALLOWLIST_REQUIRED = "execute_target_host_allowlist_required"
ERROR_PIN_MODE_INVALID = "execute_target_pin_mode_invalid"

_PIN_MODES = frozenset({PIN_MODE_WARN, PIN_MODE_ENFORCE})


@dataclass(frozen=True)
class PowerUnitsExecuteBaseUrlResolution:
    """Outcome of resolving ``POWERUNITS_INTERNAL_EXECUTE_BASE_URL``."""

    base_url: str
    configured: bool
    refused: bool
    error_code: str | None
    message: str
    hostname: str | None = None
    pin_mode: str = DEFAULT_HOST_PIN_MODE
    warned: bool = False

    def error_fields(self) -> dict[str, Any]:
        if not self.refused:
            return {}
        return {
            "error_code": self.error_code,
            "message": self.message,
            "success": False,
        }


def _raw_configured_base_url() -> str:
    return (os.getenv(POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV) or "").strip()


def powerunits_execute_base_url_is_configured() -> bool:
    """True when the Base URL env is non-empty. Does not validate scheme/host."""

    return bool(_raw_configured_base_url())


def _pin_mode() -> tuple[str | None, str | None]:
    raw = (os.getenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV) or "").strip()
    if not raw:
        return DEFAULT_HOST_PIN_MODE, None
    mode = raw.lower()
    if mode not in _PIN_MODES:
        return None, (
            f"{POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV}={raw!r} is not supported. "
            f"Allowed values: {PIN_MODE_WARN}, {PIN_MODE_ENFORCE}."
        )
    return mode, None


def _allowed_hosts() -> list[str]:
    raw = os.getenv(POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV) or ""
    hosts: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        host = part.strip().lower()
        if not host or host in seen:
            continue
        seen.add(host)
        hosts.append(host)
    return hosts


def _parse_https_base(raw: str) -> tuple[str | None, str | None, str | None, str]:
    """Return (normalized_base, hostname, error_code, message)."""

    try:
        parsed = urlparse(raw)
    except ValueError:
        return None, None, ERROR_URL_INVALID, f"{POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV} is not a valid URL."

    scheme = (parsed.scheme or "").lower()
    if scheme != "https":
        return (
            None,
            None,
            ERROR_HTTPS_REQUIRED,
            f"{POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV} must use https. "
            "HTTP is refused and is not upgraded.",
        )

    if parsed.username is not None or parsed.password is not None or "@" in (parsed.netloc or ""):
        return (
            None,
            None,
            ERROR_URL_INVALID,
            f"{POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV} must not contain userinfo/credentials.",
        )

    host = parsed.hostname
    if not host:
        return (
            None,
            None,
            ERROR_URL_INVALID,
            f"{POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV} is missing a hostname.",
        )

    return raw.rstrip("/"), host, None, ""


def resolve_powerunits_execute_base_url() -> PowerUnitsExecuteBaseUrlResolution:
    """Resolve and validate the bounded PowerUnits execute Base URL.

    Returns only the configured origin/base (trailing slash stripped).
    Does not accept a path, host, or URL from the caller.
    """

    raw = _raw_configured_base_url()
    if not raw:
        return PowerUnitsExecuteBaseUrlResolution(
            base_url="",
            configured=False,
            refused=False,
            error_code=None,
            message="",
        )

    mode, mode_err = _pin_mode()
    if mode_err:
        return PowerUnitsExecuteBaseUrlResolution(
            base_url="",
            configured=True,
            refused=True,
            error_code=ERROR_PIN_MODE_INVALID,
            message=mode_err,
            pin_mode=(os.getenv(POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV) or "").strip(),
        )

    base, hostname, parse_err, parse_msg = _parse_https_base(raw)
    if parse_err:
        return PowerUnitsExecuteBaseUrlResolution(
            base_url="",
            configured=True,
            refused=True,
            error_code=parse_err,
            message=parse_msg,
            pin_mode=mode or DEFAULT_HOST_PIN_MODE,
        )

    assert base is not None and hostname is not None and mode is not None
    allowed = _allowed_hosts()
    host_key = hostname.lower()

    if not allowed:
        if mode == PIN_MODE_ENFORCE:
            return PowerUnitsExecuteBaseUrlResolution(
                base_url="",
                configured=True,
                refused=True,
                error_code=ERROR_ALLOWLIST_REQUIRED,
                message=(
                    f"{POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV} is empty; "
                    f"{PIN_MODE_ENFORCE} cannot allow every host."
                ),
                hostname=hostname,
                pin_mode=mode,
            )
        logger.warning(
            "%s is empty and pin mode=%s; host pinning is not enforced. "
            "CODE_CAPABILITY=IMPLEMENTED PRODUCTION_ENFORCEMENT=PENDING_HUMAN_CONFIG.",
            POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV,
            mode,
        )
        return PowerUnitsExecuteBaseUrlResolution(
            base_url=base,
            configured=True,
            refused=False,
            error_code=None,
            message="",
            hostname=hostname,
            pin_mode=mode,
            warned=True,
        )

    if host_key not in set(allowed):
        detail = (
            f"{POWERUNITS_INTERNAL_EXECUTE_BASE_URL_ENV} hostname {hostname!r} "
            f"is not in {POWERUNITS_INTERNAL_EXECUTE_ALLOWED_HOSTS_ENV}."
        )
        if mode == PIN_MODE_ENFORCE:
            return PowerUnitsExecuteBaseUrlResolution(
                base_url="",
                configured=True,
                refused=True,
                error_code=ERROR_HOST_REFUSED,
                message=detail,
                hostname=hostname,
                pin_mode=mode,
            )
        logger.warning(
            "%s pin mode=%s; HTTP will proceed. "
            "Set %s=%s after confirming the production host.",
            detail,
            mode,
            POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE_ENV,
            PIN_MODE_ENFORCE,
        )
        return PowerUnitsExecuteBaseUrlResolution(
            base_url=base,
            configured=True,
            refused=False,
            error_code=None,
            message=detail,
            hostname=hostname,
            pin_mode=mode,
            warned=True,
        )

    return PowerUnitsExecuteBaseUrlResolution(
        base_url=base,
        configured=True,
        refused=False,
        error_code=None,
        message="",
        hostname=hostname,
        pin_mode=mode,
    )


def apply_powerunits_execute_base_url_refusal(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay a fail-closed Base-URL refusal onto an existing tool error payload.

    Missing configuration keeps the caller's existing structured contract.
    """

    out = dict(payload)
    resolved = resolve_powerunits_execute_base_url()
    if not resolved.refused:
        return out
    out.update(resolved.error_fields())
    for key in ("execution_attempted", "read_attempted"):
        if key in out:
            out[key] = False
    out["success"] = False
    return out
