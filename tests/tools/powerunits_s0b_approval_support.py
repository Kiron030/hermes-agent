"""Test helper: grant PowerUnits write approval for pre-S0-B execute suites."""

from __future__ import annotations

from typing import Any

import pytest


def grant_powerunits_write_approvals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing write-path tests expect HTTP to run. Grant the S0-B gate."""

    def _approved(**kwargs: Any) -> dict[str, Any]:
        return {
            "approved": True,
            "message": None,
            "rule_key": kwargs.get("operation"),
            "effect_class": "BOUNDED_WRITE",
        }

    monkeypatch.setattr(
        "tools.powerunits_bounded_write_approval_v1.require_powerunits_write_approval",
        _approved,
    )
