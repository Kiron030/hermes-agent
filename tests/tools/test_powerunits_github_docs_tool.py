import json
from pathlib import Path

import pytest


@pytest.fixture
def allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "allowlist.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "surfaces": [
                    {
                        "alias": "powerunits_roadmap",
                        "repo": "Kiron030/Powerunits.io",
                        "branch": "starting_the_seven_phases",
                        "root_prefix": "docs/roadmap",
                        "allowed_extensions": [".md", ".txt"],
                        "enabled": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    from tools import powerunits_github_docs_tool as m

    monkeypatch.setattr(m, "_ALLOWLIST_PATH", p)
    return p


def test_check_requires_token(monkeypatch: pytest.MonkeyPatch, allowlist: Path) -> None:
    from tools import powerunits_github_docs_tool as m

    monkeypatch.delenv("POWERUNITS_GITHUB_TOKEN_READ", raising=False)
    monkeypatch.delenv("POWERUNITS_GITHUB_DOCS_TOKEN", raising=False)
    assert m.check_powerunits_github_docs_requirements() is False


def test_list_and_read_happy_path(monkeypatch: pytest.MonkeyPatch, allowlist: Path) -> None:
    from tools import powerunits_github_docs_tool as m

    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "t")

    def fake_json(url: str, token: str):
        assert "docs/roadmap" in url
        return [
            {"name": "phase1", "type": "dir", "path": "docs/roadmap/phase1"},
            {"name": "overview.md", "type": "file", "path": "docs/roadmap/overview.md"},
        ]

    monkeypatch.setattr(m, "_github_json_request", fake_json)
    out = json.loads(m.list_powerunits_roadmap_dir(alias="powerunits_roadmap"))
    assert out["count"] == 2
    assert out["entries"][0]["type"] == "dir"
    assert out["alias"] == "powerunits_roadmap"

    monkeypatch.setattr(m, "_github_raw_request", lambda url, token: "# Title\n\nBody")
    rout = json.loads(m.read_powerunits_roadmap_file("overview.md", alias="powerunits_roadmap"))
    assert rout["read_only"] is True
    assert "Title" in rout["content"]


def test_reject_escape_and_extension(monkeypatch: pytest.MonkeyPatch, allowlist: Path) -> None:
    from tools import powerunits_github_docs_tool as m

    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "t")
    o1 = json.loads(m.list_powerunits_roadmap_dir("../x", alias="powerunits_roadmap"))
    assert o1.get("error_code") == "invalid_subpath"

    o2 = json.loads(m.read_powerunits_roadmap_file("../secret.md", alias="powerunits_roadmap"))
    assert o2.get("error_code") == "invalid_name"

    o3 = json.loads(m.read_powerunits_roadmap_file("notes.json", alias="powerunits_roadmap"))
    assert o3.get("error_code") == "invalid_name"

    o4 = json.loads(m.read_powerunits_roadmap_file("overview.md", alias="unknown"))
    assert o4.get("error_code") == "invalid_alias"


def test_first_safe_includes_github_docs(monkeypatch: pytest.MonkeyPatch, allowlist: Path) -> None:
    monkeypatch.setenv("HERMES_POWERUNITS_RUNTIME_POLICY", "first_safe_v1")
    monkeypatch.setenv("POWERUNITS_GITHUB_TOKEN_READ", "t")
    from model_tools import get_tool_definitions

    defs = get_tool_definitions(["memory", "powerunits_github_docs"], quiet_mode=True)
    names = {d["function"]["name"] for d in defs}
    assert "list_powerunits_roadmap_dir" in names
    assert "read_powerunits_roadmap_file" in names


def test_legacy_token_still_works(monkeypatch: pytest.MonkeyPatch, allowlist: Path) -> None:
    from tools import powerunits_github_docs_tool as m

    monkeypatch.delenv("POWERUNITS_GITHUB_TOKEN_READ", raising=False)
    monkeypatch.setenv("POWERUNITS_GITHUB_DOCS_TOKEN", "legacy")
    assert m.check_powerunits_github_docs_requirements() is True
