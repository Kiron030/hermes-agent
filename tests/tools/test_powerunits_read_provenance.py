"""HERMES-READ-TRUTH-0: immutable pinned PowerUnits read ref + uniform read provenance.

Offline only: GitHub HTTP is faked at ``urlopen`` in tools.powerunits_github_knowledge and
every call is recorded, so "no network" is asserted as an empty call list.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest

PIN = "4c489d5df3e289600eef004e3e71b5e8d4865ff4"
PIN_TIME = "2026-07-21T09:51:31+02:00"
OTHER_SHA = "1111111111111111111111111111111111111111"
TOKEN = "ghp_test_token_must_never_leak_0123456789"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_KEYS = {
    "read_sha",
    "read_commit_time",
    "read_age_days",
    "read_is_current_or_approved",
    "read_source",
    "read_provenance_complete",
}
_OMIT = object()

BAD_REFS = [
    pytest.param(None, id="missing"),
    pytest.param("", id="empty"),
    pytest.param("4c489d5", id="short_7_char_sha"),
    pytest.param("starting_the_seven_phases", id="branch_name"),
    pytest.param("main", id="branch_main"),
    pytest.param(PIN.upper(), id="uppercase_hex"),
    pytest.param("z" * 40, id="non_hex_40"),
    pytest.param(PIN + "0", id="41_chars"),
]

_TOOL_LOGGERS = (
    "tools.powerunits_github_knowledge",
    "tools.powerunits_docs_tool",
    "tools.powerunits_repo_b_read_tool",
    "tools.powerunits_github_docs_tool",
)


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _FakeGitHub:
    """Records every URL; answers only routed URL substrings, fails on anything else."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.routes: dict[str, Any] = {}

    def __call__(self, req: Any, timeout: float | None = None) -> _FakeResp:
        url = req.full_url
        self.calls.append(url)
        for needle, body in self.routes.items():
            if needle in url:
                if isinstance(body, BaseException):
                    raise body
                data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
                return _FakeResp(data)
        raise AssertionError(f"unexpected GitHub call: {url}")


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> _FakeGitHub:
    from tools import powerunits_github_knowledge as km

    fake = _FakeGitHub()
    monkeypatch.setattr(km, "urlopen", fake)
    monkeypatch.delenv("HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG", raising=False)
    monkeypatch.delenv("HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST", raising=False)
    monkeypatch.delenv("POWERUNITS_GITHUB_DOCS_TOKEN", raising=False)
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", TOKEN)
    return fake


@pytest.fixture
def captured_logs(caplog: pytest.LogCaptureFixture):
    """Attach the capture handler to the tool loggers directly (robust to propagate=False)."""
    handler = caplog.handler
    attached = []
    for name in _TOOL_LOGGERS:
        caplog.set_level(logging.DEBUG, logger=name)
        lg = logging.getLogger(name)
        if handler not in lg.handlers:
            lg.addHandler(handler)
            attached.append(lg)
    try:
        yield caplog
    finally:
        for lg in attached:
            lg.removeHandler(handler)


def _write_knowledge_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    surface_ref: Any = PIN,
    approved_ref: Any = PIN,
    approved_time: Any = PIN_TIME,
    legacy_branch: Any = _OMIT,
) -> Path:
    def _surface(alias: str, root: str) -> dict[str, Any]:
        s: dict[str, Any] = {
            "alias": alias,
            "repo": "Kiron030/Powerunits.io",
            "root_prefix": root,
            "allowed_extensions": [".md", ".txt"],
            "enabled": True,
        }
        if surface_ref is not _OMIT:
            s["ref"] = surface_ref
        if legacy_branch is not _OMIT:
            s["branch"] = legacy_branch
        return s

    cfg: dict[str, Any] = {
        "version": 2,
        "doc_key_allowlist_relative": "scripts/powerunits_docs_allowlist.json",
        "surfaces": [_surface("powerunits_docs", "docs"), _surface("powerunits_roadmap", "docs/roadmap")],
    }
    if approved_ref is not _OMIT:
        cfg["approved_ref"] = approved_ref
    if approved_time is not _OMIT:
        cfg["approved_ref_commit_time"] = approved_time
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG", str(path))
    return path


def _write_repo_b_allowlist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    entry_ref: Any = PIN,
    approved_ref: Any = PIN,
    approved_time: Any = PIN_TIME,
    legacy_branch: Any = _OMIT,
) -> Path:
    entry: dict[str, Any] = {
        "key": "implementation_state",
        "repo": "Kiron030/Powerunits.io",
        "path": "docs/implementation_state.md",
        "content_type": "markdown",
    }
    if entry_ref is not _OMIT:
        entry["ref"] = entry_ref
    if legacy_branch is not _OMIT:
        entry["branch"] = legacy_branch
    raw: dict[str, Any] = {"version": 5, "entries": [entry]}
    if approved_ref is not _OMIT:
        raw["approved_ref"] = approved_ref
    if approved_time is not _OMIT:
        raw["approved_ref_commit_time"] = approved_time
    path = tmp_path / "repo_b_allowlist.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST", str(path))
    return path


def _write_doc_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    keys = tmp_path / "doc_keys.json"
    keys.write_text(
        json.dumps(
            {
                "allowlist_version": 2,
                "source_repo_name": "EU-PP-Database",
                "entries": [
                    {
                        "key": "implementation_state.md",
                        "source_relative": "docs/implementation_state.md",
                        "freshness_tier": "volatile",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_POWERUNITS_DOC_KEY_ALLOWLIST", str(keys))


def _write_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    commit: Any = PIN,
    commit_time: Any = PIN_TIME,
) -> Path:
    root = tmp_path / "bundle"
    root.mkdir()
    content = b"# Bundled implementation state\n"
    key = "implementation_state.md"
    (root / key).write_bytes(content)
    manifest: dict[str, Any] = {
        "bundle_version": 2,
        "allowlist_version": 2,
        "generated_at": "2026-07-22T00:00:00Z",
        "source_repo_name": "EU-PP-Database",
        "entries": [
            {
                "key": key,
                "source_relative": "docs/implementation_state.md",
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
                "freshness_tier": "volatile",
            }
        ],
    }
    if commit is not _OMIT:
        manifest["source_repo_commit"] = commit
    if commit_time is not _OMIT:
        manifest["source_commit_time"] = commit_time
    (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_BUNDLE", str(root))
    return root


def _assert_block(
    payload: dict[str, Any],
    *,
    source: str,
    sha: str | None = PIN,
    current: bool = True,
    complete: bool = True,
    commit_time: str | None = PIN_TIME,
) -> None:
    assert PROVENANCE_KEYS <= set(payload), payload
    assert payload["read_source"] == source
    assert payload["read_sha"] == sha
    assert payload["read_is_current_or_approved"] is current
    assert payload["read_provenance_complete"] is complete
    assert payload["read_commit_time"] == commit_time
    if commit_time is None:
        assert payload["read_age_days"] is None
    else:
        assert isinstance(payload["read_age_days"], float)
        assert payload["read_age_days"] >= 0.0


def _contents_url(path: str, ref: str = PIN) -> str:
    return f"https://api.github.com/repos/Kiron030/Powerunits.io/contents/{path}?ref={ref}"


# --- provenance builder --------------------------------------------------------------


def test_build_read_provenance_age_in_utc_days() -> None:
    from tools import powerunits_github_knowledge as km

    now = datetime(2026, 7, 31, 7, 51, 31, tzinfo=timezone.utc)
    block = km.build_read_provenance(
        read_sha=PIN, read_commit_time=PIN_TIME, approved_ref=PIN, read_source="github", now=now
    )
    assert block == {
        "read_sha": PIN,
        "read_commit_time": PIN_TIME,
        "read_age_days": 10.0,
        "read_is_current_or_approved": True,
        "read_source": "github",
        "read_provenance_complete": True,
    }
    assert tuple(block) == km.PROVENANCE_FIELDS


def test_build_read_provenance_rejects_unknown_source() -> None:
    from tools import powerunits_github_knowledge as km

    with pytest.raises(ValueError):
        km.build_read_provenance(read_sha=PIN, read_commit_time=PIN_TIME, approved_ref=PIN, read_source="branch")


# --- shipped configs ------------------------------------------------------------------


def test_shipped_configs_pinned_to_reviewed_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG", raising=False)
    monkeypatch.delenv("HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST", raising=False)
    from tools import powerunits_github_knowledge as km
    from tools import powerunits_repo_b_read_tool as rb

    knowledge = json.loads((REPO_ROOT / "config" / "powerunits_github_knowledge.json").read_text(encoding="utf-8"))
    assert knowledge["approved_ref"] == PIN
    assert knowledge["approved_ref_commit_time"] == PIN_TIME
    assert {s["alias"]: s["root_prefix"] for s in knowledge["surfaces"]} == {
        "powerunits_docs": "docs",
        "powerunits_roadmap": "docs/roadmap",
        "powerunits_architecture": "docs/architecture",
    }
    for s in knowledge["surfaces"]:
        assert s["ref"] == PIN
        assert "branch" not in s
    assert km.load_knowledge_pin() == (PIN, PIN_TIME)
    assert {s["ref"] for s in km.load_surfaces().values()} == {PIN}

    repo_b = json.loads((REPO_ROOT / "config" / "powerunits_repo_b_read_allowlist.json").read_text(encoding="utf-8"))
    assert repo_b["approved_ref"] == PIN
    assert repo_b["approved_ref_commit_time"] == PIN_TIME
    assert len(repo_b["entries"]) == 27
    for e in repo_b["entries"]:
        assert e["ref"] == PIN
        assert "branch" not in e
    assert len(rb._load_allowlist_entries()) == 27


# --- loaders fail closed ---------------------------------------------------------------


@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_knowledge_surface_rejects_non_immutable_ref(
    bad_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km

    _write_knowledge_config(tmp_path, monkeypatch, surface_ref=bad_ref)
    with pytest.raises(km.PinnedRefError):
        km.load_surfaces()
    assert km.check_github_knowledge_available() is False
    assert github.calls == []


def test_knowledge_surface_rejects_omitted_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km

    _write_knowledge_config(tmp_path, monkeypatch, surface_ref=_OMIT)
    with pytest.raises(km.PinnedRefError, match="missing 'ref'"):
        km.load_surfaces()
    assert github.calls == []


@pytest.mark.parametrize("surface_ref", [_OMIT, PIN], ids=["branch_only", "branch_and_ref"])
def test_knowledge_surface_legacy_branch_is_never_usable(
    surface_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km

    _write_knowledge_config(
        tmp_path, monkeypatch, surface_ref=surface_ref, legacy_branch="starting_the_seven_phases"
    )
    with pytest.raises(km.PinnedRefError, match="legacy moving 'branch'"):
        km.load_surfaces()
    assert github.calls == []


@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_knowledge_config_rejects_bad_approved_ref(
    bad_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km

    _write_knowledge_config(tmp_path, monkeypatch, approved_ref=bad_ref)
    with pytest.raises(km.PinnedRefError):
        km.load_knowledge_config()
    assert github.calls == []


@pytest.mark.parametrize(
    "bad_time",
    [_OMIT, "2026-07-21T09:51:31", "not-a-time", ""],
    ids=["missing", "no_offset", "garbage", "empty"],
)
def test_knowledge_config_rejects_bad_approved_commit_time(
    bad_time: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km

    _write_knowledge_config(tmp_path, monkeypatch, approved_time=bad_time)
    with pytest.raises(km.PinnedRefError, match="approved_ref_commit_time"):
        km.load_knowledge_config()
    assert github.calls == []


@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_repo_b_allowlist_rejects_non_immutable_ref(
    bad_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km
    from tools import powerunits_repo_b_read_tool as rb

    _write_repo_b_allowlist(tmp_path, monkeypatch, entry_ref=bad_ref)
    with pytest.raises(km.PinnedRefError):
        rb._load_allowlist_entries()
    assert github.calls == []


def test_repo_b_allowlist_rejects_legacy_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km
    from tools import powerunits_repo_b_read_tool as rb

    _write_repo_b_allowlist(tmp_path, monkeypatch, entry_ref=_OMIT, legacy_branch="starting_the_seven_phases")
    with pytest.raises(km.PinnedRefError, match="legacy moving 'branch'"):
        rb._load_allowlist_entries()
    assert github.calls == []


@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_repo_b_allowlist_rejects_bad_approved_ref(
    bad_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_knowledge as km
    from tools import powerunits_repo_b_read_tool as rb

    _write_repo_b_allowlist(tmp_path, monkeypatch, approved_ref=bad_ref)
    with pytest.raises(km.PinnedRefError):
        rb._load_allowlist_entries()
    assert github.calls == []


def test_contents_fetch_refuses_branch_ref(github: _FakeGitHub) -> None:
    from tools import powerunits_github_knowledge as km

    with pytest.raises(km.PinnedRefError):
        km.github_fetch_raw_file("Kiron030/Powerunits.io", "starting_the_seven_phases", "docs/x.md", TOKEN)
    with pytest.raises(km.PinnedRefError):
        km.github_fetch_json("Kiron030/Powerunits.io", "4c489d5", "docs/roadmap", TOKEN)
    assert github.calls == []


# --- tools fail closed without network -------------------------------------------------


@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_roadmap_tools_fail_closed_without_network(
    bad_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_github_docs_tool as m

    _write_knowledge_config(tmp_path, monkeypatch, surface_ref=bad_ref)
    listed = json.loads(m.list_powerunits_roadmap_dir(alias="powerunits_roadmap"))
    read = json.loads(m.read_powerunits_roadmap_file("overview.md", alias="powerunits_roadmap"))
    assert listed["error_code"] == "pinned_ref_invalid"
    assert read["error_code"] == "pinned_ref_invalid"
    assert m.check_powerunits_github_docs_requirements() is False
    assert github.calls == []


@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_repo_b_tool_fails_closed_without_network(
    bad_ref: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_repo_b_read_tool as rb

    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    _write_repo_b_allowlist(tmp_path, monkeypatch, entry_ref=bad_ref)
    read = json.loads(rb.read_powerunits_repo_b_allowlisted("read_repo_b_key", key="implementation_state"))
    listed = json.loads(rb.read_powerunits_repo_b_allowlisted("list_repo_b_keys"))
    assert read["error_code"] == "pinned_ref_invalid"
    assert listed["error_code"] == "pinned_ref_invalid"
    assert rb.check_powerunits_repo_b_read_requirements() is False
    assert github.calls == []


@pytest.mark.parametrize("mode", ["auto", "github", "bundle"])
@pytest.mark.parametrize("bad_ref", BAD_REFS)
def test_docs_tool_fails_closed_without_network(
    bad_ref: Any, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", mode)
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch)
    _write_knowledge_config(tmp_path, monkeypatch, surface_ref=bad_ref)
    read = json.loads(m.read_powerunits_doc(action="read", key="implementation_state.md"))
    listed = json.loads(m.read_powerunits_doc(action="list_keys"))
    assert read["error_code"] == "pinned_ref_invalid"
    assert listed["error_code"] == "pinned_ref_invalid"
    assert github.calls == []


# --- read_powerunits_doc: primary (GitHub) --------------------------------------------


def test_docs_primary_read_requests_pinned_ref_with_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "github")
    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_BUNDLE", str(tmp_path / "no_bundle"))
    _write_doc_keys(tmp_path, monkeypatch)
    github.routes["/contents/docs/implementation_state.md"] = b"# Live implementation state\n"

    raw = m.read_powerunits_doc(action="read", key="implementation_state.md")
    out = json.loads(raw)

    assert github.calls == [_contents_url("docs/implementation_state.md")]
    assert "starting_the_seven_phases" not in github.calls[0]
    assert out["knowledge_actual_source"] == "github_primary"
    assert "Live implementation state" in out["content"]
    _assert_block(out, source="github")
    assert out["github_commit_sha"] == PIN
    assert out["github_branch"] == PIN
    assert out["github_ref"] == PIN
    assert TOKEN not in raw


def test_docs_list_keys_github_mode_has_pinned_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "auto")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch, commit=OTHER_SHA)

    out = json.loads(m.read_powerunits_doc(action="list_keys"))
    _assert_block(out, source="github")
    _assert_block(out["bundled_snapshot_freshness"], source="bundle", sha=OTHER_SHA, current=False)
    assert github.calls == []


# --- read_powerunits_doc: fallback (bundle) -------------------------------------------


def test_docs_bundle_read_at_approved_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "bundle")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch)

    out = json.loads(m.read_powerunits_doc(action="read", key="implementation_state.md"))
    assert out["knowledge_actual_source"] == "bundled_fallback"
    _assert_block(out, source="bundle")
    assert github.calls == []


def test_docs_bundle_commit_differs_from_approved_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "bundle")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch, commit=OTHER_SHA)

    out = json.loads(m.read_powerunits_doc(action="read", key="implementation_state.md"))
    _assert_block(out, source="bundle", sha=OTHER_SHA, current=False, complete=True)


def test_docs_bundle_without_source_commit_time_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "bundle")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch, commit_time=_OMIT)

    out = json.loads(m.read_powerunits_doc(action="read", key="implementation_state.md"))
    _assert_block(out, source="bundle", current=True, complete=False, commit_time=None)


def test_docs_bundle_legacy_short_commit_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "bundle")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch, commit="4c489d5", commit_time=_OMIT)

    out = json.loads(m.read_powerunits_doc(action="read", key="implementation_state.md"))
    _assert_block(out, source="bundle", sha=None, current=False, complete=False, commit_time=None)


def test_docs_bundle_list_keys_has_bundle_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "bundle")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch)

    out = json.loads(m.read_powerunits_doc(action="list_keys"))
    _assert_block(out, source="bundle")
    freshness = out["bundled_snapshot_freshness"]
    _assert_block(freshness, source="bundle")
    assert freshness["source_commit_time"] == PIN_TIME
    assert github.calls == []


def test_docs_auto_fallback_after_github_failure_has_bundle_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "auto")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch)
    github.routes["/contents/"] = URLError("offline")

    raw = m.read_powerunits_doc(action="read", key="implementation_state.md")
    out = json.loads(raw)
    assert out["knowledge_actual_source"] == "bundled_fallback"
    _assert_block(out, source="bundle")
    assert github.calls == [_contents_url("docs/implementation_state.md")]
    assert TOKEN not in raw


# --- read_powerunits_repo_b_allowlisted ------------------------------------------------


def test_repo_b_read_requests_pinned_ref_with_provenance(
    monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_repo_b_read_tool as rb

    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    github.routes["/contents/docs/implementation_state.md"] = b"implementation body"

    raw = rb.read_powerunits_repo_b_allowlisted("read_repo_b_key", key="implementation_state")
    out = json.loads(raw)
    assert github.calls == [_contents_url("docs/implementation_state.md")]
    assert out["content"] == "implementation body"
    _assert_block(out, source="github")
    assert out["branch"] == PIN
    assert out["ref"] == PIN
    assert out["branch_tip_sha"] == PIN
    assert TOKEN not in raw


def test_repo_b_list_has_provenance_without_network(
    monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_repo_b_read_tool as rb

    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    out = json.loads(rb.read_powerunits_repo_b_allowlisted("list_repo_b_keys"))
    assert len(out["keys"]) == 27
    _assert_block(out, source="github")
    assert github.calls == []


def test_repo_b_read_non_approved_ref_uses_exact_commit_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_repo_b_read_tool as rb

    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    _write_repo_b_allowlist(tmp_path, monkeypatch, entry_ref=OTHER_SHA)
    github.routes["/contents/"] = b"body"
    github.routes[f"/commits/{OTHER_SHA}"] = {
        "sha": OTHER_SHA,
        "commit": {"committer": {"date": "2026-08-01T10:00:00Z"}},
    }

    out = json.loads(rb.read_powerunits_repo_b_allowlisted("read_repo_b_key", key="implementation_state"))
    _assert_block(
        out, source="github", sha=OTHER_SHA, current=False, complete=True, commit_time="2026-08-01T10:00:00Z"
    )
    assert github.calls[0] == _contents_url("docs/implementation_state.md", OTHER_SHA)
    assert github.calls[1].endswith(f"/commits/{OTHER_SHA}")


def test_repo_b_read_non_approved_ref_lookup_failure_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub
) -> None:
    from tools import powerunits_repo_b_read_tool as rb

    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    _write_repo_b_allowlist(tmp_path, monkeypatch, entry_ref=OTHER_SHA)
    github.routes["/contents/"] = b"body"
    github.routes["/commits/"] = URLError("down")

    out = json.loads(rb.read_powerunits_repo_b_allowlisted("read_repo_b_key", key="implementation_state"))
    _assert_block(out, source="github", sha=OTHER_SHA, current=False, complete=False, commit_time=None)


# --- list_powerunits_roadmap_dir / read_powerunits_roadmap_file ------------------------


def test_roadmap_list_and_read_request_pinned_ref_with_provenance(github: _FakeGitHub) -> None:
    from tools import powerunits_github_docs_tool as m

    github.routes["/contents/docs/roadmap?ref="] = [
        {"name": "overview.md", "type": "file", "path": "docs/roadmap/overview.md"}
    ]
    github.routes["/contents/docs/roadmap/overview.md?ref="] = b"# Overview\n"

    listed_raw = m.list_powerunits_roadmap_dir(alias="powerunits_roadmap")
    read_raw = m.read_powerunits_roadmap_file("overview.md", alias="powerunits_roadmap")
    listed, read = json.loads(listed_raw), json.loads(read_raw)

    assert github.calls == [_contents_url("docs/roadmap"), _contents_url("docs/roadmap/overview.md")]
    for payload in (listed, read):
        _assert_block(payload, source="github")
        assert payload["commit_sha"] == PIN
        assert payload["branch"] == PIN
        assert payload["ref"] == PIN
    assert listed["count"] == 1
    assert "Overview" in read["content"]
    assert TOKEN not in listed_raw
    assert TOKEN not in read_raw


# --- secrets ---------------------------------------------------------------------------


def test_token_never_in_payloads_or_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, github: _FakeGitHub, captured_logs: pytest.LogCaptureFixture
) -> None:
    from tools import powerunits_docs_tool as docs
    from tools import powerunits_github_docs_tool as roadmap
    from tools import powerunits_repo_b_read_tool as rb

    monkeypatch.setenv("HERMES_POWERUNITS_REPO_B_READ_ENABLED", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "auto")
    _write_doc_keys(tmp_path, monkeypatch)
    _write_bundle(tmp_path, monkeypatch)
    github.routes["/contents/docs/roadmap?ref="] = [
        {"name": "overview.md", "type": "file", "path": "docs/roadmap/overview.md"}
    ]
    github.routes["/contents/docs/roadmap/overview.md?ref="] = b"# Overview\n"
    github.routes["/contents/docs/implementation_state.md"] = b"# body\n"

    outputs = [
        docs.read_powerunits_doc(action="read", key="implementation_state.md"),
        docs.read_powerunits_doc(action="list_keys"),
        rb.read_powerunits_repo_b_allowlisted("list_repo_b_keys"),
        rb.read_powerunits_repo_b_allowlisted("read_repo_b_key", key="implementation_state"),
        roadmap.list_powerunits_roadmap_dir(alias="powerunits_roadmap"),
        roadmap.read_powerunits_roadmap_file("overview.md", alias="powerunits_roadmap"),
    ]
    github.routes.clear()
    github.routes["/contents/"] = URLError("offline")
    outputs.append(docs.read_powerunits_doc(action="read", key="implementation_state.md"))

    for raw in outputs:
        assert TOKEN not in raw
        assert PROVENANCE_KEYS <= set(json.loads(raw))
    log_text = captured_logs.text
    assert f"read_sha={PIN}" in log_text
    assert "read_source=github" in log_text
    assert "read_source=bundle" in log_text
    assert TOKEN not in log_text


# --- bundler -----------------------------------------------------------------------------


def _load_bundler():
    spec = importlib.util.spec_from_file_location(
        "bundle_powerunits_docs_under_test", REPO_ROOT / "scripts" / "bundle_powerunits_docs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bundler_default_ref_is_approved_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG", raising=False)
    assert _load_bundler()._approved_ref() == PIN


@pytest.mark.parametrize("bad_ref", ["starting_the_seven_phases", "4c489d5", PIN.upper()])
def test_bundler_rejects_non_immutable_ref_before_git(
    bad_ref: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load_bundler()

    def _no_git(*_a: object, **_k: object) -> None:
        raise AssertionError("git must not run for a rejected ref")

    monkeypatch.setattr(mod, "_git", _no_git)
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        ["bundle", "--source-root", str(tmp_path), "--ref", bad_ref, "--out-dir", str(out_dir)],
    )
    assert mod.main() == 2
    assert not out_dir.exists()
