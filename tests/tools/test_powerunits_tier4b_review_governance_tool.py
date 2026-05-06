"""Tests for Tier 4B review/governance tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def t4b(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "5")
    from tools import powerunits_tier4b_review_governance_tool as m

    return m


def test_tier_gate_below_five(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "4")
    from tools import powerunits_tier4b_review_governance_tool as m

    out = json.loads(m.manifest_powerunits_tier4b_governance_scope())
    assert out["error_code"] == "tier_gate"


def test_ensure_and_governance_note_roundtrip(t4b, tmp_path: Path) -> None:
    e = json.loads(t4b.ensure_powerunits_governance_workspace())
    assert e["read_only"] is False
    gov = tmp_path / "hermes_workspace" / "governance"
    assert (gov / "review_decisions").is_dir()

    w = json.loads(
        t4b.append_powerunits_governance_note(
            relative_file_path="review_decisions/test.md",
            body="## Decision\n\nok",
        )
    )
    assert "review_decisions/test.md" in w["path_relative_to_governance"]

    r = json.loads(
        t4b.read_powerunits_governance_note(relative_file_path="review_decisions/test.md")
    )
    assert "Decision" in r["body"]


def test_set_review_status_on_draft(t4b, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "4")
    from tools import powerunits_tier4a_skill_draft_proposals_tool as t4a

    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "5")

    json.loads(
        t4a.write_powerunits_skill_draft_proposal(
            relative_file_path="x/d.md",
            body="# Hi",
            proposal_kind="skill_draft_md",
            target_skill_name="skill-a",
        )
    )
    s = json.loads(
        t4b.set_powerunits_skill_draft_review_status(
            relative_file_path="x/d.md",
            review_status="under_review",
            operator_note_one_line="peek",
        )
    )
    assert s["review_status"] == "under_review"

    raw = (
        tmp_path / "hermes_workspace" / "drafts" / "powerunits_skill_proposals" / "x" / "d.md"
    ).read_text(encoding="utf-8")
    assert "review_status: under_review" in raw
    assert "review_status_operator_note" in raw


def test_summarize_counts_statuses(t4b, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_tier4a_skill_draft_proposals_tool as t4a

    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "4")
    json.loads(
        t4a.write_powerunits_skill_draft_proposal(
            relative_file_path="a/one.md", body="# a", proposal_kind="skill_draft_md"
        )
    )
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "5")

    summ = json.loads(t4b.summarize_powerunits_tier4b_governance_lane())
    assert summ["proposal_review_status_counts"]["new"] >= 1
