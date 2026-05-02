import json
from pathlib import Path

import pytest


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from tools import powerunits_workspace_tool as m

    return m


def test_auto_create_and_list_root(ws) -> None:
    out = json.loads(ws.list_hermes_workspace())
    assert out["count"] >= 4
    names = {e["name"] for e in out["entries"] if e["type"] == "dir"}
    assert {"analysis", "notes", "drafts", "exports"}.issubset(names)


def test_save_read_roundtrip(ws) -> None:
    s = json.loads(
        ws.save_hermes_workspace_note(
            kind="notes",
            name="hello.md",
            content="# Hello\n\nworld",
            overwrite_mode="forbid",
        )
    )
    assert s["saved"] is True
    r = json.loads(ws.read_hermes_workspace_file("notes/hello.md"))
    assert "world" in r["content"]


def test_subdir_and_path_escape_blocked(ws) -> None:
    o1 = json.loads(ws.list_hermes_workspace("random"))
    assert o1.get("error_code") == "invalid_subdir"

    o2 = json.loads(ws.read_hermes_workspace_file("../secret.md"))
    assert o2.get("error_code") == "invalid_path"

    o3 = json.loads(ws.read_hermes_workspace_file("notes/../secret.md"))
    assert o3.get("error_code") == "invalid_path"


def test_only_allowed_ext_and_no_overwrite_default(ws) -> None:
    o1 = json.loads(
        ws.save_hermes_workspace_note(kind="drafts", name="x.json", content="{}", overwrite_mode="forbid")
    )
    assert o1.get("error_code") == "invalid_write_args"

    csv_save = json.loads(
        ws.save_hermes_workspace_note(
            kind="exports",
            name="coverage-inv.csv",
            content="country_code,family\nDE,x\n",
            overwrite_mode="forbid",
        )
    )
    assert csv_save.get("saved") is True

    csv_read = json.loads(ws.read_hermes_workspace_file("exports/coverage-inv.csv"))
    assert "country_code,family" in csv_read["content"]

    first = json.loads(
        ws.save_hermes_workspace_note(kind="drafts", name="x.md", content="a", overwrite_mode="forbid")
    )
    assert first["saved"] is True
    second = json.loads(
        ws.save_hermes_workspace_note(kind="drafts", name="x.md", content="b", overwrite_mode="forbid")
    )
    assert second.get("error_code") == "already_exists"
