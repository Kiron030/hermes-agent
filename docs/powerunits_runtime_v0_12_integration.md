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

- **Single writable config:** `$HERMES_HOME/config.yaml` — edited by policy script on **every** gateway start when `first_safe_v1` is set (idempotent merge; preserves unknown top-level keys Hermes still reads).
- **Curator:** Hermes v0.12 may add new defaults in templates; **policy** forces **off** when the key was never set — **Curator is still not “enabled in production” by policy**.
- **First-start / migration risks (v0.12):** session/store migrations (e.g. SQLite / FTS) may run on **first** gateway start after upgrade — allow a **longer health window** on staging; watch logs for migration errors, not only “listening”.
- **Bounded tools:** unchanged contract — still gated by `gateway/run.py` + `first_safe_v1` toolsets and Repo B HTTP; runtime upgrade must not replace those files with narrower allowlists without explicit review.

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
