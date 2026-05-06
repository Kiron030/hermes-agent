# Tier 4B — Review-state workflow + governance scaffolding (Hermes Repo A)

**Canonical roadmap:** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) — this file is operational detail only.

**Gate:** **`HERMES_POWERUNITS_CAPABILITY_TIER = 5`** on the gateway process **and** merged Telegram **`platform_toolsets.telegram`** lists **`powerunits_tier4b_review_governance`** **after** **`powerunits_tier4a_skill_draft_proposals`** when policy runs.

**Rollback:** set **`HERMES_POWERUNITS_CAPABILITY_TIER=4`**, re-run **`docker/apply_powerunits_runtime_policy.py`**, restart gateway — **no** migrations; on-disk **`governance/`** and draft files stay as artifacts.

---

## What Tier 4B is (and is not)

| | **In scope** | **Out of scope** |
|--|----------------|-------------------|
| **Purpose** | Explicit **`review_status`** on Tier 4A proposal files + bounded **`hermes_workspace/governance/`** tree for operator notes / decisions / placeholders. | Live **`$HERMES_HOME/skills`** writes, **`skill_manage`** autonomy, silent merge/apply, workflow engine, multi-agent orchestration. |
| **Truth** | Review metadata is **operator guidance** only — not Repo B or production skill truth. | Treating **`accepted_for_promotion`** as “deployed” without human copy/PR. |

---

## Review states (`review_status` in YAML frontmatter)

| Value | Meaning |
|-------|---------|
| **`new`** | Default for new Tier 4A drafts (also used when field missing/invalid in Tier 4B summaries). |
| **`under_review`** | Actively triaged. |
| **`needs_revision`** | Author/operator should update draft body or metadata. |
| **`accepted_for_promotion`** | Human-approved to copy into real **`SKILL.md`** or git — **not** auto-applied by Hermes. |
| **`rejected`** | Closed without promotion. |

**Companion fields** (optional, set by **`set_powerunits_skill_draft_review_status`**): **`review_status_updated_at_utc`**, **`review_status_operator_note`**.

**Preserved:** **`requires_human_review: true`**, **`not_auto_applied: true`**, **`powerunits_tier_4a_proposal: true`** on Tier 4A writes — do not strip.

---

## Workspace: `hermes_workspace/governance/`

Created by **`ensure_powerunits_governance_workspace`** (idempotent).

| Subdir | Use |
|--------|-----|
| **`review_decisions/`** | Short decisions / rationale linked to draft paths. |
| **`incidents/`** | Incident or follow-up notes (operator). |
| **`automation_logs/`** | Placeholders or logs for **future** automation (no runners in Tier 4B). |
| **`experiments/`** | Sandbox / experiment notes. |
| **`skill_integration_tests/`** | Notes on skill integration / smoke tests. |

Root pointer: **`README_POWERUNITS_TIER4B.txt`** (created once if missing).

**Bounded writes:** **`append_powerunits_governance_note`** — **`.md`** / **`.txt`** only, allowlisted prefix, capped note size.

---

## Toolset **`powerunits_tier4b_review_governance`**

All tools **`check_fn`:** **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 5`**.

| Tool | Role |
|------|------|
| **`manifest_powerunits_tier4b_governance_scope`** | JSON: roots, review-status enum, caps. |
| **`ensure_powerunits_governance_workspace`** | Create subdirs + README pointer. |
| **`set_powerunits_skill_draft_review_status`** | Patch **`review_status`** (+ timestamp/note) on **one** proposal file. |
| **`append_powerunits_governance_note`** | Append/create note under **`governance/*`**. |
| **`read_powerunits_governance_note`** | Read one note. |
| **`list_powerunits_governance_workspace`** | Bounded listing. |
| **`summarize_powerunits_tier4b_governance_lane`** | Status histograms, unresolved/stale heuristics, governance clutter cautions. |
| **`review_powerunits_tier4b_skill_drafts`** | Filtered board (**`review_status`**, target skill, proposal kind). |

---

## Watchers (soft caution flags)

**`summarize_powerunits_tier4b_governance_lane`** may emit:

| Flag | Meaning |
|------|---------|
| **`tier4b_unresolved_draft_count_high`** | Many drafts in **`new` / `under_review` / `needs_revision`**. |
| **`tier4b_stale_unresolved_reviews`** | Unresolved drafts with old **`review_status_updated_at_utc`** or mtime (**14d** heuristic). |
| **`tier4b_governance_workspace_clutter`** | Many files under **`governance/`** (sample cap). |
| **`tier4b_contradictory_review_metadata_*`** | e.g. **`accepted_for_promotion`** with **`requires_human_review: false`** (advisory). |

Posture embeds these under **`tier4b_governance_watch_read_only`** when **`tier ≥ 5`**.

---

## Hermes-feedback ideas: **in this step** vs **deferred**

| Incorporated now | Deferred |
|------------------|----------|
| Richer workspace subtree (`governance/*`) | Automated promotion runners |
| Explicit **`review_status`** lifecycle | Full reporting / dashboards |
| Operator decision + incident note areas | Cross-instance sync |
| “Automation logs” **placeholders** | Unattended automation |

---

## Dependency

**Tier 4B assumes Tier 4A is enabled at tier **`4`** — operators raise **`HERMES_POWERUNITS_CAPABILITY_TIER`** to **`5`** only when draft volume and review discipline justify the extra tool surface.
