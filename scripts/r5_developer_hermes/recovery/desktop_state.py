"""Official pinned Desktop source metadata. The built EXE is not truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from r5_developer_hermes.recovery.contract import (
    DESKTOP_EXPECTED_PACKAGING_PATH,
    DESKTOP_OFFICIAL_SOURCE,
    DESKTOP_PACK_ARTIFACT_RELATIVE,
    DESKTOP_SOURCE_OF_TRUTH,
)


def inspect_desktop_source(
    root: Path | None = None,
    *,
    expected_sha: str | None = None,
    expected_release: str | None = None,
) -> dict[str, Any]:
    source = Path(root) if root is not None else DESKTOP_OFFICIAL_SOURCE
    package = source / "apps" / "desktop" / "package.json"
    record: dict[str, Any] = {
        "official_upstream_source_pin": str(source),
        "expected_packaging_path": DESKTOP_EXPECTED_PACKAGING_PATH,
        "source_of_truth": DESKTOP_SOURCE_OF_TRUTH,
        "built_exe_is_source_of_truth": "NO",
        "source_present": source.is_dir(),
        "package_json_present": package.is_file(),
        "package_name": None,
        "package_version": None,
        "git_head": None,
        "pin_sha_match": None,
        "exe_present_informational": False,
        "status": "MISSING",
    }
    exe = source / DESKTOP_PACK_ARTIFACT_RELATIVE
    record["exe_present_informational"] = exe.is_file()
    if not source.is_dir():
        return record
    if package.is_file():
        try:
            payload = json.loads(package.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            record["package_name"] = payload.get("name")
            record["package_version"] = payload.get("version")
    git_head = source / ".git"
    head_file = source / ".git" / "HEAD"
    if head_file.is_file():
        text = head_file.read_text(encoding="utf-8").strip()
        if text.startswith("ref:"):
            ref = text.split(" ", 1)[1].strip()
            ref_path = source / ".git" / ref
            if ref_path.is_file():
                record["git_head"] = ref_path.read_text(encoding="utf-8").strip()
        else:
            record["git_head"] = text
    elif git_head.is_file():
        # detached worktree gitdir file — record presence only
        record["git_head"] = "GITDIR_FILE"
    if expected_sha and record["git_head"] and record["git_head"] != "GITDIR_FILE":
        record["pin_sha_match"] = record["git_head"] == expected_sha
    if expected_release and record["package_version"]:
        record["release_hint"] = expected_release
    if record["package_json_present"]:
        record["status"] = "PRESENT"
        if record["pin_sha_match"] is False:
            record["status"] = "WRONG_PIN"
    return record
