#!/usr/bin/env python3
"""
Read-only empirical ENTSO-E **candidate** validate-window — thin POST to Repo B (ADR 045).

``POST /internal/hermes/bounded/v1/entsoe-empirical-candidate/validate-window``

**Not** Tier-1 bounded; does not run jobs or promote allowlists.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any

import httpx

from powerunits_operator_country_scope_v1 import (
    EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1,
    POLICY_HOLD_COMPLEX_PRICE_ISO2_V1,
)
from tools.powerunits_bounded_family_gates import (
    ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_PRIMARY_ENV,
    entsoe_empirical_candidate_validate_enabled,
    entsoe_empirical_candidate_validate_requirement_text,
)
from tools.powerunits_entsoe_empirical_candidate_countries import (
    ALLOWED_EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1,
    EMPIRICAL_ENTSOE_CANDIDATE_USER_FACING_ISO2_DOCUMENTATION_V1,
)
from tools.powerunits_entsoe_market_bounded_countries import (
    ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_entsoe_empirical_candidate_validate_v1"
_VALIDATE_PATH = "/internal/hermes/bounded/v1/entsoe-empirical-candidate/validate-window"
_DEFAULT_VERSION = "v1"
_DEFAULT_TIMEOUT_S = 120
_MAX_SUMMARY_CHARS = 12000

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)

_HERMES_NOTE_V1 = (
    "Hermes: read-only empirical candidate validate — no jobs, no Tier-1 promotion. "
    "Empty normalized rows often mean pre_backfill_gap, not proven API failure."
)


def check_powerunits_entsoe_empirical_candidate_validate_requirements() -> bool:
    if not entsoe_empirical_candidate_validate_enabled():
        return False
    if not (os.getenv(_BASE_ENV) or "").strip():
        return False
    if not (os.getenv(_SECRET_ENV) or "").strip():
        return False
    return True


def _redact_secrets(text: str) -> str:
    if not text:
        return ""
    redacted = _SECRET_URL_RE.sub("[REDACTED_URL]", text)
    if len(redacted) > _MAX_SUMMARY_CHARS:
        return redacted[:_MAX_SUMMARY_CHARS] + "\n...[truncated]"
    return redacted


def _validate_url() -> str:
    base = (os.getenv(_BASE_ENV) or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}{_VALIDATE_PATH}"


def _read_timeout_s() -> float:
    raw = (os.getenv(_TIMEOUT_ENV) or "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT_S)
    try:
        return max(30.0, float(raw))
    except ValueError:
        return float(_DEFAULT_TIMEOUT_S)


def _default_http_post(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout_s: float,
) -> httpx.Response:
    timeout = httpx.Timeout(connect=15.0, read=timeout_s, write=60.0, pool=15.0)
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, headers=headers, json=json_body)


def _window_error(start: str, end: str) -> str | None:
    ws = (start or "").strip()
    we = (end or "").strip()
    if not ws or not we:
        return "window_start_utc and window_end_utc must be non-empty UTC ISO-8601 strings"
    return None


def _normalize_families(raw: Any) -> tuple[list[str] | None, str | None]:
    if raw is None:
        return ["market", "forecast"], None
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.replace(";", ",").split(",") if p.strip()]
    elif isinstance(raw, (list, tuple)):
        parts = [str(p).strip().lower() for p in raw if str(p).strip()]
    else:
        return None, "families must be list or comma string of market and/or forecast"
    allowed = {"market", "forecast"}
    out: list[str] = []
    for p in parts:
        if p not in allowed:
            return None, "each family must be 'market' or 'forecast'"
        if p not in out:
            out.append(p)
    if not out:
        return None, "families must not be empty"
    out.sort(key=lambda x: ("market", "forecast").index(x))
    return out, None


def _client_country_gate(cc_raw: str) -> tuple[str | None, str | None]:
    cc = (cc_raw or "").strip().upper()
    if not cc:
        return None, "country_code required (ISO2)"
    if cc in POLICY_HOLD_COMPLEX_PRICE_ISO2_V1:
        return None, (
            f"{cc} is on the separate price-policy rollout track (ES/IT/SE) — "
            "not empirical candidate validate."
        )
    if cc in ALLOWED_BOUNDED_ENTSOE_MARKET_COUNTRY_CODES_V1:
        return None, (
            f"{cc} is Tier-1 bounded live — use validate_powerunits_entsoe_market_bounded_window "
            "and validate_powerunits_entsoe_forecast_bounded_window."
        )
    if cc not in ALLOWED_EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1:
        allowed = ", ".join(sorted(ALLOWED_EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1))
        return None, f"country_code must be one of ({allowed}) for empirical candidate validate"
    return cc, None


def _chat_summary(parsed: dict[str, Any]) -> str:
    cc = parsed.get("country_code") or "?"
    evidence = parsed.get("candidate_smoke_evidence_v1") or {}
    by_fam = evidence.get("by_family_v1") if isinstance(evidence, dict) else {}
    lines = [f"**Empirical candidate {cc}** (read-only, no Tier-1 promotion)", ""]
    if isinstance(by_fam, dict):
        for fam in sorted(by_fam.keys()):
            row = by_fam[fam] if isinstance(by_fam[fam], dict) else {}
            sig = row.get("candidate_smoke_signal_v1") or "?"
            oc = row.get("outcome") or "?"
            lines.append(f"• **{fam}** — signal `{sig}`, outcome **{oc}**")
    else:
        lines.append("• No family evidence in response")
    lines.append("")
    lines.append(
        "Empty DB slices often = **pre_backfill_gap** — run Stage-0 ingest before blaming ENTSO-E API."
    )
    cid = parsed.get("correlation_id") or "n/a"
    lines.append(f"_correlation_id: `{cid}`")
    return "\n".join(lines)


def validate_powerunits_entsoe_empirical_candidate_window_v1(
    *,
    country_code: str,
    window_start_utc: str,
    window_end_utc: str,
    version: str = _DEFAULT_VERSION,
    families: Any = None,
    _http_post: Any = None,
) -> str:
    """Return JSON: Repo B empirical candidate payload plus ``chat_summary``."""
    poster = _http_post or _default_http_post

    if not check_powerunits_entsoe_empirical_candidate_validate_requirements():
        return json.dumps(
            {
                "error_code": "feature_disabled",
                "surface": _SURFACE,
                "validation_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "message": (
                    f"{entsoe_empirical_candidate_validate_requirement_text()}; "
                    f"also requires {_BASE_ENV} and {_SECRET_ENV}."
                ),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
                "allowed_country_codes": list(EMPIRICAL_ENTSOE_CANDIDATE_ISO2_V1),
            },
            ensure_ascii=False,
        )

    cc, cc_err = _client_country_gate(country_code)
    if cc_err or not cc:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_attempted": False,
                "http_status_from_repo_b": None,
                "success": False,
                "error_code": "invalid_country_code",
                "message": cc_err or "invalid country_code",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    win_err = _window_error(window_start_utc, window_end_utc)
    if win_err:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_attempted": False,
                "success": False,
                "error_code": "invalid_window",
                "message": win_err,
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    fam_list, fam_err = _normalize_families(families)
    if fam_err or not fam_list:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_attempted": False,
                "success": False,
                "error_code": "invalid_families",
                "message": fam_err or "invalid families",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    ver = (version or "").strip() or _DEFAULT_VERSION
    url = _validate_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            {
                "error_code": "validate_config_incomplete",
                "surface": _SURFACE,
                "validation_attempted": False,
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    body: dict[str, Any] = {
        "country_code": cc,
        "version": ver,
        "window_start_utc": window_start_utc.strip(),
        "window_end_utc": window_end_utc.strip(),
        "families": fam_list,
    }

    try:
        resp = poster(url, headers, body, _read_timeout_s())
    except httpx.TimeoutException:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "timeout",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as exc:
        return json.dumps(
            {
                "surface": _SURFACE,
                "validation_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(exc)[:500]),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    raw_text = resp.text or ""
    parsed: dict[str, Any] = {}
    try:
        if resp.content:
            pj = resp.json()
            parsed = pj if isinstance(pj, dict) else {}
    except (ValueError, json.JSONDecodeError, TypeError):
        parsed = {}

    merged: dict[str, Any] = dict(parsed)
    merged["surface"] = _SURFACE
    merged["validation_attempted"] = True
    merged["http_status_from_repo_b"] = status
    merged.setdefault("correlation_id", correlation_id)
    merged["hermes_operator_note_v1"] = _HERMES_NOTE_V1
    merged["promotes_tier1"] = False

    if status == 200:
        merged["success"] = True
        merged["chat_summary"] = _chat_summary(merged)
    else:
        merged["success"] = False
        merged.setdefault("response_body_summary", _redact_secrets(raw_text))

    return json.dumps(merged, ensure_ascii=False)


EMPIRICAL_CANDIDATE_VALIDATE_SCHEMA_V1 = {
    "name": "validate_powerunits_entsoe_empirical_candidate_window_v1",
    "description": (
        "**Empirical ENTSO-E candidate validate-window (read-only, ADR 045)** — one HTTP POST to "
        "Repo B **`POST /internal/hermes/bounded/v1/entsoe-empirical-candidate/validate-window`**. "
        "ISO2 pool **`DK`**, **`NO`**, **`IE`** only — **not** Tier-1 bounded promotion. "
        "Use for Nordic price-gate and IE market/forecast evidence before governance opens Tier-1. "
        "Tier-1 live ISO2 must use bounded market/forecast validate tools instead. "
        f"Gate **`{ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_PRIMARY_ENV}`** plus "
        f"**`{_BASE_ENV}`**, **`{_SECRET_ENV}`**."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country_code": {
                "type": "string",
                "description": EMPIRICAL_ENTSOE_CANDIDATE_USER_FACING_ISO2_DOCUMENTATION_V1,
            },
            "window_start_utc": {
                "type": "string",
                "description": "Inclusive UTC ISO-8601 (Z); span ≤ 7d with exclusive end.",
            },
            "window_end_utc": {
                "type": "string",
                "description": "Exclusive UTC ISO-8601 (Z).",
            },
            "version": {
                "type": "string",
                "description": "Must be v1.",
                "default": _DEFAULT_VERSION,
            },
            "families": {
                "type": "array",
                "items": {"type": "string", "enum": ["market", "forecast"]},
                "description": "Default both market and forecast.",
            },
        },
        "required": ["country_code", "window_start_utc", "window_end_utc"],
    },
}


from tools.registry import registry

registry.register(
    name="validate_powerunits_entsoe_empirical_candidate_window_v1",
    toolset="powerunits_entsoe_empirical_candidate_validate",
    schema=EMPIRICAL_CANDIDATE_VALIDATE_SCHEMA_V1,
    handler=lambda args, **kw: validate_powerunits_entsoe_empirical_candidate_window_v1(
        country_code=str((args or {}).get("country_code", "")),
        window_start_utc=str((args or {}).get("window_start_utc", "") or ""),
        window_end_utc=str((args or {}).get("window_end_utc", "") or ""),
        version=str((args or {}).get("version", "") or _DEFAULT_VERSION),
        families=(args or {}).get("families"),
    ),
    check_fn=check_powerunits_entsoe_empirical_candidate_validate_requirements,
    requires_env=[
        ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="🧪",
)
