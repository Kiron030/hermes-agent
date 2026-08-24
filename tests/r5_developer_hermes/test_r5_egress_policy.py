"""Contract tests for the R5 egress boundary.

These assert the properties a reviewer actually relies on — the policy denies
by default, the sandbox never gets a routable network, the broker never gets
authority — rather than enumerating today's hostnames. The concrete
destination list is reviewed in the PR diff of ``egress_policy.json``, not
frozen here, so adding an approved host does not require editing a test.
"""

from __future__ import annotations

import ipaddress
import json
import os
from pathlib import PureWindowsPath

import pytest

from r5_developer_hermes.container.contract import (
    BIND_MOUNTS,
    docker_run_argv,
)
from r5_developer_hermes.container.egress import host as egress


def test_policy_denies_by_default_and_never_wildcards() -> None:
    policy = egress.load_policy()
    assert policy["default_decision"] == "DENY"
    assert policy["unknown_destination_class"] == "DENY"
    assert set(policy["allowed_ports"]) <= {80, 443}
    for name, entry in policy["classes"].items():
        assert entry["decision"] in {"ALLOW", "DENY"}, name
        for approved in entry["hosts"]:
            assert approved.strip(), name
            assert "*" not in approved, name
            assert "/" not in approved, f"{name}: hosts are names, not CIDRs"
            with pytest.raises(ValueError):
                ipaddress.ip_address(approved)


def test_every_required_destination_class_is_represented() -> None:
    classes = egress.load_policy()["classes"]
    for required in (
        "MODEL_PROVIDER",
        "RESEARCH_PROCESSOR",
        "SOURCE_CONTROL_READ",
        "LANGUAGE_PACKAGE_REGISTRY",
        "OS_PACKAGE_REGISTRY",
        "SUPPLY_CHAIN_SAFETY",
        "RUNTIME_ARTIFACT",
    ):
        assert required in classes
    assert classes["OTHER_ARBITRARY_NETWORK"]["decision"] == "DENY"


def test_policy_carries_no_credential_values() -> None:
    raw = egress.POLICY_PATH.read_text(encoding="utf-8")
    mediation = egress.load_policy()["credential_mediation"]
    assert mediation["mode"] == "BROKER_ONLY"
    for entry in mediation["mediated_credentials"]:
        # The policy names the credential; it must never contain one.
        assert entry["env_name"] in raw
        assert "sk-" not in raw
    audit = egress.load_policy()["audit"]
    assert audit["mode"] == "METADATA_ONLY"
    for forbidden in ("Authorization headers", "API keys", "request body", "prompts"):
        assert forbidden in audit["never_recorded"]


def test_ssrf_guard_covers_loopback_link_local_and_private_ranges() -> None:
    networks = [
        ipaddress.ip_network(item) for item in egress.load_policy()["ssrf_deny_cidrs"]
    ]

    def covered(address: str) -> bool:
        target = ipaddress.ip_address(address)
        return any(target in net for net in networks if net.version == target.version)

    for address in (
        "127.0.0.1",
        "::1",
        "169.254.169.254",
        "10.1.2.3",
        "172.17.0.1",
        "192.168.1.1",
        "fe80::1",
    ):
        assert covered(address), address


def test_developer_never_receives_a_routable_network() -> None:
    enforced = egress.developer_network_args(mode=egress.MODE_ENFORCED)
    assert enforced == ["--network", egress.INTERNAL_NETWORK]
    offline = egress.developer_network_args(mode=egress.MODE_OFFLINE)
    assert offline == ["--network", "none"]
    for args in (enforced, offline):
        assert "bridge" not in args
        assert "host" not in args


def test_offline_mode_configures_nothing_to_route_to() -> None:
    assert egress.developer_egress_env(mode=egress.MODE_OFFLINE, token="t") == {}
    assert egress.developer_egress_mounts(mode=egress.MODE_OFFLINE) == []


def test_unknown_egress_mode_is_refused() -> None:
    with pytest.raises(ValueError):
        egress.normalize_mode("UNRESTRICTED")
    with pytest.raises(ValueError):
        egress.developer_egress_env(mode="UNRESTRICTED", token=None)


def test_sandbox_receives_a_proxy_token_not_the_provider_credential() -> None:
    token = "r5-egress-test-token"
    env = egress.developer_egress_env(mode=egress.MODE_ENFORCED, token=token)
    mediated = egress.mediated_env_names()
    assert mediated
    for name in mediated:
        assert env[name] == token
    assert env["SSL_CERT_FILE"] == egress.CONTAINER_CA_FILE


def test_broker_receives_no_repository_socket_or_host_secret() -> None:
    argv = egress.broker_run_argv(real_model_env={}, token="t")
    joined = " ".join(argv)
    assert "type=bind" not in joined
    assert "/var/run/docker.sock" not in joined
    assert "--privileged=false" in argv
    assert "--publish" not in argv and "-p" not in argv
    for source, _dst in BIND_MOUNTS:
        assert source not in joined
    # Linux pathlib treats a Windows drive path as a single name, so
    # Path(...).parent becomes ".". Keep the Windows host-secret root
    # explicit: W:\hermes-dev\credentials must never be a broker mount.
    credentials_root = str(PureWindowsPath(r"W:\hermes-dev\credentials"))
    assert str(PureWindowsPath(os.fspath(egress.EGRESS_TOKEN_FILE)).parent) == credentials_root
    assert credentials_root not in joined
    assert r"W:\hermes-dev\credentials" not in joined
    # Two networks, and the internal one is where the sandbox reaches it.
    assert egress.INTERNAL_NETWORK in argv


def test_broker_argv_redaction_hides_token_values() -> None:
    redacted = egress.broker_run_argv_without_secrets()
    assert not any("r5-egress-" in item and "TOKEN" in item for item in redacted)
    assert any(item.endswith("=REDACTED") for item in redacted)


def test_egress_contract_fingerprint_reacts_to_policy_edits() -> None:
    """Approving one more destination must change the contract identity.

    This is what stops a policy edit from applying silently to a container
    that is already running the old rules.
    """
    before_contract = egress.egress_contract_fingerprint()
    before_policy = egress.policy_sha256()
    original = egress.POLICY_PATH.read_bytes()
    policy = json.loads(original.decode("utf-8"))
    policy["classes"]["OS_PACKAGE_REGISTRY"]["hosts"].append("security.debian.org")
    try:
        egress.POLICY_PATH.write_text(json.dumps(policy, indent=2), encoding="utf-8")
        assert egress.policy_sha256() != before_policy
        assert egress.egress_contract_fingerprint() != before_contract
    finally:
        egress.POLICY_PATH.write_bytes(original)
    assert egress.egress_contract_fingerprint() == before_contract


def test_launcher_wires_the_sandbox_into_the_internal_network() -> None:
    argv = docker_run_argv(egress_mode=egress.MODE_ENFORCED, egress_token="t")
    assert argv[argv.index("--network") + 1] == egress.INTERNAL_NETWORK
    labels = [argv[i + 1] for i, item in enumerate(argv) if item == "--label"]
    assert any(item.startswith(f"{egress.LABEL_EGRESS_CONTRACT}=") for item in labels)
    assert any(item.startswith(f"{egress.LABEL_EGRESS_POLICY}=") for item in labels)
    assert f"{egress.LABEL_EGRESS_MODE}={egress.MODE_ENFORCED}" in labels


def test_research_processor_pin_names_an_approved_processor() -> None:
    approved = egress.approved_destinations()["RESEARCH_PROCESSOR"]
    assert approved, "research must have at least one approved processor"
    patch = egress.research_config_patch()
    assert patch["backend"] == egress.RESEARCH_BACKEND
    assert patch["provider_tier"][egress.RESEARCH_BACKEND] == "free"
    # The pinned vendor must actually be reachable, or research fails closed
    # on every session rather than only on throttle.
    assert any(egress.RESEARCH_BACKEND in item for item in approved)
