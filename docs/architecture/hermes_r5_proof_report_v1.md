# R5 — Developer Hermes proof report

**Slice:** R5  
**Date:** 2026-08-23  
**Base:** `origin/powerunits-internal-setup` @ `fc1700ccebe8a87f527084c7ba848aa8d0b7c692`  
**Proof tree:** `.r5-dev/` (gitignored)  
**This report does not start R2 or R3.**

```text
R5_STATUS = PASS
GATE_1_CLOSED = YES
SECURITY_OBJECTIVE = POWERFUL_IN_WORKSPACE / NOT_POWERFUL_IN_PRODUCTION
```

---

## Runtime

```text
DEVELOPER_RUNTIME     = pinned modern Hermes v2026.8.19 / 0.20.5
UPSTREAM_RELEASE_SHA  = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_IMAGE_DIGEST = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
REUSED_R1_SOURCE      = YES
LISTEN_ADDRESS        = none
PUBLIC_INGRESS        = NO
```

Separate instance: dedicated `HERMES_HOME` at `.r5-dev/home`, constructed
child env, `approvals.mode: off`. Not the Stage-1 operator clamp.

---

## Isolation boundary

```text
ISOLATION_BOUNDARY = PROCESS_CONSTRUCTED_ENV
DOCKER_ON_THIS_HOST = UNAVAILABLE
CONTAINER_USED = NO
```

The child environment is **built**, not sanitized-then-merged. Production
names are never copied. `HOME` / `USERPROFILE` point at
`.r5-dev/process-home`, not the host profile. `railway` / `vercel` on the
host PATH are shadowed by fail-closed stubs so a host-user CLI login is
not child authority.

This is not in-process redaction and does not call `env.update(os.environ)`.

---

## Workspace

```text
WORKSPACE_REPO_A_RW = YES   # W:\Workbench\hermes-agent
WORKSPACE_REPO_B_RW = YES   # W:\Workbench\EU-PP-Database
```

Proven via `model_tools.handle_function_call`:

- Repo A: `search_files` located `def isolated_env`; `read_file` of the R1
  harness; `write_file` under `.r5-dev/scratch`.
- Repo B: `read_file` of `README.md`; `write_file` of a temporary scratch
  proof that was deleted after the probe.

No per-file allowlist. No human approval on those writes.

---

## Capability probes (Hermes dispatch)

Path: `model_tools.handle_function_call` in the pinned upstream venv.

```text
ORDINARY_WORKSPACE_APPROVALS = 0
TOOL_CALL_COUNT              = 17
DEVELOPER_TASK_PROBE         = PASS
DEVELOPER_EXPERIENCE         = STRONG
```

| Probe | Result |
|---|---|
| A code exploration | `PASS` |
| B bounded edit | `PASS` |
| C fail → fix → green | `PASS` (exit 1 then 0) |
| D git status/diff | `PASS` (`M r5_add.py`, real diff) |
| E skills_list / skill_view | `PASS` (`r5-dev-skill`) |
| F web | `NOT_RUN_CREDENTIAL_REQUIRED` |

```text
FILESYSTEM   = PROVEN_NOW
TERMINAL     = PROVEN_NOW
GIT          = PROVEN_NOW
TEST_LOOP    = PROVEN_NOW
SKILLS       = PROVEN_NOW
WEB          = AVAILABLE_NOT_YET_PROVEN
BROWSER      = DEFERRED
DELEGATION   = DEFERRED
PROFILES     = AVAILABLE_NOT_YET_PROVEN
BOT_MODE     = DEFERRED
OBSERVABILITY = AVAILABLE_NOT_YET_PROVEN
```

Catalog presence was not treated as proof. Delegation was not expanded.

---

## Production impossibility

```text
PRODUCTION_DB_CREDENTIAL_PRESENT    = NO
POWERUNITS_EXECUTE_SECRET_PRESENT   = NO
DEPLOYMENT_CREDENTIAL_PRESENT       = NO
PRODUCTION_WRITE_REACHABLE          = NO
PRODUCTION_DEPLOY_REACHABLE         = NO
```

Mechanical evidence (values never printed):

1. Child env assertion: all production-authority names absent, including
   when the parent had them injected in tests.
2. Modern dispatch of `execute_powerunits_option_d_bounded_slice` →
   `Unknown tool`.
3. Fork `check_powerunits_option_d_execute_requirements()` → `False`.
4. Child `railway` / `vercel` resolve to fail-closed stubs (`exit 1`).
   Host CLI login is not inherited.

Deleting `.r5-dev/` cannot touch production. No production `.env` was read.

---

## SQLite

```text
SQLITE_RUNTIME_STATUS = KNOWN_RUNTIME_DEPENDENCY_DEBT
SQLITE_WAL_MODE       = delete
sqlite_version        = 3.38.4
```

Hermes warned: linked 3.38.4 is vulnerable to the WAL-reset bug and used
`journal_mode=DELETE`. Upgrade path: SQLite 3.51.3+ (or backports 3.50.7 /
3.44.6) via newer CPython / `hermes update`. Not an R5 blocker.

---

## Tests

```text
python -m pytest tests/r5_developer_hermes -q
19 passed
```

---

## Rollback

Delete `.r5-dev/` (or `HERMES_R5_PROOF_ROOT`). Production was never attached.

---

## R3 evidence

```text
R3_DEVELOPER_EXPERIENCE_EVIDENCE = READY
```

A representative developer task (locate symbol → edit → fail/fix test →
inspect diff) completed with zero ordinary-workspace approvals.

---

## What R5 did not do

No production Railway/Vercel deploy. No production DB. No execute secret.
No `.env` harvest. No R2 plugin. No R3 shadow comparison. No merge.
