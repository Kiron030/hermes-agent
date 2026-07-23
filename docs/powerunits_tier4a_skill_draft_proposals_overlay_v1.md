# Tier 4A — Skill draft proposals (Hermes Repo A)

**Canonical roadmap:** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) — this file is operational detail only.

**Bundled skills clusters (advisory planning):** [`powerunits_hermes_dashboard_skills_atlas_v1.md`](powerunits_hermes_dashboard_skills_atlas_v1.md).

**Gate:** **`HERMES_POWERUNITS_CAPABILITY_TIER = 4`** on the gateway process **and** merged Telegram **`platform_toolsets.telegram`** lists **`powerunits_tier4a_skill_draft_proposals`** (inserted **after** **`powerunits_tier3_skills_integration`** when policy runs).

---

## What Tier 4A is (and is not)

| | **In scope** | **Out of scope** |
|--|----------------|-------------------|
| **Purpose** | Let Hermes emit **reviewable** skill-related drafts (markdown skill bodies, patch-style text) under a **fixed workspace subtree** for **human** promotion later. | **Any** write to **`$HERMES_HOME/skills`** (“live” skills install), **silent** promotion, **automatic** merge of drafts into production **`SKILL.md`**. |
| **Truth** | Drafts are **operator staging** — label clearly with metadata (`requires_human_review`, `not_auto_applied`). | Drafts are **not** Repo B evaluator truth and **not** a substitute for governed repo changes. |
| **Self-improvement** | Hermes can **materialize proposal artifacts** for review. | Unbounded **`skill_manage`**-style autonomy, Curator-driven applies **without** ops sign-off (policy default remains **`auxiliary.curator.enabled: false`**). |

---

## Storage model

- **Root (on the persistent volume):** **`$HERMES_HOME/hermes_workspace/drafts/powerunits_skill_proposals/`**
- **Relationship to live skills:** sibling to **`analysis/`**, **`notes/`**, **`drafts/`** (general) — Tier 4A uses **`drafts/powerunits_skill_proposals`** **only**, not the live **`skills/`** tree.
- **Bootstrap pointer:** **`README_POWERUNITS_TIER4A.txt`** is created once if missing (never overwrites). It points back to this doc + roadmap.
- **Filenames:** **`.md`** or **`.txt`** only; path segments are alphanumeric + `._-`; max **12** relative segments from the proposals root; max **120,000** characters per write body.

---

## Toolset **`powerunits_tier4a_skill_draft_proposals`**

All tools **`check_fn`:** **`HERMES_POWERUNITS_CAPABILITY_TIER ≥ 4`**.

| Tool | Role |
|------|------|
| **`manifest_powerunits_tier4a_skill_draft_scope`** | Static JSON: resolved paths, caps, explicit **`not_auto_applied`** contract. |
| **`write_powerunits_skill_draft_proposal`** | Create/overwrite (optional) **one** file under the proposals root; prepends YAML frontmatter with **`powerunits_tier_4a_proposal`**, **`requires_human_review: true`**, **`not_auto_applied: true`**, and **`review_status: new`** when the body does not already start with **`---`**. **`review_status`** is the Tier **4B** lifecycle field (see Tier 4B overlay); valid values are enforced when **`tier ≥ 5`**. |
| **`list_powerunits_skill_draft_proposals`** | Bounded listing with relative paths, sizes, mtimes; optional **`subpath_prefix`**; **`sort_by`:** **`path`** \| **`mtime_desc`**. |
| **`read_powerunits_skill_draft_proposal`** | Read one draft; optional **`frontmatter`** + **`markdown_body`** parsing; optional **`max_body_preview_chars`** (preview of markdown after frontmatter). |
| **`review_powerunits_skill_draft_proposals`** | **Read-only review board:** metadata + **`body_preview`** per file, **`rollup_counts`** (target skill / kind / age bucket), optional filters — **no** promotion. |
| **`summarize_powerunits_skill_draft_proposals`** | **Watcher-style** aggregates: file count, bytes, **stale** age bucket, **24h touch** churn — soft **`caution_flags`** when thresholds are exceeded. |

**Proposal kinds (`proposal_kind`):** **`skill_draft_md`** | **`patch_style_diff_txt`** (semantic hint for reviewers; both stored as normal files with the same safety header).

---

## Operator posture + watchers

**Posture tool (`summarize_powerunits_operator_posture`)** includes:

- **`phase_tier4a_skill_drafts_read_only`** — Telegram drift if **`tier ≥ 4`** but the toolset is missing.
- **`tier4a_draft_proposals_watch_read_only`** — when **`tier ≥ 4`**, a embedded call to **`summarize_powerunits_skill_draft_proposals`** surfaces **`caution_flags`** into top-level **`caution_flags`** (prefixed **`tier4a_drafts_watch:`**).

**Summarize thresholds (soft cautions, not hard stops)**

| Flag prefix | Meaning |
|-------------|---------|
| **`tier4a_draft_file_count_high`** | Many files under proposals root → review retention / pruning. |
| **`tier4a_draft_total_bytes_high`** | Large aggregate size → volume pressure. |
| **`tier4a_many_stale_drafts`** | Many files older than **30** days → archive or delete stale drafts. |
| **`tier4a_draft_churn_24h`** | Many files touched in **24h** → confirm intentional batch work. |
| **`tier4a_proposals_list_truncated_at_*`** | Listing/summary hit internal caps → narrow prefix or prune. |
| **`tier4a_draft_review_queue_large`** | Many draft files (review queue) → schedule triage or **`review_powerunits_skill_draft_proposals`** with filters. |
| **`tier4a_drafts_some_files_missing_marker_in_head`** | Sampled files lack **`powerunits_tier_4a_proposal`** in the first bytes → confirm manual imports / non-Tier-4A text. **`README_POWERUNITS_TIER4A.txt`** is excluded from this scan. |
| **`tier4a_drafts_nested_proposals_prefix`** | Existing files under a redundant **`drafts/powerunits_skill_proposals/**` nest inside the proposals root → prune/relocate; new writes that re-include that prefix are **rejected**. |
| **`tier4a_review_*`** (from **`review_powerunits_skill_draft_proposals`**) | Filter had no matches, queue truncated, many unspecified **`target_skill_name`**, nested-prefix leftovers, or **review overload** heuristic — narrow filters or prune. |

---

## Review ergonomics (Tier 4A)

1. **`summarize_powerunits_skill_draft_proposals`** — volume + watcher flags (also mirrored in posture as **`tier4a_drafts_watch:`**).
2. **`list_powerunits_skill_draft_proposals`** with **`sort_by=mtime_desc`** — “newest first” triage list under a prefix.
3. **`review_powerunits_skill_draft_proposals`** — grouped rollups + capped queue with **metadata** and short **previews**; optional **`target_skill_substring`**, **`proposal_kind_filter`**.
4. **`read_powerunits_skill_draft_proposal`** — full file when needed; use **`max_body_preview_chars`** for a shorter Telegram-safe slice.

**Still out of scope:** auto-promotion, live **`skills/`** writes, **`skill_manage`**, Curator apply without human review.

---

## Rollback (Tier 4A)

1. Set **`HERMES_POWERUNITS_CAPABILITY_TIER=3`** (**or lower**) → `docker/apply_powerunits_runtime_policy.py` **drops** **`powerunits_tier4a_skill_draft_proposals`** from Telegram on the next merge.
2. Restart gateway → posture **`tier4a_skill_drafts_drift`** clears once Telegram aligns.
3. **No migrations:** existing draft files remain on disk as inert artifacts (operators may delete **`drafts/powerunits_skill_proposals`** manually if desired). Live **`skills/`** was never touched by Tier 4A tools.

---

## Review workflow (recommended)

1. Hermes writes draft under dated subfolder, e.g. **`drafts/powerunits_skill_proposals/2026-04-30/my-skill-draft.md`**.
2. Operator reviews content + frontmatter in IDE or **`read_powerunits_skill_draft_proposal`**.
3. Promotion = **human** copy/edit into the real **`$HERMES_HOME/skills/.../SKILL.md`** or a **git PR** — **never** an automatic Hermes apply from this overlay.

---

## Operator uplift evidence (2026-07-23)

Telegram review window **passed** at `CAPABILITY_TIER=4`: posture overlays 1–4A + `aligned`; manifest correct; smoke write `2026-07-23/tier4a_smoke_operator_note.md` with full frontmatter; list/read/review OK; path escape blocked; promote-to-live **refused** with human path; Curator off.

**Soft findings (not fail):**
- Posture caution: some files missing Tier‑4A marker in head (README pointer + legacy drafts).
- List showed a nested legacy relative path that re-includes `drafts/powerunits_skill_proposals/…`.

Tag: **`powerunits-tier4a-uplift-20260723`**.

**Adaptation ideas (ascending priority × potential):** exclude README from marker caution → nested-path watcher → prune/relabel legacy drafts → optional SOUL brevity → model bump only as separate decision → Tier 4B after soak.

### Operator hygiene (Telegram + volume)

1. Prefer important tool JSON in a **fenced code block** (Telegram drop resilience).
2. Run **`summarize_powerunits_skill_draft_proposals`** — read **`caution_flags`** + **`hygiene_hints`**.
3. On the Railway volume under `/opt/data/hermes_workspace/drafts/powerunits_skill_proposals/`: delete or move nested `drafts/powerunits_skill_proposals/**` and unmarked legacy files; **keep** `README_POWERUNITS_TIER4A.txt`.
4. New drafts: paths like `YYYY-MM-DD/name.md` only (not workspace-prefixed).

### Shipped guardrail tweaks (2026-07-23)

- Nested workspace-prefixed writes **rejected**; summarize/review emit **`tier4a_drafts_nested_proposals_prefix`** / review twin.
- Summarize **`hygiene_hints`** for operator prune.
- SOUL: tight tool-JSON narration; no invented live-skill promotion.
- Model bump remains a **separate** lever (see [`powerunits_openai_request_compatibility_v1.md`](powerunits_openai_request_compatibility_v1.md) + ladder).
