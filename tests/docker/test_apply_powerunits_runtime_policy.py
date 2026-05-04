"""Tests for Powerunits first_safe_v1 config policy (Docker bootstrap)."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY = _REPO_ROOT / "docker" / "apply_powerunits_runtime_policy.py"


def _load_apply_policy():
    """Load policy module only when PyYAML is available (policy module imports yaml)."""
    pytest.importorskip("yaml")
    spec = importlib.util.spec_from_file_location(
        "apply_powerunits_runtime_policy", _POLICY
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.apply_policy


def test_apply_policy_sets_curator_and_redaction_defaults() -> None:
    yaml = pytest.importorskip("yaml")
    apply_policy = _load_apply_policy()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            "model: {}\nplatforms: {}\nplatform_toolsets: {}\napprovals: {}\n",
            encoding="utf-8",
        )
        apply_policy(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert data["auxiliary"]["curator"]["enabled"] is False
        assert data["redaction"]["enabled"] is False


def test_apply_policy_preserves_explicit_curator_enabled_true() -> None:
    yaml = pytest.importorskip("yaml")
    apply_policy = _load_apply_policy()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            yaml.safe_dump(
                {
                    "model": {},
                    "platforms": {},
                    "platform_toolsets": {},
                    "approvals": {},
                    "auxiliary": {"curator": {"enabled": True}},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        apply_policy(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert data["auxiliary"]["curator"]["enabled"] is True


def test_apply_policy_includes_phase2a_toolset_when_capability_tier_ge_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yaml = pytest.importorskip("yaml")
    apply_policy = _load_apply_policy()
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "1")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            "model: {}\nplatforms: {}\nplatform_toolsets: {}\napprovals: {}\n",
            encoding="utf-8",
        )
        apply_policy(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        tg = data["platform_toolsets"]["telegram"]
        assert "powerunits_tier1_analysis" in tg
        assert tg.index("powerunits_tier1_analysis") == tg.index("powerunits_workspace") + 1
        assert "powerunits_tier2_allowlisted_read" not in tg


def test_apply_policy_excludes_phase2a_toolset_when_capability_tier_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yaml = pytest.importorskip("yaml")
    apply_policy = _load_apply_policy()
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "0")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            "model: {}\nplatforms: {}\nplatform_toolsets: {}\napprovals: {}\n",
            encoding="utf-8",
        )
        apply_policy(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "powerunits_tier1_analysis" not in data["platform_toolsets"]["telegram"]
        assert "powerunits_tier2_allowlisted_read" not in data["platform_toolsets"]["telegram"]
        assert "powerunits_tier3_skills_integration" not in data["platform_toolsets"]["telegram"]


def test_apply_policy_includes_phase2b_toolset_when_capability_tier_ge_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yaml = pytest.importorskip("yaml")
    apply_policy = _load_apply_policy()
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "2")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            "model: {}\nplatforms: {}\nplatform_toolsets: {}\napprovals: {}\n",
            encoding="utf-8",
        )
        apply_policy(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        tg = data["platform_toolsets"]["telegram"]
        wi = tg.index("powerunits_workspace")
        assert tg[wi + 1] == "powerunits_tier1_analysis"
        assert tg[wi + 2] == "powerunits_tier2_allowlisted_read"
        assert "powerunits_tier3_skills_integration" not in tg


def test_apply_policy_includes_tier3_skills_toolset_when_capability_tier_is_three(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yaml = pytest.importorskip("yaml")
    apply_policy = _load_apply_policy()
    monkeypatch.setenv("HERMES_POWERUNITS_CAPABILITY_TIER", "3")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "config.yaml"
        p.write_text(
            "model: {}\nplatforms: {}\nplatform_toolsets: {}\napprovals: {}\n",
            encoding="utf-8",
        )
        apply_policy(p)
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        tg = data["platform_toolsets"]["telegram"]
        wi = tg.index("powerunits_workspace")
        assert tg[wi + 1] == "powerunits_tier1_analysis"
        assert tg[wi + 2] == "powerunits_tier2_allowlisted_read"
        assert tg[wi + 3] == "powerunits_tier3_skills_integration"
