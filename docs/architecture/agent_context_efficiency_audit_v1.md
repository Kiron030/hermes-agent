# Agent Context & Token Efficiency Audit v1

**Repository:** Powerunits Hermes fork (`hermes-agent`, Repo A)  
**Date:** 2026-07-18  
**Auditor model:** Grok 4.5 (Cursor)  
**Branch:** `chore/agent-context-efficiency-audit-v1`  
**Companion audit:** product repo `EU-PP-Database` → `docs/architecture/agent_context_efficiency_audit_v1.md`

**Status:** current (meta / process)  
**Non-goals:** production Hermes behavior changes, upstream skill rewrites, hiding runtime source, cross-repo commits into Repo B.

Token figures are **proxies** (bytes ÷ 4), not Cursor tokenizer output.

---

## 1. Executive recommendation

The dominant always-on cost was root **`AGENTS.md` at ~75 KB / 1366 lines** (upstream development guide + Powerunits operator list). Secondary cost: semantic indexing of **website/**, **infographic/**, desktop media, and large optional-skills reference markdown (~19.6 MB tracked `.md` aggregate).

**Implemented now:** slim root `AGENTS.md` (~3.3 KB) with Powerunits first-safe kept; full guide relocated to `docs/agent_context/hermes_development_guide.md`; `repo_map.md`; `.cursorignore` (secrets); `.cursorindexingignore` (website/media/lockfiles); tiny alwaysApply rule `powerunits-first-safe.mdc`; copy of `scripts/audit_agent_context.py`.

**Expected impact (medium–high confidence on always-on prose):** large reduction in always-on instruction tokens; indexing quieter on marketing assets. Quality preserved by keeping first-safe boundaries in the short root file + rule.

---

## 2. Measured current-state profile

`python scripts/audit_agent_context.py --root <hermes-agent>`

| Metric | Value |
|--------|------:|
| Tracked files | 6157 |
| `tests/` | 1960 files / ~28.1 MB |
| `website/` | 734 files / ~26.0 MB |
| `apps/` | 847 files / ~19.7 MB |
| Markdown (tracked) | 1476 files / ~19.6 MB (~4.9M token-proxy if fully loaded — not realistic, but index weight) |
| Largest files | desktop/jpg/png/icns under apps/, infographic/, website static |
| Root `AGENTS.md` before | 75 208 bytes (~18.8k token-proxy) |
| Root `AGENTS.md` after | ~3 300 bytes (~0.8k token-proxy) |
| Full guide (on-demand) | `docs/agent_context/hermes_development_guide.md` ~75 KB |

### Instruction inventory

| Path | Role | Always-on? |
|------|------|------------|
| `AGENTS.md` (before) | Full upstream guide | Yes — **too large** |
| `AGENTS.md` (after) | Powerunits + hard invariants | Yes |
| `docs/agent_context/hermes_development_guide.md` | Full guide | On-demand |
| `.cursor/rules/powerunits-first-safe.mdc` | First-safe reminder | Yes (short) |
| Nested `AGENTS.md` | None beyond root | — |
| Prior `.cursorignore` / indexingignore | Absent | — |

---

## 3. High-cost context sources

1. Always-on 75 KB `AGENTS.md`.  
2. `website/` + i18n docs + static images.  
3. `infographic/` PNGs.  
4. `optional-skills/.../llms-full.md` class reference dumps.  
5. Broad `tests/` tree in semantic search for unrelated operator tasks.  
6. Repeated re-listing of Powerunits stage docs inside root AGENTS (now in `repo_map.md`).

---

## 4–5. Instruction architecture

**Target:** slim always-on (Powerunits + cache/profile pitfalls) + on-demand full guide + indexing exclusions for media/site.

| | Before | After |
|--|--------|-------|
| Always-on proxy | ~75 KB | ~3.3 KB AGENTS + ~0.5 KB rule |
| Full guide | inside AGENTS | `docs/agent_context/hermes_development_guide.md` |

---

## 6. Ignore-pattern decisions

### `.cursorignore`

Secrets (`.env*`, keys), `cli-config.yaml`, caches, `node_modules`, venvs, logs. **No** source trees (`gateway/`, `agent/`, `hermes_cli/`).

### `.cursorindexingignore`

`website/**`, `infographic/**`, image binaries, lockfiles, unsloth reference dumps, desktop public/pr-assets, achievement plugin image docs.

**Must remain visible:** runtime Python/TS, `config/powerunits_repo_b_read_allowlist.json`, Powerunits docs, tests when explicitly opened.

---

## 7. Documentation-governance findings

* Powerunits progressive posture doc is the staged roadmap — keep canonical.  
* Stage 2 writer docs must stay labeled not-live (preserved in repo_map).  
* Upstream guide relocation is a **move of always-on → on-demand**, not deletion.

---

## 8. Before/after benchmark protocol

Same fields as product-repo audit. Five Hermes tasks:

1. Gateway notification / cache-aware slash command touch (read guide + one module).  
2. Powerunits posture doc consistency check (no runtime change).  
3. Allowlist JSON review for Repo B read tool.  
4. Small skill frontmatter fix.  
5. Targeted pytest for one touched module.

Fixed starting commit; capture Cursor usage manually.

---

## 9. Implementation summary

| Change | Done |
|--------|------|
| Slim `AGENTS.md` | Yes |
| Relocate full guide | Yes |
| `repo_map.md` | Yes |
| `.cursorignore` / `.cursorindexingignore` | Yes |
| `powerunits-first-safe.mdc` | Yes |
| `.gitignore` exception for `.cursor/rules/**` | Yes |
| `scripts/audit_agent_context.py` | Yes |
| This audit | Yes |
| Delete upstream content | No (relocated) |

---

## 10. Risks and rollback

| Risk | Rollback |
|------|----------|
| Contributors expect full guide at root | Guide path in AGENTS; `git checkout` old AGENTS |
| alwaysApply rule + AGENTS overlap | Delete rule or shorten further |
| Indexing ignore too broad for website work | Remove `website/**` line when doing docs-site tasks |

Preserve Hermes first-safe boundaries — they remain in root `AGENTS.md`.

---

## 11. One exact next recommendation

**Run the controlled before/after Cursor benchmark next** (paired with the product-repo protocol).

---

## Appendix — Recommendation tiers

| Change | Tier | Token | Speed | Quality |
|--------|------|-------|-------|---------|
| Slim + relocate AGENTS | implement_now | high ↓ always-on | med ↑ | neutral/↑ |
| indexingignore media/website | implement_now | med ↓ index | low ↑ | neutral |
| secrets .cursorignore | implement_now | safety | — | ↑ |
| Ignore all `tests/` | defer | — | — | risk of missed fixtures |
| Ignore `skills/` | reject | — | — | breaks skill work |
