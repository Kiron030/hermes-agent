"""Tests for Phase 1B read-only operator posture tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def posture_mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "0")
    from tools import powerunits_operator_posture_tool as m

    return m


def test_posture_read_only_happy(posture_mod) -> None:
    out = json.loads(posture_mod.summarize_powerunits_operator_posture())
    assert out["read_only"] is True
    assert out["phase"] == "1B_operator_posture_tool"
    assert out["environment"]["tier_effective_integer"] == 0
    assert out["environment"]["HERMES_POWERUNITS_RUNTIME_POLICY"] == "first_safe_v1"
    assert out["phase_2a_overlay_read_only"]["tier_gate_workspace_analysis"] is False
    p2b = out["phase_2b_overlay_read_only"]
    assert p2b["tier_gate_allowlisted_locals_read"] is False
    assert p2b["telegram_powerunits_tier2_allowlisted_read_observed"] is None
    assert "bounded_assumptions_summary" in out
    p3 = out["phase_tier3_skills_observer_read_only"]
    assert p3["tier_gate_skills_integration"] is False
    assert p3["telegram_powerunits_tier3_skills_integration_observed"] is None
    p4 = out["phase_tier4a_skill_drafts_read_only"]
    assert p4["tier_gate_skill_draft_proposals"] is False
    assert p4["telegram_powerunits_tier4a_skill_draft_proposals_observed"] is None
    assert out["tier4a_draft_proposals_watch_read_only"]["skipped_not_tier4a"] is True


def test_posture_tier_ge_one_phase2a_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "1")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram: [memory]\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    p2 = out["phase_2a_overlay_read_only"]
    assert p2["tier_gate_workspace_analysis"] is True
    assert p2["telegram_powerunits_tier1_analysis_observed"] is False
    assert any("phase_2a_drift" in x for x in out["caution_flags"])


def test_posture_tier_ge_one_phase2a_aligned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "1")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram: [memory, powerunits_tier1_analysis]\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    assert out["phase_2a_overlay_read_only"]["telegram_powerunits_tier1_analysis_observed"] is True
    assert not any(x.startswith("phase_2a_drift") for x in out["caution_flags"])


def test_posture_tier_ge_two_phase2b_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "2")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram: [memory, powerunits_tier1_analysis]\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    pb = out["phase_2b_overlay_read_only"]
    assert pb["tier_gate_allowlisted_locals_read"] is True
    assert pb["telegram_powerunits_tier2_allowlisted_read_observed"] is False
    assert any("phase_2b_drift" in x for x in out["caution_flags"])


def test_posture_tier_ge_two_phase2b_aligned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "2")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram: "
        "[memory, powerunits_tier1_analysis, powerunits_tier2_allowlisted_read]\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    assert (
        out["phase_2b_overlay_read_only"]["telegram_powerunits_tier2_allowlisted_read_observed"] is True
    )
    assert not any(x.startswith("phase_2b_drift") for x in out["caution_flags"])
    assert (
        out["phase_tier3_skills_observer_read_only"]["tier_gate_skills_integration"] is False
    )


def test_posture_tier_three_tier3_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "3")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram: "
        "[memory, powerunits_tier1_analysis, powerunits_tier2_allowlisted_read]\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    t3 = out["phase_tier3_skills_observer_read_only"]
    assert t3["tier_gate_skills_integration"] is True
    assert t3["telegram_powerunits_tier3_skills_integration_observed"] is False
    assert any("tier3_skills_drift" in x for x in out["caution_flags"])


def test_posture_tier_three_aligned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "3")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram: "
        "[memory, powerunits_tier1_analysis, powerunits_tier2_allowlisted_read, "
        "powerunits_tier3_skills_integration]\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    assert (
        out["phase_tier3_skills_observer_read_only"][
            "telegram_powerunits_tier3_skills_integration_observed"
        ]
        is True
    )
    assert not any(x.startswith("tier3_skills_drift") for x in out["caution_flags"])


def test_posture_tier_three_curator_extra_caution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "3")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram:\n"
        "  - memory\n  - powerunits_tier1_analysis\n  - powerunits_tier2_allowlisted_read\n"
        "  - powerunits_tier3_skills_integration\n"
        "auxiliary:\n  curator:\n    enabled: true\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    assert any("tier3_curator_autonomous_path_enabled" in x for x in out["caution_flags"])


def test_posture_unset_policy_caution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_POWERUNITS_RUNTIME_POLICY", raising=False)
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "0")
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    assert any("runtime_policy_unset" in x for x in out["caution_flags"])




def test_posture_tier_four_tier4a_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "4")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram:\n"
        "  - memory\n  - powerunits_tier1_analysis\n"
        "  - powerunits_tier2_allowlisted_read\n  - powerunits_tier3_skills_integration\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    p4 = out["phase_tier4a_skill_drafts_read_only"]
    assert p4["tier_gate_skill_draft_proposals"] is True
    assert p4["telegram_powerunits_tier4a_skill_draft_proposals_observed"] is False
    assert any("tier4a_skill_drafts_drift" in x for x in out["caution_flags"])


def test_posture_tier_four_aligned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "4")
    (tmp_path / "config.yaml").write_text(
        "platform_toolsets:\n  telegram:\n"
        "  - memory\n  - powerunits_tier1_analysis\n"
        "  - powerunits_tier2_allowlisted_read\n  - powerunits_tier3_skills_integration\n"
        "  - powerunits_tier4a_skill_draft_proposals\n",
        encoding="utf-8",
    )
    from tools import powerunits_operator_posture_tool as m

    out = json.loads(m.summarize_powerunits_operator_posture())
    assert (
        out["phase_tier4a_skill_drafts_read_only"][
            "telegram_powerunits_tier4a_skill_draft_proposals_observed"
        ]
        is True
    )
    assert not any(x.startswith("tier4a_skill_drafts_drift") for x in out["caution_flags"])


def test_posture_curator_true_caution(posture_mod, tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "auxiliary:\n  curator:\n    enabled: true\n",
        encoding="utf-8",
    )
    out = json.loads(posture_mod.summarize_powerunits_operator_posture())
    assert out["config_curator_observation_read_only"]["auxiliary.curator.enabled"] is True
    assert any("curator_enabled_true" in x for x in out["caution_flags"])


def test_posture_includes_exports_subset(posture_mod, tmp_path: Path) -> None:
    from tools import powerunits_workspace_tool as ws

    json.loads(ws.list_hermes_workspace())
    json.loads(
        ws.save_hermes_workspace_note(
            kind="exports",
            name="probe.csv",
            content="a,b\n1,2\n",
            overwrite_mode="forbid",
        )
    )
    out = json.loads(posture_mod.summarize_powerunits_operator_posture())
    exp = out["phase_1a_exports_signals_read_only"]
    assert exp.get("exports_pointer_present") is True
    assert exp.get("summarize_attempted") is True
    assert int(exp.get("file_count") or 0) >= 1
