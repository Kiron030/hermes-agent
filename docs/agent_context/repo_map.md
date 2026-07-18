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
| Access matrix | [`ACCESS_MATRIX.md`](../../ACCESS_MATRIX.md) |
| Stage 1 soul / runbook | `SOUL.hermes.md`, `RUNBOOK.hermes-trusted-analyst.md` |
| Repo B allowlist | `config/powerunits_repo_b_read_allowlist.json` |

## Task → entry points

| Task type | Entry | Notes |
|-----------|-------|-------|
| Gateway / runtime | `gateway/`, `agent/` | Preserve prompt-cache invariants |
| CLI | `hermes_cli/`, `cli.py` patterns in guide | |
| Skills / plugins | `skills/`, `plugins/` | Prefer edges over core tools |
| Powerunits operator posture | `docs/powerunits_*` | First-safe; env-gated tools |
| Timescale bounded read | docs + tool allowlist | Not general SQL |
| Repo B product changes | **do in Repo B** | Schemas/pipelines/API |

## Labels

* **current** — `AGENTS.md`, progressive posture doc, ACCESS_MATRIX
* **Stage 2 docs** — writer soul/runbook/checklist are **not live** until human gate
* **upstream guide** — `hermes_development_guide.md` (moved out of always-on root)

## Usually irrelevant for Powerunits operator tasks

* `website/`, `infographic/`, desktop marketing assets
* Large optional-skills MLOps reference dumps
* Full `tests/` tree unless touching that area
