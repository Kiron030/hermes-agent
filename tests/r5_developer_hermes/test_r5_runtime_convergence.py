"""Focused proofs for Developer-Hermes source/image/container convergence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from r5_developer_hermes.container.contract import (
    IMAGE_CONTRACT_VERSION,
    IMAGE_LABEL_CONTRACT_VERSION,
    IMAGE_LABEL_HERMES_BASE_DIGEST,
    IMAGE_LABEL_INPUT_SHA256,
    PINNED_DIGEST,
    PYTEST_PIN,
    TYPESCRIPT_PIN,
)
from r5_developer_hermes.container.image_identity import (
    IMAGE_INPUT_RELATIVE_PATHS,
    ConvergenceObservation,
    compute_developer_image_input_fingerprint,
    decide_convergence,
    expected_image_labels,
    identities_converged,
    load_build_contract,
    parse_pytest_version,
    parse_typescript_version,
    required_labels_present,
)
from r5_developer_hermes.harness import REPO_ROOT


CONTAINER_DIR = REPO_ROOT / "scripts" / "r5_developer_hermes" / "container"


def _copy_inputs(tmp_path: Path) -> Path:
    dest = tmp_path / "container"
    for relative in IMAGE_INPUT_RELATIVE_PATHS:
        source = CONTAINER_DIR / relative
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return dest


def test_image_input_set_is_the_minimum_material_build_context() -> None:
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (CONTAINER_DIR / ".dockerignore").read_text(encoding="utf-8")
    assert IMAGE_INPUT_RELATIVE_PATHS == (
        "Dockerfile",
        ".dockerignore",
        "entrypoint.sh",
        "seed_home.py",
        "telegram_ops.py",
        "profiles/telegram-ops/config.yaml",
        "profiles/telegram-ops/SOUL.md",
        "profiles/telegram-ops/env.template",
        "skills/r5-dev-skill/SKILL.md",
        "image_inputs/build_contract.json",
    )
    for relative in IMAGE_INPUT_RELATIVE_PATHS:
        assert (CONTAINER_DIR / relative).is_file()
        if relative in {"Dockerfile", ".dockerignore"}:
            continue
        assert relative.split("/", 1)[0] in dockerignore or relative in dockerignore
    assert "COPY entrypoint.sh" in dockerfile
    assert "COPY seed_home.py" in dockerfile
    assert "COPY telegram_ops.py" in dockerfile
    assert "COPY profiles/telegram-ops" in dockerfile
    assert "COPY skills/r5-dev-skill" in dockerfile
    assert "COPY image_inputs/build_contract.json" in dockerfile
    assert "launch.py" not in IMAGE_INPUT_RELATIVE_PATHS
    assert "compose.yaml" not in IMAGE_INPUT_RELATIVE_PATHS


def test_build_contract_pins_match_dockerfile_and_python_contract() -> None:
    contract = load_build_contract()
    pin = json.loads((REPO_ROOT / "scripts" / "r5_developer_hermes" / "pin.json").read_text(encoding="utf-8"))
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert contract["contract_version"] == IMAGE_CONTRACT_VERSION
    assert pin["developer_image_contract_version"] == IMAGE_CONTRACT_VERSION
    assert contract["upstream_image_digest"] == PINNED_DIGEST
    assert contract["typescript_pin"] == TYPESCRIPT_PIN == "7.0.2"
    assert contract["pytest_pin"] == PYTEST_PIN == "9.1.1"
    assert f"typescript@{TYPESCRIPT_PIN}" in dockerfile
    assert f"pytest=={PYTEST_PIN}" in dockerfile
    assert PINNED_DIGEST in dockerfile


def test_fingerprint_is_stable_for_identical_inputs(tmp_path: Path) -> None:
    root = _copy_inputs(tmp_path)
    first = compute_developer_image_input_fingerprint(root)
    second = compute_developer_image_input_fingerprint(root)
    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == 71


def test_fingerprint_changes_when_synthetic_build_contract_changes(tmp_path: Path) -> None:
    root = _copy_inputs(tmp_path)
    before = compute_developer_image_input_fingerprint(root)
    fixture = root / "image_inputs" / "build_contract.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["synthetic_probe"] = "stale-image-fixture"
    fixture.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    after = compute_developer_image_input_fingerprint(root)
    assert after != before
    restored = _copy_inputs(tmp_path / "restored")
    assert compute_developer_image_input_fingerprint(restored) == before


def test_image_label_contract_names_and_values() -> None:
    labels = expected_image_labels()
    assert set(labels) >= {
        IMAGE_LABEL_INPUT_SHA256,
        IMAGE_LABEL_HERMES_BASE_DIGEST,
        IMAGE_LABEL_CONTRACT_VERSION,
    }
    assert labels[IMAGE_LABEL_INPUT_SHA256] == compute_developer_image_input_fingerprint()
    assert labels[IMAGE_LABEL_HERMES_BASE_DIGEST] == PINNED_DIGEST
    assert labels[IMAGE_LABEL_CONTRACT_VERSION] == IMAGE_CONTRACT_VERSION
    dockerfile = (CONTAINER_DIR / "Dockerfile").read_text(encoding="utf-8")
    for name in (
        IMAGE_LABEL_INPUT_SHA256,
        IMAGE_LABEL_HERMES_BASE_DIGEST,
        IMAGE_LABEL_CONTRACT_VERSION,
    ):
        assert name in dockerfile
    assert required_labels_present(labels) is True
    assert required_labels_present({"io.powerunits.r5.input-sha256": "sha256:abc"}) is False


def test_current_source_image_and_container_are_ready() -> None:
    expected = compute_developer_image_input_fingerprint()
    decision = decide_convergence(
        ConvergenceObservation(
            expected_fingerprint=expected,
            actual_image_fingerprint=expected,
            image_present=True,
            labels_present=True,
            current_tag_image_id="sha256:current",
            running_container_image_id="sha256:current",
            container_present=True,
            container_running=True,
            dx_ready=True,
        )
    )
    assert decision.action == "REUSE"
    assert decision.reason == "IDENTITIES_MATCH"
    assert decision.trusted is True
    assert identities_converged(
        expected_fingerprint=expected,
        running_fingerprint=expected,
        current_tag_image_id="sha256:current",
        running_container_image_id="sha256:current",
        labels=expected_image_labels(),
    )


def test_stale_image_fingerprint_rebuilds(tmp_path: Path) -> None:
    root = _copy_inputs(tmp_path)
    expected = compute_developer_image_input_fingerprint(root)
    fixture = root / "image_inputs" / "build_contract.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["synthetic_probe"] = "stale"
    fixture.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    new_expected = compute_developer_image_input_fingerprint(root)
    decision = decide_convergence(
        ConvergenceObservation(
            expected_fingerprint=new_expected,
            actual_image_fingerprint=expected,
            image_present=True,
            labels_present=True,
            current_tag_image_id="sha256:old",
            running_container_image_id="sha256:old",
            container_present=True,
            container_running=True,
        )
    )
    assert new_expected != expected
    assert decision.action == "REBUILD"
    assert decision.reason == "FINGERPRINT_MISMATCH"
    assert decision.trusted is False


def test_same_tag_different_image_id_recreates_container() -> None:
    expected = compute_developer_image_input_fingerprint()
    decision = decide_convergence(
        ConvergenceObservation(
            expected_fingerprint=expected,
            actual_image_fingerprint=expected,
            image_present=True,
            labels_present=True,
            current_tag_image_id="sha256:new-id",
            running_container_image_id="sha256:old-id",
            container_present=True,
            container_running=True,
        )
    )
    assert decision.action == "RECREATE"
    assert decision.reason == "STALE_CONTAINER_IMAGE_ID"
    assert identities_converged(
        expected_fingerprint=expected,
        running_fingerprint=expected,
        current_tag_image_id="sha256:new-id",
        running_container_image_id="sha256:old-id",
        labels=expected_image_labels(),
    ) is False


def test_missing_label_is_not_silently_trusted() -> None:
    expected = compute_developer_image_input_fingerprint()
    decision = decide_convergence(
        ConvergenceObservation(
            expected_fingerprint=expected,
            actual_image_fingerprint=None,
            image_present=True,
            labels_present=False,
            current_tag_image_id="sha256:present",
            running_container_image_id="sha256:present",
            container_present=True,
            container_running=True,
            dx_ready=True,
        )
    )
    assert decision.action == "REBUILD"
    assert decision.reason == "MISSING_LABEL_FAIL_CLOSED"
    assert decision.trusted is False
    assert identities_converged(
        expected_fingerprint=expected,
        running_fingerprint=None,
        current_tag_image_id="sha256:present",
        running_container_image_id="sha256:present",
        labels={},
    ) is False


def test_source_unchanged_does_not_rebuild() -> None:
    expected = compute_developer_image_input_fingerprint()
    decision = decide_convergence(
        ConvergenceObservation(
            expected_fingerprint=expected,
            actual_image_fingerprint=expected,
            image_present=True,
            labels_present=True,
            current_tag_image_id="sha256:same",
            running_container_image_id="sha256:same",
            container_present=True,
            container_running=True,
        )
    )
    assert decision.action == "REUSE"
    missing = decide_convergence(
        ConvergenceObservation(
            expected_fingerprint=expected,
            actual_image_fingerprint=None,
            image_present=False,
            labels_present=False,
            current_tag_image_id=None,
            running_container_image_id=None,
            container_present=False,
        )
    )
    assert missing.action == "BUILD"


def test_launcher_converges_from_identity_not_tag_presence() -> None:
    launch = (CONTAINER_DIR / "launch.py").read_text(encoding="utf-8")
    assert "observe_convergence" in launch
    assert "decide_convergence" in launch
    assert "MISSING_LABEL_FAIL_CLOSED" not in launch or "identities_converged" in launch
    assert '["images", "-q", DEVELOPER_IMAGE]' not in launch
    assert "R5_INPUT_SHA256" in launch
    assert "RUNTIME_CONVERGED" in launch


def test_version_parsers_accept_tool_output() -> None:
    assert parse_typescript_version("Version 7.0.2") == "7.0.2"
    assert parse_pytest_version("pytest 9.1.1") == "9.1.1"
    assert parse_pytest_version("9.1.1") == "9.1.1"
