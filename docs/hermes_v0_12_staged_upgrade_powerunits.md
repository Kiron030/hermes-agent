# Hermes Agent v0.12.x — staged upgrade preparation (Powerunits / Railway)

**Audience:** operators maintaining the **internal Powerunits Hermes** deployment (Repo A: `hermes-agent` + Railway). **Repo B (EU-PP-Database)** stays the **canonical** bounded HTTP and allowlist source — this note is **runtime-only**.

**Process:** preparation (this doc) → **staging** deploy & smoke → confidence → **production** rollout. Do **not** use this file to justify broadening bounded families or enabling Curator/self-improvement in production without a separate decision.

---

## What changes in v0.12 (relevant to us)

Upstream (NousResearch) **v0.12.0** introduces, among other things:

- **Autonomous Curator** — background skill maintenance on the gateway cron (default **~7-day** cycle), reports under `logs/curator/` (`run.json`, `REPORT.md`), configured under **`auxiliary.curator`**.
- **Self-improvement loop** — upgraded background **review fork** (memory + skills toolsets; rubric-based review; may **write** skills/memories after turns).
- **Secret redaction** — **off by default** upstream (`redaction.enabled` opt-in) to avoid mangling patches/tool JSON; Powerunits bounded tools retain **their own** URL-style redaction helpers.
- **First-start migration noise** — session/memory stack changes (e.g. **FTS5** indexing migrations, checkpoint hygiene) — first gateway boot after upgrade may log more or take slightly longer **once**.

Unbundled-from-core items (Teams plugins, Spotify, Meet, Langfuse, achievements, Vercel sandbox backends, bundled Comfy/TouchDesigner) are **not** part of our **Stage 1 / first_safe_v1** contract unless explicitly adopted.

---

## Our posture (staging and production rollout)

| Topic | Staging recommendation | Production (until explicitly approved) |
|--------|-------------------------|----------------------------------------|
| **Curator (`auxiliary.curator`)** | Prefer **`enabled: false`** in `$HERMES_HOME/config.yaml`; if you deliberately test Curator, use a **throwaway `HERMES_HOME`** or short intervals and inspect `logs/curator/*/REPORT.md`. | **Keep disabled.** No background skill pruning/consolidation on the operator gateway. |
| **Self-improvement / review fork** | Treat as **experimental**; do not rely on learned skills for **allowlist** or **Repo B** truth. | **Do not** treat memory/skill auto-updates as authoritative for bounded operations. |
| **Global `redaction.enabled`** | Default **off** unless you are debugging a specific leak; align with upstream default. | **Off** unless security review requires opt-in and operators accept patch/JSON distortion risk. |
| **Bundled telemetry/plugins** | Do not enable Langfuse/achievements/Spotify/etc. unless testing in isolation. | **Leave inactive** until product/security sign-off. |
| **`HERMES_POWERUNITS_RUNTIME_POLICY`** | Remains **`first_safe_v1`**. | Unchanged. |
| **`config.yaml` merge** | After upgrading the **Hermes binary/image**, reconcile **`$HERMES_HOME/config.yaml`** with your existing Powerunits entries (Telegram toolsets applied by [`docker/apply_powerunits_runtime_policy.py`](../docker/apply_powerunits_runtime_policy.py) or equivalent); **explicitly set Curator off** if the merged upstream template omits it. | Same; review on each production deploy. |

**Exact YAML shape** depends on the installed Hermes v0.12 build — verify keys with `hermes doctor` / upstream docs. A **commented illustration** lives at [`config/hermes_v0_12_powerunits_config_snippet.yaml.example`](../config/hermes_v0_12_powerunits_config_snippet.yaml.example) (not loaded automatically).

---

## Skill pinning (critical Powerunits surfaces)

Curator and `skill_manage` are documented upstream to **respect pins** (pinned skills are not rewritten by Curator). Pin **operator procedures** that must not drift:

**High priority (pin first in production/staging `HERMES_HOME` skill store):**

- Any **custom** skill that encodes **bounded tool order**, **governance vs overlay** interpretation, or **Railway env** recipes for Powerunits.
- References that duplicate **allowlist discipline** (market vs forecast `ALLOWED_COUNTRIES` separation).

**Repository-truth docs (canonical text in Git — prefer GitHub docs reader / allowlisted Repo B read; pin only if mirrored as installed skills):**

- `SOUL.hermes.md` — Stage 1 stance, no second truth source.
- `RUNBOOK.hermes-trusted-analyst.md`, `RUNBOOK.hermes-stage1-validation.md`.
- `docs/powerunits_bounded_operating_model_v1.md`, `docs/powerunits_bounded_flags_consolidated_v1.md`.
- `ACCESS_MATRIX.md`.
- Bounded family operator docs under `docs/powerunits_*_bounded_operator_v1.md` that your operators actually load as skills.

**Do not pin** upstream **bundled** hub skills unless you forked them into agent-authored copies (upstream protects bundled paths; pins are mainly for **your** procedural skills).

---

## First boot after upgrade — log and migration checks

After deploying a **v0.12.x** image to staging:

1. **Startup window** — allow **extra time** once; watch for SQLite/FTS/session migration lines; ensure the process becomes healthy (no crash loop).
2. **No secrets in logs** — confirm still **no** full `DATABASE_URL`, bearer tokens, or `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` in plaintext (same bar as today).
3. **Telegram** — single allowlisted operator ping; confirm **bounded** tool surface only (`first_safe_v1`).
4. **Optional** — if **Curator** was left on by mistake, look for unexpected `logs/curator/` activity; **disable** and document.

Full bounded smokes stay in **`RUNBOOK.hermes-stage1-validation.md`** (ENTSO-E, ERA5, inventory, governance, etc.).

---

## Intentionally not enabled yet (checklist)

Use this as a **negative** checklist until separately approved:

- [ ] Curator **on** in production.
- [ ] Relying on **self-improvement** memory/skill writes for **bounded allowlist** or **Repo B** semantics.
- [ ] Enabling **Langfuse**, **hermes-achievements**, **Spotify**, **Google Meet**, **Teams**, or other **optional/bundled** plugins on the internal Powerunits service.
- [ ] **Vercel Sandbox** (or other cloud execute backends) for `execute_code` / terminal without security review.
- [ ] Disabling or weakening **`first_safe_v1`** / widening Telegram toolsets “to try v0.12 features”.

---

## Railway / env — before first staging upgrade

- **No new Railway variable is strictly required** solely to *prepare* this branch (documentation-only in git).
- **After** you deploy a **v0.12** Hermes build to staging, ensure:
  - Existing Powerunits env vars unchanged unless the release notes require renames (check upstream changelog when merging).
  - **`$HERMES_HOME/config.yaml`** on the volume is merged/reviewed and **Curator** is **explicitly off** for our policy.
- Optional: run **`hermes update --check`** (or your image build’s equivalent) from a maintainer workstation before bumping the deploy tag.

---

## Related files

- [`RUNBOOK.hermes-stage1-validation.md`](../RUNBOOK.hermes-stage1-validation.md) — v0.12 staging cutover checklist (short).
- [`RUNBOOK.hermes-trusted-analyst.md`](../RUNBOOK.hermes-trusted-analyst.md) — operator entry context.
- [`config/hermes_v0_12_powerunits_config_snippet.yaml.example`](../config/hermes_v0_12_powerunits_config_snippet.yaml.example) — illustrative `config.yaml` fragment.
