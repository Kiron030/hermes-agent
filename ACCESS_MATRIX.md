# Access matrix — Powerunits Hermes (Stage 1: Trusted Analyst)

**Scope:** Internal Hermes on Railway with `first_safe_v1`. One row = one **class** of access (not every tool name).

| Surface | Stage 1 | Gating / notes |
|---------|---------|----------------|
| **Telegram → Hermes** | Allowed | Operator-facing; allowlisted users/env as configured. |
| **GitHub docs (allowlisted)** | Allowed (primary) | `POWERUNITS_GITHUB_TOKEN_READ` (or legacy docs token); paths/branches per `powerunits_github_knowledge` config. |
| **Bundled Powerunits docs** | Allowed (fallback) | Build-time / env-directed; not primary when GitHub is healthy. |
| **Workspace** (`hermes_workspace` allowlisted subdirs) | Allowed | Text notes / analysis under bounded paths; no delete/rename escapes. |
| **Memory / session search / todo** | Allowed | Part of first_safe bounded set for continuity and tasks. |
| **Timescale read** (`read_powerunits_timescale_dataset`) | Allowed **only** when gated | `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` + `DATABASE_URL_TIMESCALE`; single view `public.market_price_model_dataset_v`; fixed patterns only. |
| **Repo B file read** (`read_powerunits_repo_b_allowlisted`) | Allowed **only** when gated | `HERMES_POWERUNITS_REPO_B_READ_ENABLED` + GitHub read token; actions `list_repo_b_keys` / `read_repo_b_key` only (snake_case keys from `config/powerunits_repo_b_read_allowlist.json`); not the doc manifest tool. |
| **Option D preflight** (`preflight_powerunits_option_d_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED`; validates PL / `v1` / ≤24h UTC slice and returns operator CLI + rollback SQL only — **no** wrapper execution, **no** shell, **no** DB writes from Hermes. |
| **Option D bounded execute** (`execute_powerunits_option_d_bounded_slice`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED` + `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`; **one** HTTP POST to Powerunits internal bounded recompute API — **no** direct SQL from Hermes, **no** subprocess/product-root on this path; not a general writer. |
| **Option D bounded validate** (`validate_powerunits_option_d_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED` + same base URL and bearer as execute; **one** HTTP POST to internal **read-only** validate-window API — **no** SQL from Hermes; structured `passed` / `warning` / `failed` outcome only. |
| **Option D bounded readiness** (`readiness_powerunits_option_d_bounded_window`) | Allowed **only** when gated | `HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED` + same base URL and bearer as execute; **one** HTTP POST to internal **read-only** readiness-window API — **no** SQL from Hermes; `readiness` `go` / `no_go` on normalized **inputs** for `market_feature_job` (not output rows). |
| **General web / browser / terminal / file / code-exec / MCP / cron** | **Not** in first_safe Telegram surface | Fail-closed for Powerunits internal profile — do not “temporarily” widen without policy change. |
| **Broad DB / free SQL / schema writes** | Forbidden | Hermes has no such tool in this profile; Repo B owns schema. |
| **Repo B direct git writes from Hermes** | Forbidden | Product changes go through human/CI workflows, not agent. |
| **Infra mutation (Railway, DNS, secrets in git)** | Forbidden | Operators use consoles; agents document only. |

## Stage 1 documentation map

| File | Use |
|------|-----|
| `SOUL.hermes.md` | Profile and intent. |
| `RUNBOOK.hermes-trusted-analyst.md` | Operator context and triage table. |
| `ACCESS_MATRIX.md` | This matrix — allowed / gated / forbidden. |
| `RUNBOOK.hermes-stage1-validation.md` | Checklists, post-deploy verification, rollback basics. |
| `SOUL.hermes-writer.md` / `RUNBOOK.hermes-writer.md` | **Stage 2 scaffolding only** — not live until explicitly enabled. |
| `CHECKLIST.hermes-writer-activation.md` | **Gate** — all mandatory items + sign-off before Stage 2 is real on any environment. |

## Stage 2 — Controlled Implementer (**planned / not active by default**)

**Binding contract today:** only the **Stage 1** table above. The rows below describe **intended** behavior **only after** `CHECKLIST.hermes-writer-activation.md` is fully satisfied **and** maintainers record sign-off — not implicit availability, **not** the current Railway internal Hermes deployment.

| Surface | Stage 2 (when/if explicitly activated) | Still forbidden / unchanged |
|---------|----------------------------------------|----------------------------|
| **Repo A bounded code edits** | Planned: minimal patches only under agreed file list + plan; proposal-before-apply; human/CI gate as defined at rollout time. | No drive-by refactors; no scope expansion without re-approval. |
| **Repo B product repo** | **Not** default Hermes apply target; remains human/CI unless a separate approved workflow exists. | Same as Stage 1 unless explicitly documented elsewhere. |
| **DB / Timescale** | Read path may remain as today; **writes** stay **out of scope** for this Stage 2 doc. | No Hermes DB writer tool by default. |
| **Deploy / infra / secrets** | **Forbidden** from Hermes (same as Stage 1). | Railway, DNS, `.env`, secrets in git — operators only. |
| **Telegram → Hermes** | Would still be operator-facing; **tighter** review on any write-capable tool surface when introduced. | No “silent” broadening of `first_safe` without explicit policy change. |

**Docs:** `SOUL.hermes-writer.md`, `RUNBOOK.hermes-writer.md`, `CHECKLIST.hermes-writer-activation.md`.

## Stage 3 — Orchestrated Operator Read (**planned / not active**)

- Would add *orchestrated* read workflows; **no** default broader DB until defined and enabled separately.

---

**Summary:** Stage 1 rows are **live**. Stage 2/3 sections are **specification only** until runtime and access controls are deliberately changed — not this document alone.
