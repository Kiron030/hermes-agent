"""Deterministic tests for the R5 container launcher and mount contract."""

from __future__ import annotations

import json

from r5_developer_hermes.container.contract import (
    BIND_MOUNTS,
    CONTAINER_HERMES_HOME,
    DEVELOPER_IMAGE,
    FORBIDDEN_HOST_SOURCES,
    HERMES_HOME_VOLUME,
    PINNED_DIGEST,
    PINNED_IMAGE,
    REPO_A_CONTAINER,
    REPO_B_CONTAINER,
    docker_run_argv,
    is_forbidden_host_source,
)
from r5_developer_hermes.harness import (
    REPO_ROOT,
    isolation_boundary_status,
    load_pin,
)


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"


def test_pin_declares_container_as_primary_boundary() -> None:
    pin = load_pin()
    assert pin["isolation_boundary"] == "CONTAINER"
    assert pin["isolation_boundary_fallback"] == "DEDICATED_OS_PRINCIPAL"
    assert pin["isolation_boundary_rejected"] == "PROCESS_CONSTRUCTED_ENV"
    assert pin["workspace_acl_script_role"] == "FALLBACK_ONLY"
    assert pin["upstream_image_ref"] == PINNED_IMAGE
    assert "latest" not in pin["upstream_image_ref"]


def test_bind_mounts_are_exactly_the_two_dedicated_repos() -> None:
    dests = [dst for _src, dst in BIND_MOUNTS]
    sources = [src for src, _dst in BIND_MOUNTS]
    assert dests == [REPO_A_CONTAINER, REPO_B_CONTAINER]
    assert sources == [
        r"W:\hermes-dev\workspace\hermes-agent",
        r"W:\hermes-dev\workspace\EU-PP-Database",
    ]
    assert len(BIND_MOUNTS) == 2


def test_forbidden_host_sources_are_not_approved_binds() -> None:
    approved = {src.lower() for src, _dst in BIND_MOUNTS}
    for source in FORBIDDEN_HOST_SOURCES:
        assert source.lower().rstrip("\\") not in {item.rstrip("\\") for item in approved}
        if source in {r"W:\\", r"C:\\", r"D:\\"}:
            assert is_forbidden_host_source(source)


def test_approved_repo_binds_are_not_classified_forbidden() -> None:
    for source, _dst in BIND_MOUNTS:
        assert is_forbidden_host_source(source) is False


def test_docker_run_argv_is_narrow_and_unprivileged() -> None:
    argv = docker_run_argv()
    joined = " ".join(argv)
    assert argv[:3] == ["docker", "run", "--detach"]
    assert "--privileged=false" in argv
    assert "--tmpfs" not in argv
    assert f"type=volume,src={HERMES_HOME_VOLUME},dst={CONTAINER_HERMES_HOME}" in argv
    assert "--network" in argv and "bridge" in argv
    assert "host" not in argv[argv.index("--network") + 1]
    assert "--pid" not in argv
    assert "--env-file" not in argv
    assert "/var/run/docker.sock" not in joined
    assert r"\\.\pipe\docker_engine" not in joined
    assert "--entrypoint" in argv
    assert argv[argv.index("--entrypoint") + 1] == "/opt/r5-developer/entrypoint.sh"
    assert DEVELOPER_IMAGE in argv
    assert PINNED_IMAGE not in argv  # derived image; pin lives in Dockerfile FROM
    assert argv.count("--mount") == 3
    assert f"type=bind,src={BIND_MOUNTS[0][0]},dst={REPO_A_CONTAINER}" in argv
    assert f"type=bind,src={BIND_MOUNTS[1][0]},dst={REPO_B_CONTAINER}" in argv
    assert any(item == f"HERMES_HOME={CONTAINER_HERMES_HOME}" or item.endswith(
        f"HERMES_HOME={CONTAINER_HERMES_HOME}"
    ) for item in argv)
    assert "C:\\Users" not in joined
    assert "W:\\Workbench" not in joined
    assert "W:\\dataset" not in joined


def test_canonical_launch_contract_is_docker_run_argv() -> None:
    text = (CONTAINER_DIR / "compose.yaml").read_text(encoding="utf-8")
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "NON-AUTHORITATIVE EXAMPLE ONLY" in text
    assert "docker_run_argv()" in text
    assert PINNED_IMAGE in dockerfile
    assert PINNED_DIGEST in dockerfile
    argv = docker_run_argv()
    assert argv[:3] == ["docker", "run", "--detach"]
    assert DEVELOPER_IMAGE in argv
    assert "--privileged=false" in argv
    assert "pid: host" not in text
    assert "/init" not in text
    joined = " ".join(argv)
    assert "/var/run/docker.sock" not in joined
    assert "docker_engine" not in joined
    assert "C:\\Users" not in joined
    assert "W:\\Workbench" not in joined
    assert "W:\\dataset" not in joined


def test_container_files_add_no_hermes_core() -> None:
    names = {path.name for path in CONTAINER_DIR.iterdir()}
    assert (CONTAINER_DIR / "launch.py").is_file()
    assert (CONTAINER_DIR / "isolation_probe.py").is_file()
    assert (CONTAINER_DIR / "compose.yaml").is_file()
    assert (CONTAINER_DIR / "Dockerfile").is_file()
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert f"FROM {PINNED_IMAGE}" in dockerfile


def test_isolation_boundary_claims_container_only_on_proof(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("HERMES_R5_PROOF_ROOT", str(tmp_path / "proof"))
    status = isolation_boundary_status()
    assert status["ISOLATION_BOUNDARY"] == "PROCESS_CONSTRUCTED_ENV"
    assert status["container_used"] is False
    assert status["workspace_acl_script_role"] == "FALLBACK_ONLY"

    artifacts = tmp_path / "proof" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "container_boundary.json").write_text(
        json.dumps({"ISOLATION_BOUNDARY": "CONTAINER", "ISOLATION_ACCEPTANCE": "FAIL"}),
        encoding="utf-8",
    )
    assert isolation_boundary_status()["BOUNDARY_SUFFICIENT"] == "NO"

    (artifacts / "container_boundary.json").write_text(
        json.dumps({"ISOLATION_BOUNDARY": "CONTAINER", "ISOLATION_ACCEPTANCE": "PASS"}),
        encoding="utf-8",
    )
    status = isolation_boundary_status()
    assert status["ISOLATION_BOUNDARY"] == "CONTAINER"
    assert status["BOUNDARY_SUFFICIENT"] == "YES"
    assert status["container_used"] is True
