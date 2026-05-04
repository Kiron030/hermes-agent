"""Tests for Phase 2A Tier-1 workspace analysis overlay tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def t1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "1")
    from tools import powerunits_tier1_workspace_analysis_tool as m

    return m


def test_tier_gate_returns_error_at_tier_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "0")
    from tools import powerunits_tier1_workspace_analysis_tool as m

    out = json.loads(m.summarize_powerunits_workspace_full())
    assert "error_code" in out
    assert out["error_code"] == "tier_gate"


def test_workspace_full_summary(t1) -> None:
    from tools import powerunits_workspace_tool as ws

    json.loads(ws.list_hermes_workspace())
    json.loads(
        ws.save_hermes_workspace_note(
            kind="notes",
            name="hello.md",
            content="# X\nalpha\n",
            overwrite_mode="forbid",
        )
    )
    out = json.loads(t1.summarize_powerunits_workspace_full())
    assert out["read_only"] is True
    assert out["phase"] == "2A"
    assert out["total_files"] >= 1
    assert out["per_subdir"]["notes"]["files"] >= 1


def test_workspace_text_search(t1) -> None:
    from tools import powerunits_workspace_tool as ws

    json.loads(ws.list_hermes_workspace())
    json.loads(
        ws.save_hermes_workspace_note(
            kind="analysis",
            name="p.md",
            content="unique-marker-xyz\n",
            overwrite_mode="forbid",
        )
    )
    out = json.loads(
        t1.search_powerunits_workspace_text(
            query="unique-marker-xyz",
            subdir="analysis",
        )
    )
    assert out["match_count"] >= 1
    assert any("analysis/p.md" in m["path"] for m in out["matches"])


def test_search_rejects_bad_subdir(t1) -> None:
    raw = t1.search_powerunits_workspace_text(query="x", subdir="nope")
    out = json.loads(raw)
    assert out.get("error_code") == "invalid_subdir"
