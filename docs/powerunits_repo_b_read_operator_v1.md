# Powerunits Repo B read — operator (Stage 1 Trusted Analyst, v1)

**Status:** **Live tool (Repo A)** — `read_powerunits_repo_b_allowlisted` in toolset `powerunits_repo_b_read`, included under `first_safe_v1` **together with** an explicit env gate (see below). Repo B is still **not** modified from Hermes; reads go through the **GitHub Contents API** only (same principle as the primary GitHub docs reader).

## Tool

| Item | Value |
|------|--------|
| Tool name | `read_powerunits_repo_b_allowlisted` |
| Toolset | `powerunits_repo_b_read` |
| Actions | `list_keys` (no `key`), `read` (requires allowlist `key`) |
| Allowlist file | `config/powerunits_repo_b_read_allowlist.json` (override: `HERMES_POWERUNITS_REPO_B_READ_ALLOWLIST`) |
| Feature gate | `HERMES_POWERUNITS_REPO_B_READ_ENABLED` must be truthy (`1`, `true`, `yes`, `on`) |
| GitHub auth | Same as docs: `POWERUNITS_GITHUB_TOKEN_READ` or legacy `POWERUNITS_GITHUB_DOCS_TOKEN` |

There is **no** parameter for a free repo path — unknown keys **fail closed**.

## Smoke / validation (live)

Operator checklist and JSON-style smoke steps: **`RUNBOOK.hermes-stage1-validation.md`** → section **“Bounded Repo B read”** (gate, `list_keys`, one allowed `read`, unknown-key negative, no free `path`, rollback).

## Purpose

Supplemental **read-only** access to a **small** set of high-signal Repo B paths (implementation state, boundaries, runbook, architecture overview, one job entrypoint) keyed for **Trusted Analyst** grounding.

## Why this is separate from GitHub docs (primary)

The primary GitHub docs reader uses the **doc-key manifest** under curated `docs/` surfaces. This tool reads the **fixed v1 allowlist** including **non-doc-key** paths (e.g. one Python job file). Use **docs reader first** for narrative roadmap content; use **Repo B read** for allowlisted implementation files when needed.

## Why this is separate from Timescale

Timescale answers **row-level factual** queries on one view. Repo B read answers **source layout / job wiring** questions. Different credentials and contracts.

## Why this is not writer capability (Stage 2)

Read-only; no commits, no PR tool, no Repo B writes. Stage 2 remains gated by `CHECKLIST.hermes-writer-activation.md`.

## Explicit prohibitions (unchanged contract)

- **No free paths** — only allowlist keys.
- **No broad repo traversal** — no directory walk APIs beyond `list_keys` over the **frozen** key set.
- **No secret-oriented keys** in the allowlist (operators must not add them).
- **No writes** — GitHub read-only API.
- **No local clone** — no filesystem path to a mounted Repo B clone in this design.

## Allowlist authority

Changes to scope = **edit JSON + review**; Hermes does not infer new paths from chat.
