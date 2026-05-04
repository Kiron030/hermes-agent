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
    assert "Body here" in out["body"]


def test_propose_returns_flag(t3, tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir(parents=True, exist_ok=True)
    raw = t3.propose_powerunits_skill_integration_actions()
    obj = json.loads(raw)
    assert obj["explicitly_not_auto_applied"] is True
