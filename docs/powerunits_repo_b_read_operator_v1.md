# Powerunits Repo B read — operator (Stage 1 Trusted Analyst)

**Status:** **Live tool (Repo A)** — `read_powerunits_repo_b_allowlisted` in toolset `powerunits_repo_b_read`, included under `first_safe_v1` **together with** an explicit env gate (see below). Repo B is still **not** modified from Hermes; reads go through the **GitHub Contents API** only (same principle as the primary GitHub docs reader).

## Tool

| Item | Value |
|------|--------|
| Tool name | `read_powerunits_repo_b_allowlisted` |
| Toolset | `powerunits_repo_b_read` |
| Actions | `list_repo_b_keys` (no `key`), `read_repo_b_key` (requires allowlist `key`) — distinct from `read_powerunits_doc`’s `list_keys` / `read` (manifest `*.md` keys). Legacy `list_keys` / `read` are still accepted by the handler but omitted from the schema. |
| Allowlist file | `config/powerunits_repo_b_read_allowlist.json` (override: `HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST`) |
| Feature gate | `HERMES_POWERUNITS_REPO_B_READ_ENABLED` must be truthy (`1`, `true`, `yes`, `on`) |
| GitHub auth | Same as docs: `POWERUNITS_GITHUB_TOKEN_READ` or legacy `POWERUNITS_GITHUB_DOCS_TOKEN` |

There is **no** parameter for a free repo path — unknown keys **fail closed**.

## Smoke / validation (live)

Operator checklist and JSON-style smoke steps: **`RUNBOOK.hermes-stage1-validation.md`** → section **“Bounded Repo B read”** (gate, `list_repo_b_keys`, one allowed `read_repo_b_key`, unknown-key negative, no free `path`, rollback).

## Purpose

Supplemental **read-only** access to a **fixed allowlist** of high-signal Repo B paths (see **Allowlist v2** below) for **Trusted Analyst** grounding. Still **one GitHub file per key**, **no** free paths, **fail-closed** on unknown keys.

## Allowlist v2 (controlled expansion)

**Config:** `config/powerunits_repo_b_read_allowlist.json` **version 2** — retains all **v1** keys and adds **exactly eight** entries for architecture / pipeline / ADR depth:

| Key | Why added |
|-----|-----------|
| `job_entsoe_market` | ENTSO-E market ingestion orchestration — complements `job_market_feature`. |
| `adr_013_entsoe_raw_object_store` | Normative raw object-store path for ENTSO-E archive questions. |
| `job_era5_weather` | Weather ingestion job entrypoint; pairs with weather ADR and Timescale. |
| `adr_010_weather_ingestion_mvp` | Weather MVP semantics (indices, windows) at ADR level. |
| `job_market_driver_feature` | Driver-feature job — links hourly features to modeling drivers. |
| `agent_repo_overview` | Repo layout for agents/operators; orients Hermes work across Repo A/B. |
| `target_architecture_v04` | Target architecture doc; use with `implementation_state` for plan vs reality. |
| `adr_014_entsoe_generation_outages` | Outage pipeline ADR — high value next to market/outage analyst threads. |

**Unchanged rules:** only **`list_repo_b_keys`** / **`read_repo_b_key`**; keys are **snake_case** from this JSON only; **GitHub remote only**; **Stage 1** stays read-only (no writer, no new tool classes).

## Why this is separate from GitHub docs (primary)

The primary GitHub docs reader uses the **doc-key manifest** under curated `docs/` surfaces. This tool reads the **Repo B implementation allowlist** (including **non-manifest** paths such as selected `backend/...` jobs). Use **docs reader first** for narrative roadmap content; use **Repo B read** for allowlisted implementation files when needed.

## Why this is separate from Timescale

Timescale answers **row-level factual** queries on one view. Repo B read answers **source layout / job wiring** questions. Different credentials and contracts.

## Why this is not writer capability (Stage 2)

Read-only; no commits, no PR tool, no Repo B writes. Stage 2 remains gated by `CHECKLIST.hermes-writer-activation.md`.

## Explicit prohibitions (unchanged contract)

- **No free paths** — only allowlist keys.
- **No broad repo traversal** — no directory walk APIs beyond `list_repo_b_keys` over the **frozen** key set.
- **No secret-oriented keys** in the allowlist (operators must not add them).
- **No writes** — GitHub read-only API.
- **No local clone** — no filesystem path to a mounted Repo B clone in this design.

## Allowlist authority

Changes to scope = **edit JSON + review**; Hermes does not infer new paths from chat.
