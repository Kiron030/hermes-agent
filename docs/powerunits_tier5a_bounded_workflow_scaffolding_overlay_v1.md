# Tier 5A — bounded operator workflow scaffolding overlay (Powerunits progressive posture)

**Canonical roadmap (not duplicated here):** [`powerunits_hermes_progressive_posture_v1.md`](powerunits_hermes_progressive_posture_v1.md)

**Capability env:** `HERMES_POWERUNITS_CAPABILITY_TIER = 6` — Telegram toolset `powerunits_tier5a_bounded_workflow_scaffolding` merged **immediately after** `powerunits_tier4b_review_governance`.

**Intent:** Give operators and the **single main Hermes agent** a **native, artifact-first** way to track **preflight → execute → validate → summary** style **bounded** work **without** a parallel workflow engine, **without** silent skill mutation, and **without** substituting Hermes notes for **Repo B** HTTP truth.

---

## What Tier 5A is / is not

| Yes (Tier 5A) | No (out of scope) |
|---------------|-------------------|
| Markdown **run records** with YAML frontmatter under `hermes_workspace/operator_bounded_workflows/run_records/` | Calling Option D / ENTSO-E / ERA5 / other bounded execute tools automatically |
| **Checkpoints**, **bounded_logs**, **escalation_notes**, **experiment_records**, **skill_integration_test_notes** | Live `$HERMES_HOME/skills` writes |
| **Summarize / review-board** rollups + **soft caution flags** (stuck `running`, retries, escalation pile-up, clutter) | Autonomous orchestration, auto-approve, silent merge |
| **Human-visible** workflow **status** and **stage** enums | Repo B schema or bounded family semantics changes |

**Repo B** remains the **canonical** source for bounded API behavior and outcomes. Fields like `repo_b_truth_canonical: true` and `not_auto_executed: true` on run records are **declarations**, not enforcement — operators still use existing bounded tools with explicit env gates.

---

## Workspace layout (under `hermes_workspace/`)

| Path | Role |
|------|------|
| `operator_bounded_workflows/README_POWERUNITS_TIER5A.txt` | Idempotent pointer (created if missing). |
| `operator_bounded_workflows/run_records/*.md` | **Run records** — frontmatter state machine (create/patch via `upsert_powerunits_bounded_workflow_run`). |
| `operator_bounded_workflows/checkpoints/` | Operator checkpoint / decision notes. |
| `operator_bounded_workflows/bounded_logs/` | Free-form operational log snippets. |
| `operator_bounded_workflows/escalation_notes/` | Escalation narrative (pairs with `escalation_count` on runs). |
| `operator_bounded_workflows/experiment_records/` | Short experiment / hypothesis notes. |
| `operator_bounded_workflows/skill_integration_test_notes/` | Links or notes for skill-related integration tests (not a test runner). |

---

## Frontmatter enums (run records)

**`workflow_status`:** `ready_to_run`, `running`, `validate_pending`, `summary_pending`, `retry_suggested`, `escalation_suggested`, `aborted`, `paused`, `completed`

**`workflow_stage`:** `preflight`, `execute`, `validate`, `summary`, `idle`

Invalid patch values are **rejected** (no partial silent writes).

---

## Tools (toolset `powerunits_tier5a_bounded_workflow_scaffolding`)

| Tool | Role |
|------|------|
| `manifest_powerunits_tier5a_bounded_workflow_scope` | JSON contract + roots + enums (distinct from Tier 4B / bounded HTTP). |
| `ensure_powerunits_bounded_workflow_workspace` | Idempotent subtree + README pointer. |
| `upsert_powerunits_bounded_workflow_run` | Create or patch **one** `run_records/*.md` (+ optional markdown append). |
| `read_powerunits_bounded_workflow_run` | Read any `.md` under the bounded workflow tree (validated path). |
| `list_powerunits_bounded_workflow_workspace` | Bounded listing (cap — not `list_hermes_workspace`). |
| `append_powerunits_bounded_workflow_note` | Append/create under allowlisted **note** subdirs only (not `run_records/`). |
| `summarize_powerunits_tier5a_bounded_workflow_lane` | Histograms + **caution_flags** (clutter, stuck running, retries, escalation signals, review overload). |
| `review_powerunits_bounded_workflow_runs` | Filterable operator “review board” over run records. |

---

## Posture embedding (Phase 1B)

When `tier ≥ 6`, `summarize_powerunits_operator_posture` includes:

- `phase_tier5a_workflow_read_only` — gate + tool list + Telegram observed flag + overlay doc link.
- `tier5a_workflow_watch_read_only` — embedded `summarize_powerunits_tier5a_bounded_workflow_lane` subset; cautions prefixed `tier5a_workflow_watch:`.

Drift if tier 6 but Telegram omits the toolset: `tier5a_workflow_scaffolding_drift:…`.

---

## Rollback

Set `HERMES_POWERUNITS_CAPABILITY_TIER=5`, re-apply policy, restart gateway. **Tier 5A tool surface disappears**; on-disk `operator_bounded_workflows/**` files remain for audit.

---

## Deferred (explicit)

- Full cross-run dependency DAG / job queue.
- Automatic retry execution or exponential backoff workers inside Hermes.
- Cross-repo promotion pipelines wired from run records alone.
- Broadening Repo B bounded families from Hermes workspace state.

Those stay **out of scope** until separate product/security sign-off.
