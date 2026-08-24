#!/usr/bin/env python3
"""R5 egress broker entrypoint.

Renders the checked-in destination policy into an upstream iron-proxy config
and execs the proxy as PID 1, so container health is proxy health.

Deliberately thin. Everything security-relevant — the destination allowlist
schema, the SSRF CIDR guard, the proxy-token substitution — is upstream
``agent.proxy_sources.iron_proxy`` from the pinned Hermes image. This file
supplies the policy and the bind address and gets out of the way.

Fail-closed rules, in order of appearance below: a missing or malformed
policy, an empty allowlist, a bind address that is not the internal-network
address we were told to serve, or a mediated credential that is configured
but unusable all abort before the proxy ever listens. There is no branch in
this file that falls back to forwarding everything.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import shutil
import sys
from pathlib import Path

BROKER_ROOT = Path("/opt/r5-egress")
POLICY_PATH = BROKER_ROOT / "egress_policy.json"
CONTRACT_PATH = BROKER_ROOT / "broker_contract.json"
STATE_DIR = BROKER_ROOT / "state"
CA_PUBLIC_DIR = BROKER_ROOT / "ca-pub"
IRON_PROXY_BIN = BROKER_ROOT / "bin" / "iron-proxy"

POLICY_SCHEMA = "r5-egress-policy-v1"
TOKEN_ENV_PREFIX = "R5_EGRESS_TOKEN_"
MGMT_KEY_ENV = "HERMES_IRON_PROXY_MGMT_KEY"


class BrokerFailClosed(RuntimeError):
    """Any condition that must stop the broker before it accepts traffic."""


def _fail(message: str) -> "BrokerFailClosed":
    return BrokerFailClosed(message)


def load_policy(path: Path = POLICY_PATH) -> dict:
    """Read and validate the destination policy. Never returns allow-all."""
    if not path.is_file():
        raise _fail(f"EGRESS_POLICY_MISSING: {path}")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _fail(f"EGRESS_POLICY_INVALID: not valid JSON ({exc})") from exc
    if not isinstance(policy, dict):
        raise _fail("EGRESS_POLICY_INVALID: top level must be an object")
    if policy.get("schema") != POLICY_SCHEMA:
        raise _fail(
            f"EGRESS_POLICY_INVALID: schema must be {POLICY_SCHEMA!r}, "
            f"got {policy.get('schema')!r}"
        )
    if policy.get("default_decision") != "DENY":
        raise _fail("EGRESS_POLICY_INVALID: default_decision must be DENY")
    classes = policy.get("classes")
    if not isinstance(classes, dict) or not classes:
        raise _fail("EGRESS_POLICY_INVALID: classes must be a non-empty object")
    for name, entry in classes.items():
        if not isinstance(entry, dict):
            raise _fail(f"EGRESS_POLICY_INVALID: class {name} must be an object")
        if entry.get("decision") not in {"ALLOW", "DENY"}:
            raise _fail(f"EGRESS_POLICY_INVALID: class {name} has no ALLOW/DENY decision")
        hosts = entry.get("hosts")
        if not isinstance(hosts, list) or any(not isinstance(h, str) or not h for h in hosts):
            raise _fail(f"EGRESS_POLICY_INVALID: class {name} hosts must be a list of strings")
    return policy


def allowed_hosts(policy: dict) -> list[str]:
    """Flatten the ALLOW classes into iron-proxy's allowlist domain list."""
    hosts: list[str] = []
    for name, entry in policy["classes"].items():
        if entry.get("decision") != "ALLOW":
            continue
        for host in entry["hosts"]:
            if host in {"*", "*.*"} or host.strip() == "":
                raise _fail(f"EGRESS_POLICY_INVALID: class {name} contains a wildcard-all host")
            if host not in hosts:
                hosts.append(host)
    if not hosts:
        raise _fail("EGRESS_POLICY_INVALID: no approved destinations — refusing to start")
    return hosts


def policy_sha256(path: Path = POLICY_PATH) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def resolve_bind_ip() -> str:
    """The internal-network address the sandbox reaches us on.

    Refuses the unspecified address: binding 0.0.0.0 would publish the proxy
    on the external-capable interface too, which is exactly the dual-homing
    mistake the topology exists to prevent.
    """
    raw = (os.environ.get("R5_EGRESS_BIND_IP") or "").strip()
    if not raw:
        raise _fail("EGRESS_BIND_IP_MISSING: broker must be told its internal address")
    try:
        addr = ipaddress.IPv4Address(raw)
    except ipaddress.AddressValueError as exc:
        raise _fail(f"EGRESS_BIND_IP_INVALID: {raw!r}") from exc
    if addr.is_unspecified or addr.is_loopback or addr.is_multicast:
        raise _fail(f"EGRESS_BIND_IP_REFUSED: {raw} is not an internal-network address")
    if str(addr) not in set(_local_ipv4_addresses()):
        raise _fail(
            f"EGRESS_BIND_IP_NOT_LOCAL: {raw} is not configured on this container — "
            "the internal network is missing or the static address did not apply"
        )
    return str(addr)


def _local_ipv4_addresses() -> list[str]:
    """This container's IPv4 addresses.

    ``getaddrinfo`` on the container hostname returns only the primary
    address on some engines, and a dual-homed broker has two. The kernel's
    routing table lists every locally configured address, so read that too.
    """
    import socket

    found: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(str(info[4][0]))
    except OSError:
        pass
    try:
        text = Path("/proc/net/fib_trie").read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for line in text.splitlines():
        token = line.split()
        if len(token) == 2 and token[0] == "|--":
            found.append(token[1])
    return sorted(set(found))


def build_mappings(policy: dict, ip_module) -> list:
    """One upstream TokenMapping per mediated credential that is usable.

    A configured token with no real credential behind it is a misconfiguration
    and stops the broker: iron-proxy's ``require`` flag would otherwise reject
    every request to that provider with an error that looks like an outage.
    A credential the operator simply has not supplied is not an error — the
    class stays allowlisted and the provider call fails at the provider.
    """
    mediation = policy.get("credential_mediation") or {}
    if mediation.get("mode") != "BROKER_ONLY":
        return []
    classes = policy["classes"]
    mappings = []
    for entry in mediation.get("mediated_credentials") or []:
        env_name = str(entry.get("env_name") or "")
        class_name = str(entry.get("class") or "")
        if not env_name or class_name not in classes:
            raise _fail(f"EGRESS_POLICY_INVALID: bad mediated credential entry {entry!r}")
        token = (os.environ.get(TOKEN_ENV_PREFIX + env_name) or "").strip()
        real = (os.environ.get(env_name) or "").strip()
        if not token and not real:
            continue
        if token and not real:
            raise _fail(
                f"EGRESS_CREDENTIAL_MEDIATION_BROKEN: a proxy token was minted for "
                f"{env_name} but the broker holds no real credential for it"
            )
        if real and not token:
            raise _fail(
                f"EGRESS_CREDENTIAL_MEDIATION_BROKEN: the broker holds a real "
                f"{env_name} but no proxy token was minted, so the sandbox would "
                "need the real credential"
            )
        hosts = list(classes[class_name].get("hosts") or [])
        if not hosts:
            raise _fail(
                f"EGRESS_CREDENTIAL_MEDIATION_BROKEN: class {class_name} has no "
                f"approved hosts to scope {env_name} to"
            )
        mappings.append(
            ip_module.TokenMapping(
                real_env_name=env_name,
                proxy_token=token,
                upstream_hosts=tuple(hosts),
            )
        )
    return mappings


def _apply_require_flag(config: dict, policy: dict) -> None:
    """Set the secrets ``require`` flag from policy instead of upstream's default.

    Upstream hardcodes ``require: true``. On the pinned iron-proxy 0.39 the
    secrets transform also runs against the ``CONNECT`` request, which carries
    no Authorization header, so the flag rejects every HTTPS provider call
    before the inner request exists. Overriding the generated config is the
    external wrap this gap calls for — patching Hermes core is not.
    """
    mediation = policy.get("credential_mediation") or {}
    require = bool(mediation.get("require_token_on_provider_hosts", False))
    for transform in config.get("transforms") or []:
        if transform.get("name") != "secrets":
            continue
        for secret in (transform.get("config") or {}).get("secrets") or []:
            replace = secret.get("replace")
            if isinstance(replace, dict):
                replace["require"] = require


def publish_ca_public(ca_cert: Path) -> Path:
    """Copy only the CA certificate where the sandbox can read it.

    The signing key never leaves the broker-private state volume.
    """
    CA_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    target = CA_PUBLIC_DIR / "ca.crt"
    shutil.copyfile(ca_cert, target)
    target.chmod(0o644)
    return target


def proxy_process_env(mappings: list) -> dict[str, str]:
    """Minimal environment for the proxy process.

    Carries the real provider credentials (that is the whole point of
    mediation) and nothing else that could redirect the proxy's own egress.
    """
    env: dict[str, str] = {}
    for name in ("PATH", "HOME", "TMPDIR", "TZ", "LANG"):
        if name in os.environ:
            env[name] = os.environ[name]
    for mapping in mappings:
        value = os.environ.get(mapping.real_env_name)
        if value:
            env[mapping.real_env_name] = value
    env[MGMT_KEY_ENV] = hashlib.sha256(os.urandom(32)).hexdigest()
    env["NO_COLOR"] = "1"
    return env


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Upstream's state helpers key off HERMES_HOME. Point them at the
    # broker-private volume so the CA key, config and mappings land there.
    os.environ["HERMES_HOME"] = str(STATE_DIR)
    sys.path.insert(0, "/opt/hermes")

    from agent.proxy_sources import iron_proxy as ip  # noqa: E402
    import yaml  # noqa: E402

    policy = load_policy()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    hosts = allowed_hosts(policy)
    bind_ip = resolve_bind_ip()
    tunnel_port = int(os.environ.get("R5_EGRESS_TUNNEL_PORT") or contract["network"]["tunnel_port"])

    if not IRON_PROXY_BIN.is_file():
        raise _fail(f"EGRESS_BROKER_BINARY_MISSING: {IRON_PROXY_BIN}")

    ca_cert, ca_key = ip.ensure_ca_cert()
    published = publish_ca_public(ca_cert)

    mappings = build_mappings(policy, ip)
    config = ip.build_proxy_config(
        mappings=mappings,
        ca_cert=ca_cert,
        ca_key=ca_key,
        tunnel_port=tunnel_port,
        allowed_hosts=hosts,
        upstream_deny_cidrs=list(policy.get("ssrf_deny_cidrs") or []),
        http_listen=[f"{bind_ip}:{tunnel_port}"],
    )
    _apply_require_flag(config, policy)
    config_path = STATE_DIR / "proxy.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    config_path.chmod(0o600)

    # Startup banner is metadata only: destinations and decisions, never a
    # credential value and never a request.
    banner = {
        "R5_EGRESS_BROKER": "STARTING",
        "IRON_PROXY_VERSION": contract["iron_proxy_version"],
        "EGRESS_POLICY_SHA256": policy_sha256(),
        "APPROVED_DESTINATIONS": len(hosts),
        "APPROVED_CLASSES": sorted(
            name for name, entry in policy["classes"].items() if entry.get("decision") == "ALLOW"
        ),
        "MEDIATED_CREDENTIALS": sorted(m.real_env_name for m in mappings),
        "CREDENTIAL_VALUES_LOGGED": "NO",
        "TUNNEL_LISTEN": f"{bind_ip}:{tunnel_port}",
        "PLAIN_HTTP_LISTEN": f"{bind_ip}:{tunnel_port + 1}",
        "CA_PUBLISHED": str(published),
        "DEFAULT_DECISION": policy["default_decision"],
    }
    print(json.dumps(banner, indent=2), flush=True)

    env = proxy_process_env(mappings)
    os.execve(str(IRON_PROXY_BIN), [str(IRON_PROXY_BIN), "--config", str(config_path)], env)
    return 0  # unreachable


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokerFailClosed as exc:
        print(f"R5_EGRESS_BROKER = FAIL_CLOSED\nreason: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(78)
