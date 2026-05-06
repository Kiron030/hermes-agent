# Powerunits — Hermes Dashboard & bundled skills atlas (v0.12+)

**Audience:** Repo A (`hermes-agent`) operators and integrators.  
**Not a roadmap** — the **single canonical progressive roadmap** remains [**`powerunits_hermes_progressive_posture_v1.md`**](powerunits_hermes_progressive_posture_v1.md). This file is a **capability atlas + operational memory**: deployment lessons, volume layout, and **advisory** tier-suitability hints for bundled skills. It does **not** change gates or Repo B semantics.

**Cross-links:** Railway HTTP/502 and dual-process start → [`powerunits_railway_bootstrap_v1.md`](powerunits_railway_bootstrap_v1.md) § Part D.1; dashboard persistence / observe mode → [`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) § *Hermes Dashboard*; Tier 3 observer tools → [`powerunits_tier3_skills_integration_overlay_v1.md`](powerunits_tier3_skills_integration_overlay_v1.md).

---

## 1. Dashboard — runtime and deployment (post–v0.12)

| Lesson | Detail |
|--------|--------|
| **Default Docker CMD** | **`gateway run`** only → Telegram/messaging gateway; **no** HTTP listener on Railway **`PORT`**. |
| **502 on public domain** | Railway’s proxy targets **`$PORT`**; nothing bound → **502 Bad Gateway** even when Telegram works. |
| **Fix (one service)** | Run **gateway + dashboard** in the **same** container: see [`docker/railway_gateway_with_dashboard.sh`](../docker/railway_gateway_with_dashboard.sh) and § Part D.1 in [`powerunits_railway_bootstrap_v1.md`](powerunits_railway_bootstrap_v1.md). Dashboard must bind **`0.0.0.0:$PORT`** with **`--insecure`** (upstream requirement for non-loopback). |
| **Stage 1 posture** | **Observability-first**; set **`HERMES_POWERUNITS_DASHBOARD_MODE=observe`** with **`HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`** to block mutating **HTTP** methods under **`/api/`** (REST). **WebSockets** are not covered by that flag — control exposure via network policy if you need end-to-end read-only. |
| **Drift risk** | Dashboard can persist **`config.yaml`**, **`.env`**, **cron**, skill disable lists, etc. **Canonical** Telegram tool surface and tier overlays still come from **`docker/apply_powerunits_runtime_policy.py`**, **`toolsets.py`**, **`model_tools.py`**, and env — not from treating the UI as source of truth. |

---

## 2. Live `HERMES_HOME` / volume layout (Railway)

Typical production mount: **`HERMES_HOME=/opt/data`** (not **`/app/skills`**).

| Path | Role |
|------|------|
| **`/opt/data/config.yaml`** | Hermes config; policy merges on boot when `first_safe_v1` is set. |
| **`/opt/data/.env`** | Secrets / provider keys; **not** rewritten by policy script. |
| **`/opt/data/state.db`** | Session / analytics SQLite (Hermes state store). |
| **`/opt/data/hermes_workspace/`** | Bounded Powerunits workspace (`analysis`, `notes`, `drafts`, `exports`, …). |
| **`/opt/data/skills/`** | **Live** bundled + operator-installed skills tree (nested folders, see §3). |
| **`/opt/data/logs/`** | Runtime logs (dashboard log viewer reads here). |
| **`/opt/data/sessions/`** | Legacy/aux session-related paths (see gateway layout); prefer **`state.db`** for session inventory in current stacks. |
| **`/opt/data/cron/`** | Scheduled job definitions (`jobs.json`, outputs). |

**Bundled skills on disk:** Under **`/opt/data/skills`**, Hermes mirrors the repo’s **`skills/`** tree (when sync/policy allows). Category folders often include **`DESCRIPTION.md`**; leaf skills use **`SKILL.md`**. Paths are **nested** (e.g. `github/github-pr-workflow`), not flat-only.

---

## 3. Bundled skills repository structure (Repo A)

Source tree: **`skills/`** at repo root (copied/synced into **`$HERMES_HOME/skills`** when policy permits).

- **Top-level folders** = domains (e.g. `creative`, `github`, `mlops`, `software-development`).
- **Hub folders** may contain **`DESCRIPTION.md`** only and **child** skills with **`SKILL.md`**.
- **Operational discovery:** the **dashboard skill list** is a useful **capability map** for what *could* be loaded — it is **not** the Powerunits **authorization** plane.

---

## 4. Canonical enable/disable plane (Powerunits)

**Do not** treat dashboard skill toggles as the **canonical** on/off contract for production posture.

Authoritative gates remain:

| Mechanism | Role |
|-----------|------|
| **`HERMES_POWERUNITS_RUNTIME_POLICY`** (`first_safe_v1`) | Fail-closed Telegram toolsets, platform disables, model pin, curator default-off (`setdefault`), etc. |
| **`HERMES_POWERUNITS_CAPABILITY_TIER`** (`0`…`4`) | Inserts/removes overlay toolsets (2A/2B/Tier 3/Tier 4A) via policy merge. |
| **`toolsets.py` / `model_tools.py`** | Tool surfacing and allowlisting at the Hermes tool layer. |
| **`docker/apply_powerunits_runtime_policy.py`** | Boot-time `config.yaml` enforcement for policy-owned sections. |

Dashboard toggles affect **`config.yaml`** skill disable lists and similar — they can **drift** from the above until reconciled. Use dashboard observations to **inform** planning; use **git/env/policy** to **decide** what the gateway may actually invoke.

---

## 5. Bundled skills — capability clusters (atlas)

Below: **representative slugs** = path under **`skills/`** (as in dashboard / Tier 3 preview), built from the **bundled** tree in this fork. **Advisory tier hint** is **not** binding — it helps compare bundles to **capability env `0`–`4`** and the **conceptual** tiers in [**`powerunits_hermes_progressive_posture_v1.md`**](powerunits_hermes_progressive_posture_v1.md).

**Legend — advisory tier hint**

- **lower:** generally read-only or narrow internal assist; fewer outbound side effects if ever allowlisted for experiments.  
- **mid:** engineering integrations (repos, PRs), richer outbound APIs — needs explicit review per use case.  
- **lab:** autonomous agents, red-team, heavy infra — default **not** candidates for routine internal operator expansion without a lab contract.

### 5.1 Engineering / coding

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `software-development/plan`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `requesting-code-review`, `spike`, `subagent-driven-development`, `python-debugpy`, `node-inspect-debugger`, `debugging-hermes-tui-commands`, `hermes-agent-skill-authoring` | Planning, TDD, debugging, subagent flows, Hermes meta-debug | High value for **internal** dev velocity on Repo A/B; unrelated to customer-facing product API | Code and agent guidance; mind outbound tools invoked *inside* skill playbooks | **mid** |
| `data-science/jupyter-live-kernel` | Notebooks / live kernels | Useful for **analytics experiments**, not production ingestion | Requires compute + data hygiene | **mid** |
| `dogfood` | Hermes self-use patterns | Internal QA / dogfooding | Low scope if kept internal | **lower**–**mid** |

### 5.2 GitHub / repo ops

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `github/github-auth`, `github-code-review`, `github-pr-workflow`, `github-repo-management`, `github-issues`, `codebase-inspection` | Auth, PRs, issues, repo management, inspection | Strong for **internal** Repo A/B hygiene; **never** imply Repo B governance truth from skill output alone | **Token scope** and write paths are sensitive | **mid** |

### 5.3 Research / intelligence

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `research/arxiv`, `blogwatcher`, `llm-wiki`, `polymarket`, `research-paper-writing` | Literature, feeds, markets, drafting | Useful for **market intelligence** narrative (advisory); cross-check against Repo B datasets | External fetch + interpretation bias | **lower**–**mid** |

### 5.4 Productivity / workspace / documents

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `productivity/google-workspace`, `notion`, `linear`, `airtable`, `maps`, `nano-pdf`, `ocr-and-documents`, `powerpoint`, `note-taking/obsidian` | SaaS productivity, docs, PDF/OCR | Good **operator** ergonomics; orthogonal to bounded HTTP families | OAuth/credentials breadth | **mid** |

### 5.5 MLOps / model infra

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `mlops/huggingface-hub`, `mlops/inference/*` (e.g. `vllm`, `llama-cpp`, `outlines`, `obliteratus`), `mlops/models/*`, `mlops/training/*`, `mlops/evaluation/*`, `mlops/research/dspy` | Train/eval/serve stacks | Relevant for **future** model ops **outside** customer DB paths | GPU/network cost; supply-chain | **mid**–**lab** |

*Hub-only subtrees (e.g. `mlops/vector-databases/DESCRIPTION.md`) group related skills — enumerate in UI under the same category.*

### 5.6 Creative / media / design

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `creative/*` (e.g. `excalidraw`, `manim-video`, `pixel-art`, `comfyui`, `p5js`, `architecture-diagram`, …), `media/*` (e.g. `youtube-content`, `spotify`, `gif-search`, …) | Graphics, video, audio, design pipelines | Mostly **internal** content / comms; optional customer-facing assets later | Asset hosting + copyright | **mid** |

### 5.7 Messaging / platform / integrations

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `email/himalaya`, `mcp/native-mcp`, `yuanbao`, `smart-home/openhue`, `social-media/xurl`, `apple/*` (e.g. `imessage`, `apple-notes`, `findmy`), `gaming/*`, `devops/webhook-subscriptions` | Channels, MCP, OEM/consumer integrations | Overlaps **Hermes platform** surface — must stay aligned with **`first_safe_v1`** platform locks | Broad exfil/CSRF classes if misconfigured | **mid**–**lab** |

### 5.8 Advanced / risky / lab-only

| Representative slugs | Capability focus | SaaS / Hermes evolution | Safety posture | Advisory tier |
|----------------------|------------------|-------------------------|----------------|---------------|
| `red-teaming/godmode` | Aggressive / high-priv patterns | **Not** default internal posture | High misuse potential | **lab** |
| `autonomous-ai-agents/*` (`hermes-agent`, `claude-code`, `codex`, `opencode`) | External agent CLIs | Conflicts with **one-main-agent** discipline if enabled casually | Autonomy + credential sprawl | **lab** |

---

## 6. Tier relevance (advisory only)

Use this section for **planning conversations**, not for automatic promotion of capability env or roadmap phases.

| Skill cluster | Typical advisory stance toward **capability env `0`–`2`** (bounded operator) | Typical stance toward **env `3`–`4`** (skills observer / drafts) | Notes |
|---------------|-----------------------------------------------------------------------------|------------------------------------------------------------------|-------|
| Engineering / coding | **Observer value** high; **invocation** still gated by Telegram toolsets | Tier 3 **inventory/diagnose** aligns; Tier 4A **draft proposals** for curated overlaps | Does not replace code review |
| GitHub / repo ops | **High caution** on write scopes | Same; drafts may propose **human** merge plans | Repo B truth remains HTTP/evaluator |
| Research | **Lower** risk if read-only fetch | Good fit for **structured exports** to workspace | Distinguish from market **data plane** |
| Productivity | **Mid** — OAuth breadth | Observer-friendly | Map to internal-only accounts |
| MLOps | **Lab-leaning** for train/serve | Observer-only until infra contract | Cost + data boundary |
| Creative / media | **Mid** — asset and IP | Drafts / internal comms | |
| Messaging / integrations | **Align with platform policy** — many conflict with disabled platforms in `first_safe_v1` | Do not use Tier 3 to **widen** platforms silently | |
| Advanced / lab | **Default exclude** from routine tiers | **Never** auto-apply proposals | Requires separate lab decision record |

**Explicit guardrail:** Raising **`HERMES_POWERUNITS_CAPABILITY_TIER`** or changing **`first_safe_v1`** is done only via the **canonical roadmap** and runbooks — **not** by skill-toggle patterns in the dashboard.

---

## 7. Maintenance

- When upstream adds skills, refresh §5 paths from **`skills/**`** (`SKILL.md` inventory).  
- When deployment lessons change (Railway, ports), update §1 and `powerunits_railway_bootstrap_v1.md` § D.1 in tandem.  
- This document **must not** grow a second phase roadmap — link [**`powerunits_hermes_progressive_posture_v1.md`**](powerunits_hermes_progressive_posture_v1.md) instead.
