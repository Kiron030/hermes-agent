# Hermes Stage 1 — manual preview / browser validation (read-only)

**Status:** v1 — **operator-run**, **no Hermes automation**. Supplements bounded tools (docs, Timescale, Repo B read); it does **not** add URL fetching, browsers, or MCP from the service.

## Purpose

After a **Vercel preview**, **staging**, or other **HTTPS** frontend build you care about, the operator **manually** opens approved URLs in a normal browser and runs a **short** checklist. This catches obvious UI regressions and broken deploys without widening Stage 1 to web automation or arbitrary network access from Hermes.

## Approved targets (max 3)

Configure **at most three** HTTPS URLs **outside** this repo (operator notes, ticket, password manager, or CI output). **Do not** commit real preview URLs if they embed tokens or non-public paths.

Placeholders (replace before a validation pass):

1. `https://PLACEHOLDER_PREVIEW_1.example`
2. `https://PLACEHOLDER_PREVIEW_2.example`
3. `https://PLACEHOLDER_PREVIEW_3.example`

Use only hosts and paths your organisation accepts as **non-sensitive** to share in runbooks.

## Checklist (per target, manual)

- [ ] **Page loads** — HTTP success, visible content (no permanent blank shell).
- [ ] **One chosen viewport** — e.g. desktop **1280×720** *or* one mobile preset; stick to **one** per pass unless you extend the runbook.
- [ ] **Core visible UI path** — e.g. landing loads, primary nav or hero visible; **smoke only**, not full product QA.
- [ ] **Basic console observation** — open devtools; note **severe** errors (red); no automated log collection required.
- [ ] *(Optional)* **Compare to frontend/product docs** — if Repo B read is enabled, cross-check high-level behaviour or wording against allowlisted keys such as `frontend_product_ux_principles` / `frontend_ui_architecture` (`read_powerunits_repo_b_allowlisted`); Hermes does **not** open the browser for you.

## Explicitly forbidden (Stage 1 contract)

| Forbidden | Why |
|-----------|-----|
| **Server-side URL fetching** by Hermes / gateway / workers | SSRF and scope creep; not part of Stage 1. |
| **Headless browser** (Playwright, Puppeteer, etc.) from this stack | Automation and supply-chain surface; not Stage 1. |
| **Broad web / generic browse MCP** | Violates bounded Trusted Analyst tool policy. |
| **Deploy hooks, Vercel/Railway/Git mutations, production config changes** | Out of scope; preview validation is **read-only observation** only. |

## Relation to other checks

- **GitHub docs** and **Repo B read** ground *what the product claims*; this doc grounds *what the built UI shows* — both are human-in-the-loop for Stage 1.
- Failing preview checks → fix in **Repo B / CI**, not by widening Hermes tools.
