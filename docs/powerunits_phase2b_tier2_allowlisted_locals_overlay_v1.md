# Phase 2B — Tier-2 allowlisted local read overlay (Hermes Repo A)

**Canonical roadmap:** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md) — this document is operational detail only.

**Gate:** **`HERMES_POWERUNITS_CAPABILITY_TIER >= 2`** on the gateway environment **and** policy merge placing **`powerunits_tier2_allowlisted_read`** on Telegram **`platform_toolsets.telegram`** (**after** **`powerunits_tier1_analysis`** when tier ≥ 2).

**Requires Phase 2A prerequisites:** Effective tier **`2`** implies **`tier >= 1`**, so **Phase 2A** overlays remain expected on Telegram alongside **2B** after policy apply.

---

## Tier 2 vs Tier 1 (capability env)

| | **Tier 1** (`>=1`) | **Tier 2** (`>=2`) |
|--|---------------------|---------------------|
| **Adds** | Phase **2A** workspace summary + substring search (`*.md`/`.txt`/`.csv`). | Phase **2B** broader **allowlisted-local** reads: **`*.json`/`.yaml`/`.yml`** included, **`powerunits_local_reference`** subtree, manifest + aggregated summary + scoped search + single-file reads. |
| **Does not replace** | — | Bounded **`powerunits_workspace`** writes (**unchanged**). **`read_hermes_workspace_file`** stays **`.md`/`.txt`/`.csv`** only; use **`read_powerunits_allowlisted_workspace_extended_file`** for structured exports under Tier 2. |

---

## What becomes available

| Tool | Behavior |
|------|-----------|
| **`manifest_powerunits_tier2_allowlisted_read_scope`** | Read-only manifest: roots, extensions, tool names (**no disk walk**). |
| **`summarize_powerunits_allowlisted_locals`** | Inventory across **`hermes_workspace`** (same **`analysis/note/drafts/exports`** contract) and **`$HERMES_HOME/powerunits_local_reference`** if present (**Hermes never creates this directory**). Extensions: `.md`/`.txt`/`.csv`/`.json`/`.yaml`/`.yml`. Aggregate scan cap **`12000`** files (**`tier2_locals_full_scan_cap`**). Optional **`subdir`** narrows workspace leg only (**reference root skipped** when set). |
| **`search_powerunits_allowlisted_local_text`** | Bounded substring search; **`root_scope`**: **`all`** \| **`hermes_workspace`** \| **`powerunits_local_reference`**. Hits default **`48`** / cap **`96`**; per-file skip **`> 4 MiB`**; **`900`** candidate path cap before truncation. |
| **`read_powerunits_allowlisted_workspace_extended_file`** | Single-file UTF-8 read under workspace allowlisted subdirs — **supports JSON/YAML** (path shape same as bounded workspace: `subdir/tail`). |
| **`read_powerunits_local_reference_file`** | Single-file read under **`powerunits_local_reference`** with strict relative path segments (**`..`** forbidden); safe segment regex aligned with workspace save-name discipline. |

**Path safety:** **`resolve()`** + **`relative_to()`** containment under each root; file symlinks skipped; depth caps (**workspace `8`** per subtree, reference **`10`**).

---

## Remains forbidden

- **Repo B** widening, evaluator truth, bounded HTTP POST family expansion (**unchanged**).
- **Writes** beyond existing **`save_hermes_workspace_note`** (this toolset does **not** persist).
- **Curator**, self-improvement, shell, arbitrary **`HERMES_HOME`** paths (**no** bare `config.yaml` dump, **`sessions/`**, **`logs/`**, etc.).
- **Regex** search; **upstream generic** unrestricted file tools (**not** enabled wholesale).

---

## Watchers — before enabling (tier 2 uplift)

| Check | Reason |
|-------|--------|
| Baseline **`powerunits-tier0-baseline-*`** + snapshot | Rollback anchors. |
| Tier **1** stable (posture, smokes, no **`phase_2a_drift`**) | 2B builds on 2A policy ordering. |
| **`summarize_powerunits_operator_posture`** | **`phase_2b_overlay_read_only.telegram_powerunits_tier2_allowlisted_read_observed`** **`true`** after policy + restart. |

## Watchers — after enabling

| Signal | Interpretation |
|--------|----------------|
| **`high_*` / aggregate caps** | Sprawl — archive reference tree or tighten exports. |
| **`tier2_locals_full_scan_cap`** | Raise volume discipline or scope with **`subdir`**. |
| **`phase_2b_drift:*`** posture caution | Telegram missing **`powerunits_tier2_allowlisted_read`** while env tier ≥ **`2`** — re-apply **`apply_powerunits_runtime_policy.py`** + restart. |

## Rollback

1. **`HERMES_POWERUNITS_CAPABILITY_TIER=1`** (**keeps Tier 1 / 2A only**) or **`0`** (baseline) per operational choice.
2. Re-run **`apply_policy`** on boot path + restart gateway (**no migration**).
