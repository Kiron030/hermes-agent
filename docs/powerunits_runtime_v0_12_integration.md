# Hermes Agent v0.12 — Powerunits runtime integration path (Repo A)

**Scope:** how the **Hermes runtime** is built and rolled out for the internal Powerunits Railway service. **Repo B** remains the bounded HTTP source of truth — no product API changes here.

**Repeatable upgrades (all versions):** [`powerunits_hermes_upgrade_playbook.md`](powerunits_hermes_upgrade_playbook.md) — branches, staging-first, tag vs `main`, Curator posture, `think`/`extra_body` pitfall.

**Progressive liberation (Phase 0 — tier vocabulary, rollback contract, watchlist):** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md).

---

## How Hermes enters this repo today

| Layer | Mechanism |
|--------|-----------|
| **Source of truth** | This **monorepo checkout** (your `hermes-agent` fork); not a separate pip-only `hermes-agent` wheel from PyPI in the Powerunits Docker path. |
| **Install** | [`Dockerfile`](../Dockerfile): `COPY` full tree → **`uv venv` + `uv pip install -e ".[all]"`** into `/opt/hermes/.venv`. Runtime runs `hermes gateway run` via [`docker/entrypoint.sh`](../docker/entrypoint.sh). |
| **Version label** | `[project].version` in [`pyproject.toml`](../pyproject.toml) documents the **packaged** semantic version; it should match the **upstream lineage** you merged (see below). |
| **Dependency pins** | Declared in **`pyproject.toml`** (ranges); lock behavior depends on `uv` resolve at **image build** time. After a major upstream merge, run a **fresh image build** — do not rely on an old cached layer if manifests changed. |
| **Powerunits config** | Persisted volume: **`HERMES_HOME`** (Railway: usually `/opt/data`). On first boot [`docker/entrypoint.sh`](../docker/entrypoint.sh) copies [`cli-config.yaml.example`](../cli-config.yaml.example) → `config.yaml` if missing. When **`HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`**, [`docker/apply_powerunits_runtime_policy.py`](../docker/apply_powerunits_runtime_policy.py) rewrites **model**, **platform_toolsets**, **platforms**, **approvals**, and (for v0.12 prep) **`auxiliary.curator`** / **`redaction`** defaults. |

---

## Upgrade target: release tag vs `main` HEAD

**Recommended for staging (and first production cut):** merge from the **annotated release** matching **Hermes Agent v0.12.0**, e.g. Git tag **`v2026.4.30`** (release notes: *v2026.4.30* / commit cited on the GitHub release).

| Option | Why |
|--------|-----|
| **Tag `v2026.4.30` (recommended)** | **Reproducible** baseline: known release notes, CI artifacts, and operator expectations. Lowest “unknown delta” for a **staging-first** rollout. |
| **`main` HEAD after the tag** | Hundreds of additional merges may land; use only if you need a **specific fix** not backported — then **pin the SHA** in your runbook/deploy notes, not floating `main`. |

**This branch** can carry **integration prep** (policy, docs) before you complete the **actual git merge** from NousResearch/upstream; the Docker image is only “true v0.12” once the merged tree matches that release (or your chosen SHA).

**After upstream code is merged:** set [`pyproject.toml`](../pyproject.toml) `[project].version` to **`0.12.0`** (or upstream’s exact version string) so operators, logs, and support align with the deployed tree.

---

## Minimal repo changes for a staged runtime bump

Already in this integration track:

1. **Policy guardrails** — `first_safe_v1` applies **`auxiliary.curator.enabled: false`** by default (using `setdefault`, so an explicit operator `enabled: true` is preserved) and **`redaction.enabled: false`** when absent (matches upstream v0.12 default philosophy).
2. **Operator docs** — this file + [`hermes_v0_12_staged_upgrade_powerunits.md`](hermes_v0_12_staged_upgrade_powerunits.md) + staging cutover checklist in [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md).

**Not required before staging:** new Railway env vars, if you only change the container image built from this repo.

---

## `HERMES_HOME` / `config.yaml` assumptions

- **Writable config:** `$HERMES_HOME/config.yaml` — when `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`, [`docker/entrypoint.sh`](../docker/entrypoint.sh) runs [`apply_powerunits_runtime_policy.py`](../docker/apply_powerunits_runtime_policy.py) on **every container start** and **rewrites policy-owned sections** (model/provider routing, `platform_toolsets`, `platforms`, `approvals`, `agent.reasoning_effort`, `command_allowlist`, `powerunits.runtime_policy`, `auxiliary.curator` / `redaction` defaults). **Other top-level keys** present in the file remain unless Hermes or the dashboard overwrites them separately.
- **Curator:** Hermes v0.12 may add new defaults in templates; **policy** uses `setdefault` so **omitted** curator flag → **disabled**; an explicit `enabled: true` in `config.yaml` is **preserved** — do not set that via dashboard for Powerunits staging/production unless deliberately testing Curator.
- **First-start / migration risks (v0.12):** session/store migrations (e.g. SQLite / FTS) may run on **first** gateway start after upgrade — allow a **longer health window** on staging; watch logs for migration errors, not only “listening”.
- **Bounded tools:** unchanged contract — still gated by `gateway/run.py` + `first_safe_v1` toolsets and Repo B HTTP; runtime upgrade must not replace those files with narrower allowlists without explicit review.

---

## Hermes Dashboard (Powerunits) — persistence, boot reconcile, Stage 1

The dashboard is served by the **same** Hermes process as the gateway when operators run `hermes dashboard` / the web UI stack; it is **not** a second agent runtime. Risk is **accidental persistence** under `$HERMES_HOME` that **outlives** what `first_safe_v1` rewrites on boot, or **in-process** drift until the next restart.

### Paths the dashboard/API can persist to (typical)

| Location | What writes there | Boot `apply_powerunits_runtime_policy` |
|----------|-------------------|----------------------------------------|
| `$HERMES_HOME/config.yaml` | `PUT /api/config`, `PUT /api/config/raw`, `POST /api/model/set`, `PUT /api/dashboard/theme`, `PUT /api/skills/toggle` (skills disabled list), setup/CLI | **Rewrites** policy-owned sections listed above; **does not** remove arbitrary keys. **Does not** reset `skills.*` disabled lists, plugins, or other untouched sections. |
| `$HERMES_HOME/.env` | `PUT`/`DELETE` `/api/env` | **Not** modified by policy script — survives restarts; treat as operational truth alongside Railway env. |
| `$HERMES_HOME/state.db` | gateway/sessions; `DELETE /api/sessions/...` | **Not** touched by policy — session/analytics data persists. |
| `$HERMES_HOME/cron/jobs.json` (+ `cron/output/`) | `/api/cron/*` | **Not** touched — cron definitions can drift until manually removed. |
| `$HERMES_HOME/logs/*` | runtime logging; log viewer is read-only | N/A |
| `$HERMES_HOME/skills/` | skill install/sync flows (not the bounded Tier 4A draft tree) | Policy does not delete skills; entrypoint **skips** bundled skills sync when `first_safe_v1` is set. |

### Post-boot reconciliation (what drifts vs what resets)

- **After each container start with `first_safe_v1`:** Telegram **platform_toolsets** (including tier overlays from `HERMES_POWERUNITS_CAPABILITY_TIER`), model pin, disabled platforms, approvals/cron mode, curator/redaction defaults (via `setdefault`), and related fields match **policy**.
- **Can still diverge across restarts until fixed:** `skills.disabled` or related skill toggles, `.env` contents from dashboard edits, `cron/jobs.json`, contents of `state.db`, and **any** `config.yaml` keys the policy script does not set (e.g. plugins) — plus **temporary** in-process changes (e.g. model pick) until the next restart reconciles policy-owned blocks.
- **Explicit curator enablement** in YAML survives policy (`setdefault` only).

### Optional HTTP observe mode (Stage 1 hardening)

Set **`HERMES_POWERUNITS_DASHBOARD_MODE=observe`** (aliases: `observability`, `readonly`, `read_only`, `read-only`, `stage1`, `stage_1`) **together with** `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`. The dashboard REST API then returns **403** for mutating HTTP methods under `/api/` (POST/PUT/PATCH/DELETE); **GET** (sessions list, logs, config read, toolset listing, analytics, etc.) stays available. **WebSockets** used for embedded chat/event bridges are **not** gated by this flag — restrict by network exposure if you require an end-to-end read-only surface.

### Stage 1 / risky / off-limits (operator matrix)

| Scope | Use |
|--------|-----|
| **Stage 1 (observability-first)** | Status/log/session **read** paths, analytics **read**, `GET` toolset listing, `GET` config/schema (for inspection), optional `HERMES_POWERUNITS_DASHBOARD_MODE=observe`. |
| **Risky — only with discipline + runbook + eventual git/env sync** | Full settings UI, raw YAML editor, model picker, env editor, skill toggles, cron UI, gateway restart / `hermes update` from UI — each can cause **drift** or operational surprise relative to Repo B posture. |
| **Off-limits for bounded Powerunits posture** | Enabling **Curator** or other **autonomous** maintainer paths, widening platforms/tooling beyond policy, pasting **production-write** or infra secrets into UI fields, relying on dashboard-only state as **canonical** policy (Repo B +Railway env + this repo remain truth). |

---

## Staging deploy sequence (concise)

1. Merge upstream **v0.12.0 tag** (recommended) into your integration branch; resolve conflicts; bump **`pyproject.toml` version** to **0.12.0**.
2. **Rebuild** Docker image (no cache staleness on `uv pip` layer if `pyproject`/lock changed).
3. Deploy to **staging** Railway (same env pattern as prod: `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`, `HERMES_HOME` volume).
4. On first boot, confirm `config.yaml` contains **`auxiliary.curator.enabled: false`** (unless you deliberately pre-seeded true) and bounded **Telegram toolsets** unchanged.
5. Run **post-upgrade smoke** (below) + full [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) **“Hermes runtime v0.12.x — staging cutover”** section.

---

## Post-upgrade smoke — bounded core (order)

Run on **staging** Telegram (allowlisted operator):

1. **`HERMES_POWERUNITS_RUNTIME_POLICY`** / config: still `first_safe_v1`; **Curator** remains off in `config.yaml`.
2. **Governance read:** `governance_powerunits_bounded_rollout_read_v1` (or operator prompt equivalent) — JSON success; optional CSV export sanity.
3. **Coverage inventory:** `inventory_powerunits_bounded_coverage_v1` — `repo_b_inventory` present; `skipped` semantics unchanged.
4. **ENTSO-E market:** preflight → validate (or execute in non-prod slice if your process allows) — still correct family routes.
5. **ENTSO-E forecast:** same — **orthogonal** path to market (**forecast** tools only).
6. **ERA5:** preflight Tier-1 ISO2 spot check (e.g. DE or NL) — still `feature_disabled` gates when env says so.
7. **Secrets:** logs must **not** contain raw `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` or full `DATABASE_URL`.

Then promote to production only after sign-off.

---

## Post-upgrade note (v0.12.0 / tag `v2026.4.30` — successful path)

- Bounded smokes (governance, inventory, ENTSO‑E market + forecast, ERA5) validated on **staging** before production.
- **HTTP 400 `think`:** if `provider` is `custom` and the endpoint is **official OpenAI** (or Azure OpenAI host), the runtime must **not** send Ollama-only `extra_body.think` — see playbook → **Lesson: `think`** and `agent/transports/chat_completions.py`.
