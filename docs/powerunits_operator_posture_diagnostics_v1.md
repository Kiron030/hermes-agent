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
| `phase` | Stable label **`1B_operator_posture_tool`** — merges **2A** and **2B** overlay readouts when applicable. |
| `environment` | **`HERMES_HOME`**, raw env string for **`HERMES_POWERUNITS_CAPABILITY_TIER`**, **`tier_effective_integer`**, **`HERMES_POWERUNITS_RUNTIME_POLICY`**. |
| `config_curator_observation_read_only` | Best-effort parse of **`$HERMES_HOME/config.yaml`** for **`auxiliary.curator.enabled`** only. |
| `telegram_toolsets_observation_read_only` | **`platform_toolsets.telegram`**: **`powerunits_tier1_analysis_listed`**, **`powerunits_tier2_allowlisted_read_listed`**, counts, **`parse_error`** — drift checks when **`tier_effective_integer`** crosses **1**/**2**. |
| `phase_2a_overlay_read_only` | Tier **≥ 1** gate + **2A** tool names + **`telegram_powerunits_tier1_analysis_observed`**. |
| `phase_2b_overlay_read_only` | Tier **≥ 2** gate + **2B** tool names + roots hint + **`telegram_powerunits_tier2_allowlisted_read_observed`**, **`overlay_detail_doc`**. |
| `phase_1a_exports_signals_read_only` | Presence of **`EXPORTS_PHASE1_OPERATOR.txt`** + condensed **`summarize_powerunits_workspace_exports`** output. |
| `bounded_assumptions_summary` | Short bullet strings aligning with roadmap (not live policy enforcement). |
| `operator_next_checks_before_tier_increase` | Runbook pointers + Phase **2A** / **2B** rollout confirmations. |
| `caution_flags` | Exports hygiene, curator, runtime policy — plus **`phase_2a_*`** / **`phase_2b_drift*`** Telegram alignment when tier implies missing overlay toolsets. |

**Not included:** Secrets, bearer tokens, model API keys, or full `config.yaml`.

---

## Watcher linkage

Interpret **`caution_flags`** alongside:

- Bounded smokes (**`RUNBOOK.hermes-stage1-validation.md`**)
- **`summarize_powerunits_workspace_exports`** (Phase 1A)

If **`summarize_attempted`** is false under `phase_1a_exports_signals_read_only`, investigate **`summarize_skipped_reason`** (workspace path or import issue on that host).

---

## Rollback

Tool removal = normal Hermes Repo A revert/deploy; persistent volume unaffected.
