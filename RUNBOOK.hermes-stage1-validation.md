# Stage 1 Trusted Analyst — validation pack (Powerunits internal Hermes)

**Use:** After deploy, env change, or incident triage — confirm Hermes is still **Stage 1 Trusted Analyst**, bounded and reviewable. Repo A only; product truth stays Repo B.

## Stage 1 documentation map

| Artifact | Role |
|----------|------|
| `SOUL.hermes.md` | Profile intent, knowledge order, roadmap stages (1 live; 2–3 placeholders). |
| `RUNBOOK.hermes-trusted-analyst.md` | Ongoing operator context, paths, “if something is wrong”. |
| `ACCESS_MATRIX.md` | What is allowed vs gated vs forbidden in Stage 1. |
| **This file** | Repeatable checks + post-change verification + rollback basics. |
| `docs/powerunits_timescale_read_operator_v1.md` | Timescale tool env gates and scope. |
| `docs/powerunits_repo_b_read_operator_v1.md` | Repo B allowlisted read (`read_powerunits_repo_b_allowlisted`); env-gated. |
| `config/powerunits_repo_b_read_allowlist.json` | v1 keys → Repo B paths (authoritative for that tool). |

---

## Post-change deploy verification (Trusted Analyst still on)

Run this block **first** after any Railway deploy or variable edit:

- [ ] `HERMES_POWERUNITS_RUNTIME_POLICY` is exactly `first_safe_v1` (Railway env for this service).
- [ ] `config.yaml` on the instance (under `HERMES_HOME`, e.g. `/opt/data`) shows Powerunits policy as expected: Telegram toolsets match the bounded set (see `docker/apply_powerunits_runtime_policy.py` / gateway lockdown behavior).
- [ ] Logs: gateway starts **telegram**; no stack trace loop; **no** full `DATABASE_URL*` or token strings in stdout/stderr.
- [ ] Telegram: bot answers; `/help` or equivalent shows only **bounded** tools (no web/terminal/MCP surge “for debugging”).
- [ ] **If Repo B read is supposed to be live:** `HERMES_POWERUNITS_REPO_B_READ_ENABLED` truthy **and** GitHub read token set; run the **Repo B read** subsection below.

If any item fails → treat as **not** Trusted Analyst until fixed; do not widen toolsets to “unblock”.

---

## Startup checks

- [ ] Service reaches healthy / listening state within expected window.
- [ ] One log line confirms messaging platform init for **Telegram** (not a disabled platform).
- [ ] Disk/volume mount for `HERMES_HOME` present if workspace is required.

---

## Telegram checks

- [ ] Inbound message from an **allowlisted** operator identity gets a reply.
- [ ] `/new` or session reset still works if you rely on it for clean tests.
- [ ] Bot cannot invoke tools outside first_safe (e.g. no generic web search if not in allowlist).

---

## GitHub docs checks (primary knowledge)

- [ ] Ask Hermes to use the GitHub docs path for a **known allowlisted** file; content is non-empty and plausible.
- [ ] If GitHub is intentionally down: Hermes should **not** silently pretend live GitHub — expect error or explicit fallback messaging per tool behavior.

---

## Bundled docs (fallback only)

- [ ] If bundle is configured: a read returns explicit **bundled** / snapshot semantics when used.
- [ ] If bundle is absent: primary path remains GitHub; no crash.

---

## Bounded Timescale checks (optional but live when gated)

- [ ] `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` truthy **and** `DATABASE_URL_TIMESCALE` set **iff** you expect the tool.
- [ ] Valid call: `read_powerunits_timescale_dataset` with allowed `pattern_id`, `country_code`, `version`, `window_id` → JSON payload with `data_plane: timescale` / bounded fields.
- [ ] Row cap: request `row_limit` above max → **rejected** (fail closed), not truncated silently against policy.

---

## Bounded Repo B read (supplemental; live only when gated)

Tool: `read_powerunits_repo_b_allowlisted` — **GitHub API only**, **key-only** (allowlist: `config/powerunits_repo_b_read_allowlist.json`). Primary knowledge remains **GitHub docs reader**; this is extra surface for allowlisted implementation paths.

### Checklist

- [ ] **Feature gate:** With `HERMES_POWERUNITS_REPO_B_READ_ENABLED` unset/false, a `read_repo_b_key` call returns a clear **disabled** / missing-feature error (not a GitHub stack trace to the user).
- [ ] **Gate on:** With flag **true** and `POWERUNITS_GITHUB_TOKEN_READ` (or legacy docs token) set, tool appears in the bounded tool surface (same `first_safe_v1` set as other Powerunits tools).
- [ ] **`list_repo_b_keys`:** `action=list_repo_b_keys` returns JSON with `surface: powerunits_repo_b_read` and keys from `config/powerunits_repo_b_read_allowlist.json` only (must include `job_market_feature` and v2 samples such as `job_entsoe_market`, `adr_010_weather_ingestion_mvp` — see current allowlist version in that file).
- [ ] **Allowed read:** `action=read_repo_b_key`, `key=implementation_state` returns JSON with non-empty `content` and `path` matching allowlist (`docs/implementation_state.md`).
- [ ] **Unknown key (negative):** `action=read_repo_b_key`, `key=__nonexistent_key__` → error JSON (`unknown` / invalid key); no partial file body.
- [ ] **No free path:** Confirm tool schema / `/help` description has **no** `path` / `repo` / free-form file argument — only `action`, optional `key`, optional `max_output_chars` (see `docs/powerunits_repo_b_read_operator_v1.md`).

### Smoke prompts (copy for internal / Telegram test)

Use **`read_powerunits_repo_b_allowlisted`** (not `read_powerunits_doc`). Doc manifest keys use `*.md` names; Repo B allowlist uses **snake_case** keys (`job_market_feature`, …).

1. **List Repo B allowlist keys** — `{"action": "list_repo_b_keys"}` → JSON with `surface: powerunits_repo_b_read`, `key_namespace: repo_b_allowlist_snake_case`, keys include `job_market_feature`.
2. **Happy read** — `{"action": "read_repo_b_key", "key": "implementation_state"}` (expect markdown body in `content`).
3. **Reject** — `{"action": "read_repo_b_key", "key": "__nonexistent_key__"}` (expect JSON error, no secrets).
4. **Wrong-tool check** — `read_powerunits_doc` with `{"action": "list_keys"}` → keys look like `implementation_state.md` and `surface: powerunits_doc_key_manifest` — **different** from step 1.

### Rollback (Repo B read only)

- [ ] Set `HERMES_POWERUNITS_REPO_B_READ_ENABLED` to **falsy** or remove it; redeploy or restart if your platform caches env — tool should disappear or return disabled without touching Repo B or GitHub.

---

## Fail-closed / negative checks

- [ ] Invalid `pattern_id` or `window_id` → error JSON, no raw SQL exposure.
- [ ] Unknown country or version → error, no query broadening.
- [ ] With Timescale gate **off**: tool absent from definitions or handler returns disabled message — **not** a connection leak stack to the client.
- [ ] **Repo B read:** unknown key and disabled gate — covered in **Bounded Repo B read** above (avoid duplicating full matrix here).

---

## Rollback basics

- [ ] **Webhook:** point Telegram webhook back to last-known-good Hermes URL (previous Railway service / project) if this service is bad.
- [ ] **Timescale:** set `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` to falsy / unset to drop DB reads without redeploying Hermes logic.
- [ ] **Repo B read:** unset or falsify `HERMES_POWERUNITS_REPO_B_READ_ENABLED` (see Repo B read subsection).
- [ ] **Policy:** do not remove `first_safe_v1` casually; rollback to prior image/env snapshot per your Railway practice, then re-run this validation pack.

---

*Tick boxes in copy/paste or your ticket tracker; keep evidence (timestamp + operator) for production-impacting changes.*
