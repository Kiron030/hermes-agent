"""Deterministic proofs for Developer Hermes recovery manifest + audit."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from r5_developer_hermes.container.contract import (
    IMAGE_CONTRACT_VERSION,
    PINNED_DIGEST,
    RUNTIME_GID,
    RUNTIME_UID,
)
from r5_developer_hermes.harness import PIN_PATH, load_pin
from r5_developer_hermes.recovery.audit import (
    evaluate_readiness,
    format_human_report,
    run_audit,
)
from r5_developer_hermes.recovery.contract import (
    DEVELOPER_SECRET_SLOTS,
    HERMES_HOME_CLASS,
    HERMES_HOME_VOLUME,
    OFF_DEVICE_ENCRYPTED_BACKUP,
    PRODUCTION_SECRET_PATHS_EXCLUDED,
    READINESS_BLOCKED,
    READINESS_BLOCKED_LOCAL_WORK,
    READINESS_READY,
    RECOVERY_SCHEMA_VERSION,
    REQUIRED_HOST_PATHS,
    SCHEMA_PATH,
    TEMPLATE_PATH,
)
from r5_developer_hermes.recovery.desktop_state import inspect_desktop_source
from r5_developer_hermes.recovery.git_state import GitSnapshot, classify_local_work, inspect_repo_a
from r5_developer_hermes.recovery.manifest import (
    build_manifest,
    canonicalize,
    extract_hermes_pins,
    load_schema,
    load_template,
    strip_volatile,
)
from r5_developer_hermes.recovery.secrets import (
    assert_no_secret_leaks,
    find_secret_shaped_leaks,
    inspect_developer_secret_slots,
    production_paths_are_excluded,
    sanitize_git_remote,
)
from r5_developer_hermes.recovery.staging import file_sha256, verify_staging_hashes


PIN = load_pin()
FIXED_NOW = datetime(2026, 8, 26, 15, 0, 0, tzinfo=timezone.utc)

CANONICAL_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CANONICAL_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _write_staging(tmp: Path, *, extra_identity: str = "covered-local-sha") -> Path:
    root = tmp / "recovery-0b"
    (root / "bundles").mkdir(parents=True, exist_ok=True)
    inventory = root / "INVENTORY.txt"
    bundle = root / "bundles" / "repo-a-workbench-local-only.bundle"
    bundle.write_bytes(b"git-bundle-placeholder")
    inventory.write_text(
        "RECOVERY_0B_LOCAL_GIT_SAFETY\n"
        f"unique_commits={extra_identity} deadbeefdeadbeef\n"
        "source=W:\\Workbench\\hermes-agent\n"
        "refs=r2-standalone-powerunits-plugin@077187a5d2\n"
        "secrets_included=NO\n",
        encoding="utf-8",
    )
    lines = []
    for relative in ("INVENTORY.txt", "bundles/repo-a-workbench-local-only.bundle"):
        digest = file_sha256(root / relative.replace("/", "\\") if False else root / Path(*relative.split("/")))
        lines.append(f"{digest}  {relative.replace('/', chr(92))}")
    (root / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _git_runner(*answer_maps: dict[tuple[str, ...], str], by_cwd: dict[str, dict[tuple[str, ...], str]] | None = None) -> object:
    def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        answers: dict[tuple[str, ...], str] = {}
        for mapping in answer_maps:
            answers.update(mapping)
        if by_cwd:
            answers.update(by_cwd.get(Path(cwd).name, {}))
        key = tuple(args)
        if key in answers:
            return subprocess.CompletedProcess(["git", *args], 0, answers[key], "")
        for prefix, value in answers.items():
            if args[: len(prefix)] == list(prefix):
                return subprocess.CompletedProcess(["git", *args], 0, value, "")
        return subprocess.CompletedProcess(["git", *args], 1, "", "missing")

    return run


def _clean_git_answers(canonical_sha: str, branch: str = "powerunits-internal-setup") -> dict[tuple[str, ...], str]:
    return {
        ("remote", "get-url", "origin"): "https://github.com/Kiron030/hermes-agent.git",
        ("rev-parse", "--abbrev-ref", "HEAD"): branch,
        ("rev-parse", "HEAD"): canonical_sha,
        ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): f"origin/{branch}",
        ("status", "--porcelain"): "",
        ("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"): "0\t0",
        ("stash", "list", "--format=%gs"): "",
        ("for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads"): f"{branch} {canonical_sha}",
        ("branch", "-r", "--contains", canonical_sha): f"  origin/{branch}",
        ("ls-remote", "--heads", "origin", branch): f"{canonical_sha}\trefs/heads/{branch}",
        ("rev-parse", f"origin/{branch}"): canonical_sha,
        ("rev-list", "--all", "--not", "--remotes"): "",
    }


def _docker_runner() -> object:
    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["docker", *args], 1, "", "unused")

    return run


def _present_slots(tmp: Path) -> Path:
    creds = tmp / "credentials"
    creds.mkdir(exist_ok=True)
    for name in (
        "developer-hermes-model.env",
        "developer-hermes-desktop.env",
        "developer-hermes-egress.token",
    ):
        (creds / name).write_text("PLACEHOLDER_NOT_A_SECRET\n", encoding="utf-8")
    return creds


def _desktop_source(tmp: Path) -> Path:
    root = tmp / "desktop-official"
    pkg = root / "apps" / "desktop"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text(
        json.dumps({"name": "hermes-desktop", "version": "0.20.5"}),
        encoding="utf-8",
    )
    git = root / ".git"
    git.mkdir(exist_ok=True)
    (git / "HEAD").write_text(PIN["upstream_release_sha"] + "\n", encoding="utf-8")
    return root


def _base_audit(tmp: Path, **overrides):
    staging = _write_staging(tmp)
    creds = _present_slots(tmp)
    desktop = _desktop_source(tmp)
    kwargs = {
        "repo_a_root": tmp / "repo-a",
        "repo_b": tmp / "repo-b",
        "staging_root": staging,
        "credentials_dir": creds,
        "desktop_root": desktop,
        "write_live_manifest": False,
        "now": FIXED_NOW,
        "git_runner": _git_runner(
            by_cwd={
                "repo-a": _clean_git_answers(CANONICAL_A),
                "repo-b": {
                    **_clean_git_answers(CANONICAL_B, branch="main"),
                    ("remote", "get-url", "origin"): "https://github.com/Kiron030/Powerunits.io.git",
                },
            }
        ),
        "docker_runner": _docker_runner(),
        "inspect_payload": {
            "Id": "abc",
            "Image": "sha256:image",
            "State": {"Running": True},
            "Config": {
                "Image": "r5-developer-hermes:dx-v1",
                "User": "10000:10000",
                "Env": ["HERMES_HOME=/opt/data"],
                "Labels": {
                    "io.powerunits.r5.hermes-base-digest": PINNED_DIGEST,
                    "io.powerunits.r5.contract-version": IMAGE_CONTRACT_VERSION,
                },
            },
            "HostConfig": {},
            "Mounts": [],
            "NetworkSettings": {"Networks": {}},
        },
        "volumes_present": {HERMES_HOME_VOLUME: True},
        "telegram_meta": {"exists": True, "size": 64, "uid": 10000, "gid": 10000, "mode": "600"},
        "pin": PIN,
        "skip_host_trust": True,
        "staging_index_override": {
            "inventory_text": "covered-local-sha r2-standalone-powerunits-plugin",
            "bundle_heads": ["covered-local-sha"],
            "artifact_names": ["repo-a-workbench-local-only.bundle"],
            "hash_status": "PASS",
            "checked": 2,
            "creation_timestamp": "2026-08-26T14:45:00Z",
        },
    }
    (tmp / "repo-a").mkdir(exist_ok=True)
    (tmp / "repo-b").mkdir(exist_ok=True)
    kwargs.update(overrides)
    return run_audit(**kwargs)


def test_schema_version_and_template_contract() -> None:
    schema = load_schema()
    template = load_template()
    assert schema["properties"]["recovery_schema_version"]["const"] == RECOVERY_SCHEMA_VERSION
    assert template["recovery_schema_version"] == RECOVERY_SCHEMA_VERSION
    assert SCHEMA_PATH.is_file()
    assert TEMPLATE_PATH.is_file()
    pins = extract_hermes_pins(PIN)
    assert pins["upstream_release"] == PIN["upstream_release"]
    assert pins["developer_image_contract_version"] == IMAGE_CONTRACT_VERSION
    assert pins["upstream_image_digest"] == PINNED_DIGEST
    assert pins["upstream_release_sha"] == PIN["upstream_release_sha"]


def test_canonical_pin_and_image_contract_extraction() -> None:
    pins = extract_hermes_pins()
    raw = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    assert pins["upstream_release"] == raw["upstream_release"]
    assert pins["upstream_project_version"] == raw["upstream_project_version"]
    assert pins["upstream_release_sha"] == raw["upstream_release_sha"]
    assert pins["upstream_image_digest"] == raw["upstream_image_digest"]
    assert pins["developer_image_contract_version"] == raw["developer_image_contract_version"]
    assert pins["developer_image_contract_version"] == IMAGE_CONTRACT_VERSION


def test_manifest_contains_no_secrets_and_excludes_production_paths() -> None:
    manifest = build_manifest(
        repo_a={"canonical_sha": CANONICAL_A},
        repo_b={"canonical_sha": CANONICAL_B},
        created_at="2026-08-26T15:00:00Z",
    )
    assert_no_secret_leaks(manifest, context="manifest")
    assert find_secret_shaped_leaks(manifest) == []
    leaked = {
        "sk-live-not-a-real-key-value",
        "ghp_notarealtokenvalue1234567890",
        "postgresql://user:hunter2@prod/db",
        "123456789:AAHnotarealtokenvalueXXXX",
        "Bearer supersecrettokenvalue",
    }
    for needle in leaked:
        assert needle.lower() not in json.dumps(manifest).lower()
    slot_paths = [slot["path"] for slot in DEVELOPER_SECRET_SLOTS]
    assert production_paths_are_excluded(REQUIRED_HOST_PATHS, slot_paths)
    for forbidden in PRODUCTION_SECRET_PATHS_EXCLUDED:
        assert forbidden not in slot_paths
        if "powerunits" in forbidden.lower() or "git-credentials" in forbidden.lower():
            assert forbidden not in REQUIRED_HOST_PATHS
    assert HERMES_HOME_VOLUME in manifest["required_named_volumes"]
    assert manifest["named_volumes"][0]["class"] == HERMES_HOME_CLASS
    assert manifest["off_device_encrypted_backup"] == OFF_DEVICE_ENCRYPTED_BACKUP
    assert manifest["runtime"]["uid"] == RUNTIME_UID
    assert manifest["runtime"]["gid"] == RUNTIME_GID


def test_secret_shaped_values_cannot_leak_into_audit_output(tmp_path: Path) -> None:
    report = _base_audit(tmp_path)
    blob = json.dumps(report)
    for needle in (
        "sk-live-not-a-real-key-value",
        "OPENAI_API_KEY=",
        "TELEGRAM_BOT_TOKEN=",
        "postgresql://",
        "ghp_",
    ):
        assert needle not in blob
    human = format_human_report(report)
    assert "sk-" not in human
    assert "TELEGRAM_BOT_TOKEN" not in human
    assert_no_secret_leaks(human, context="human")


def test_secret_slot_metadata_only_and_unexpected_fail_closed(tmp_path: Path) -> None:
    creds = _present_slots(tmp_path)
    records = inspect_developer_secret_slots(
        credentials_dir=creds,
        telegram_meta={"exists": True, "size": 12, "uid": 10000, "gid": 10000},
    )
    by_id = {item["id"]: item for item in records}
    assert by_id["developer-hermes-model"]["status"] == "PRESENT"
    assert by_id["developer-hermes-model"]["size"] == (creds / "developer-hermes-model.env").stat().st_size
    assert "PLACEHOLDER_NOT_A_SECRET" not in json.dumps(records)
    (creds / "operator-railway.env").write_text("RAILWAY_TOKEN=should-not-appear\n", encoding="utf-8")
    dirty = inspect_developer_secret_slots(credentials_dir=creds, telegram_meta={"exists": False})
    unexpected = [item for item in dirty if item["status"] == "UNEXPECTED"]
    assert unexpected
    assert "should-not-appear" not in json.dumps(dirty)
    report = _base_audit(tmp_path, credentials_dir=creds)
    assert report["backup_readiness"] == READINESS_BLOCKED
    assert "UNEXPECTED_SECRET_SLOT" in report["backup_readiness_reasons"]


def test_missing_host_secret_slot_blocks(tmp_path: Path) -> None:
    creds = tmp_path / "empty-creds"
    creds.mkdir()
    report = _base_audit(tmp_path, credentials_dir=creds)
    assert report["backup_readiness"] == READINESS_BLOCKED
    assert "MISSING_DEVELOPER_SECRET_SLOT" in report["backup_readiness_reasons"]


def test_dirty_unpushed_uncovered_git_blocks_readiness() -> None:
    snap = GitSnapshot(
        root="W:/tmp/repo",
        remote="https://github.com/Kiron030/hermes-agent.git",
        branch="feat/local",
        head="ffffffffffffffffffffffffffffffffffffffff",
        canonical_branch="powerunits-internal-setup",
        canonical_sha=CANONICAL_A,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        dirty=["scripts/new_file.py"],
        ahead=2,
        tracking="origin/feat/local",
        dirty_state="dirty",
    )
    items = classify_local_work(snap, repo="A", staging_index={"inventory_text": "", "bundle_heads": []})
    status, reasons = evaluate_readiness(
        git_items=items,
        docker_findings=[],
        pin_findings=[],
        unexpected=[],
        missing_slots=[],
        staging_status="PASS",
    )
    assert status == READINESS_BLOCKED_LOCAL_WORK
    assert READINESS_BLOCKED_LOCAL_WORK in reasons


def test_covered_git_bundle_state_accepted() -> None:
    snap = GitSnapshot(
        root="W:/tmp/repo",
        remote="https://github.com/Kiron030/hermes-agent.git",
        branch="r2-standalone-powerunits-plugin",
        head="077187a5d2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        canonical_branch="powerunits-internal-setup",
        canonical_sha=CANONICAL_A,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        local_only_branches={"r2-standalone-powerunits-plugin": "077187a5d2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
        dirty_state="clean",
    )
    items = classify_local_work(
        snap,
        repo="A",
        staging_index={
            "inventory_text": "refs=r2-standalone-powerunits-plugin@077187a5d2",
            "bundle_heads": ["077187a5d2aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
            "artifact_names": ["repo-a-workbench-local-only.bundle"],
        },
    )
    assert all(item.coverage != "UNCOVERED" for item in items)
    status, reasons = evaluate_readiness(
        git_items=items,
        docker_findings=[],
        pin_findings=[],
        unexpected=[],
        missing_slots=[],
        staging_status="PASS",
    )
    assert status == READINESS_READY
    assert reasons == []


def test_staging_hash_verification_pass_and_fail(tmp_path: Path) -> None:
    root = _write_staging(tmp_path)
    ok = verify_staging_hashes(root)
    assert ok["status"] == "PASS"
    target = root / "INVENTORY.txt"
    target.write_text(target.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    bad = verify_staging_hashes(root)
    assert bad["status"] == "FAIL"
    assert bad["mismatched"]


def test_missing_hermes_home_volume_detected(tmp_path: Path) -> None:
    report = _base_audit(tmp_path, volumes_present={HERMES_HOME_VOLUME: False})
    assert report["backup_readiness"] == READINESS_BLOCKED
    assert "MISSING_HERMES_HOME_VOLUME" in report["backup_readiness_reasons"]
    assert report["docker"]["hermes_home_volume_present"] is False


def test_wrong_runtime_uid_gid_detected(tmp_path: Path) -> None:
    payload = {
        "Id": "abc",
        "Image": "sha256:image",
        "State": {"Running": True},
        "Config": {
            "Image": "r5-developer-hermes:dx-v1",
            "User": "0:0",
            "Env": ["HERMES_HOME=/opt/data"],
            "Labels": {
                "io.powerunits.r5.hermes-base-digest": PINNED_DIGEST,
                "io.powerunits.r5.contract-version": IMAGE_CONTRACT_VERSION,
            },
        },
        "HostConfig": {},
        "Mounts": [],
        "NetworkSettings": {"Networks": {}},
    }
    report = _base_audit(tmp_path, inspect_payload=payload)
    assert report["backup_readiness"] == READINESS_BLOCKED
    assert "WRONG_RUNTIME_UID_GID" in report["backup_readiness_reasons"]


def test_stale_wrong_upstream_pin_detected(tmp_path: Path) -> None:
    stale = dict(PIN)
    stale["upstream_image_digest"] = "sha256:" + ("0" * 64)
    report = _base_audit(tmp_path, pin=stale)
    assert report["backup_readiness"] == READINESS_BLOCKED
    assert "STALE_OR_WRONG_UPSTREAM_PIN" in report["backup_readiness_reasons"]


def test_generated_manifest_deterministic_except_volatile(tmp_path: Path) -> None:
    first = _base_audit(tmp_path, now=FIXED_NOW)
    second = _base_audit(
        tmp_path,
        now=datetime(2026, 8, 26, 16, 0, 0, tzinfo=timezone.utc),
    )
    left = strip_volatile(first["manifest"])
    right = strip_volatile(second["manifest"])
    assert canonicalize(left) == canonicalize(right)
    assert first["manifest"]["created_at"] != second["manifest"]["created_at"]


def test_desktop_source_not_the_exe(tmp_path: Path) -> None:
    root = _desktop_source(tmp_path)
    exe = root / "apps" / "desktop" / "release" / "win-unpacked"
    exe.mkdir(parents=True)
    (exe / "Hermes.exe").write_bytes(b"not-source")
    record = inspect_desktop_source(root, expected_sha=PIN["upstream_release_sha"])
    assert record["built_exe_is_source_of_truth"] == "NO"
    assert record["exe_present_informational"] is True
    assert record["package_json_present"] is True
    assert record["status"] == "PRESENT"


def test_staging_stash_patches_cover_and_pgurl_stash_is_excluded() -> None:
    snap = GitSnapshot(
        root="W:/tmp/repo-b",
        remote="https://github.com/Kiron030/Powerunits.io.git",
        branch="main",
        head=CANONICAL_B,
        canonical_branch="main",
        canonical_sha=CANONICAL_B,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        stash_count=2,
        stash_subjects=[
            "On research/x: local-env-pgurl-before-merge",
            "On feature/y: wip-untracked-e2e-script",
        ],
        dirty_state="clean",
    )
    items = classify_local_work(
        snap,
        repo="B",
        staging_index={
            "inventory_text": "STASHES_LEFT_IN_PLACE\nRepo B stash@{0} path=.env.pgurl\n",
            "artifact_names": ["repo-b-stash-1.patch", "hashes.sha256"],
            "bundle_heads": [],
        },
    )
    by_subject = {item.identity: item.coverage for item in items}
    assert by_subject["On research/x: local-env-pgurl-before-merge"] == "EXCLUDED_NOT_SOURCE"
    assert by_subject["On feature/y: wip-untracked-e2e-script"] == "LOCAL_ONLY_BUT_RECOVERY_STAGED"


def test_github_reachable_is_not_ready_by_itself() -> None:
    snap = GitSnapshot(
        root="W:/tmp/repo",
        remote="https://github.com/Kiron030/hermes-agent.git",
        branch="powerunits-internal-setup",
        head=CANONICAL_A,
        canonical_branch="powerunits-internal-setup",
        canonical_sha=CANONICAL_A,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        dirty=["uncommitted.py"],
        dirty_state="dirty",
    )
    items = classify_local_work(snap, repo="A", staging_index={})
    status, _reasons = evaluate_readiness(
        git_items=items,
        docker_findings=[],
        pin_findings=[],
        unexpected=[],
        missing_slots=[],
        staging_status="PASS",
    )
    assert status != READINESS_READY


def test_git_remote_userinfo_is_stripped() -> None:
    dirty = "https://user:MyProductionPassword123@github.com/Kiron030/hermes-agent.git"
    assert sanitize_git_remote(dirty) == "https://github.com/Kiron030/hermes-agent.git"
    tokenish = "https://oauth2:abcdefghijklmnopqrstuvwxyz0123456789ABCD@github.com/org/repo.git"
    assert "abcdefghijklmnopqrstuvwxyz0123456789ABCD" not in sanitize_git_remote(tokenish)
    answers = _clean_git_answers(CANONICAL_A)
    answers[("remote", "get-url", "origin")] = dirty
    snap = inspect_repo_a(Path("."), runner=_git_runner(answers))
    assert snap.remote == "https://github.com/Kiron030/hermes-agent.git"
    assert "MyProductionPassword123" not in json.dumps(snap.to_dict())


def test_stash_subject_is_not_serialized() -> None:
    snap = GitSnapshot(
        root="W:/tmp/repo",
        remote="https://github.com/Kiron030/hermes-agent.git",
        branch="powerunits-internal-setup",
        head=CANONICAL_A,
        canonical_branch="powerunits-internal-setup",
        canonical_sha=CANONICAL_A,
        canonical_sha_source="ORIGIN_LS_REMOTE",
        stash_count=1,
        stash_subjects=["On main: wip contains nonstandardtokenvalueXYZ"],
        dirty_state="clean",
    )
    items = classify_local_work(snap, repo="A", staging_index={})
    serialized = [item.to_dict() for item in items]
    blob = json.dumps(serialized)
    assert "nonstandardtokenvalueXYZ" not in blob
    assert all(item["identity"] == "stash" for item in serialized if item["kind"] == "stash")
