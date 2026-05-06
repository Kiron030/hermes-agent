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
    assert "review_status: new" in body["body"]


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


def test_read_includes_frontmatter_and_preview(t4, tmp_path: Path) -> None:
    rel = "2026-05-06/meta.md"
    json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path=rel,
            body="# Body\n\nMore\n",
            proposal_kind="skill_draft_md",
            target_skill_name="z-target",
        )
    )
    full = json.loads(t4.read_powerunits_skill_draft_proposal(relative_file_path=rel))
    assert full.get("tier4a_marker_present") is True
    assert full["frontmatter"].get("target_skill_name") == "z-target"
    assert "Body" in full["markdown_body"]
    prv = json.loads(
        t4.read_powerunits_skill_draft_proposal(
            relative_file_path=rel, max_body_preview_chars=4, include_frontmatter_meta=True
        )
    )
    assert prv["body_preview"] == "# Bo"
    assert prv["body_preview_truncated"] is True


def test_list_sort_mtime_desc(t4, tmp_path: Path) -> None:
    import os

    json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path="batch/a.md", body="# a", proposal_kind="skill_draft_md"
        )
    )
    json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path="batch/b.md", body="# b", proposal_kind="skill_draft_md"
        )
    )
    # Ensure distinct mtimes even on coarse-resolution filesystems.
    a_path = tmp_path / "hermes_workspace" / "drafts" / "powerunits_skill_proposals" / "batch" / "a.md"
    b_path = tmp_path / "hermes_workspace" / "drafts" / "powerunits_skill_proposals" / "batch" / "b.md"
    st_a = a_path.stat()
    os.utime(b_path, (st_a.st_mtime + 2, st_a.st_mtime + 2))
    lst = json.loads(
        t4.list_powerunits_skill_draft_proposals(subpath_prefix="batch", sort_by="mtime_desc")
    )
    paths = [e["relative_path"] for e in lst["entries"]]
    assert paths[0].endswith("b.md")


def test_review_filters_and_rollups(t4, tmp_path: Path) -> None:
    json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path="r/one.md",
            body="# x",
            proposal_kind="skill_draft_md",
            target_skill_name="alpha-skill",
        )
    )
    json.loads(
        t4.write_powerunits_skill_draft_proposal(
            relative_file_path="r/two.md",
            body="# y",
            proposal_kind="patch_style_diff_txt",
            target_skill_name="beta-skill",
        )
    )
    rev = json.loads(
        t4.review_powerunits_skill_draft_proposals(
            max_entries=10, target_skill_substring="alpha", proposal_kind_filter="skill_draft_md"
        )
    )
    assert rev["review"]["matching_file_count"] == 1
    assert rev["review"]["entries"][0]["relative_path"] == "r/one.md"
    assert rev["rollup_counts"]["by_target_skill"].get("alpha-skill") == 1


def test_summarize_missing_marker_probe(t4, tmp_path: Path) -> None:
    root = tmp_path / "hermes_workspace" / "drafts" / "powerunits_skill_proposals"
    root.mkdir(parents=True)
    (root / "note.md").write_text("# no frontmatter\n", encoding="utf-8")
    s = json.loads(t4.summarize_powerunits_skill_draft_proposals())
    assert any("tier4a_drafts_some_files_missing_marker" in x for x in s["caution_flags"])
