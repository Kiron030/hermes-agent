#!/usr/bin/env python3
"""
Bounded **country coverage inspect** — thin read-only POST to Repo B.

One HTTP ``POST /internal/hermes/bounded/v1/country-coverage/inspect``.
Hermes performs no SQL and holds no DB credential for this path.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import httpx

from powerunits_operator_country_scope_v1 import BZN_ADVISORY_ISO2_V1, NATIONAL_TIER1_ISO2_V1
from tools.powerunits_bounded_family_gates import (
    COUNTRY_COVERAGE_INSPECT_PRIMARY_ENV,
    country_coverage_inspect_enabled,
    country_coverage_inspect_requirement_text,
)
from tools.powerunits_execute_base_url_v1 import (
    apply_powerunits_execute_base_url_refusal,
    powerunits_execute_base_url_is_configured,
    resolve_powerunits_execute_base_url,
)

logger = logging.getLogger(__name__)

_BASE_ENV = "POWERUNITS_INTERNAL_EXECUTE_BASE_URL"
_SECRET_ENV = "POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET"
_TIMEOUT_ENV = "POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S"
_SURFACE = "powerunits_country_coverage_inspect_v1"
_INSPECT_PATH = "/internal/hermes/bounded/v1/country-coverage/inspect"
_DEFAULT_TIMEOUT_S = 120
_DEFAULT_VERSION = "v1"
_MAX_SPAN_DAYS = 31
_MAX_SUMMARY_CHARS = 12000

DATASET_CATALOG_V1: Final[tuple[str, ...]] = (
    "model_dataset",
    "day_ahead_price",
    "demand",
    "generation_by_type",
    "weather",
    "cross_border",
    "outage",
    "bzn_price",
)
SUPPORTED_COUNTRIES_V1: Final[frozenset[str]] = frozenset(NATIONAL_TIER1_ISO2_V1) | frozenset(
    BZN_ADVISORY_ISO2_V1
)
BZN_ONLY_DATASETS_V1: Final[frozenset[str]] = frozenset({"bzn_price"})

_SECRET_URL_RE = re.compile(
    r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s'\"<>]+",
    re.IGNORECASE,
)

_HERMES_NOTE_V1 = (
    "Hermes: read-only bounded POST to Repo B country-coverage/inspect. "
    "No jobs, no SQL from Hermes, no DB credential, no writes. "
    "Repo B JSON is canonical. Status NO_DATA is a successful empty read, not a system error."
)


def check_powerunits_country_coverage_inspect_requirements() -> bool:
    if not country_coverage_inspect_enabled():
        return False
    if not powerunits_execute_base_url_is_configured():
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


def _inspect_url() -> str:
    resolved = resolve_powerunits_execute_base_url()
    if resolved.refused or not resolved.base_url:
        return ""
    return f"{resolved.base_url}{_INSPECT_PATH}"


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


def _parse_iso(raw: str, *, field: str) -> datetime | str:
    text = (raw or "").strip()
    if not text:
        return f"{field} must be non-empty when the other bound is set"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text + "T00:00:00+00:00"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return f"{field} must be ISO-8601 or YYYY-MM-DD"
    if dt.tzinfo is None:
        return f"{field} must be timezone-aware (use Z or an offset)"
    return dt.astimezone(timezone.utc)


def _validate_args(
    country: Any,
    dataset: Any,
    start: str,
    end: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    iso2 = str(country or "").strip().upper()
    if len(iso2) != 2 or not iso2.isalpha():
        return None, {
            "error_code": "invalid_country",
            "message": "country must be a canonical ISO-3166 alpha-2 code (e.g. AT, DE, FR)",
        }
    if iso2 not in SUPPORTED_COUNTRIES_V1:
        return None, {
            "error_code": "unsupported_country",
            "message": (
                f"country {iso2!r} is not in the v1 supported set "
                f"({', '.join(sorted(SUPPORTED_COUNTRIES_V1))})"
            ),
        }
    dataset_id = str(dataset or "").strip() or None
    if dataset_id is not None and dataset_id not in DATASET_CATALOG_V1:
        return None, {
            "error_code": "invalid_dataset",
            "message": f"dataset must be one of: {', '.join(DATASET_CATALOG_V1)}",
        }
    if dataset_id in BZN_ONLY_DATASETS_V1 and iso2 not in BZN_ADVISORY_ISO2_V1:
        return None, {
            "error_code": "dataset_not_applicable_for_country",
            "message": f"dataset {dataset_id!r} is not applicable for country {iso2}",
        }
    if dataset_id is not None and dataset_id not in BZN_ONLY_DATASETS_V1 and iso2 not in NATIONAL_TIER1_ISO2_V1:
        return None, {
            "error_code": "dataset_not_applicable_for_country",
            "message": f"dataset {dataset_id!r} is not applicable for country {iso2}",
        }

    start_text = (start or "").strip()
    end_text = (end or "").strip()
    if start_text or end_text:
        if not start_text or not end_text:
            return None, {
                "error_code": "invalid_window",
                "message": "start and end must both be provided, or both omitted",
            }
        start_dt = _parse_iso(start_text, field="start")
        if isinstance(start_dt, str):
            return None, {"error_code": "invalid_timestamp", "message": start_dt}
        end_dt = _parse_iso(end_text, field="end")
        if isinstance(end_dt, str):
            return None, {"error_code": "invalid_timestamp", "message": end_dt}
        if end_dt <= start_dt:
            return None, {
                "error_code": "invalid_window",
                "message": "end must be strictly after start (exclusive end)",
            }
        if (end_dt - start_dt) > timedelta(days=_MAX_SPAN_DAYS):
            return None, {
                "error_code": "invalid_window",
                "message": f"window span must be <= {_MAX_SPAN_DAYS} days",
            }

    body: dict[str, Any] = {"country": iso2, "version": _DEFAULT_VERSION}
    if dataset_id is not None:
        body["dataset"] = dataset_id
    if start_text and end_text:
        body["start"] = start_text
        body["end"] = end_text
    return body, None


def _chat_summary(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    country = payload.get("country") or "?"
    mode = payload.get("mode") or "?"
    lines.append(f"**Country coverage inspect** `{country}` — mode `{mode}`")
    lines.append(
        f"Window `[start,end)`: `{payload.get('requested_start')}` → `{payload.get('requested_end')}` "
        f"(default={payload.get('used_default_range')})"
    )
    if payload.get("no_data"):
        lines.append("**NO_DATA** for the requested slice — this is an empty coverage result, not a system error.")
    for item in payload.get("items") or []:
        ds = item.get("dataset") or "?"
        status = item.get("status") or "?"
        ratio = item.get("coverage_ratio")
        ratio_s = "n/a" if ratio is None else f"{ratio:.1%}"
        latest = item.get("latest_timestamp") or "n/a"
        age = item.get("age_hours")
        age_s = "n/a" if age is None else f"{age}h"
        lines.append(
            f"• **{ds}** — `{status}` coverage={ratio_s} "
            f"observed={item.get('observed_points')}/{item.get('expected_points')} "
            f"latest=`{latest}` age={age_s}"
        )
    lines.append("")
    lines.append(
        "Read-only Repo B inspect — gap math is computed in Repo B, not by the model. "
        "Rerun after bounded repairs."
    )
    lines.append(f"_correlation_id: `{payload.get('correlation_id') or 'n/a'}`")
    return "\n".join(lines)


def _fail(payload: dict[str, Any]) -> str:
    base = {
        "surface": _SURFACE,
        "read_attempted": False,
        "http_status_from_repo_b": None,
        "success": False,
        "hermes_operator_note_v1": _HERMES_NOTE_V1,
        "effect_class": "READ",
    }
    base.update(payload)
    return json.dumps(base, ensure_ascii=False)


def inspect_powerunits_country_coverage_v1(
    *,
    country: str = "",
    dataset: str = "",
    start: str = "",
    end: str = "",
    version: str = _DEFAULT_VERSION,
    _http_post: Any = None,
) -> str:
    """Return JSON: Repo B country-coverage inspect payload plus chat_summary."""
    poster = _http_post or _default_http_post

    if not check_powerunits_country_coverage_inspect_requirements():
        return _fail(
            {
                "error_code": "feature_disabled",
                "message": (
                    f"{country_coverage_inspect_requirement_text()}; "
                    f"also requires {_BASE_ENV} and {_SECRET_ENV}."
                ),
            }
        )

    body, err = _validate_args(country, dataset, start, end)
    if err or not body:
        return _fail(err or {"error_code": "invalid_arguments", "message": "invalid arguments"})

    url = _inspect_url()
    secret = (os.getenv(_SECRET_ENV) or "").strip()
    if not url or not secret:
        return json.dumps(
            apply_powerunits_execute_base_url_refusal(
                {
                    "error_code": "read_config_incomplete",
                    "surface": _SURFACE,
                    "read_attempted": False,
                    "http_status_from_repo_b": None,
                    "success": False,
                    "hermes_operator_note_v1": _HERMES_NOTE_V1,
                    "effect_class": "READ",
                }
            ),
            ensure_ascii=False,
        )

    correlation_id = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlation_id,
    }
    body["version"] = (version or "").strip() or _DEFAULT_VERSION

    try:
        resp = poster(url, headers, body, _read_timeout_s())
    except httpx.TimeoutException:
        logger.warning("country coverage inspect: HTTP timeout")
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "timeout",
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
                "effect_class": "READ",
            },
            ensure_ascii=False,
        )
    except httpx.RequestError as e:
        logger.warning("country coverage inspect: HTTP error %s", e)
        return json.dumps(
            {
                "surface": _SURFACE,
                "read_attempted": True,
                "http_status_from_repo_b": None,
                "success": False,
                "error_class": "http_client_error",
                "response_body_summary": _redact_secrets(str(e)[:500]),
                "hermes_operator_note_v1": _HERMES_NOTE_V1,
                "effect_class": "READ",
            },
            ensure_ascii=False,
        )

    status = int(resp.status_code)
    raw_text = _redact_secrets(resp.text or "")
    try:
        parsed = resp.json() if resp.content else {}
        if not isinstance(parsed, dict):
            parsed = {"repo_b_non_object_json": parsed}
    except (ValueError, TypeError):
        parsed = {"parse_error": True, "response_body_summary": raw_text[:8000]}

    merged: dict[str, Any] = dict(parsed)
    merged["http_status_from_repo_b"] = status
    merged["read_attempted"] = True
    merged.setdefault("correlation_id", correlation_id)
    merged["hermes_operator_note_v1"] = _HERMES_NOTE_V1
    merged["surface"] = _SURFACE
    merged["effect_class"] = "READ"
    if status == 200 and merged.get("success") is not False:
        merged["chat_summary"] = _chat_summary(merged)
    else:
        merged.setdefault("response_body_summary", raw_text)
    return json.dumps(merged, ensure_ascii=False)


COUNTRY_COVERAGE_INSPECT_SCHEMA_V1 = {
    "name": "inspect_powerunits_country_coverage_v1",
    "description": (
        "**Country data coverage inspect (read-only)** — answers “how complete is country X?” "
        "via one bounded Repo B POST `/internal/hermes/bounded/v1/country-coverage/inspect`. "
        "Use for operational coverage, gaps, freshness, and stale datasets. "
        "**country** is canonical ISO-3166 alpha-2 (national Tier-1: AT BE CZ DE FI FR HU NL PL RO SK; "
        "BZN advisory: DK NO SE IT IE). "
        "**dataset** is optional from the v1 catalog: model_dataset, day_ahead_price, demand, "
        "generation_by_type, weather, cross_border, outage, bzn_price. "
        "Omit dataset for a bounded catalog summary. "
        "Omit start/end for the last 7 days; both must be set together; max 31 days; exclusive end. "
        "**status:** OK (coverage ≥80% and fresh), THIN, STALE, STALE_AND_THIN, NO_DATA. "
        "NO_DATA is a successful empty read, not a system error. "
        "Does not accept SQL, table names, or URLs. Hermes does not run SQL or hold a DB credential. "
        "Not a multi-country monitoring agent — call once per country. "
        "Gate `HERMES_POWERUNITS_COUNTRY_COVERAGE_INSPECT_ENABLED` plus "
        "`POWERUNITS_INTERNAL_EXECUTE_BASE_URL` and `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "country": {
                "type": "string",
                "description": "Required ISO-3166 alpha-2 / PowerUnits canonical ISO2 (e.g. AT, DE, FR).",
            },
            "dataset": {
                "type": "string",
                "description": (
                    "Optional catalog id. Omit for summary over datasets eligible for the country. "
                    "Allowed: model_dataset, day_ahead_price, demand, generation_by_type, "
                    "weather, cross_border, outage, bzn_price."
                ),
            },
            "start": {
                "type": "string",
                "description": "Optional inclusive UTC ISO-8601 or YYYY-MM-DD. Omit with end for default 7d.",
            },
            "end": {
                "type": "string",
                "description": "Optional exclusive UTC ISO-8601 or YYYY-MM-DD. Span ≤ 31d.",
            },
        },
        "required": ["country"],
    },
}


from tools.registry import registry

registry.register(
    name="inspect_powerunits_country_coverage_v1",
    toolset="powerunits_country_coverage_inspect",
    schema=COUNTRY_COVERAGE_INSPECT_SCHEMA_V1,
    handler=lambda args, **kw: inspect_powerunits_country_coverage_v1(
        country=str((args or {}).get("country", "") or ""),
        dataset=str((args or {}).get("dataset", "") or ""),
        start=str((args or {}).get("start", "") or ""),
        end=str((args or {}).get("end", "") or ""),
        version=str((args or {}).get("version", "") or _DEFAULT_VERSION),
    ),
    check_fn=check_powerunits_country_coverage_inspect_requirements,
    requires_env=[
        COUNTRY_COVERAGE_INSPECT_PRIMARY_ENV,
        _BASE_ENV,
        _SECRET_ENV,
    ],
    emoji="📈",
)
