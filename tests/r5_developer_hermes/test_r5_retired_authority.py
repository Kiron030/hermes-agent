"""The retired-authority contract must be narrow, verified and fail-closed.

Everything here uses a fake git runner, so the tests assert the contract rather
than the current state of a sibling checkout. No historical credential is read.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

import pytest

from r5_developer_hermes.retired_authority import (
    EVIDENCE_PATH,
    LIVE_OR_UNKNOWN,
    LIVE_SECRET_PRESENT,
    NO_SECRET_MATERIAL,
    PROVEN_RETIRED,
    REQUIRED_CHECKS,
    classify,
    classify_all,
    load_evidence,
)

RETIRED_PATH = ".env.pgurl"


def make_git(
    *,
    canonical_tracks: bool = False,
    is_ancestor: bool = True,
    deletes: bool = True,
):
    def git(repo: Path, args: Sequence[str]) -> "subprocess.CompletedProcess[str]":
        cmd = list(args)
        if cmd[0] == "ls-tree":
            return subprocess.CompletedProcess(cmd, 0, f"{RETIRED_PATH}\n" if canonical_tracks else "", "")
        if cmd[0] == "merge-base":
            return subprocess.CompletedProcess(cmd, 0 if is_ancestor else 1, "", "")
        if cmd[0] == "show":
            body = f"D\t{RETIRED_PATH}\n" if deletes else "M\tREADME.md\n"
            return subprocess.CompletedProcess(cmd, 0, body, "")
        return subprocess.CompletedProcess(cmd, 1, "", "unexpected git call")

    return git


def evidence(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "repo": "EU-PP-Database",
        "relative_path": RETIRED_PATH,
        "canonical_ref": "origin/main",
        "retirement_commit": "7bd3f9a09d94cfa1c26ccc9486920ec23f84699c",
        "authority_target": "legacy sandbox service",
        "human_attestation": {
            "statement": "service deleted by a human operator",
            "attested_by": "operator",
            "attested_utc": "2026-08-23",
            "service_deleted": True,
        },
    }
    entry.update(overrides)
    return {"schema": "r5.retired_secret_authority.v1", "entries": [entry]}


@pytest.fixture
def repo_b(tmp_path: Path) -> Path:
    root = tmp_path / "EU-PP-Database"
    root.mkdir()
    (root / RETIRED_PATH).write_text("", encoding="utf-8")
    return root


def finding(root: Path, relative_path: str = RETIRED_PATH, **overrides: Any) -> dict[str, Any]:
    base = {
        "root": str(root),
        "relative_path": relative_path,
        "size": 0,
        "git_tracked": True,
        "in_git_history": True,
    }
    base.update(overrides)
    return base


def test_exact_retired_contract_is_not_a_blocker(repo_b: Path) -> None:
    result = classify(finding(repo_b), evidence(), make_git())
    assert result["verdict"] == PROVEN_RETIRED
    assert result["blocking"] is False
    assert [check["id"] for check in result["checks"]] == list(REQUIRED_CHECKS)
    assert all(check["ok"] for check in result["checks"])


def test_live_credential_blocks_even_with_evidence(repo_b: Path) -> None:
    """Content in the working tree outranks any retirement claim."""
    (repo_b / RETIRED_PATH).write_text("x" * 91, encoding="utf-8")
    result = classify(finding(repo_b, size=91), evidence(), make_git())
    assert result["verdict"] == LIVE_SECRET_PRESENT
    assert result["blocking"] is True


def test_unknown_historical_credential_blocks(repo_b: Path) -> None:
    result = classify(finding(repo_b), {"entries": []}, make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN
    assert result["blocking"] is True
    assert "no retirement evidence" in result["reason"]


def test_a_different_historical_secret_still_blocks(repo_b: Path) -> None:
    """The contract is one exact path, not a family of dotfiles."""
    (repo_b / ".env").write_text("", encoding="utf-8")
    result = classify(finding(repo_b, relative_path=".env"), evidence(), make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN
    assert result["blocking"] is True


def test_same_path_in_a_different_repo_still_blocks(repo_b: Path, tmp_path: Path) -> None:
    other = tmp_path / "some-other-repo"
    other.mkdir()
    (other / RETIRED_PATH).write_text("", encoding="utf-8")
    result = classify(finding(other), evidence(), make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN


def test_missing_retirement_evidence_file_retires_nothing(
    repo_b: Path, tmp_path: Path
) -> None:
    absent = load_evidence(tmp_path / "does-not-exist.json")
    assert absent["entries"] == []
    result = classify(finding(repo_b), absent, make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN


def test_unparsable_evidence_file_retires_nothing(repo_b: Path, tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    result = classify(finding(repo_b), load_evidence(broken), make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN


@pytest.mark.parametrize(
    "git_kwargs, failed_check",
    [
        ({"canonical_tracks": True}, "CANONICAL_MAIN_UNTRACKED"),
        ({"is_ancestor": False}, "RETIREMENT_COMMIT_IN_CANONICAL"),
        ({"deletes": False}, "RETIREMENT_COMMIT_IN_CANONICAL"),
    ],
)
def test_each_git_verified_element_is_load_bearing(
    repo_b: Path, git_kwargs: dict[str, Any], failed_check: str
) -> None:
    result = classify(finding(repo_b), evidence(), make_git(**git_kwargs))
    assert result["verdict"] == LIVE_OR_UNKNOWN
    assert failed_check in result["reason"]


@pytest.mark.parametrize(
    "attestation",
    [
        None,
        {"statement": "s", "attested_by": "o", "attested_utc": "2026-08-23", "service_deleted": False},
        {"statement": "", "attested_by": "o", "attested_utc": "2026-08-23", "service_deleted": True},
        {"statement": "s", "attested_by": "", "attested_utc": "2026-08-23", "service_deleted": True},
        {"statement": "s", "attested_by": "o", "attested_utc": "", "service_deleted": True},
    ],
)
def test_human_attestation_is_load_bearing(repo_b: Path, attestation: Any) -> None:
    result = classify(finding(repo_b), evidence(human_attestation=attestation), make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN
    assert "HUMAN_ATTESTATION" in result["reason"]


def test_short_retirement_sha_is_rejected(repo_b: Path) -> None:
    result = classify(finding(repo_b), evidence(retirement_commit="7bd3f9a"), make_git())
    assert result["verdict"] == LIVE_OR_UNKNOWN
    assert "RETIREMENT_COMMIT_IN_CANONICAL" in result["reason"]


def test_empty_untracked_file_is_not_secret_material(repo_b: Path) -> None:
    result = classify(
        finding(repo_b, git_tracked=False, in_git_history=False), evidence(), make_git()
    )
    assert result["verdict"] == NO_SECRET_MATERIAL
    assert result["blocking"] is False


def test_aggregate_counters_drive_the_preflight_gates(repo_b: Path, tmp_path: Path) -> None:
    live = tmp_path / "EU-PP-Database-live"
    live.mkdir()
    (live / ".env").write_text("secret-shaped", encoding="utf-8")

    report = classify_all(
        [
            finding(repo_b),
            finding(live, relative_path=".env", size=13),
        ],
        evidence(),
        make_git(),
    )
    assert report["ACTIVE_WORKSPACE_SECRET_FILES"] == 1
    assert report["UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY"] == 0
    assert report["HISTORICAL_DEAD_AUTHORITY"] == 1
    assert report["SECRET_AUTHORITY_BLOCKED"] is True


def test_shipped_evidence_file_is_narrow_and_carries_no_secret() -> None:
    raw = EVIDENCE_PATH.read_text(encoding="utf-8-sig")
    parsed = json.loads(raw)
    assert parsed["schema"] == "r5.retired_secret_authority.v1"
    assert len(parsed["entries"]) == 1, "widening this file needs its own review"

    entry = parsed["entries"][0]
    assert entry["relative_path"] == RETIRED_PATH
    assert entry["repo"] == "EU-PP-Database"
    assert len(entry["retirement_commit"]) == 40
    assert entry["human_attestation"]["service_deleted"] is True

    # No wildcard escape hatch, and no credential material.
    lowered = raw.lower()
    for forbidden in ("*", "ignore_git_history", "postgres://", "postgresql://", "password"):
        assert forbidden not in lowered, forbidden
