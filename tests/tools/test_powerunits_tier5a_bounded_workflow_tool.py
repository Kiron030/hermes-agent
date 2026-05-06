"""Tests for Tier 5A bounded operator workflow scaffolding tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tier5_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "6")
    return tmp_path


def test_manifest_tier_gated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "5")
    from tools import powerunits_tier5a_bounded_workflow_tool as m

    raw = m.manifest_powerunits_tier5a_bounded_workflow_scope()
    obj = json.loads(raw)
    assert obj.get("error_code") == "tier_gate"


def test_upsert_run_record_and_summarize(tier5_home: Path) -> None:
    from tools import powerunits_tier5a_bounded_workflow_tool as m

    json.loads(m.ensure_powerunits_bounded_workflow_workspace())
    json.loads(
        m.upsert_powerunits_bounded_workflow_run(
            "smoke-run-1",
            frontmatter_patch={
                "workflow_status": "running",
                "workflow_stage": "execute",
                "retry_count": 2,
            },
        )
    )
    wf = tier5_home / "hermes_workspace" / "operator_bounded_workflows"
    run_fp = wf / "run_records" / "smoke-run-1.md"
    assert run_fp.is_file()

    summ = json.loads(m.summarize_powerunits_tier5a_bounded_workflow_lane())
    assert summ.get("error_code") is None
    assert summ["run_record_files_scanned"] >= 1
    counts = summ["workflow_status_counts"]
    assert counts.get("running") >= 1

    board = json.loads(
        m.review_powerunits_bounded_workflow_runs(workflow_status_filter="running")
    )
    assert board["matching_count"] >= 1


def test_invalid_workflow_status_rejected(tier5_home: Path) -> None:
    from tools import powerunits_tier5a_bounded_workflow_tool as m

    json.loads(m.ensure_powerunits_bounded_workflow_workspace())
    raw = m.upsert_powerunits_bounded_workflow_run(
        "bad-status",
        frontmatter_patch={"workflow_status": "not_a_real_status"},
    )
    obj = json.loads(raw)
    assert obj.get("error_code") == "invalid_frontmatter_patch"


def test_append_note_only_allowlisted_prefix(tier5_home: Path) -> None:
    from tools import powerunits_tier5a_bounded_workflow_tool as m

    json.loads(m.ensure_powerunits_bounded_workflow_workspace())
    raw = m.append_powerunits_bounded_workflow_note(
        "run_records/evil.md",
        body="x",
    )
    assert "note_path_must_start_with" in json.loads(raw).get("error", "")
