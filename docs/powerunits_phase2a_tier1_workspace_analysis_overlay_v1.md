# Phase 2A — Tier-1 workspace analysis overlay (Hermes Repo A)

**Canonical roadmap:** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) — this document is operational detail only.

**Gate:** **`HERMES_POWERUNITS_CAPABILITY_TIER >= 1`** on the **gateway process environment** **and** a successful pass of **`docker/apply_powerunits_runtime_policy.py`** so Telegram’s `platform_toolsets.telegram` includes **`powerunits_tier1_analysis`**.

**Baseline (tier 0):** Overlay toolset omitted from Telegram allowlist; tools remain in codebase but **`check_fn` fails** → operators see “unavailable” behavior consistent with tooling rules.

---

## What becomes available

| Tool | Behavior |
|------|-----------|
| **`summarize_powerunits_workspace_full`** | Read-only: per-subdir (**analysis / notes / drafts / exports**) file counts & bytes under **`$HERMES_HOME/hermes_workspace`**, global totals, up to ~16 largest `*.md`/`*.txt`/`*.csv` paths, **`caution_flags`**. Scan cap **`6000`** text files aggregate (else error **`workspace_full_scan_cap`**). |
| **`search_powerunits_workspace_text`** | Read-only: case-insensitive **substring** on **path/basename** (`match_kind=path`) then **file content** (`match_kind=content`); optional **`subdir`** filter, **`max_hits`** default **`40`** / cap **`80`**. Files **`> 2 MiB`** skipped (count in **`skipped_oversized_files:N`**). Candidate file walks capped at **`480`** paths per call. Content line previews trimmed to ~400 chars. |

**Same invariant as Phase 1 workspace:** extensions **`.md` / `.txt` / `.csv`**, max **8** logical depth segments beneath each subdirectory root, symlinks skipped, path escape guarded via `resolve()` + `relative_to(workspace_root)` patterns.

---

## Remains forbidden

- **Repo B** HTTP contracts unchanged; no broaden of bounded POST families from this overlay.
- **No writes** beyond what existing **`save_hermes_workspace_note`** already allowed (`powerunits_workspace` toolset untouched).
- **No Curator**, no autonomous skill/memory writes.
- No arbitrary filesystem paths outside **`hermes_workspace`**.
- No regex search (ReDoS / complexity avoided).

---

## Watchers — before enabling (tier uplift)

| Check | Reason |
|-------|--------|
| **`powerunits-tier0-baseline-*` tag + optional `HERMES_HOME` snapshot** | Cheap rollback anchor. |
| Bounded smokes (**`RUNBOOK.hermes-stage1-validation.md`**) green | Preserve operator contract. |
| **`summarize_powerunits_operator_posture`** | **`phase_2a_overlay_read_only.telegram_powerunits_tier1_analysis_observed`** → **`true`** after restart with policy applied. |

## Watchers — after enabling

| Signal | Interpretation |
|--------|----------------|
| **`caution_flags`** on **`summarize_powerunits_workspace_full`** | **`high_*`**, **`skipped_paths_over_depth_cap_total`**, `stat_failed:*` → investigate accidental sprawl or permissions. |
| **`hit_cap_reached` / truncated_file_list`** on **`search`** | Operator should narrow **`query`** / **`subdir`**. |
| **Posture **`phase_2a_drift:*`** caution** | Env says tier≥1 but Telegram list missing **`powerunits_tier1_analysis`** — re-run policy or fix manual `config.yaml` drift. |

## Rollback

1. **`HERMES_POWERUNITS_CAPABILITY_TIER=0`** (or unset) on Railway/host.
2. **Restart gateway** → policy script removes **`powerunits_tier1_analysis`** from merged Telegram toolsets **on next** `apply_policy` run.
3. **Git revert** image if code removal required; persistent volume unaffected (no Tier-1 tool writes artifacts by design).

---

## Uplift evidence (2026-07-23)

Telegram smokes after `CAPABILITY_TIER=1` + v0.19: posture overlay observed, workspace full summary clean (8 files), search content OK; filename-only queries previously returned 0 hits — addressed by path/basename matching in `search_powerunits_workspace_text`. Tag: **`powerunits-tier1-uplift-20260723`**. See [`powerunits_hermes_coworker_tier_ladder_v1.md`](powerunits_hermes_coworker_tier_ladder_v1.md).
