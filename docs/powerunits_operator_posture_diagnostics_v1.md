# Powerunits operator posture diagnostics (`summarize_powerunits_operator_posture`)

**Canonical roadmap (do not duplicate as a second roadmap):** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md)

**Scope:** Describes the **Phase 1B** read-only tool **`summarize_powerunits_operator_posture`** (`toolset: powerunits_operator_posture`). Same safety class as **`summarize_powerunits_workspace_exports`**: observation only, **no writes**, **no bounded family expansion**.

---

## When to call

- After Railway env / image changes, before increasing **`HERMES_POWERUNITS_CAPABILITY_TIER`** or broadening tooling.
- When operators need a **quick JSON fingerprint** without opening the volume manually.

---

## Response shape (summary)

Typical JSON top-level keys (see handler for exhaustive list):

| Key | Meaning |
|-----|---------|
| `read_only` | Always `true` for this tool. |
| `phase` | **`"1B"`** |
| `environment` | **`HERMES_HOME`**, **`HERMES_POWERUNITS_CAPABILITY_TIER`**, effective tier int, **`HERMES_POWERUNITS_RUNTIME_POLICY`** |
| `config_curator_observation_read_only` | Best-effort parse of **`$HERMES_HOME/config.yaml`** for **`auxiliary.curator.enabled`** only |
| `phase_1a_exports_signals_read_only` | Presence of **`EXPORTS_PHASE1_OPERATOR.txt`** + condensed **`summarize_powerunits_workspace_exports`** output |
| `bounded_assumptions_summary` | Short bullet strings aligning with roadmap (not live policy enforcement) |
| `operator_next_checks_before_tier_increase` | Pointers back to **`RUNBOOK.hermes-stage1-validation.md`** and roadmap rollback § |
| `caution_flags` | Deduped soft warnings (tier label mismatch, unset policy, curator on, exports hygiene flags, summarize errors) |

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
