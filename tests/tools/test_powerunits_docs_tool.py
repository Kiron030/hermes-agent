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
    return root


def test_check_requirements_true(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    assert m.check_powerunits_docs_requirements() is True


def test_list_keys(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="list_keys"))
    assert out["count"] == 1
    assert out["keys"] == ["test_doc.md"]
    assert "bundle_path" not in out
    assert out.get("bundle_version") == 2
    assert out.get("allowlist_version") == 2
    assert "bundled_docs_notice" in out
    assert out.get("generated_at") == "2026-01-01T12:00:00Z"
    assert out.get("source_repo_name") == "TestRepo"
    assert out.get("source_repo_commit")
    allowed = {
        "keys",
        "count",
        "bundle_version",
        "allowlist_version",
        "bundled_docs_notice",
        "generated_at",
        "source_repo_name",
        "source_repo_commit",
        "bundle_age_days",
        "stale_warning",
    }
    assert set(out.keys()) <= allowed
    for k in out["keys"]:
        assert "/" not in k and "\\" not in k and ".." not in k


def test_read_roundtrip(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert out["truncated"] is False
    assert "Hello" in out["content"]
    assert out["sha256_verified"] is True
    assert out.get("bundled_docs_notice")
    assert out.get("freshness_tier") == "volatile"
    assert out.get("doc_class") == "test"


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


def test_truncation(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    out = json.loads(
        m.read_powerunits_doc(action="read", key="test_doc.md", max_output_chars=10)
    )
    assert out["truncated"] is True
    assert len(out["content"]) <= 200


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
    assert listed2.get("stale_warning")


def test_integrity_failure(tiny_bundle: Path) -> None:
    from tools import powerunits_docs_tool as m

    (tiny_bundle / "test_doc.md").write_bytes(b"tampered")
    out = json.loads(m.read_powerunits_doc(action="read", key="test_doc.md"))
    assert "error" in out
    assert out.get("error_code") == "integrity_failure"
