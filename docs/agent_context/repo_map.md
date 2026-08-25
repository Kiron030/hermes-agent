# Agent repo map (Hermes / Repo A)

**Status:** current (navigation only)  
**Git root:** `hermes-agent` (Powerunits internal fork)

## Always start

| Need | Path |
|------|------|
| Behavioral contract (short) | [`AGENTS.md`](../../AGENTS.md) |
| Full development guide | [`hermes_development_guide.md`](hermes_development_guide.md) |
| This map | [`repo_map.md`](repo_map.md) |
| Progressive posture (canonical staged roadmap) | [`docs/powerunits_hermes_progressive_posture_v1.md`](../powerunits_hermes_progressive_posture_v1.md) |
| Co-worker tier ladder (ops plan to climb tiers) | [`docs/powerunits_hermes_coworker_tier_ladder_v1.md`](../powerunits_hermes_coworker_tier_ladder_v1.md) |
| Upstream sync log / preflight | [`docs/upstream_sync_log.md`](../upstream_sync_log.md), [`docs/powerunits_fork_sync_preflight_checklist.md`](../powerunits_fork_sync_preflight_checklist.md) |
| Access matrix | [`ACCESS_MATRIX.md`](../../ACCESS_MATRIX.md) |
| Stage 1 soul / runbook | `SOUL.hermes.md`, `RUNBOOK.hermes-trusted-analyst.md` |
| Repo B allowlist | `config/powerunits_repo_b_read_allowlist.json` |
| Developer Hermes (R5) closeout | [`hermes_r5_closeout_v1.md`](../architecture/hermes_r5_closeout_v1.md) — `R5_GATE = CLOSED`, residuals, post-merge status |
| Developer Hermes (R5) architecture | [`hermes_r5_developer_hermes_v1.md`](../architecture/hermes_r5_developer_hermes_v1.md) |
| Developer Hermes upstream update | [`hermes_r5_developer_dx_v1.md`](../architecture/hermes_r5_developer_dx_v1.md) § Upstream update contract — ROUTINE / MATERIAL / TRUST_BOUNDARY_CHANGE |
| Developer Hermes egress boundary | [`hermes_r5_egress_policy_gate_v1.md`](../architecture/hermes_r5_egress_policy_gate_v1.md), policy in `scripts/r5_developer_hermes/container/egress/egress_policy.json` |
| Telegram 0B PREP (`telegram-ops`) | [`hermes_r5_telegram_ops_0b_v1.md`](../architecture/hermes_r5_telegram_ops_0b_v1.md) — dedicated profile seed; live token stays on Railway |

## Task → entry points

| Task type | Entry | Notes |
|-----------|-------|-------|
| Gateway / runtime | `gateway/`, `agent/` | Preserve prompt-cache invariants |
| CLI | `hermes_cli/`, `cli.py` patterns in guide | |
| Skills / plugins | `skills/`, `plugins/` | Prefer edges over core tools |
| Powerunits operator posture | `docs/powerunits_*` | First-safe; env-gated tools |
| Timescale bounded read | docs + tool allowlist | Not general SQL |
| Repo B product changes | **do in Repo B** | Schemas/pipelines/API |
| Powerful developer Hermes | [`hermes_r5_closeout_v1.md`](../architecture/hermes_r5_closeout_v1.md), then `scripts/r5_developer_hermes/` | Closed R5 gate; local Docker only; upstream updates via DX update contract; no production authority |
| Approving an outbound destination | `scripts/r5_developer_hermes/container/egress/egress_policy.json` | Security decision, not a config fix; changes the contract hash |

## Labels

* **current** — `AGENTS.md`, progressive posture doc, ACCESS_MATRIX
* **Stage 2 docs** — writer soul/runbook/checklist are **not live** until human gate
* **upstream guide** — `hermes_development_guide.md` (moved out of always-on root)

## Usually irrelevant for Powerunits operator tasks

* `website/`, `infographic/`, desktop marketing assets
* Large optional-skills MLOps reference dumps
* Full `tests/` tree unless touching that area
