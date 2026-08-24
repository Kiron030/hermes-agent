# R5 — Developer Hermes closeout

**Slice:** `R5_CLOSE`  
**Date:** 2026-08-24  
**PR:** [#67](https://github.com/Kiron030/hermes-agent/pull/67) — open, not merged  
**Status:** `R5_GATE = CLOSED_PENDING_HUMAN_MERGE`

This is the single entry point for the closed R5 architecture/security
milestone. Detailed reasoning stays in the linked docs. Future agents must
not need chat transcripts. Machine-specific proof stays in
`.r5-dev/artifacts/` (gitignored).

```text
R5_CLOSE                         = PASS
R5_EGRESS_VERIFIED               = YES
R5_CLOSE_READY                   = YES
PR_67_MERGE_RECOMMENDATION       = MERGE
```

Pinned runtime at closeout:

```text
CURRENT_HERMES_VERSION           = v2026.8.19 / 0.20.5
CURRENT_UPSTREAM_DIGEST          = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
LATEST_EGRESS_IMPLEMENTATION     = f9d44ab155
PREVIOUS_RUNTIME_CONVERGENCE     = c039096457
PREVIOUS_SECURITY_REMEDIATION    = bc1ca032f8
```

---

## 1. Final architecture

```text
Developer Hermes =
  PINNED PURE UPSTREAM HERMES
  + R5 DEVELOPER CONTAINER
  + TWO APPROVED RW REPOS
  + PERSISTENT ISOLATED HERMES_HOME
  + ENFORCED EGRESS BROKER
  + NO PRODUCTION AUTHORITY
```

| Boundary | Mechanism | Authority |
|---|---|---|
| Host / filesystem | Docker mount topology: exactly two RW binds | Host confidentiality |
| Outbound confidentiality | Internal-only Docker network + enforcing egress broker | Destination set |
| Runtime truth | Source fingerprint + image labels + running image identity | What is actually executing |

```text
DEVELOPER_HERMES_CONTROLLER      = PINNED_PURE_UPSTREAM
DEVELOPER_RUNTIME_SOURCE         = /opt/hermes
GENERIC_FINAL_TOOLSET_CAP_ACTIVE = NO
REPO_A_REPO_B_SAME_TRUST_DOMAIN  = YES
DEDICATED_CONTAINER_CLONES       = DO_NOT_EXECUTE_ON_HOST
R5_F06_STATUS                    = ENFORCED_EGRESS_POLICY
HOST_ISOLATION                   = PASS
PRODUCTION_AUTHORITY_ISOLATION   = PASS
FILESYSTEM_BOUNDARY              = PASS
EGRESS_BOUNDARY                  = PASS
```

Host execution rule: dedicated clones under `W:\hermes-dev` are never
executed on the Windows host. Repo A and Repo B are one Developer-Hermes
trust domain. The runtime is pinned `/opt/hermes`, not the mounted
checkout. No Operator final-toolset cap is claimed.

Detail:

- Architecture: [`hermes_r5_developer_hermes_v1.md`](./hermes_r5_developer_hermes_v1.md)
- Mount boundary: [`hermes_r5_container_boundary_v1.md`](./hermes_r5_container_boundary_v1.md)
- DX + runtime identity: [`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md)
- Egress: [`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md)
- Policy: [`egress_policy.json`](../../scripts/r5_developer_hermes/container/egress/egress_policy.json)
- Runbook: [`scripts/r5_developer_hermes/README.md`](../../scripts/r5_developer_hermes/README.md)

---

## 2. Security contract

```text
R5_SECURITY_CONTRACT_FINAL = YES
R5_CONFIDENTIALITY_CONTRACT =
  HOST_AND_PRODUCTION_ISOLATION
  + PRIVATE_REPO_CONFIDENTIALITY_AGAINST_ARBITRARY_THIRD_PARTIES
```

**MUST PROTECT**

- host confidentiality
- production authority
- private Repo B against arbitrary third-party destinations
- model credential against arbitrary exfiltration
- persistent Hermes state against arbitrary exfiltration

Developer Hermes **MAY** intentionally send necessary context to approved
external processors: the approved model provider, the approved research
processor, and approved package/source infrastructure.

This is not perfect DLP. Content the sandbox may read can reach any
*approved* destination. The reduction is that the recipient set is short,
named, human-approved, and reviewable in a PR diff.

See [`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md) §1 and §18.9.

---

## 3. Developer capability contract

```text
R5_DEVELOPER_CAPABILITY_FINAL = YES
DEVELOPER_CAPABILITY_PRESERVED = YES
```

R5 intentionally preserves:

- Repo A/B read-write
- cross-repo work
- Terminal, Python, uv, Git, Node/npm/TypeScript, pytest
- Skills
- persistent `HERMES_HOME`
- local Git commits
- model calls
- provider-mediated web research
- approved package installation
- GitHub HTTPS read

No remote push. No production authority. No Docker daemon authority inside
the sandbox. Desktop, Bot Mode, and model routing remain unimplemented.

---

## 4. Accepted residual risks

```text
R5_ACCEPTED_RISKS_DOCUMENTED = YES
CRITICAL_OPEN                = 0
HIGH_OPEN                    = 0
MEDIUM_OPEN                  = 0
```

Do not reopen these. They were measured and accepted.

| Residual | Class | Why accepted |
|---|---|---|
| TLS interception inside the isolated egress architecture (iron-proxy requires it) | `ACCEPTED_LOW_RISK` | CA trust is sandbox-scoped; host trust store is unaffected; the broker is intentionally trusted for approved HTTPS; audit stores neither request bodies nor credentials |
| `require_token_on_provider_hosts=false` | `ACCEPTED_LOW_RISK` | Another credential could be used only against an already approved provider host. It does **not** create new arbitrary destinations, host authority, production authority, or Docker authority |
| Container root | accepted defense-in-depth posture | uid 10000 cannot write Windows bind-mount `.git/objects`; the container is already unprivileged |
| Git hooks | contained code execution | part of the in-sandbox arbitrary-code authority already granted; host-side clone non-execution is the protection that matters |
| Linux capability reduction | deferred, not blocking | a guessed `cap_drop` subset would risk the proven DX |

Latest targeted egress re-attack:
`R5_EGRESS_DELTA_REATTACK_XS = PASS_WITH_ACCEPTED_LOW_RISKS`.
`NEW_CRITICAL = NEW_HIGH = NEW_MEDIUM = NEW_LOW = 0`.

---

## 5. Knowledge retention

```text
R5_KNOWLEDGE_RETENTION = PASS
```

Durable truth lives in versioned architecture docs, runbooks, contracts,
and `tests/r5_developer_hermes/`. Chat transcripts are not required.

| Kind | Location |
|---|---|
| This closeout | this file |
| Architecture / security / DX / egress | `docs/architecture/hermes_r5_*.md` |
| Pin / identities | `scripts/r5_developer_hermes/pin.json` |
| Launch + egress contract | `scripts/r5_developer_hermes/container/` |
| Regression | `tests/r5_developer_hermes/` |
| Host evidence | `.r5-dev/artifacts/` (gitignored) |

[`hermes_r5_proof_report_v1.md`](./hermes_r5_proof_report_v1.md) is a
historical early-slice report, not current gate status.

---

## 6. Upstream-update handoff

```text
UPSTREAM_UPDATE_HANDOFF_READY = YES
```

This is **not** the updater. The next slice
(`R5_UPSTREAM_UPDATE_CONTRACT_XS`) must use these already-proven
foundations:

- pinned upstream digest (`pin.json`); no floating tags; never `docker pull latest`
- image-input fingerprint + image labels + running-image convergence
- egress policy contract + egress-policy hash/convergence
- R5 regression suite
- real Hermes smoke when an upstream change materially affects runtime behavior

Future update flow:

```text
discover release
  -> verify tag / SHA / digest
  -> inspect security/network changes
  -> update pin
  -> rebuild
  -> convergence proof
  -> regression
  -> egress tests
  -> bounded real Hermes smoke where required
  -> PR
  -> human merge
```

Network-review checklist and state machine:
[`hermes_r5_developer_dx_v1.md`](./hermes_r5_developer_dx_v1.md)
§ Upstream update state machine.
Egress-specific update checks:
[`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md) §14.

---

## 7. Post-R5 roadmap

```text
POST_R5_ROADMAP_DOCUMENTED = YES
```

Immediate canonical sequence. Do **not** implement these in the closeout.

1. R5 human merge (PR #67)
2. `R5_UPSTREAM_UPDATE_CONTRACT_XS`
3. Desktop container integration
4. Bot Mode / Telegram integration
5. Model routing
6. PowerUnits-specific Developer-Hermes Skills / Memory / operating model

Model-routing intent only:

```text
Terra     = default
Luna      = cheap / auxiliary
Sol       = explicit difficult-task escalation
future    = approved OpenRouter/free models, then local open-weight models
```

Desktop and Bot Mode remain `NEEDS_REMEDIATION`. Transport constraint for
Desktop: the Developer container stays on the internal network; a future
localhost-only authenticated sidecar is the dual-homed party, not the
sandbox itself. See
[`hermes_r5_egress_policy_gate_v1.md`](./hermes_r5_egress_policy_gate_v1.md) §15.

This Developer-Hermes sequence is independent of the Stage-1 operator
capability-tier ladder in
[`powerunits_hermes_progressive_posture_v1.md`](../powerunits_hermes_progressive_posture_v1.md).
