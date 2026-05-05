# Powerunits operator posture diagnostics (`summarize_powerunits_operator_posture`)

**Canonical roadmap (do not duplicate as a second roadmap):** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md)

**Scope:** Describes the **Phase 1B** read-only tool **`summarize_powerunits_operator_posture`** (`toolset: powerunits_operator_posture`). Same safety class as **`summarize_powerunits_workspace_exports`**: observation only, **no writes**, **no bounded family expansion**.

---

## When to call

- After Railway env / image changes, before increasing **`HERMES_POWERUNITS_CAPABILITY_TIER`** or broadening tooling.
- When operators need a **quick JSON fingerprint** without opening the volume manually.

---

## Response shape (summary)

Typical JSON top-level keys (see handler `summarize_powerunits_operator_posture` for exhaustive list):

| Key | Meaning |
|-----|---------|
| `read_only` | Always `true` for this tool. |
| `phase` | Stable label **`1B_operator_posture_tool`**; merges overlays **2A / 2B / Tier 3 / Tier 4A** when **`tier_effective_integer`** implies them. |
| `environment` | **`HERMES_HOME`**, **`HERMES_POWERUNITS_CAPABILITY_TIER`**, **`tier_effective_integer`**, **`HERMES_POWERUNITS_RUNTIME_POLICY`**. |
| `config_curator_observation_read_only` | Best-effort **`auxiliary.curator.enabled`** from **`config.yaml`**. |
| `telegram_toolsets_observation_read_only` | Telegram list flags: **`powerunits_tier1_analysis_listed`**, **`powerunits_tier2_allowlisted_read_listed`**, **`powerunits_tier3_skills_integration_listed`**, **`powerunits_tier4a_skill_draft_proposals_listed`**, **`parse_error`**. |
| `phase_2a_overlay_read_only` | Tier **≥ 1** gate + **2A** tool names + **`telegram_powerunits_tier1_analysis_observed`**. |
| `phase_2b_overlay_read_only` | Tier **≥ 2** gate + **2B** tools + **`telegram_powerunits_tier2_allowlisted_read_observed`**. |
| `phase_tier3_skills_observer_read_only` | Tier **≥ 3** gate + Tier 3 tools + **`telegram_powerunits_tier3_skills_integration_observed`** + **`curator_tier3_contract_read_only`**. |
| `phase_tier4a_skill_drafts_read_only` | Tier **≥ 4** gate + Tier 4A manifest/write/list/read/summarize + **`telegram_powerunits_tier4a_skill_draft_proposals_observed`**. |
| `tier4a_draft_proposals_watch_read_only` | When **`tier ≥ 4`**, embedded **`summarize_powerunits_skill_draft_proposals`** subset + merged cautions. |
| `phase_1a_exports_signals_read_only` | Phase **1A** export subset condensed. |
| `bounded_assumptions_summary` | Roadmap-aligned bullets (non-enforcing). |
| `operator_next_checks_before_tier_increase` | Runbook pointers through **Tier 4A** rollout confirmations. |
| `caution_flags` | Includes **`tier3_skills_drift*`**, **`tier4a_skill_drafts_drift*`**, **`tier4a_drafts_watch:*`**, **`tier3_curator_autonomous_path_enabled`** (when **`tier ≥ 3`** and **`auxiliary.curator.enabled`**), plus **2A/2B** drift flags. |

**Not included:** Secrets, bearer tokens, model API keys, or full `config.yaml`.

---

## Watcher linkage

Interpret **`caution_flags`** alongside:

- Bounded smokes (**`RUNBOOK.hermes-stage1-validation.md`**)
- **`summarize_powerunits_workspace_exports`** (Phase 1A)
- **`phase_tier3_skills_observer_read_only`** when **`tier_effective_integer ≥ 3`** (**`tier3_skills_drift`**, **`tier3_curator_autonomous_path_enabled`**)
- **`phase_tier4a_skill_drafts_read_only`**, **`tier4a_draft_proposals_watch_read_only`** when **`tier_effective_integer ≥ 4`**

If **`summarize_attempted`** is false under `phase_1a_exports_signals_read_only`, investigate **`summarize_skipped_reason`** (workspace path or import issue on that host).

---

## Rollback

Tool removal = normal Hermes Repo A revert/deploy; persistent volume unaffected.
