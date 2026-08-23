"""S0-C host-pinning semantics for the standalone plugin.

HTTPS only. Exact hostname match against an allowlist. The caller cannot
supply a host, URL, or path — only process env is read.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from .operations import ALLOWED_HOSTS_ENV, BASE_URL_ENV, HOST_PIN_MODE_ENV

logger = logging.getLogger(__name__)

PIN_MODE_WARN = "warn"
PIN_MODE_ENFORCE = "enforce"
# R2 client contract requires exact host validation. Enforce is the plugin default.
# S0-C wrappers still default to warn; this plugin does not change that core code.
DEFAULT_HOST_PIN_MODE = PIN_MODE_ENFORCE

ERROR_HTTPS_REQUIRED = "execute_target_https_required"
ERROR_URL_INVALID = "execute_target_url_invalid"
ERROR_HOST_REFUSED = "execute_target_host_refused"
ERROR_ALLOWLIST_REQUIRED = "execute_target_host_allowlist_required"
ERROR_PIN_MODE_INVALID = "execute_target_pin_mode_invalid"

_PIN_MODES = frozenset({PIN_MODE_WARN, PIN_MODE_ENFORCE})


@dataclass(frozen=True)
class TargetResolution:
    base_url: str
    configured: bool
    refused: bool
    error_code: str | None
    message: str
    hostname: str | None = None
    pin_mode: str = DEFAULT_HOST_PIN_MODE

    def error_fields(self) -> dict[str, Any]:
        if not self.refused:
            return {}
        return {
            "error_code": self.error_code,
            "message": self.message,
            "success": False,
        }


def _raw_base_url() -> str:
    return (os.getenv(BASE_URL_ENV) or "").strip()


def base_url_is_configured() -> bool:
    return bool(_raw_base_url())


def _pin_mode() -> tuple[str | None, str | None]:
    raw = (os.getenv(HOST_PIN_MODE_ENV) or "").strip()
    if not raw:
        return DEFAULT_HOST_PIN_MODE, None
    mode = raw.lower()
    if mode not in _PIN_MODES:
        return None, (
            f"{HOST_PIN_MODE_ENV}={raw!r} is not supported. "
            f"Allowed values: {PIN_MODE_WARN}, {PIN_MODE_ENFORCE}."
        )
    return mode, None


def _allowed_hosts() -> list[str]:
    raw = os.getenv(ALLOWED_HOSTS_ENV) or ""
    hosts: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        host = part.strip().lower().rstrip(".")
        if not host or host in seen:
            continue
        seen.add(host)
        hosts.append(host)
    return hosts


def _parse_https_base(raw: str) -> tuple[str | None, str | None, str | None, str]:
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None, None, ERROR_URL_INVALID, f"{BASE_URL_ENV} is not a valid URL."

    scheme = (parsed.scheme or "").lower()
    if scheme != "https":
        return (
            None,
            None,
            ERROR_HTTPS_REQUIRED,
            f"{BASE_URL_ENV} must use https. HTTP is refused and is not upgraded.",
        )

    if parsed.username is not None or parsed.password is not None or "@" in (parsed.netloc or ""):
        return (
            None,
            None,
            ERROR_URL_INVALID,
            f"{BASE_URL_ENV} must not contain userinfo/credentials.",
        )

    host = parsed.hostname
    if not host:
        return (
            None,
            None,
            ERROR_URL_INVALID,
            f"{BASE_URL_ENV} is missing a hostname.",
        )

    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        return (
            None,
            None,
            ERROR_URL_INVALID,
            f"{BASE_URL_ENV} must be an origin only (no path, query, or fragment).",
        )

    return raw.rstrip("/"), host.lower().rstrip("."), None, ""


def resolve_target() -> TargetResolution:
    """Resolve the configured origin. Does not accept caller host/URL/path."""

    raw = _raw_base_url()
    if not raw:
        return TargetResolution(
            base_url="",
            configured=False,
            refused=False,
            error_code=None,
            message="",
        )

    mode, mode_err = _pin_mode()
    if mode_err:
        return TargetResolution(
            base_url="",
            configured=True,
            refused=True,
            error_code=ERROR_PIN_MODE_INVALID,
            message=mode_err,
            pin_mode=(os.getenv(HOST_PIN_MODE_ENV) or "").strip(),
        )

    base, hostname, parse_err, parse_msg = _parse_https_base(raw)
    if parse_err:
        return TargetResolution(
            base_url="",
            configured=True,
            refused=True,
            error_code=parse_err,
            message=parse_msg,
            pin_mode=mode or DEFAULT_HOST_PIN_MODE,
        )

    assert base is not None and hostname is not None and mode is not None
    allowed = _allowed_hosts()

    if not allowed:
        if mode == PIN_MODE_ENFORCE:
            return TargetResolution(
                base_url="",
                configured=True,
                refused=True,
                error_code=ERROR_ALLOWLIST_REQUIRED,
                message=(
                    f"{ALLOWED_HOSTS_ENV} is empty; {PIN_MODE_ENFORCE} cannot allow every host."
                ),
                hostname=hostname,
                pin_mode=mode,
            )
        logger.warning(
            "%s is empty and pin mode=%s; host pinning is not enforced.",
            ALLOWED_HOSTS_ENV,
            mode,
        )
        return TargetResolution(
            base_url=base,
            configured=True,
            refused=False,
            error_code=None,
            message="",
            hostname=hostname,
            pin_mode=mode,
        )

    if hostname not in set(allowed):
        detail = (
            f"{BASE_URL_ENV} hostname {hostname!r} is not an exact match in "
            f"{ALLOWED_HOSTS_ENV}."
        )
        if mode == PIN_MODE_ENFORCE:
            return TargetResolution(
                base_url="",
                configured=True,
                refused=True,
                error_code=ERROR_HOST_REFUSED,
                message=detail,
                hostname=hostname,
                pin_mode=mode,
            )
        logger.warning("%s pin mode=%s; HTTP will proceed.", detail, mode)
        return TargetResolution(
            base_url=base,
            configured=True,
            refused=False,
            error_code=None,
            message=detail,
            hostname=hostname,
            pin_mode=mode,
        )

    return TargetResolution(
        base_url=base,
        configured=True,
        refused=False,
        error_code=None,
        message="",
        hostname=hostname,
        pin_mode=mode,
    )


def apply_target_refusal(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    resolved = resolve_target()
    if not resolved.refused:
        return out
    out.update(resolved.error_fields())
    for key in ("execution_attempted", "read_attempted", "inventory_attempted", "readiness_attempted"):
        if key in out:
            out[key] = False
    out["success"] = False
    return out
