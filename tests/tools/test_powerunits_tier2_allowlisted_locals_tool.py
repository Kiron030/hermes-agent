"""Tests for Phase 2B Tier-2 allowlisted local read overlay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def t2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "2")
    from tools import powerunits_tier2_allowlisted_locals_tool as m

    return m


def test_tier_gate_returns_error_at_tier_below_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "1")
    from tools import powerunits_tier2_allowlisted_locals_tool as m

    out = json.loads(m.manifest_powerunits_tier2_allowlisted_read_scope())
    assert out.get("error_code") == "tier_gate"


def test_manifest_reports_scope(t2) -> None:
    out = json.loads(t2.manifest_powerunits_tier2_allowlisted_read_scope())
    assert out["read_only"] is True
    assert out["phase"] == "2B"
    assert "hermes_workspace" in str(out["roots_relative_to_HERMES_HOME"]).lower()


def test_summarize_sees_workspace_json_and_reference(t2, tmp_path: Path) -> None:
    ws = tmp_path / "hermes_workspace"
    for sd in ("analysis", "notes", "drafts", "exports"):
        (ws / sd).mkdir(parents=True, exist_ok=True)
    (ws / "exports" / "meta.json").write_text('{"k":"v"}', encoding="utf-8")

    ref = tmp_path / "powerunits_local_reference"
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "readme.yaml").write_text("x: 1\n", encoding="utf-8")

    out = json.loads(t2.summarize_powerunits_allowlisted_locals())
    assert out["read_only"] is True
    assert out["hermes_workspace"]["files"] >= 1
    assert out["powerunits_local_reference"]["files"] >= 1


def test_read_workspace_extended_json(t2, tmp_path: Path) -> None:
    ws = tmp_path / "hermes_workspace"
    (ws / "analysis").mkdir(parents=True, exist_ok=True)
    (ws / "analysis" / "cfg.json").write_text('{"a": 2}', encoding="utf-8")

    out = json.loads(
        t2.read_powerunits_allowlisted_workspace_extended_file(path="analysis/cfg.json")
    )
    assert out["truncated"] is False
    assert '"a"' in out["content"]
    assert out["phase"] == "2B"


def test_search_across_roots(t2, tmp_path: Path) -> None:
    ws = tmp_path / "hermes_workspace"
    (ws / "notes").mkdir(parents=True, exist_ok=True)
    (ws / "notes" / "n.md").write_text("token-beta-unique\n", encoding="utf-8")
    ref = tmp_path / "powerunits_local_reference"
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "r.txt").write_text("token-beta-unique\n", encoding="utf-8")

    out = json.loads(
        t2.search_powerunits_allowlisted_local_text(query="token-beta-unique")
    )
    assert out["match_count"] >= 1
    paths_upper = "|".join(m["path"] for m in out["matches"]).upper()
    assert "POWERUNITS_LOCAL_REFERENCE" in paths_upper


def test_read_reference_file(t2, tmp_path: Path) -> None:
    ref = tmp_path / "powerunits_local_reference"
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "z.json").write_text("[]", encoding="utf-8")
    out = json.loads(t2.read_powerunits_local_reference_file(path="z.json"))
    assert out["truncated"] is False
    assert "[" in out["content"]
