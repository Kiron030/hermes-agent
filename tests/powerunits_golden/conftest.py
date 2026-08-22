"""Golden suite isolation: caches + no production credentials."""

from __future__ import annotations

import pytest

from tests.powerunits_golden.env import invalidate_tool_surface_caches


@pytest.fixture(autouse=True)
def _golden_cache_reset() -> None:
    invalidate_tool_surface_caches()
    yield
    invalidate_tool_surface_caches()
