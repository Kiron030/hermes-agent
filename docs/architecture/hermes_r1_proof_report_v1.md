# R1 — Modern Hermes proof report

**Slice:** R1  
**Date:** 2026-08-22  
**Base:** `origin/powerunits-internal-setup` @ `7eafef21053e42705553ac19916fdcf9dc998691`  
**Proof tree:** `.r1-proof/` (gitignored)  
**This report does not decide** `ZERO_CORE_FORK` / `THIN_FORK` / `RETAIN_CURRENT_FORK`.

```text
R0 = safety / compatibility floor
R0 != capability ceiling
R0_IS_SAFETY_FLOOR_NOT_CAPABILITY_CEILING = CONFIRMED
```

---

## Immutable pin

```text
UPSTREAM_RELEASE         = v2026.8.19
UPSTREAM_PROJECT_VERSION = 0.20.5
UPSTREAM_RELEASE_SHA     = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_TAG_OBJECT      = b05e680e63d39d5a8e3ec0f5842a41d1c4209c03
UPSTREAM_IMAGE_DIGEST    = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
IMMUTABLE_PIN            = PASS
```

Live metadata on 2026-08-22 matched the pin (GitHub annotated tag + `pyproject.toml` + Docker Hub index digest). Image revision label was not read; that requires an image-config pull. Docker is not installed in this proof host. The source worktree is the matching SHA.

Reconstruct:

```text
python scripts/r1_modern_hermes_proof/harness.py verify-pin
python scripts/r1_modern_hermes_proof/harness.py prepare-source
python scripts/r1_modern_hermes_proof/harness.py frozen-install
```

Optional image (not required for this evidence):

```text
docker pull nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

---

## Install and startup

```text
FROZEN_INSTALL           = PASS          # uv sync --frozen at the pinned SHA
RUNTIME_LAZY_INSTALL     = ABSENT_OR_DISABLED
```

`tools/lazy_deps.py` exists and is opt-in. CLI/agent startup files do not call `ensure()`. The proof process sets `HERMES_DISABLE_LAZY_INSTALLS=1` and `security.allow_lazy_installs: false`. No upstream patch.

---

## Isolation

```text
ISOLATED_HERMES_HOME     = YES   # .r1-proof/homes/{operator,developer}
PUBLIC_INGRESS           = NO
LISTEN_ADDRESS           = none  # no server started; no 0.0.0.0; no Multiplex
```

Process env is built by **absence of authority**, not by promising unused secrets stay unused.

```text
PRODUCTION_DB_CREDENTIAL_PRESENT      = NO
POWERUNITS_EXECUTE_SECRET_PRESENT     = NO
DEPLOYMENT_CREDENTIAL_PRESENT         = NO
```

Asserted absent (never printed):

- `DATABASE_URL_TIMESCALE`, `DATABASE_URL`
- `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`
- `RAILWAY_TOKEN`, `RAILWAY_API_TOKEN`, `RAILWAY_SERVICE_ID`, `RAILWAY_PROJECT_ID`, `RAILWAY_ENVIRONMENT_ID`, `RAILWAY_PUBLIC_DOMAIN`, `RAILWAY_STATIC_URL`
- `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_DEPLOY_HOOK`

No production `.env` was read. No Railway/Vercel/GitHub write token was used.

---

## Runtime smoke

```text
MODERN_RUNTIME_BOOT      = PASS
TOOL_SURFACE_INSPECTABLE = YES
MODEL_SMOKE              = HUMAN_CREDENTIAL_REQUIRED
```

Boot evidence: isolated `import hermes_cli, model_tools, toolsets` and `hermes --help` against the pinned venv.

Operator callable surface (config allow `memory`/`todo`/`web`, deny high-authority families):

```text
memory, todo, web_extract
```

`web_search` is check_fn-gated without a provider key. That is not a clamp bypass.

Human model smoke (do **not** read production `.env`):

```text
set HERMES_R1_MODEL_API_KEY=<non-production-key>
set HERMES_R1_MODEL_PROVIDER=openai
set HERMES_R1_MODEL=gpt-4.1-mini
python scripts/r1_modern_hermes_proof/harness.py model-smoke
```

---

## Operator clamp experiment

Representative upstream names (not guessed):

- allowed: `memory`, `todo`, `web`
- forbidden: `terminal`, `file`, `session_search`, `delegation`, `browser`, `cronjob`, `computer_use`, `skills`, `code_execution`

| Case | Result |
|---|---|
| Normal allowed set | `memory`, `todo`, `web_extract` — forbidden absent |
| Disabled family `terminal` | `terminal`/`process` absent |
| Explicit caller requests `terminal` **without** disabled arg | **`terminal` and `process` restored** |
| Explicit caller + `disabled_toolsets` argument | forbidden absent again |
| Unknown toolset `not_a_real_toolset` | surface does not widen |
| `tools_config._get_platform_tools` | subtracts `agent.disabled_toolsets` from enabled |
| `hermes_cli/oneshot.py` | passes `enabled_toolsets` only — **does not pass `disabled_toolsets`** |
| Multiplex | not used |

```text
CLAMP_EQUIVALENCE = PATCH_REQUIRED
```

`disabled_toolsets` works when it is actually passed into `get_tool_definitions`. It is **not** a final caller-proof cap. An explicit oneshot/CLI `enabled_toolsets` request restores a forbidden family because upstream has no post-resolution operator intersection.

```text
PATCH_SEAM_IF_REQUIRED =
  Smallest seam: model_tools._compute_tool_definitions after enabled/disabled
  resolution. Add a final declared-operator intersection that callers cannot
  widen. Alternative: oneshot/AIAgent always union config
  agent.disabled_toolsets into the disabled argument.
  R1 does not implement this patch.
```

This is evidence for later `THIN_FORK` vs `ZERO_CORE_FORK`. It is not a Thin-Fork implementation.

---

## Capability uplift (separate developer context)

Developer proof home is **not** the operator toolset. Production authority remains absent.

### Inventory (exact upstream names)

| Primitive | Upstream surface |
|---|---|
| filesystem read | `file` / `read_file` |
| filesystem write | `file` / `write_file`, `patch` |
| terminal | `terminal` / `terminal`, `process` |
| git | via `terminal` + `file` |
| tests / subprocess | `terminal` |
| web / research | `web` / `web_search`, `web_extract` |
| browser | `browser` |
| skills | `skills` / `skills_list`, `skill_view`, `skill_manage` |
| delegation | `delegation` / `delegate_task` |
| profiles | documented (`website/docs/user-guide/profiles.md`) |
| Bot Mode | documented (`website/docs/user-guide/bot-mode.md`) |
| observability | documented (`docs/observability`) |

Developer callable surface in this proof:

```text
memory, patch, process, read_file, search_files, skill_manage, skill_view,
skills_list, terminal, todo, web_extract, web_search, write_file
```

### Probes (scratch only)

```text
CAPABILITY_PROBE_1_WORKSPACE          = PASS
  read alpha.txt + beta.txt, write note.txt, show git diff --no-index

CAPABILITY_PROBE_2_TERMINAL_TEST_LOOP = PASS
  failing r1_add_probe.py, trivial fix, rerun success

CAPABILITY_PROBE_3_MODERN_PRIMITIVE   = PASS
  skills_list / skill_view / skill_manage present and enumerable
```

```text
CAPABILITY_UPLIFT          = STRONG
CAPABILITY_UPLIFT_EVIDENCE =
  workspace edit+diff; fail/fix/rerun command loop; skills primitive
```

These probes ran in the isolated modern runtime (pinned venv + scratch workspace), not as a billed production session. Missing PowerUnits plugin tools are **not** a regression; that is R2.

---

## R0 comparison notes

| Bucket | Meaning in R1 |
|---|---|
| `R0_POWERUNITS_SPECIFIC` | Bounded PU HTTP tools, gates, execute wrappers. Absent in bare upstream. Expected. R2. |
| `R0_GENERIC_OPERATOR_CONTRACT` | No `read_file` / terminal / delegation / free SQL / free repo path / `session_search`; writes gated. Operator **config** can subtract those families when disabled is applied. Caller paths can restore them without a final intersection. |
| `MODERN_UPSTREAM_GENERIC_SURFACE` | File, terminal, skills, browser, delegation, web, profiles, Bot Mode, observability. Materially richer than Stage-1 operator. Intended developer-proof upside. |

Do not treat additional safe non-production capabilities as regressions.

---

## Gate

```text
GATE_1_STATUS = CLOSED_PENDING_MODEL_SMOKE
```

Closed on isolation, frozen install, boot, inspectable surface, clamp answer, and capability probes. Model smoke waits for a dedicated non-production key.

---

## What R1 did not do

No PowerUnits plugin. No R2/R5 operationalization. No core clamp patch. No production mutation. No OIDC / mTLS / token broker / result firewall / audit service / public gateway / Desktop distribution.
