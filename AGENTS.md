# Hermes Agent — AGENTS.md (Powerunits fork)

Instructions for AI coding assistants working in this **hermes-agent** Git root.

**Never give up on the right solution.**

Full upstream-oriented development guide (structure, tools, skills, pitfalls, testing detail):
[`docs/agent_context/hermes_development_guide.md`](docs/agent_context/hermes_development_guide.md)
Compact navigation: [`docs/agent_context/repo_map.md`](docs/agent_context/repo_map.md)

---

## Powerunits internal deployment (Repo A vs Repo B)

- **Repo A (`hermes-agent`):** Hermes **runtime** — gateway, tools, agent loop, Railway-oriented internal images and Powerunits-first-safe policy.
- **Repo B (Powerunits product repo, e.g. EU-PP-Database):** **Product, data platform, APIs, migrations** — canonical for schemas, pipelines, and production DB behavior. Do **not** treat Repo A as source of truth for those.

**Agent defaults here:** **Read-first**. Prefer existing docs and tool outputs over speculation. **No broad product writes** in this repo; **no infra mutation** (Railway, DNS, secrets) via code commits; **do not commit or edit `.env` / secrets**.

Bounded **Timescale** access (`read_powerunits_timescale_dataset`) is optional, **env-gated**, allowlisted view/patterns only — not a general DB tool. Bounded **Repo B file** read (`read_powerunits_repo_b_allowlisted`) is optional, **env-gated** (`HERMES_POWERUNITS_REPO_B_READ_ENABLED`), key-only GitHub API + allowlist in `config/powerunits_repo_b_read_allowlist.json` — not free-path browsing.

**Operator / stage docs:** see [`docs/agent_context/repo_map.md`](docs/agent_context/repo_map.md) (Stage 1 Trusted Analyst, progressive posture, Tier overlays). Stage 2 writer docs are documentation-only until a human activation gate.

---

## What Hermes is (lens)

Same agent core across CLI, messaging gateway, TUI, and desktop. Capability grows at the **edges** (plugins, skills, adapters); the **core tool schema** stays narrow because every core tool is paid on every API call.

Two sacred properties:

1. **Per-conversation prompt caching** — do not mutate past context, swap toolsets, or rebuild the system prompt mid-conversation (exception: context compression).
2. **Narrow waist** — prefer CLI/skill/plugin over new core model tools.

Contribution rubric, footprint ladder, architecture details → development guide.

---

## Hard invariants (recurring mistakes)

* Do **not** hardcode `~/.hermes`; use `get_hermes_home()` (`hermes_constants`).
* Do **not** break prompt caching (see guide § Important Policies).
* Tests must **not** write to `~/.hermes/`.
* Prefer behavior tests over brittle enumeration/catalog snapshot tests.
* Slash commands that mutate prompt state: cache-aware deferred invalidation by default (`--now` opt-in).

---

## Dev / test entry

Prefer project `.venv`. See development guide for layout and commands. Run the smallest relevant test target for the touched module before broad suites.

---

## Cursor context notes

* Root `AGENTS.md` stays short on purpose (always-on cost).
* Large website/static/infographic assets are indexing-excluded; open explicitly if needed.
* Product schema/pipeline truth remains in Repo B.
