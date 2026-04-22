"""Tests for manifest-keyed Powerunits docs reader."""

import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def tiny_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "powerunits_docs"
    root.mkdir()
    content = b"# Hello\n\nPowerunits test doc.\n"
    key = "test_doc.md"
    (root / key).write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    manifest = {
        "bundle_version": 2,
        "allowlist_version": 2,
        "generated_at": "2026-01-01T12:00:00Z",
        "source_repo_name": "TestRepo",
        "source_repo_commit": "abcdef1234567890abcdef1234567890abcdef12",
        "entries": [
            {
                "key": key,
                "source_relative": "docs/test_doc.md",
                "sha256": digest,
                "bytes": len(content),
                "doc_class": "test",
                "freshness_tier": "volatile",
                "summary": "unit test doc",
            }
        ],
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_BUNDLE", str(root))
    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_SOURCE", "bundle")
    keys = tmp_path / "doc_keys.json"
    keys.write_text(
        json.dumps(
            {
                "allowlist_version": 99,
                "source_repo_name": "TestRepo",
                "entries": [
                    {
                        "key": key,
                        "source_relative": "docs/test_doc.md",
                        "doc_class": "test",
                        "freshness_tier": "volatile",
                        "summary": "unit test doc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_POWERUNITS_DOC_KEY_ALLOWLIST", str(keys))
    return root


def test_check_requirements_true(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    assert m.check_powerunits_docs_requirements() is True


def test_list_keys(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="list_keys"))
    assert out["count"] == 1
    assert out["keys"] == ["test_doc.md"]
    assert out.get("primary_knowledge_path") == "github_allowlisted_docs"
    assert "bundled_snapshot_freshness" in out


def test_read_roundtrip(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert out["truncated"] is False
    assert "Hello" in out["content"]
    assert out["sha256_verified"] is True
    assert out.get("knowledge_actual_source") == "bundled_fallback"
    assert out.get("bundled_fallback_explicit") is True


def test_unknown_key(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="read", key="nope.md"))
    assert "error" in out
    assert out.get("error_code") == "unknown_key_not_allowlisted"


def test_invalid_key_format(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="read", key="../etc/passwd"))
    assert "error" in out
    assert out.get("error_code") == "invalid_key_format"


def test_path_like_key_rejected(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="read", key="docs/nope.md"))
    assert "error" in out
    assert out.get("error_code") == "invalid_key_format"


def test_truncation(tiny_bundle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setattr(m, "_ABS_MIN_OUT", 5)
    out = json.loads(
        m.read_powerunits_doc(action="read", key="test_doc.md", max_output_chars=10)
    )
    assert out["truncated"] is True
    assert len(out["content"]) <= 200


def test_github_primary_when_token_and_auto(
    tiny_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_DOCS_SOURCE", raising=False)
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "tok")
    from tools import powerunits_docs_tool as m
    from tools import powerunits_github_knowledge as km

    def _fake_fetch(repo: str, branch: str, api_path: str, token: str) -> str:
        assert repo == "Kiron030/Powerunits.io"
        assert branch == "starting_the_seven_phases"
        assert api_path == "docs/test_doc.md"
        assert token == "tok"
        return "# From GitHub\n"

    monkeypatch.setattr(km, "github_fetch_raw_file", _fake_fetch)
    monkeypatch.setattr(km, "github_branch_tip_sha", lambda r, b, t: "abc1234")

    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert out.get("knowledge_actual_source") == "github_primary"
    assert "From GitHub" in out["content"]
    assert out.get("github_commit_sha") == "abc1234"


def test_explicit_fallback_when_github_fails(
    tiny_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERMES_POWERUNITS_DOCS_SOURCE", raising=False)
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "tok")
    from tools import powerunits_docs_tool as m
    from tools import powerunits_github_knowledge as km

    def _raise(*_a: object, **_k: object) -> str:
        raise OSError("network")

    monkeypatch.setattr(km, "github_fetch_raw_file", _raise)

    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert out.get("knowledge_actual_source") == "bundled_fallback"
    assert out.get("bundled_fallback_explicit") is True
    assert "github_primary_failed" in str(out.get("bundled_fallback_reason", ""))
    assert "Hello" in out["content"]


def test_first_safe_tool_cap_includes_reader(
    tiny_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "file", "web", "powerunits_docs"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "read_powerunits_doc" in names
    assert "read_file" not in names


def test_first_safe_excludes_clarify_even_if_requested(
    tiny_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    from model_tools import get_tool_definitions

    defs = get_tool_definitions(
        ["memory", "clarify", "powerunits_docs"],
        quiet_mode=True,
    )
    names = {d["function"]["name"] for d in defs}
    assert "read_powerunits_doc" in names
    assert "clarify" not in names


def test_read_stale_warning_old_bundle(
    tiny_bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import powerunits_docs_tool as m

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_STALE_DAYS_VOLATILE", "1")
    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_STALE_WARNING_DAYS", "1")
    man = json.loads((tiny_bundle / "MANIFEST.json").read_text(encoding="utf-8"))
    man["generated_at"] = "2000-01-01T00:00:00Z"
    (tiny_bundle / "MANIFEST.json").write_text(json.dumps(man), encoding="utf-8")

    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert out.get("stale_warning")
    assert "freshness_tier=volatile" in out["stale_warning"]

    monkeypatch.setenv("HERMES_POWERUNITS_DOCS_STALE_WARNING_DAYS", "1")
    listed2 = json.loads(m.read_powerunits_doc(action="list_keys"))
    assert listed2.get("bundled_snapshot_freshness", {}).get("stale_warning")


def test_integrity_failure(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    (tiny_bundle / "test_doc.md").write_bytes(b"tampered")
    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert "error" in out
    assert out.get("error_code") == "integrity_failure"
