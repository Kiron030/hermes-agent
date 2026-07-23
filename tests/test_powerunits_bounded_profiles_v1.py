"""Tests for bounded env profile expansion (v1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import powerunits_bounded_profiles_v1 as profiles


def test_stage1_analyst_read_is_alias_of_read_health() -> None:
    assert profiles.PROFILE_ENV_EXPANSIONS_V1["stage1_analyst_read"] is profiles.STAGE1_READ_HEALTH
    assert "GB" in profiles.STAGE1_READ_HEALTH["HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES"]


def test_apply_profile_fills_missing_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED", "1")

    out = profiles.apply_bounded_profile_to_process_env()
    assert out["profile"] == "stage1_read_health"
    assert out["unknown"] is False
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["applied"]
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED" in out["skipped_explicit"]
    assert os.getenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED") == "1"
    assert os.getenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED") == "1"


def test_evaluate_profile_alignment_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    out = profiles.evaluate_bounded_profile_alignment()
    assert out["aligned"] is False
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["missing_truthy"]


def test_evaluate_profile_alignment_csv_allowlist_not_missing_truthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ERA5 allowlist is CSV, not 1/true — must not false-flag posture drift."""
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    for key, value in profiles.STAGE1_READ_HEALTH.items():
        monkeypatch.setenv(key, value)
    out = profiles.evaluate_bounded_profile_alignment()
    assert out["aligned"] is True
    assert out["missing_truthy"] == []


def test_persist_profile_writes_managed_block_to_hermes_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")

    out = profiles.persist_bounded_profile_to_hermes_env(env_path)
    assert out["profile"] == "stage1_read_health"
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["persisted"]
    text = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-test" in text
    assert profiles.ENV_MANAGED_BEGIN in text
    assert profiles.ENV_MANAGED_END in text
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED=1" in text


def test_persist_profile_skips_explicit_railway_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", "0")
    env_path = tmp_path / ".env"
    explicit = profiles._explicit_env_keys_at_boot()

    out = profiles.persist_bounded_profile_to_hermes_env(
        env_path, explicit_env_keys=explicit
    )
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["skipped_explicit"]
    assert profiles.ENV_MANAGED_BEGIN not in (env_path.read_text(encoding="utf-8") if env_path.exists() else "")


def test_profile_gated_toolsets_missing_returns_empty_without_active_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_PROFILE", raising=False)
    assert profiles.profile_gated_toolsets_missing_from_telegram_v1() == []


def test_profile_gated_toolsets_missing_flags_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    fake_requirements = {
        "powerunits_worker_country_coverage_freshness": {
            "env_vars": ["HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED"],
        },
        "powerunits_some_new_family_not_yet_on_telegram": {
            "env_vars": ["HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED"],
        },
        "powerunits_unrelated_toolset": {
            "env_vars": ["HERMES_SOME_UNRELATED_ENV"],
        },
    }
    missing = profiles.profile_gated_toolsets_missing_from_telegram_v1(
        toolset_requirements=fake_requirements
    )
    assert missing == ["powerunits_some_new_family_not_yet_on_telegram"]


def test_profile_gated_toolsets_missing_empty_when_all_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    fake_requirements = {
        "powerunits_worker_country_coverage_freshness": {
            "env_vars": ["HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED"],
        },
        "powerunits_bounded_coverage_snapshot": {
            "env_vars": ["HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED"],
        },
    }
    missing = profiles.profile_gated_toolsets_missing_from_telegram_v1(
        toolset_requirements=fake_requirements
    )
    assert missing == []


def test_profile_gated_toolsets_missing_unknown_profile_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "totally_unknown_profile")
    assert (
        profiles.profile_gated_toolsets_missing_from_telegram_v1(toolset_requirements={})
        == []
    )


def test_persist_not_suppressed_after_apply_in_same_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: apply then persist in init subprocess must still write .env."""
    monkeypatch.setenv("HERMES_POWERUNITS_BOUNDED_PROFILE", "stage1_read_health")
    monkeypatch.delenv("HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED", raising=False)
    env_path = tmp_path / ".env"
    explicit = profiles._explicit_env_keys_at_boot()
    profiles.apply_bounded_profile_to_process_env()

    out = profiles.persist_bounded_profile_to_hermes_env(
        env_path, explicit_env_keys=explicit
    )
    assert "HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED" in out["persisted"]
