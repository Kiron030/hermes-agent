"""Deterministic Developer-Hermes image identity and convergence policy.

Live runtime claims must refer to the actual running image:

  CHECKED_IN_RUNTIME_CONTRACT
  == BUILT_IMAGE_IDENTITY
  == RUNNING_CONTAINER_IMAGE_IDENTITY

The fingerprint is computed from the minimum material image-input set.
It excludes credentials, host secrets, timestamps, machine-specific
artifacts, and Docker image IDs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


CONTAINER_DIR = Path(__file__).resolve().parent

IMAGE_INPUT_SCHEMA = "r5-developer-image-inputs-v1"
IMAGE_CONTRACT_VERSION = "r5-dx-image-v1"

LABEL_INPUT_SHA256 = "io.powerunits.r5.input-sha256"
LABEL_HERMES_BASE_DIGEST = "io.powerunits.r5.hermes-base-digest"
LABEL_CONTRACT_VERSION = "io.powerunits.r5.contract-version"
LABEL_SOURCE_GIT_SHA = "io.powerunits.r5.source-git-sha"

REQUIRED_IMAGE_LABELS: tuple[str, ...] = (
    LABEL_INPUT_SHA256,
    LABEL_HERMES_BASE_DIGEST,
    LABEL_CONTRACT_VERSION,
)

# Minimum R5-controlled inputs that materially affect r5-developer-hermes:dx-v1.
# Paths are relative to the container build directory. Do not add unrelated
# repository files, credentials, or machine-specific artifacts.
IMAGE_INPUT_RELATIVE_PATHS: tuple[str, ...] = (
    "Dockerfile",
    ".dockerignore",
    "entrypoint.sh",
    "seed_home.py",
    "telegram_ops.py",
    "profiles/telegram-ops/config.yaml",
    "profiles/telegram-ops/SOUL.md",
    "profiles/telegram-ops/env.template",
    "profiles/telegram-ops/plugins/telegram-ops-write-approval/plugin.yaml",
    "profiles/telegram-ops/plugins/telegram-ops-write-approval/__init__.py",
    "skills/r5-dev-skill/SKILL.md",
    "image_inputs/build_contract.json",
)

ConvergenceAction = Literal["BUILD", "REBUILD", "RECREATE", "REUSE"]


def image_input_paths(root: Path | None = None) -> tuple[Path, ...]:
    base = Path(root) if root is not None else CONTAINER_DIR
    return tuple(base / relative for relative in IMAGE_INPUT_RELATIVE_PATHS)


def load_build_contract(root: Path | None = None) -> dict[str, str]:
    path = (Path(root) if root is not None else CONTAINER_DIR) / "image_inputs" / "build_contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("build_contract.json must be a JSON object")
    required = (
        "contract_version",
        "upstream_image_digest",
        "typescript_pin",
        "pytest_pin",
        "developer_image",
    )
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise RuntimeError(f"build_contract.json missing keys: {missing}")
    return {key: str(payload[key]) for key in payload if not str(key).startswith("_")}


def _normalize_text_bytes(data: bytes) -> bytes:
    text = data.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256(_normalize_text_bytes(path.read_bytes())).hexdigest()
    return f"sha256:{digest}"


def compute_developer_image_input_fingerprint(root: Path | None = None) -> str:
    """SHA-256 over the canonical material image-input set.

    Line endings are normalized to LF so Windows/Linux checkouts agree.
    """
    base = Path(root) if root is not None else CONTAINER_DIR
    lines = [IMAGE_INPUT_SCHEMA]
    for relative in IMAGE_INPUT_RELATIVE_PATHS:
        path = base / relative
        if not path.is_file():
            raise RuntimeError(f"missing Developer-Hermes image input: {relative}")
        lines.append(f"{relative}\t{_file_digest(path)}")
    payload = "\n".join(lines) + "\n"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def expected_image_labels(
    *,
    root: Path | None = None,
    source_git_sha: str = "",
) -> dict[str, str]:
    contract = load_build_contract(root)
    labels = {
        LABEL_INPUT_SHA256: compute_developer_image_input_fingerprint(root),
        LABEL_HERMES_BASE_DIGEST: contract["upstream_image_digest"],
        LABEL_CONTRACT_VERSION: contract["contract_version"],
    }
    if source_git_sha:
        labels[LABEL_SOURCE_GIT_SHA] = source_git_sha
    return labels


def labels_from_inspect(payload: dict[str, Any] | None) -> dict[str, str]:
    if not payload:
        return {}
    config = payload.get("Config") or payload.get("config") or {}
    raw = config.get("Labels") or payload.get("Labels") or payload.get("labels") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}


def actual_image_fingerprint(labels: dict[str, str] | None) -> str | None:
    if not labels:
        return None
    value = labels.get(LABEL_INPUT_SHA256)
    return value or None


def required_labels_present(labels: dict[str, str] | None) -> bool:
    if not labels:
        return False
    return all(bool(labels.get(name)) for name in REQUIRED_IMAGE_LABELS)


def normalize_image_id(value: str | None) -> str:
    if not value:
        return ""
    return value.strip()


@dataclass(frozen=True)
class ConvergenceObservation:
    expected_fingerprint: str
    actual_image_fingerprint: str | None
    image_present: bool
    labels_present: bool
    current_tag_image_id: str | None
    running_container_image_id: str | None
    container_present: bool
    container_running: bool = False
    dx_ready: bool = True
    # False when the running container was created under a different egress
    # policy, contract or mode than the checked-in one.
    egress_converged: bool = True
    egress_reason: str = ""


@dataclass(frozen=True)
class ConvergenceDecision:
    action: ConvergenceAction
    reason: str
    expected_fingerprint: str
    actual_image_fingerprint: str | None
    current_tag_image_id: str | None
    running_container_image_id: str | None
    trusted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "EXPECTED_IMAGE_FINGERPRINT": self.expected_fingerprint,
            "ACTUAL_IMAGE_FINGERPRINT": self.actual_image_fingerprint,
            "CURRENT_TAG_IMAGE_ID": self.current_tag_image_id,
            "RUNNING_CONTAINER_IMAGE_ID": self.running_container_image_id,
            "trusted": self.trusted,
        }


def decide_convergence(observation: ConvergenceObservation) -> ConvergenceDecision:
    """Fail closed: missing labels or identity disagreement are never trusted."""
    expected = observation.expected_fingerprint
    actual = observation.actual_image_fingerprint
    tag_id = normalize_image_id(observation.current_tag_image_id)
    running_id = normalize_image_id(observation.running_container_image_id)
    trusted = False

    if not observation.image_present:
        return ConvergenceDecision(
            action="BUILD",
            reason="IMAGE_MISSING",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id or None,
            running_container_image_id=running_id or None,
            trusted=False,
        )
    if not observation.labels_present or not actual:
        return ConvergenceDecision(
            action="REBUILD",
            reason="MISSING_LABEL_FAIL_CLOSED",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id or None,
            running_container_image_id=running_id or None,
            trusted=False,
        )
    if actual != expected:
        return ConvergenceDecision(
            action="REBUILD",
            reason="FINGERPRINT_MISMATCH",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id or None,
            running_container_image_id=running_id or None,
            trusted=False,
        )
    if not tag_id:
        return ConvergenceDecision(
            action="REBUILD",
            reason="TAG_IMAGE_ID_MISSING",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=None,
            running_container_image_id=running_id or None,
            trusted=False,
        )
    if not observation.container_present:
        return ConvergenceDecision(
            action="RECREATE",
            reason="CONTAINER_MISSING",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id,
            running_container_image_id=None,
            trusted=True,
        )
    if not running_id:
        return ConvergenceDecision(
            action="RECREATE",
            reason="RUNNING_IMAGE_ID_MISSING",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id,
            running_container_image_id=None,
            trusted=False,
        )
    if running_id != tag_id:
        return ConvergenceDecision(
            action="RECREATE",
            reason="STALE_CONTAINER_IMAGE_ID",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id,
            running_container_image_id=running_id,
            trusted=False,
        )
    if not observation.egress_converged:
        return ConvergenceDecision(
            action="RECREATE",
            reason=observation.egress_reason or "EGRESS_CONTRACT_MISMATCH",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id,
            running_container_image_id=running_id,
            trusted=False,
        )
    if not observation.dx_ready:
        return ConvergenceDecision(
            action="RECREATE",
            reason="CONTAINER_NOT_DX_READY",
            expected_fingerprint=expected,
            actual_image_fingerprint=actual,
            current_tag_image_id=tag_id,
            running_container_image_id=running_id,
            trusted=False,
        )
    trusted = True
    return ConvergenceDecision(
        action="REUSE",
        reason="IDENTITIES_MATCH",
        expected_fingerprint=expected,
        actual_image_fingerprint=actual,
        current_tag_image_id=tag_id,
        running_container_image_id=running_id,
        trusted=trusted,
    )


def parse_typescript_version(raw: str) -> str:
    text = (raw or "").strip()
    if text.lower().startswith("version "):
        return text.split(None, 1)[1].strip()
    return text.split()[-1] if text else ""


def parse_pytest_version(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    # `pytest --version` → "pytest 9.1.1" or just "9.1.1"
    parts = text.replace(",", " ").split()
    for part in parts:
        if part[0].isdigit():
            return part
    return text


def identities_converged(
    *,
    expected_fingerprint: str,
    running_fingerprint: str | None,
    current_tag_image_id: str | None,
    running_container_image_id: str | None,
    labels: dict[str, str] | None,
) -> bool:
    if not required_labels_present(labels):
        return False
    if not expected_fingerprint or running_fingerprint != expected_fingerprint:
        return False
    tag_id = normalize_image_id(current_tag_image_id)
    running_id = normalize_image_id(running_container_image_id)
    return bool(tag_id) and tag_id == running_id
