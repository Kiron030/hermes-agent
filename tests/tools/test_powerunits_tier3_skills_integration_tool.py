"""Tests for Tier 3 skills integration observer tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def t3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "3")
    from tools import powerunits_tier3_skills_integration_tool as m

    return m


def test_tier_gate_below_three(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "2")
    from tools import powerunits_tier3_skills_integration_tool as m

    out = json.loads(m.summarize_powerunits_skills_observer())
    assert out["error_code"] == "tier_gate"


def test_observer_empty_skills_tree(t3, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    out = json.loads(t3.summarize_powerunits_skills_observer())
    assert out["read_only"] is True
    assert out["skill_md_paths_scanned"] == 0


def test_preview_reads_skill_md(t3, tmp_path: Path) -> None:
    d = tmp_path / "skills" / "my-skill"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: x\n---\nBody here\n",
        encoding="utf-8",
    )
    out = json.loads(t3.read_powerunits_skill_body_preview(skill_name="my-skill"))
    assert out["read_only"] is True
    assert out.get("preview_kind") == "skill_md_body"
    assert "Body here" in out["body"]


def test_preview_nested_slug(t3, tmp_path: Path) -> None:
    cat = tmp_path / "skills" / "research"
    sub = cat / "arxiv"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "SKILL.md").write_text(
        "---\nname: arxiv\n---\nNested body\n",
        encoding="utf-8",
    )
    out = json.loads(t3.read_powerunits_skill_body_preview(skill_name="research/arxiv"))
    assert out.get("preview_kind") == "skill_md_body"
    assert "Nested body" in out["body"]
    assert out["path_relative_to_skills"] == "research/arxiv/SKILL.md"


def test_preview_category_hub_with_description(t3, tmp_path: Path) -> None:
    cat = tmp_path / "skills" / "research"
    sub = cat / "arxiv"
    sub.mkdir(parents=True, exist_ok=True)
    (cat / "DESCRIPTION.md").write_text("# Research category\nPick a subfolder.\n", encoding="utf-8")
    (sub / "SKILL.md").write_text("---\nname: arxiv\n---\n\n", encoding="utf-8")
    out = json.loads(t3.read_powerunits_skill_body_preview(skill_name="research"))
    assert out["preview_kind"] == "skill_category_hub_with_description"
    assert "Research category" in out["description_excerpt"]
    assert "research/arxiv" in out["nested_skill_slugs"]


def test_preview_category_index_without_description(t3, tmp_path: Path) -> None:
    cat = tmp_path / "skills" / "software-development"
    sub = cat / "hermes-authoring"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "SKILL.md").write_text("---\nname: x\n---\n\n", encoding="utf-8")
    out = json.loads(
        t3.read_powerunits_skill_body_preview(skill_name="software-development/hermes-authoring")
    )
    assert out.get("preview_kind") == "skill_md_body"

    hub = json.loads(t3.read_powerunits_skill_body_preview(skill_name="software-development"))
    assert hub["preview_kind"] == "skill_category_index"
    assert "software-development/hermes-authoring" in hub["nested_skill_slugs"]


def test_preview_rejects_parent_segments(t3, tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    out = json.loads(t3.read_powerunits_skill_body_preview(skill_name="a/../b"))
    assert out["error_code"] == "invalid_skill_name"


def test_preview_rejects_forbidden_tree_part(t3, tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    out = json.loads(t3.read_powerunits_skill_body_preview(skill_name=".hub/nope"))
    assert out["error_code"] == "invalid_skill_name"


def test_propose_returns_flag(t3, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    raw = t3.propose_powerunits_skill_integration_actions()
    obj = json.loads(raw)
    assert obj["explicitly_not_auto_applied"] is True
