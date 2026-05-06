"""
Shared review_status contract for Tier 4A drafts + Tier 4B governance.

Human-review lifecycle only — not Repo B truth, not live skill deployment.
"""

from __future__ import annotations

REVIEW_STATUS_VALUES: tuple[str, ...] = (
    "new",
    "under_review",
    "needs_revision",
    "accepted_for_promotion",
    "rejected",
)

REVIEW_STATUSES: frozenset[str] = frozenset(REVIEW_STATUS_VALUES)


def validate_review_status(value: str | None) -> tuple[str | None, str | None]:
    """
    Return (None, error_message) if invalid; (normalized_status, None) if OK.
    Empty / whitespace-only is treated as missing (valid for parsing; use ``new`` upstream).
    """

    s = str(value or "").strip()
    if not s:
        return "", None
    if s not in REVIEW_STATUSES:
        return None, (
            "review_status must be exactly one of: "
            + ", ".join(sorted(REVIEW_STATUSES))
        )
    return s, None
