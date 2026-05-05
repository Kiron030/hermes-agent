"""Tests for Tier 4A skill draft proposal tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def t4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "4")
    from tools import powerunits_tier4a_skill_draft_proposals_tool as m

    return m


def test_tier_gate_below_four(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "3")
    from tools import powerunits_tier4a_skill_draft_proposals_tool as m

    out = json.loads(m.manifest_powerunits_tier4a_skill_draft_scope())
    assert out["error_code"] == "tier_gate"


def test_write_list_read_roundtrip(t4, tmp_path: Path) -> None:
    rel = "2026-04-30/example.md"
    w = json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path=rel,
            body="# Draft skill\n\nHello\n",
            proposal_kind="skill_draft_md",
            target_skill_name="probe-skill",
        )
    )
    assert w.get("read_only") is False
    assert "drafts/powerunits_skill_proposals" in w["path_relative_to_hermes_workspace"]

    lst = json.loads(t4.list_powerunits_skill_draft_proposals())
    assert any(e["relative_path"] == rel for e in lst["entries"])

    body = json.loads(t4.read_powerunits_skill_draft_proposal(relative_file_path=rel))
    assert "# Draft skill" in body["body"]
    assert "powerunits_tier_4a_proposal" in body["body"]


def test_summarize_empty(t4) -> None:
    s = json.loads(t4.summarize_powerunits_skill_draft_proposals())
    assert s["proposal_file_count"] == 0
    assert s["caution_flags"] == []


def test_path_traversal_rejected(t4) -> None:
    out = json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path="../../../../etc/passwd.md",
            body="nope",
            proposal_kind="skill_draft_md",
        )
    )
    assert out["error_code"] == "invalid_path"
