# Runbook — Hermes Trusted Analyst (Powerunits internal, Railway)

Operator-facing checklist for the **internal Hermes service** running in the **Powerunits Railway project** (or equivalent). Paths assume container defaults; adjust only if your image overrides them.

**Doc set (Stage 1):** `SOUL.hermes.md` · `ACCESS_MATRIX.md` · **this runbook** · `RUNBOOK.hermes-stage1-validation.md` (repeatable checks + post-deploy verification) · `docs/powerunits_bounded_operating_model_v1.md` (bounded cross-family model; canonical detail in EU-PP-Database `docs/architecture/internal_hermes_bounded_operating_model_v1.md`) · `docs/hermes_v0_12_staged_upgrade_powerunits.md` (**Hermes v0.12.x** staging-first upgrade prep — Curator/self-improve guardrails; no Repo B change).

**After any deploy or env change:** run `RUNBOOK.hermes-stage1-validation.md` first to confirm Trusted Analyst mode is still intact.

**Before bumping the Hermes runtime to v0.12.x:** read `docs/hermes_v0_12_staged_upgrade_powerunits.md`, apply **staging-first**, keep **Curator disabled**, and use the **Hermes runtime v0.12.x — staging cutover** section in `RUNBOOK.hermes-stage1-validation.md` after the new image is live.

**Stage 2 (future only):** Controlled Implementer / writer rules are scaffolded in `SOUL.hermes-writer.md` and `RUNBOOK.hermes-writer.md`. They are **not** active on this Railway service until explicitly enabled by maintainers.

## What this deployment is

- **Hermes** = messaging gateway + agent loop from **Repo A** (`hermes-agent`).
- **Powerunits product/data** = **Repo B**; Hermes does not replace it as source of truth.
- **Stage 1 — Trusted Analyst:** read-first tooling only; `first_safe_v1` enforced for Powerunits.

## Preconditions (mental model)

| Item | Expected |
|------|----------|
| Runtime policy | `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` |
| Primary knowledge | GitHub docs reader (token via `POWERUNITS_GITHUB_TOKEN_READ` or legacy `POWERUNITS_GITHUB_DOCS_TOKEN`) |
| Bundled docs | Fallback when policy/source says so — not primary |
| Telegram | Current operator UI; webhook URL points at **this** Hermes service |
| Workspace | Bounded tree under `HERMES_HOME` (often `/opt/data`) → `hermes_workspace/` with allowlisted subdirs |
| Timescale (optional) | `DATABASE_URL_TIMESCALE` + `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED`; tool = `read_powerunits_timescale_dataset` only, view `public.market_price_model_dataset_v` |

## Startup sanity (quick)

1. Service **healthy** after deploy.
2. Logs show gateway up for **telegram**; other platforms disabled by Powerunits policy script unless you intentionally diverged.
3. No full database URLs or tokens printed in logs.

**Full checklist (Telegram, docs, Timescale, negatives, rollback):** `RUNBOOK.hermes-stage1-validation.md`.

## Knowledge surfaces (spot-checks)

1. **GitHub docs:** ask for a known roadmap/doc path; response should reflect allowlisted repo/branch behavior.
2. **Bundled:** only if your build ships a bundle and env points to it — expect explicit “bundled” messaging when used.
3. **Workspace:** list/read only under allowed subdirs; no arbitrary filesystem.
4. **Timescale:** with gate on, call bounded tool with valid `pattern_id` / `country_code` / `version` / `window_id`; invalid combo must fail closed.

## Bounded ENTSO‑E market + forecast (Hermes ↔ Repo B)

- **Repo B Tier‑1 ISO2 (bounded v1, same HTTP routes):** **DE, NL, BE, FR** for both **market** (`…/entsoe-market-sync/*`) and **forecast** (`…/entsoe-forecast/*`).
- **Hermes narrowing:** optional **`HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ALLOWED_COUNTRIES`** / **`HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ALLOWED_COUNTRIES`** — **unset** still implies implicit **`DE`** intersection on the primary path; **explicit empty** ⇒ fail‑closed; set e.g. **`DE,NL,BE,FR`** to align Hermes with Repo B Core‑4 when primaries are on.

## Bounded rollout governance CSV (read-only audit)

- Tool **`governance_powerunits_bounded_rollout_read_v1`** (toolset **`powerunits_bounded_rollout_governance`**): Repo B JSON is canonical; use **`export_format=csv`** for a Hermes-derived **`csv_export`** (and optional **`exports_csv_workspace_filename`** to persist under **`hermes_workspace/exports/`**). Columns include **`effective_status`** / **`blocking_reason`** (Repo B) plus **`_*_cross_layer`** when the Hermes overlay is applied.

## If something is wrong

| Symptom | Check |
|---------|--------|
| No tools / very few | `HERMES_POWERUNITS_RUNTIME_POLICY`; `config.yaml` `platform_toolsets.telegram` includes bounded sets (see `docker/apply_powerunits_runtime_policy.py`). |
| Docs always empty | GitHub token env; network; allowlist config paths. |
| Timescale tool missing from model | Env gate **and** toolset in first_safe allowlists (`gateway/run.py`, `model_tools.py`). |
| Timescale errors at call time | URL, RO user grants, view exists; not Hermes “broad DB” — stay within tool contract. |

## Local dev vs Railway (wording)

- **Local:** upstream Hermes often uses `~/.hermes/config.yaml` — see main `AGENTS.md`.
- **Railway internal:** config is typically under `HERMES_HOME` (e.g. `/opt/data/config.yaml`) after policy apply — same semantics, different path.

## Do not do from this runbook

Change Repo B from Hermes chat, rotate production secrets in-repo, disable `first_safe` casually, or enable broad toolsets “just to unblock” — escalate and change policy explicitly instead.
