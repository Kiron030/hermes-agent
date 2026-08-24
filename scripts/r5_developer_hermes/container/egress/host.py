"""Launcher-side egress contract for Developer Hermes.

The security boundary is the Docker topology, not the proxy environment
variables. Developer Hermes attaches to an ``internal: true`` network with no
default route; the broker is the only dual-homed container. Deleting
``HTTP_PROXY`` inside the sandbox therefore removes convenience routing, not
the boundary.

This module owns three things:

* the network and container contract that produces that topology,
* the egress contract fingerprint, so a policy edit cannot silently apply to
  a running sandbox, and
* the local proxy token, so the real provider credential stays in the broker.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

EGRESS_DIR = Path(__file__).resolve().parent
POLICY_PATH = EGRESS_DIR / "egress_policy.json"
BROKER_CONTRACT_PATH = EGRESS_DIR / "broker_contract.json"
BROKER_DOCKERFILE = EGRESS_DIR / "broker.Dockerfile"
BROKER_ENTRYPOINT = EGRESS_DIR / "broker_entrypoint.py"

EGRESS_CONTRACT_SCHEMA = "r5-egress-contract-v1"

# Every R5-controlled input that materially changes where Developer Hermes may
# send data. Runtime audit logs are deliberately absent: they are evidence,
# not policy, and including them would make the contract change on every
# request.
EGRESS_INPUT_RELATIVE_PATHS: tuple[str, ...] = (
    "egress_policy.json",
    "broker_contract.json",
    "broker.Dockerfile",
    "broker_entrypoint.py",
    "host.py",
)

MODE_ENFORCED = "PRIVATE_DEVELOPER_EGRESS_ENFORCED"
MODE_OFFLINE = "OFFLINE"
EGRESS_MODES: tuple[str, ...] = (MODE_ENFORCED, MODE_OFFLINE)

BROKER_CONTAINER_NAME = "r5-egress-broker"

LABEL_EGRESS_MODE = "io.powerunits.r5.egress-mode"
LABEL_EGRESS_CONTRACT = "io.powerunits.r5.egress-contract-sha256"
LABEL_EGRESS_POLICY = "io.powerunits.r5.egress-policy-sha256"
LABEL_IRON_PROXY_VERSION = "io.powerunits.r5.iron-proxy-version"
LABEL_IRON_PROXY_SHA256 = "io.powerunits.r5.iron-proxy-sha256"
LABEL_HERMES_BASE_DIGEST = "io.powerunits.r5.hermes-base-digest"

REQUIRED_BROKER_LABELS: tuple[str, ...] = (
    LABEL_EGRESS_CONTRACT,
    LABEL_EGRESS_POLICY,
    LABEL_IRON_PROXY_VERSION,
    LABEL_IRON_PROXY_SHA256,
)

# The CA public certificate arrives through a Docker-managed volume, never a
# host bind. The bind allowlist stays exactly two repositories.
CONTAINER_CA_DIR = "/opt/r5-egress-ca"
CONTAINER_CA_FILE = f"{CONTAINER_CA_DIR}/ca.crt"

# Local, non-provider credential. Leaking it buys nothing off-box: it is only
# meaningful to this broker, which will not forward it anywhere.
EGRESS_TOKEN_FILE = Path(r"W:\hermes-dev\credentials\developer-hermes-egress.token")
TOKEN_ENV_PREFIX = "R5_EGRESS_TOKEN_"

UPSTREAM_EGRESS_COMPONENT = "iron-proxy (agent/proxy_sources/iron_proxy.py, hermes-agent 0.20.5)"
PINNED_HERMES_NATIVE_EGRESS_SUPPORT = "FULL"

# Which upstream research vendor the sandbox enters on.
#
# Upstream's keyless tier walks a five-vendor ring and, when no vendor is
# pinned, starts at a per-session random cursor. Three of those five are
# deliberately not approved, and a connection refused by the broker is not a
# throttle, so upstream's failover stops the walk instead of advancing. An
# unpinned sandbox would therefore lose research on most sessions purely by
# where the cursor landed.
#
# Pinning makes the entry vendor deterministic and equal to an approved
# processor. It is a routing decision, not a security control: the broker still
# decides what may leave, and pinning a denied vendor would simply fail closed.
# It lives here so it is covered by the egress contract fingerprint — changing
# which processor receives our queries is a reviewable change.
RESEARCH_BACKEND = "exa"
RESEARCH_TIER = "free"
RESEARCH_PATH_ORIGIN = "plugins/web/keyless_mcp.py::_KEYLESS_RING in hermes-agent 0.20.5"


def research_config_patch() -> dict[str, Any]:
    """The ``web`` config the Developer HERMES_HOME is seeded with, if unset."""
    return {
        "backend": RESEARCH_BACKEND,
        "provider_tier": {RESEARCH_BACKEND: RESEARCH_TIER},
    }


def load_broker_contract() -> dict[str, Any]:
    payload = json.loads(BROKER_CONTRACT_PATH.read_text(encoding="utf-8"))
    required = ("broker_image", "base_image_digest", "iron_proxy_version", "iron_proxy_sha256", "network")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise RuntimeError(f"broker_contract.json missing keys: {missing}")
    if "latest" in str(payload["broker_image"]).rsplit(":", 1)[-1]:
        raise RuntimeError("broker image must not use a floating tag")
    return payload


BROKER_CONTRACT = load_broker_contract()
BROKER_IMAGE = str(BROKER_CONTRACT["broker_image"])
INTERNAL_NETWORK = str(BROKER_CONTRACT["network"]["internal_network"])
INTERNAL_SUBNET = str(BROKER_CONTRACT["network"]["internal_subnet"])
BROKER_INTERNAL_IP = str(BROKER_CONTRACT["network"]["broker_internal_ip"])
EGRESS_NETWORK = str(BROKER_CONTRACT["network"]["egress_network"])
TUNNEL_PORT = int(BROKER_CONTRACT["network"]["tunnel_port"])
PLAIN_HTTP_PORT = int(BROKER_CONTRACT["network"]["plain_http_port"])
BROKER_STATE_VOLUME = str(BROKER_CONTRACT["volumes"]["broker_state"])
CA_PUBLIC_VOLUME = str(BROKER_CONTRACT["volumes"]["ca_public"])
BROKER_HOME_VOLUME = str(BROKER_CONTRACT["volumes"]["broker_home"])


def load_policy() -> dict[str, Any]:
    """Read the destination policy, failing closed on anything unreviewable."""
    if not POLICY_PATH.is_file():
        raise RuntimeError(f"EGRESS_POLICY_MISSING: {POLICY_PATH}")
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"EGRESS_POLICY_INVALID: {exc}") from exc
    if policy.get("schema") != "r5-egress-policy-v1":
        raise RuntimeError("EGRESS_POLICY_INVALID: unexpected schema")
    if policy.get("default_decision") != "DENY":
        raise RuntimeError("EGRESS_POLICY_INVALID: default_decision must be DENY")
    if not isinstance(policy.get("classes"), dict) or not policy["classes"]:
        raise RuntimeError("EGRESS_POLICY_INVALID: classes must be a non-empty object")
    return policy


def _normalized_digest(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def policy_sha256() -> str:
    return _normalized_digest(POLICY_PATH)


def egress_contract_fingerprint() -> str:
    """SHA-256 over the material egress-security inputs.

    Line endings are normalized so a Windows checkout and a Linux checkout
    agree, matching the image-input fingerprint's rule.
    """
    lines = [EGRESS_CONTRACT_SCHEMA]
    for relative in EGRESS_INPUT_RELATIVE_PATHS:
        path = EGRESS_DIR / relative
        if not path.is_file():
            raise RuntimeError(f"missing egress contract input: {relative}")
        lines.append(f"{relative}\t{_normalized_digest(path)}")
    payload = "\n".join(lines) + "\n"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approved_destinations() -> dict[str, list[str]]:
    policy = load_policy()
    return {
        name: list(entry.get("hosts") or [])
        for name, entry in policy["classes"].items()
        if entry.get("decision") == "ALLOW"
    }


def approved_host_count() -> int:
    return sum(len(hosts) for hosts in approved_destinations().values())


def mediated_env_names() -> list[str]:
    policy = load_policy()
    mediation = policy.get("credential_mediation") or {}
    return [
        str(entry["env_name"])
        for entry in mediation.get("mediated_credentials") or []
        if entry.get("env_name")
    ]


def ensure_egress_token(path: Path | None = None) -> str:
    """Read, or mint once, the sandbox-visible proxy token.

    Persisted next to the dedicated model credential, under the host-only
    secret root that is never mounted into any container. Rotation is
    deleting the file; the next launch mints a fresh one.
    """
    target = path or EGRESS_TOKEN_FILE
    if target.is_file():
        existing = target.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    token = f"r5-egress-{secrets.token_hex(16)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(token + "\n", encoding="utf-8")
    return token


def developer_egress_env(*, mode: str, token: str | None) -> dict[str, str]:
    """Environment the Developer container receives for a given egress mode.

    In ``OFFLINE`` there is nothing to configure: the container has no network
    at all, so proxy variables would only be misleading.

    In the enforced mode these variables are routing convenience. They are not
    the control — MISSION D. The CA bundle variables follow the upstream
    Docker-sandbox recipe, including its asymmetry: the Python/curl variables
    replace the system trust store while ``NODE_EXTRA_CA_CERTS`` adds to it.
    """
    if mode == MODE_OFFLINE:
        return {}
    if mode != MODE_ENFORCED:
        raise ValueError(f"unknown egress mode {mode!r}")
    tunnel = f"http://{BROKER_INTERNAL_IP}:{TUNNEL_PORT}"
    plain = f"http://{BROKER_INTERNAL_IP}:{PLAIN_HTTP_PORT}"
    env = {
        "HTTPS_PROXY": tunnel,
        "https_proxy": tunnel,
        "HTTP_PROXY": plain,
        "http_proxy": plain,
        "NO_PROXY": "127.0.0.1,localhost,::1",
        "no_proxy": "127.0.0.1,localhost,::1",
        "REQUESTS_CA_BUNDLE": CONTAINER_CA_FILE,
        "SSL_CERT_FILE": CONTAINER_CA_FILE,
        "CURL_CA_BUNDLE": CONTAINER_CA_FILE,
        "NODE_EXTRA_CA_CERTS": CONTAINER_CA_FILE,
        "GIT_SSL_CAINFO": CONTAINER_CA_FILE,
    }
    if token:
        for name in mediated_env_names():
            env[name] = token
    return env


def developer_network_args(*, mode: str) -> list[str]:
    if mode == MODE_OFFLINE:
        return ["--network", "none"]
    return ["--network", INTERNAL_NETWORK]


def developer_egress_mounts(*, mode: str) -> list[str]:
    if mode == MODE_OFFLINE:
        return []
    return [
        "--mount",
        f"type=volume,src={CA_PUBLIC_VOLUME},dst={CONTAINER_CA_DIR},readonly",
    ]


def developer_egress_labels(*, mode: str) -> dict[str, str]:
    return {
        LABEL_EGRESS_MODE: mode,
        LABEL_EGRESS_CONTRACT: egress_contract_fingerprint(),
        LABEL_EGRESS_POLICY: policy_sha256(),
    }


def broker_run_argv(*, real_model_env: dict[str, str], token: str) -> list[str]:
    """Deterministic ``docker run`` argv for the broker.

    MISSION O is enforced here by what is absent: no repository bind, no
    HERMES_HOME, no Docker socket, no host secret root, no published port.
    The broker gets two networks, its own state volume, the CA publication
    volume, and the provider credentials it mediates.
    """
    labels = {
        LABEL_EGRESS_MODE: MODE_ENFORCED,
        LABEL_EGRESS_CONTRACT: egress_contract_fingerprint(),
        LABEL_EGRESS_POLICY: policy_sha256(),
    }
    argv = [
        "docker",
        "run",
        "--detach",
        "--name",
        BROKER_CONTAINER_NAME,
        "--user",
        "0:0",
        "--privileged=false",
        "--security-opt",
        "no-new-privileges:true",
        "--restart",
        "unless-stopped",
        "--network",
        INTERNAL_NETWORK,
        "--ip",
        BROKER_INTERNAL_IP,
        "--env",
        f"R5_EGRESS_BIND_IP={BROKER_INTERNAL_IP}",
        "--env",
        f"R5_EGRESS_TUNNEL_PORT={TUNNEL_PORT}",
        "--mount",
        f"type=volume,src={BROKER_STATE_VOLUME},dst=/opt/r5-egress/state",
        "--mount",
        f"type=volume,src={CA_PUBLIC_VOLUME},dst=/opt/r5-egress/ca-pub",
        # The base image declares VOLUME /opt/data. Give it a name so the
        # broker never inherits an unnamed volume and the trust check can
        # assert that the Developer's home volume is not among its mounts.
        "--mount",
        f"type=volume,src={BROKER_HOME_VOLUME},dst=/opt/data",
    ]
    for key, value in labels.items():
        argv.extend(["--label", f"{key}={value}"])
    for name in mediated_env_names():
        argv.extend(["--env", f"{TOKEN_ENV_PREFIX}{name}={token}"])
        if name in real_model_env:
            argv.extend(["--env", f"{name}={real_model_env[name]}"])
    argv.append(BROKER_IMAGE)
    return argv


def broker_run_argv_without_secrets() -> list[str]:
    """The same argv shape with credential values replaced by their names."""
    argv = broker_run_argv(real_model_env={}, token="REDACTED")
    return [
        item if not item.startswith(f"{TOKEN_ENV_PREFIX}") else item.split("=", 1)[0] + "=REDACTED"
        for item in argv
    ]


def egress_contract_summary(*, mode: str) -> dict[str, Any]:
    """Metadata-only description of the enforced boundary, safe to persist."""
    contract = BROKER_CONTRACT
    return {
        "EGRESS_MODE": mode,
        "SELECTED_EGRESS_ARCHITECTURE": "G_HYBRID",
        "EGRESS_POLICY_FILE": "scripts/r5_developer_hermes/container/egress/egress_policy.json",
        "EGRESS_POLICY_HASH": policy_sha256(),
        "EGRESS_CONTRACT_FINGERPRINT": egress_contract_fingerprint(),
        "DEVELOPER_NETWORK": "none" if mode == MODE_OFFLINE else INTERNAL_NETWORK,
        "BROKER_NETWORKS": [INTERNAL_NETWORK, EGRESS_NETWORK],
        "DEVELOPER_EXTERNAL_NETWORK_ATTACHMENT": "NO",
        "BROKER_DUAL_HOMED": "YES",
        "BROKER_IDENTITY": {
            "image": BROKER_IMAGE,
            "base_image_digest": contract["base_image_digest"],
            "iron_proxy_version": contract["iron_proxy_version"],
            "iron_proxy_sha256": contract["iron_proxy_sha256"],
            "license": contract.get("iron_proxy_license", ""),
        },
        "UPSTREAM_EGRESS_COMPONENT": UPSTREAM_EGRESS_COMPONENT,
        "PINNED_HERMES_NATIVE_EGRESS_SUPPORT": PINNED_HERMES_NATIVE_EGRESS_SUPPORT,
        "APPROVED_DESTINATION_CLASSES": approved_destinations(),
        "MEDIATED_CREDENTIALS": mediated_env_names(),
        "MODEL_CREDENTIAL_LOCATION": "BROKER_ONLY",
        "CREDENTIAL_VALUES_RECORDED": "NO",
    }


def host_egress_token_present(path: Path | None = None) -> bool:
    target = path or EGRESS_TOKEN_FILE
    return target.is_file() and bool(target.read_text(encoding="utf-8").strip())


def is_offline(mode: str) -> bool:
    return mode == MODE_OFFLINE


def normalize_mode(raw: str | None) -> str:
    mode = (raw or os.environ.get("R5_EGRESS_MODE") or MODE_ENFORCED).strip()
    if mode not in EGRESS_MODES:
        raise ValueError(f"unknown egress mode {mode!r}; expected one of {EGRESS_MODES}")
    return mode
