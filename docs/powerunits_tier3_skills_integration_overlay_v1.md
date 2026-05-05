# Tier 3 — Skills integration observer (Hermes Repo A)

**Canonical roadmap:** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) — this file is operational detail only.

**Gate:** **`HERMES_POWERUNITS_CAPABILITY_TIER = 3`** on the gateway process **and** merged Telegram **`platform_toolsets.telegram`** lists **`powerunits_tier3_skills_integration`** (inserted **after** **`powerunits_tier2_allowlisted_read`** when policy runs).

---

## Capability Tier 3 vs conceptual roadmap `tier3`

- **Capability env `3`** = this overlay (**bounded observe / diagnose / propose JSON / read previews**).
- **Conceptual roadmap `tier3`** (historic placeholder phrasing around Curator/autonomy products) stays **orthogonal**: Powerunits **does not** authorize silent production merges solely because this overlay exists.

---

## Toolset **`powerunits_tier3_skills_integration`**

All tools **`check_fn`:** **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 3`**.  
**Writes:** none from this toolset (including **no** automatic `SKILL.md` patches, merges, archives).

| Tool | Role |
|------|------|
| **`summarize_powerunits_skills_observer`** | Inventory: provenance-ish buckets (**bundled manifest / hub lock / agent-eligible paths** heuristic), **`SKILL.md` scan cap**, `.usage.json` histogram, **`agent.curator.load_state`** slice (read-only). |
| **`diagnose_powerunits_skills_signals`** | Duplicates (**same declared `name:`**), stale/archived agent usage rows, idle hints, heuristic “injection-like” head markers (**advisory**, not antivirus). |
| **`propose_powerunits_skill_integration_actions`** | Consolidates diagnoses into **`proposal_items`** for **human merge** (`explicitly_not_auto_applied: true`). |
| **`read_powerunits_skill_body_preview`** | Bounded **`SKILL.md`** read for a path under **`$HERMES_HOME/skills`**: flat slug or nested path (**`category/sub-skill`**); category folders with **`DESCRIPTION.md`** and no **`SKILL.md`** return a hub JSON (excerpt + **`nested_skill_slugs`**). |

**Scope boundaries:** Reads only under **`skills/`** (with the same **`SKILL.md` enumeration skips** as core Hermes: **`.hub`**, **`.archive`**, dot dirs). Does **not** read **`config.yaml`** secrets wholesale; **not** Repo B.

---

## Tier 0–4A wiring audit (operators, non-authoritative)

Quick consistency check (canonical numbers live in [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md)):

- **`HERMES_POWERUNITS_CAPABILITY_TIER`**: `0` baseline → `1` **2A** → `2` **2B** → `3` Tier 3 skills observer → `4` adds **Tier 4A** draft proposals only — **no** live **`skills/`** writes from Tier 4A tools.
- **`docker/apply_powerunits_runtime_policy.py`** merges Telegram toolsets in that order after **`powerunits_workspace`**; **`model_tools.py`** / **`toolsets.py`** list the same bounded Powerunits toolset names.
- **Curator**: policy default remains **`auxiliary.curator.enabled: false`**; Tier 3 stays **observe / propose-only** (no tool-level merges).
- **Tier 4A**: writes only under **`hermes_workspace/drafts/powerunits_skill_proposals/`** — snapshot via **`summarize_powerunits_operator_posture`** / Tier 4A summarize when enabled.

---

## Nested / category **`read_powerunits_skill_body_preview`**

| `skill_name` input | Result |
|--------------------|--------|
| **`dogfood`** | Resolves to **`dogfood/SKILL.md`** when present, or legacy match on declared skill **`name:`** elsewhere. |
| **`research/arxiv`** | Path join under **`skills/`** → reads that directory’s **`SKILL.md`**. |
| **Category** (e.g. **`research`**) with **`DESCRIPTION.md`**, no **`SKILL.md`** | JSON **`preview_kind`:** **`skill_category_hub_with_description`** with **`description_excerpt`** and **`nested_skill_slugs`** (immediate subdirs that contain **`SKILL.md`**). |
| **Category** without **`DESCRIPTION.md`**, with nested skills | JSON **`preview_kind`:** **`skill_category_index`** listing **`nested_skill_slugs`** only. |
| **`foo/../bar`**, **`.hub/foo`**, **`foo/../../etc/passwd`** segments | Rejected **`invalid_skill_name`** (**no** traversal); reserved tree parts (**`.hub`**, **`.archive`**, …) rejected. |
| Normal skill | JSON includes **`preview_kind`:** **`skill_md_body`** plus **`body`** (unchanged fields: **`canonical_name_observed`**, **`path_relative_to_skills`**, …). |

---

## Curator posture (Powerunits Tier 3)

| | **Allowed / expected at this stage** | **Not authorized as “silent production truth”** |
|--|--------------------------------------|--------------------------------------------------|
| **`apply_powerunits_runtime_policy.py`** | Continues **`auxiliary.curator.enabled: false`** by default (**unchanged**). | Flipping **`true`** for autonomous runs is **explicit ops** outside this overlay contract. |
| **Hermes Curator subsystem** (**when globally enabled**) | May **inspect/propose lifecycle** transitions on **agent-created** skills per upstream rules in repo **`agent/curator.py`**. | **Silent** acceptance of destructive merges to **critical operator skills**, or treating Curator artifacts as Repo B canon. |
| **Tier 3 tools** | **Observe**, **diagnose**, **emit structured proposals**. | Applying proposals, pinning, archiving **without human review**. |

**Operational default:** Prefer **Tier 3 tools + human PR** workflows; keep **`paused: true`** in **`.curator_state`** whenever experimenting with **`auxiliary.curator.enabled: true`**.

---

## Watchers — before uplift to capability tier `3`

- Baseline tag + **`HERMES_HOME`** snapshot (skills + `.usage.json`).
- Tier **2** posture clean (no **`phase_2b_drift*`**).
- Decide **explicitly** whether **`auxiliary.curator`** may ever flip **true** on this gateway; if yes, document who reviews Curator deltas.

## Watchers — after uplift

| Signal | Action |
|--------|--------|
| **`tier3_skills_drift:*`** posture caution | Telegram missing **`powerunits_tier3_skills_integration`** while env **`= 3`** — re-run **`apply_policy`**, restart gateway. |
| **`tier3_curator_autonomous_path_enabled`** caution **`auxiliary.curator.enabled`** is **true** | Confirm **paused** scheduler + outbound model budgets; revisit [**`hermes_v0_12_staged_upgrade_powerunits.md`**](hermes_v0_12_staged_upgrade_powerunits.md) negative checklist. |
| Elevated **`proposal_count`** repeatedly | Schedule human triage sessions; optionally capture exports in **`hermes_workspace/exports`** via existing workspace tools (**manual**, not Tier 3 auto). |

## Rollback

1. **`HERMES_POWERUNITS_CAPABILITY_TIER=2`** (**or lower**) → policy strips Tier 3 toolset on next **`apply_policy`**.  
2. Restart gateway → verify posture **`tier3_skills_drift`** cleared.  
3. **Git revert** optional; **no** DB/volume migrations from Tier 3 tools alone.
