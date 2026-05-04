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
| `phase` | Stable label **`1B_operator_posture_tool`** — Phase **1B** tool; merges **Phase 2A** overlay readout below. |
| `environment` | **`HERMES_HOME`**, raw env string for **`HERMES_POWERUNITS_CAPABILITY_TIER`**, **`tier_effective_integer`**, **`HERMES_POWERUNITS_RUNTIME_POLICY`**. |
| `config_curator_observation_read_only` | Best-effort parse of **`$HERMES_HOME/config.yaml`** for **`auxiliary.curator.enabled`** only. |
| `telegram_toolsets_observation_read_only` | **`platform_toolsets.telegram`** from merged **`config.yaml`**: **`powerunits_tier1_analysis_listed`** (bool/`null`), counts, **`parse_error`** if unreadable — used for drift when **`tier_effective_integer ≥ 1`**. |
| `phase_2a_overlay_read_only` | **`tier_gate_workspace_analysis`** (true iff tier ≥ 1), tool names (**`summarize_powerunits_workspace_full`**, **`search_powerunits_workspace_text`**), **`telegram_powerunits_tier1_analysis_observed`**, **`overlay_detail_doc`**. |
| `phase_1a_exports_signals_read_only` | Presence of **`EXPORTS_PHASE1_OPERATOR.txt`** + condensed **`summarize_powerunits_workspace_exports`** output. |
| `bounded_assumptions_summary` | Short bullet strings aligning with roadmap (not live policy enforcement). |
| `operator_next_checks_before_tier_increase` | Pointers back to **`RUNBOOK.hermes-stage1-validation.md`**, rollout / Phase **2A** confirmation. |
| `caution_flags` | Deduped soft warnings: exports hygiene, curator, runtime policy — plus **`phase_2a_*`** when tier ≥ 1 implies **`powerunits_tier1_analysis`** on Telegram but config observation disagrees (**`phase_2a_drift:*`**, **`phase_2a_telegram_parse_error:*`**). |

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
