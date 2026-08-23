# R3 — Shadow Comparison / Migration Decision Gate

**Slice:** R3
**Date:** 2026-08-23
**Base:** `origin/powerunits-internal-setup` @ `d7dbb7e64072659d3ebd27aaaee197c91ce3fa6c`
**Worktree:** `W:\cache\hermes-r3` (branch `r3-shadow-comparison`, dedicated — the
parallel R5 tree on `r5-developer-hermes` was never switched or mutated)

R3 measures and decides. It removes no wrapper, removes no clamp, ports no
transport, and changes no production behaviour. Everything below is either a
re-run of frozen R0/R1/R2 evidence or a new measurement produced by the scripts
named in [Reproducing this report](#reproducing-this-report).

```text
GOAL = a supportable migration decision, not a supported migration
```

---

## 1. Preconditions — verified mechanically, not quoted

| Claim | How it was checked | Result |
|---|---|---|
| Base is the canonical integration state | `git fetch origin` then `git rev-parse origin/powerunits-internal-setup` | `d7dbb7e640…` — equals the expected SHA |
| `GATE_0` closed / R0 present | `pytest tests/powerunits_golden -q` | **116 passed** |
| `GATE_1` closed / R1 present | `docs/architecture/hermes_r1_proof_report_v1.md`; pinned tree at `fcbd1076a9…` reachable and bootable (§5) | PRESENT |
| R2 standalone plugin present | `standalone/powerunits/` — 7 files, 1,134 lines | PRESENT |
| `THIN_CLAMP_XS` present | `agent.final_allowed_toolsets` + `_read_final_toolset_cap` + `_resolve_final_allowed_tools` in `model_tools.py` | PRESENT |
| `GATE_2` closed | `pytest tests/test_final_toolset_cap.py tests/r2_powerunits_plugin -q` | **60 passed** |
| Legacy PowerUnits clamp still exists | `HERMES_POWERUNITS_RUNTIME_POLICY` branch in `model_tools._compute_tool_definitions` (`model_tools.py:533–542`) | PRESENT, untouched |
| Packaging follow-up merged | `powerunits_operator_country_scope_v1` in `pyproject.toml` `py-modules` (line 346) | PRESENT |

```text
GATE_0 = CLOSED
GATE_1 = CLOSED
GATE_2 = CLOSED
R3_BASE_READY = YES
```

The prior packaging omission is recorded as **discovered and remediated
migration debt**, not as a current modern-runtime defect.

---

## 2. Systems under comparison

Only what has actually been proved is compared.

```text
A. CURRENT_FORK
   this fork's built-in tools/powerunits_* wrappers
   + the PowerUnits-specific first_safe clamp (HERMES_POWERUNITS_RUNTIME_POLICY)
   + fork-local toolset registration in toolsets.py
   → the R0 golden baseline

B. MODERN_HERMES_PROOF
   pinned upstream Hermes v2026.8.19 (0.20.5) @ fcbd1076a9…
   + standalone/powerunits plugin via the official ctx.register_tool path
   + ONE generic bounded client (operation_id + typed JSON)
   + agent.final_allowed_toolsets as the final positive cap
   + the existing, unchanged Repo-B bounded API
```

Two measurement planes, deliberately kept apart:

- **In-process A/B** — both architectures in one interpreter against one
  registry, so a difference is architecture and not runtime version.
  (`tests/r3_shadow_comparison`)
- **Pinned-runtime probe** — the modern half on the real pinned upstream tree
  with its own venv, importing nothing from this fork.
  (`scripts/r3_shadow_comparison/modern_runtime_probe.py`)

---

## 3. Representative operator corpus

Built from operator intents R0/R2 already cover. One argument dict per intent,
taken from the frozen R0 contracts, dispatched on both systems. No prompt was
tuned toward either side.

| # | Intent | CURRENT_FORK tool | MODERN tool |
|---|---|---|---|
| 1 | coverage snapshot / data health | `read_powerunits_coverage_snapshot_v1` | same name, plugin-owned |
| 2 | coverage inventory | `inventory_powerunits_bounded_coverage_v1` | same name, plugin-owned |
| 3 | ENTSO-E BZN price readiness | `read_powerunits_entsoe_bzn_price_readiness_v1` | same name, plugin-owned |
| 4 | model / readiness window | `readiness_powerunits_option_d_bounded_window` | same name, plugin-owned |
| 5 | methodology / documentation | `read_powerunits_doc` | **none — gap** |

Source: `tests/r3_shadow_comparison/corpus.py`.

Case 5 is a real, named gap: R2 ported the four bounded HTTP reads only. The
docs surface is not a bounded Repo-B operation, so it is neither in the plugin
nor reachable under a cap that allows only `powerunits_bounded_reads`.

---

## 4. Correctness

### 4.1 Wire parity — what each system actually sends

HTTP is mocked on both sides with the same recorder and the same canned Repo-B
body. Both sides dispatch through `model_tools.handle_function_call`.

| Case | Route identical | Host identical | Request body identical |
|---|---|---|---|
| coverage snapshot | YES | YES | YES |
| coverage inventory | YES | YES | YES |
| BZN price readiness | YES | YES | YES |
| Option D readiness window | YES | YES | YES |

All four R0 `happy_fields` sets are satisfied on **both** systems.

```text
R0_FIELD_COMPATIBILITY = PASS (4/4 ported operations)
WIRE_PARITY            = PASS (4/4 route + host + body identical)
```

### 4.2 Response-field deltas — where the modern side is not equivalent

This is the honest part. Field sets are relative to one identical canned Repo-B
payload, so these are implementation deltas, not Repo-B differences.

| Case | Fork-only response fields | Modern-only response fields |
|---|---|---|
| coverage snapshot | — | `effect_class`, `http_status` |
| BZN price readiness | — | `effect_class`, `http_status`, `surface` |
| coverage inventory | `csv_export`, `hint_export`, `repository_response_content_type`, `repository_response_preview`, `request_echo` | `correlation_id`, `effect_class`, `http_status_from_repo_b`, `pipeline_run_id`, `read_attempted`, `rows_written` |
| Option D readiness | `checks`, `dominant_blocker`, `explanation`, `http_ok`, `readiness_go`, `reason_codes`, `response_body_summary`, `warnings` | `effect_class`, `http_status_from_repo_b`, `pipeline_run_id`, `read_attempted`, `rows_written` |

Two of these matter and one does not:

- **Option D is a genuine semantic loss.** `readiness_go`, `dominant_blocker`,
  `reason_codes` and `explanation` are the operator-facing *verdict*. The fork
  wrapper derives them locally; the plugin deliberately does not re-own domain
  rules (R2 §Operations) and returns the Repo-B payload. The question "is the
  window usable?" is therefore answered by the fork and only *supported* by the
  modern side. This is a migration condition, not a defect in the plugin design:
  the verdict belongs in Repo B or in a plugin projection, and until it lives in
  one of them this operation is not at parity.
- **Coverage inventory's CSV/export fields** were removed on purpose as
  write-adjacent (R2 §Operations). Schema narrowing, not a contract regression.
- **The added fields** (`effect_class`, `http_status*`, `read_attempted`) are
  provenance, and are additive.

### 4.3 Failure behaviour and determinism

| Property | CURRENT_FORK | MODERN |
|---|---|---|
| gate off → `feature_disabled`, zero POSTs | PASS | PASS (R2 `test_r0_compat`) |
| transport field in args → refused pre-HTTP | PASS (schema) | PASS, `unexpected_field`, zero POSTs |
| unknown `operation_id` | not expressible | `unknown_operation_id` |
| `http://` origin | refused | `execute_target_https_required`, zero POSTs |
| suffix host `…example.test.evil.invalid` | refused | `execute_target_host_refused`, zero POSTs |
| correlation ID present and preserved | YES | YES |
| determinism | route/host/body deterministic | route/host/body deterministic; `correlation_id` is a fresh UUID by design |

```text
CORRECTNESS = MIXED
  4/5 corpus intents answered by both, with identical wire semantics
  1/5 corpus intent (methodology) unported
  2/4 ported operations lose fork-local derived or export fields
```

---

## 5. Security / authority

### 5.1 The generic cap on the real pinned runtime

The modern half was run on the pinned upstream tree at `fcbd1076a9…` with its
own venv. `sys.modules` was checked for leaked fork modules.

| Property | Measured |
|---|---|
| runtime under test | `W:\cache\hermes-r3-modern\model_tools.py` (pinned v0.20.5) |
| fork modules leaked into runtime | **none** |
| PowerUnits references in the patched runtime `model_tools.py` | **0** |
| cap helpers present | YES |
| production-authority env names present | **none** |
| plugin loaded via official discovery | YES, 4 tools registered |
| boot | 2,826 ms |
| plugin load | 250 ms |

Control, then bound:

| State | Callable catalog | Unsafe families present | Plugin visible |
|---|---|---|---|
| **uncapped** (as R1/R2 found it) | 42 | **9** — `delegate_task`, `execute_code`, `patch`, `process`, `read_file`, `search_files`, `session_search`, `terminal`, `write_file` | 4 |
| **capped**, `enabled=None` (`--toolsets all`) | 4 | 0 | 4 |
| **capped**, caller demands `terminal`/`file`/`delegation`/`browser` | 4 | 0 | 4 |
| **capped** to `memory`, plugin self-expands | — | 0 | **0** |
| **capped**, narrow caller asks `memory` only | 0 | 0 | 0 |

```text
CALLER_OVERRIDE_BLOCKED        = YES
TOOLSETS_ALL_BLOCKED           = YES
PLUGIN_SELF_EXPANSION_BLOCKED  = YES
NARROW_CALLER_STAYS_NARROW     = YES
DISABLED_TOOLS_NOT_RESURRECTED = YES   (tests/test_final_toolset_cap.py)
ENFORCED_ON_PINNED_UPSTREAM    = YES
```

The uncapped row is the control that makes the capped rows mean something: the
same runtime, one config key apart, differs by 38 tools and nine high-authority
families.

### 5.2 Where the refusal lives

| | CURRENT_FORK | MODERN |
|---|---|---|
| enforcement point | `model_tools._compute_tool_definitions`, env-keyed | `model_tools._compute_tool_definitions`, config-keyed |
| enforcement input | `HERMES_POWERUNITS_RUNTIME_POLICY` + capability tier + Telegram overlay | `agent.final_allowed_toolsets` |
| imports into shared core | `powerunits_capability_tier`, `powerunits_telegram_overlays` | none |
| domain terms in the enforcing helpers | PowerUnits, Telegram, tier | **none** (asserted at source level) |
| operator can declare a bound without a code change | no | yes |
| bounds a plugin registered next week | no (subtractive enumeration) | yes (positive intersection) |

Both hold at every tier. `tests/r3_shadow_comparison/test_security_parity.py`
asserts the fork clamp still bounds tiers 0–6 with zero unsafe leakage, and that
R3 did **not** remove it.

### 5.3 Transport authority

| | CURRENT_FORK | MODERN |
|---|---|---|
| model can name host / URL / path / SQL | no | no |
| `additionalProperties: false` on the four schemas | **absent on all four** (unset) | **`false` on all four** |
| declared parameters on those schemas | 4 / 8 / 4 / 5 | 4 / 5 / 4 / 5 |
| host pin default | `warn` (core wrappers) | `enforce` (plugin contract) |
| bearer reachable by the model | no | no |
| Repo B authoritative for domain validity | yes | yes, and the plugin owns strictly less |
| bounded write surface added by R2/R3 | — | **none** |

`enforce`-by-default is a real hardening, and the narrower plugin schemas are a
smaller attack surface than the wrappers they would replace.

```text
SECURITY = PASS for MODERN, on operator authority
```

**Explicitly not counted here:** R5 developer isolation. R5's original
process-constructed-env boundary was independently rejected
(`PROCESS_CONSTRUCTED_ENV = INSUFFICIENT`) and is under remediation toward a
dedicated Windows OS principal. It is not operator security and is not scored as
a pass.

---

## 6. Maintainability

Exact counts, `scripts/r3_shadow_comparison/measure_migration_cost.py`.

### 6.1 PowerUnits code owned today

| Surface | Files | Lines |
|---|---|---|
| top-level fork modules `powerunits_*.py` | 5 | 774 |
| `tools/powerunits_*.py` — total | 72 | 24,748 |
| … of which tool modules (`*tool*.py`) | 55 | — |
| … of which shared support modules | 17 | — |
| … R2's wrapper definition (httpx **and** execute Base URL) | **35** | 12,165 |
| … all HTTP-touching files (broader marker) | 44 | 14,781 |
| … non-HTTP (workspace, docs, preflight, campaigns) | 28 | 9,967 |
| PowerUnits-aware tests | 95 | 29,846 |

R2's `CURRENT_WRAPPER_FILES = 35` and `CURRENT_POWERUNITS_TOOL_FILES = 55`
reproduce exactly under the same definitions; the 44 is a broader marker set that
also catches the shared support modules.

### 6.2 Domain knowledge inside generic shared core

Lines mentioning `powerunits` in files that are otherwise upstream's:

| Shared-core file | PowerUnits lines |
|---|---|
| `toolsets.py` | **253** |
| `gateway/run.py` | 30 |
| `hermes_cli/tools_config.py` | 13 |
| `hermes_cli/web_server.py` | 12 |
| `model_tools.py` | 9 |
| `gateway/config.py` | 8 |
| `hermes_cli/banner.py` | 7 |
| `hermes_cli/commands.py` | 4 |
| `gateway/slash_commands.py` | 4 |
| `tools/registry.py` | 1 |
| **total** | **10 files, 341 lines** |

`toolsets.py` is the dominant seam, not `model_tools.py`. The plugin does not
touch it at all: `ctx.register_tool` carries its own toolset name, so a migrated
operation removes shared-core lines rather than adding them.

### 6.3 What the modern architecture owns instead

| Surface | Files | Lines | Domain-specific |
|---|---|---|---|
| `standalone/powerunits/` plugin | 7 | 1,134 | yes — but outside shared core |
| generic cap in `model_tools.py` | 1 | 96 | **no** |
| cap design note | 1 | 132 | no |
| cap tests | 2 | 494 | one uses the plugin as a fixture |

```text
MODERN_SHARED_CORE_FILES          = 1   (model_tools.py, 2 symbols, 96 lines)
MODERN_DOMAIN_SPECIFIC_CORE_FILES = 0
MAINTAINABILITY = PASS for MODERN, by a wide margin
```

---

## 7. Upstream proximity

Merge base with pinned upstream: `3ef6bbd201…` = upstream **v0.19.0 (2026.7.20)**.
Pinned modern target: `fcbd1076a9…` = upstream **v0.20.5 (2026.8.19)**.

Lockfiles, `website/`, `locales/`, `assets/` and `infographic/` are excluded as
churn that says nothing about maintenance burden.

| Measure | Value |
|---|---|
| fork-owned delta since merge base | 340 files, +66,081 / −1,669 |
| … fork-only new files | 295 files, +63,412 |
| … **modifications to shared upstream files** | **45 files, +2,669 / −1,669** |
| upstream's own delta over the same month | 6,907 files, +1,004,471 / −432,579 |
| **upgrade conflict surface** — shared files the fork *and* upstream both changed | **43 of 45 files, 3,906 fork lines** |

Largest fork-touched shared files: `toolsets.py` (+722/−24), `model_tools.py`
(+125/−6), `agent/transports/chat_completions.py` (+111/−7), `gateway/run.py`
(+98/−16), `hermes_cli/banner.py` (+54/−49). All five also moved upstream.

The fork is one minor release and roughly one month behind, and 43 of the 45
shared files it edits were edited upstream in that same month. Every future
upgrade pays that conflict surface again.

### 7.1 The generic patch, ported to pinned upstream

The load-bearing upstreamability question was answered mechanically rather than
argued: the cap commit's `model_tools.py` diff was applied with `git apply -3` to
a scratch worktree of `fcbd1076a9…`.

| Result | Value |
|---|---|
| final size on pinned upstream | **+96 / −1**, identical to the fork |
| PowerUnits references after porting | **0** |
| residual conflict markers | 0 |
| parses | AST OK |
| enforces on that runtime | YES (§5.1) |
| 3-way conflict hunks | 2 |
| cause of both conflicts | **only** the fork-local PowerUnits clamp sitting next to the seam and the fork's cache-comment edit — not the cap itself |

```text
UPSTREAM_PROXIMITY = PASS for MODERN
UPSTREAMABILITY(cap) = HIGH — one config key, inert unless configured,
                       no cache-key change, no call-site change
```

### 7.2 Upstream-only capability now reachable

Measured on the pinned runtime: with the cap active, this runtime assembles the
`tool_search` bridge, so the model receives **3 meta-tools (2,250 chars,
≈562 est. tokens)** with the 4 capped tools as the searchable catalog behind
them. The bridge inherits the cap — it cannot surface or invoke anything the cap
excluded. Uncapped, the bridge does not assemble and the model sees 42 schemas.

Other upstream surfaces inventoried in R1 and unavailable to the fork's Stage-1
operator profile: `skills`, `browser`, `delegation`, profiles, Bot Mode,
observability.

---

## 8. Agent capability — AVAILABLE vs PROVEN

| Primitive | CURRENT_FORK operator | MODERN available | MODERN proven | Proof |
|---|---|---|---|---|
| bounded PowerUnits reads | yes (37 operations) | yes (4 ported) | yes | R2 + §4 |
| filesystem read/write/search | **denied** | yes | **yes** | R1 tool-dispatch probes; R5 |
| terminal / process | **denied** | yes | **yes** | R1 fail→fix→rerun; R5 |
| git | denied | via terminal | **yes** | R5 |
| test loop | denied | via terminal | **yes** | R5 |
| skills | denied | yes | **yes** | R1 `skills_list` + `skill_view`; R5 |
| `tool_search` bridge | not in operator profile | yes | **yes** | §7.2 |
| delegation | denied | yes | no | inventory only |
| browser / computer use | denied | yes | no | inventory only |
| profiles / Bot Mode / observability | denied | yes | no | documentation only |

```text
CAPABILITY = PASS for MODERN
  AVAILABLE > PROVEN, and the report keeps them apart
```

Additional safe non-production capability is not scored as a fork regression.

---

## 9. Performance

Mocked HTTP, deterministic local paths, no production endpoint was contacted for
timing. 40 iterations per operation after a warm-up call.

### 9.1 Controlled A/B — same process, same registry

| Operation | CURRENT_FORK median | MODERN median | Delta |
|---|---|---|---|
| coverage snapshot | 0.0896 ms | 0.0893 ms | −0.3 % |
| coverage inventory | 0.0878 ms | 0.0885 ms | +0.8 % |
| BZN price readiness | 0.0851 ms | 0.0836 ms | −1.8 % |
| Option D readiness | 0.0911 ms | 0.0832 ms | −8.7 % |

The generic `operation_id` client costs nothing measurable versus 35 bespoke
wrappers. Routing through one client is not a performance argument in either
direction.

### 9.2 Pinned-runtime observation (not a controlled comparison)

On the pinned upstream tree, dispatch medians were 2.03–2.18 ms — roughly 23×
the fork's in-process figure. Different tree, different interpreter, different
core version, so this is a **runtime-version observation, not an architecture
measurement**. Both magnitudes are negligible next to a bounded Repo-B HTTP
round trip. Boot 2,827 ms; plugin load 250 ms.

```text
PERFORMANCE = PASS (neutral) — no architectural penalty found
```

---

## 10. Model cost / token overhead

Characters of serialized tool schema are measured exactly. Tokens are an
estimate at 4 chars/token and are labelled as such. **No dollar figure is given
— the model/provider sample is far too small to support one.**

### 10.1 Like-for-like: the same four operations

| System | Tools | Schema chars | Est. tokens |
|---|---|---|---|
| CURRENT_FORK wrappers | 4 | 7,003 | ≈1,751 |
| MODERN plugin | 4 | 3,389 | ≈847 |
| **reduction** | — | **−51.6 %** | **−51.6 %** |

### 10.2 Whole operator surface, as each is configured today

| System | Tools the model sees | Schema chars | Est. tokens |
|---|---|---|---|
| CURRENT_FORK, first_safe tier 6 | 92 | 82,552 | ≈20,638 |
| MODERN, capped catalog | 4 | 3,389 | ≈847 |
| MODERN, `tool_search` bridge (what is actually sent) | 3 | 2,250 | ≈562 |

The second table is **not** like-for-like: the modern figure is small partly
because R2 ported 4 of 37 bounded operations. It is a configuration and scope
statement, not a compression claim. Only §10.1 is a fair per-operation
comparison, and the bridge in §7.2 is what makes the surface size stop scaling
with the catalog.

```text
MODEL_COST = PASS for MODERN
  −51.6 % schema bytes per equivalent operation (exact)
  token figures are estimates; no cost extrapolation is claimed
```

### 10.3 Fork surface growth by tier

| Tier | Callable | Unsafe leaked |
|---|---|---|
| 0 | 57 | none |
| 1 | 59 | none |
| 2 | 64 | none |
| 3 | 70 | none |
| 4 | 76 | none |
| 5 | 84 | none |
| 6 | 92 | none |

Reproduces R0's frozen tier counts exactly — the fork clamp is sound; it is just
expensive and domain-coupled.

---

## 11. Developer experience

R5's capability evidence is used; R5's isolation claim is not.

| Dimension | Evidence | Status |
|---|---|---|
| filesystem RW | R5 | PROVEN |
| terminal | R5 | PROVEN |
| Git | R5 | PROVEN |
| test loop | R5 | PROVEN |
| skills | R5 | PROVEN |
| ordinary workspace micro-approvals | R5 | **0** |
| overall developer experience | R5 | STRONG |
| **production isolation** | independently reviewed | **NOT PROVEN** |

The original boundary was rejected: same Windows principal, host profile
readable, Railway authentication reachable, PATH stubs bypassable.

```text
DEVELOPER_EXPERIENCE = PASS (capability/usability only)
R5_ISOLATION_STATUS  = PARTIAL_PENDING_ISOLATION
  remediation target: DEDICATED_WINDOWS_OS_PRINCIPAL
  HOST_ONLY_SECRET_ROOT = %USERPROFILE%\.powerunits\secrets\
  R5_SECRET_RELOCATION_PLAN = READY
  no production credential rotation required for the active PowerUnits SoT;
  the only historical tracked credential is the legacy trolley PostgreSQL DSN
```

R5 was not a blocker for constructing this comparison, and its isolation is not
scored as a pass. If R5 closes before the human decision, §14's condition C6
falls away; until then the caveat stands.

---

## 12. Migration cost

Nothing was deleted. These are the quantities a migration would move.

| Quantity | Value |
|---|---|
| `CURRENT_WRAPPER_FILES` (R2 definition) | 35 |
| `ESTIMATED_REPLACEABLE_WRAPPERS` | 35 |
| bounded HTTP operations in the R0 contract | 37 |
| … already ported | 4 |
| … **remaining** | **33** |
| non-HTTP PowerUnits tool files (later slices) | 28 |
| shared support modules that become unused after the HTTP move | 2 (`powerunits_execute_base_url_v1.py`, `powerunits_bounded_family_gates.py`) |
| top-level fork modules | 5 (774 lines) |
| shared-core domain lines to retire | 341 across 10 files, of which `toolsets.py` is 253 |
| new plugin files already written | 7 (1,134 lines) |
| **shared-core generic patch surface** | **1 file, 2 symbols, 96 lines, domain-agnostic** |
| PowerUnits-aware test files to re-point | 95 (29,846 lines) |
| remaining legacy-fork seams after a full bounded-read migration | Telegram transport overlay, capability-tier ladder, campaign-as-loop tools, workspace/docs tools |

Deletion and reduction happen **only after** a migration decision. R3 deleted
nothing.

```text
MIGRATION_COST = QUANTIFIED, NON-TRIVIAL
  the expensive part is not the client — it is 33 remaining operations,
  341 shared-core domain lines, and 95 test files
```

---

## 13. Thin-fork decision

R1/R2/Thin-Clamp materially changed the question. The relevant test is not
"is it zero?" but "who owns the remaining generic seam, and how much does it
churn?"

| Criterion | Measured |
|---|---|
| shared files the modern architecture needs | **1** (`model_tools.py`) |
| shared symbols | **2** (`_read_final_toolset_cap`, `_resolve_final_allowed_tools`) |
| shared lines | **96** |
| domain knowledge in that shared code | **none** — asserted at source level and re-verified after porting to pinned upstream |
| ports to pinned upstream cleanly | yes, +96/−1, 0 domain refs, enforces there |
| upstreamability | HIGH — one config key beside `agent.disabled_toolsets`, inert unless set, no cache-key or call-site change |
| expected maintenance burden | one function-sized seam in one file, in a function the fork already edits |

`ZERO_CORE_FORK` is not currently reachable: the cap is not upstream yet, and
without it the plugin's callable surface is not boundable (R1/R2 proved caller
override, `--toolsets all` and plugin self-expansion all defeat config-only
subtraction). It becomes reachable the moment upstream accepts the cap, at which
point the strategy converges to zero without any rework.

```text
FUTURE_CORE_STRATEGY = THIN_GENERIC_FORK
```

This is not a penalty. A 96-line domain-agnostic seam with a credible upstream
path is a categorically different liability from 341 domain lines across 10
shared files plus a 43-file upgrade conflict surface.

---

## 14. Decision

### 14.1 Scorecard

Nine dimensions, 0–5 each, unweighted. The scheme is stated so the reader can
disagree with a specific cell rather than with a verdict.

| Dimension | CURRENT_FORK | MODERN | Why |
|---|---|---|---|
| Correctness | **5** | 3 | fork is the reference and answers all 5 intents; modern answers 4, loses Option D's verdict |
| Security / authority | 3 | **5** | both bound the surface; only modern does it generically, with `enforce` pinning and a 4-tool surface |
| Maintainability | 1 | **5** | 341 shared-core domain lines vs 96 generic ones |
| Upstream proximity | 1 | **5** | 43-file conflict surface vs a patch that applies to pinned upstream |
| Capability | 2 | **4** | operator-bounded vs rich upstream surface, partly PROVEN |
| Performance | 4 | 4 | no measurable architectural delta |
| Model cost | 2 | **4** | −51.6 % schema bytes per equivalent operation |
| Developer experience | 2 | **4** | R5 proven capability, isolation pending |
| Migration cost | **5** | 3 | status quo costs nothing; migration is quantified and non-trivial |
| **Total** | **25 / 45** | **37 / 45** | |

### 14.2 Verdict

```text
MODERN_HERMES_PROOF = PASS
```

Not `STRONG_PASS`. Three things hold it back, all of them named and measured:
the Option D verdict regression, the unported methodology path, and 33 of 37
bounded operations still to move. Not `MIXED` either — the architecture cleared
every security, maintainability and upstream test on a real pinned runtime, and
the correctness gaps are scope and projection gaps rather than design faults.

```text
MIGRATION_RECOMMENDATION = PROCEED_WITH_CONDITIONS
```

| # | Condition |
|---|---|
| C1 | The Option D operator verdict (`readiness_go`, `dominant_blocker`, `reason_codes`, `explanation`) must be owned by Repo B or by an explicit plugin projection **before** that operation migrates. Do not ship a readiness tool that stops answering the readiness question. |
| C2 | A methodology/documentation path must exist under the operator cap before Stage-1 parity is claimed. |
| C3 | Port the remaining 33 bounded operations in slices, each gated on R0 field compatibility and wire parity, using the §4 harness. |
| C4 | Either land `agent.final_allowed_toolsets` upstream, or consciously accept `THIN_GENERIC_FORK` ownership of 96 generic lines. |
| C5 | Collapse the legacy first_safe clamp onto the generic cap only **after** the cap is the sole enforcement path, as its own slice with its own tests. Not in a migration slice. |
| C6 | R5 isolation must close (`DEDICATED_WINDOWS_OS_PRINCIPAL`) before the modern developer runtime is used with production authority. Operator migration does not depend on it. |
| C7 | Telegram transport migration stays out of the bounded-read slices. |

```text
GATE_3 = READY_FOR_HUMAN_DECISION
R4_READY = NO   (R4 requires a human PROCEED first)
```

---

## 15. Threats to validity

Stated so the decision is not read as stronger than the evidence.

- The in-process A/B runs both architectures on **this fork's** interpreter. It
  isolates architecture from runtime version, which is what it is for, but it is
  not a pinned-runtime measurement. §5.1 and §7.1 supply that separately.
- Response-field deltas in §4.2 are relative to one canned Repo-B payload. They
  show which side derives which field, not how Repo B behaves in production.
- Token figures are `chars / 4`. Real tokenizers will differ. No provider was
  called, and no cost is extrapolated.
- §9.2's 23× dispatch difference confounds tree, interpreter and core version.
  It is reported as an observation and is deliberately not used in the scorecard.
- Only 4 of 37 bounded operations are ported. The modern side's small surface is
  partly scope, not only architecture. §10.2 says so explicitly.
- Linux was not exercised. Windows only, as with R0.
- No production endpoint, credential, `.env` file or host credential store was
  read or contacted at any point.

---

## 16. Reproducing this report

```text
# preconditions
pytest tests/powerunits_golden -q                                  # 116 passed
pytest tests/test_final_toolset_cap.py tests/r2_powerunits_plugin -q   # 60 passed

# the R3 comparison harness
pytest tests/r3_shadow_comparison -q

# measurements
python scripts/r3_shadow_comparison/measure_upstream_proximity.py
python scripts/r3_shadow_comparison/measure_migration_cost.py \
    --out docs/architecture/evidence/hermes_r3_migration_cost_v1.json
python scripts/r3_shadow_comparison/emit_evidence.py \
    --out docs/architecture/evidence/hermes_r3_measurements_v1.json

# the modern half on the pinned runtime (needs a pinned-upstream tree + venv)
git worktree add --detach <MODERN_TREE> fcbd1076a93841fa88855acce810e342a5b78101
git diff a1501732b8dd9cfe7ded37a9df932d39c78cfcaf~1 \
         a1501732b8dd9cfe7ded37a9df932d39c78cfcaf -- model_tools.py > cap.patch
git -C <MODERN_TREE> apply -3 cap.patch      # 2 context conflicts, both fork-local
python scripts/r3_shadow_comparison/modern_runtime_probe.py \
    --hermes-root <MODERN_TREE> --plugin-src standalone/powerunits \
    --scratch <SCRATCH> \
    --out docs/architecture/evidence/hermes_r3_modern_runtime_probe_v1.json
```

Artifacts:

| File | Contents |
|---|---|
| `docs/architecture/evidence/hermes_r3_measurements_v1.json` | corpus, tier surfaces, schema cost, dispatch timings, wire parity |
| `docs/architecture/evidence/hermes_r3_modern_runtime_probe_v1.json` | pinned-runtime boot, cap enforcement, dispatch |
| `docs/architecture/evidence/hermes_r3_migration_cost_v1.json` | file/symbol/line counts |

Upstream references: R0 `hermes_r0_golden_behaviour_baseline_v1.md`, R1
`hermes_r1_proof_report_v1.md`, R2 `hermes_r2_standalone_plugin_v1.md`, cap
`final_callable_surface_cap_v1.md`.

---

## 17. What R3 did not do

No wrapper removed. No legacy clamp removed or weakened. No Telegram migration.
No Desktop work. No R4, no R7. No write surface added. No Repo-B change. No
production deployment change. No R5 repair. No credential rotation. No
production `.env`, `app/.env.local`, `scripts/mapbox/.env.local`, `.env.pgurl` or
host credential store was read. No live model call was required, so no human
model smoke was requested.

Changes are additive only: `tests/r3_shadow_comparison/`,
`scripts/r3_shadow_comparison/`, `docs/architecture/evidence/`, and this
document.
