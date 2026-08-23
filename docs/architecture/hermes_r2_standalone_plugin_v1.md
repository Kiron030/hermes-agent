# R2 — Standalone PowerUnits Plugin / Thin Adapter

**Slice:** R2  
**Base:** `origin/powerunits-internal-setup` @ `fc1700ccebe8a87f527084c7ba848aa8d0b7c692`  
**Status:** standalone-plugin proof — no production mutation, no shared-core patch

```text
PREFLIGHT
SLICE              = R2
BASE_SHA           = fc1700ccebe8a87f527084c7ba848aa8d0b7c692
R1_PRESENT         = YES
GATE_1_CLOSED      = YES
SCOPE_CONFIRMED    = YES
BLOCKERS           = NONE
EXPECTED_FILES     =
  standalone/powerunits/plugin.yaml
  standalone/powerunits/__init__.py
  standalone/powerunits/operations.py
  standalone/powerunits/host.py
  standalone/powerunits/client.py
  standalone/powerunits/schemas.py
  standalone/powerunits/tools.py
  tests/r2_powerunits_plugin/
  docs/architecture/hermes_r2_standalone_plugin_v1.md
```

R1 remains closed and unpatched:

```text
GATE_1                      = CLOSED
CLAMP_EQUIVALENCE           = PATCH_REQUIRED
CLAMP_IMPLEMENTATION_CLASS  = THIN_CORE_PATCH
FUTURE_CORE_PATCH           = NOT_IMPLEMENTED
```

R2 does **not** hide that fact and does **not** implement the generic final-cap patch.

---

## Architecture proved

```text
Modern Hermes
   ↓
standalone PowerUnits plugin   (standalone/powerunits)
   ↓
ONE generic bounded client     (operation_id + typed JSON)
   ↓
existing Repo-B bounded API    /internal/hermes/bounded/v1/<operation>
```

Repo B remains authoritative. Plugin-side checks fail early on empty or unknown
fields; they never turn an invalid operation into an authoritative valid one.

```text
PLUGIN_API                 = ctx.register_tool (official PluginContext)
PLUGIN_LOCATION            = standalone/powerunits
PLUGIN_API_CORE_PATCH_REQUIRED = NO
```

The plugin is an isolated directory outside shared Hermes core
(`agent/`, `tools/`, `hermes_cli/`, `plugins/`). It is loaded in tests through
the official **user-plugin** path (`$HERMES_HOME/plugins/powerunits` +
`plugins.enabled`). No PowerUnits-specific Hermes-core code was added.

---

## Operations

Four read-only operations. No fifth write was added.

| Plugin tool | R0 wrapper | Route suffix | Effect |
|---|---|---|---|
| `read_powerunits_coverage_snapshot_v1` | `tools.powerunits_bounded_coverage_snapshot_tool` | `/internal/hermes/bounded/v1/coverage-snapshot` | READ |
| `inventory_powerunits_bounded_coverage_v1` | `tools.powerunits_bounded_coverage_inventory_tool` | `/internal/hermes/bounded/v1/coverage-inventory` | READ |
| `read_powerunits_entsoe_bzn_price_readiness_v1` | `tools.powerunits_entsoe_bzn_price_readiness_tool` | `/internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read` | READ |
| `readiness_powerunits_option_d_bounded_window` | `tools.powerunits_option_d_readiness_tool` | `/internal/hermes/bounded/v1/market-features-hourly/readiness-window` | READ |

```text
OPERATIONS       = the four rows above
OPERATION_COUNT  = 4
EFFECT_CLASS     = READ
WRITES           = NONE
```

Inventory workspace-CSV persist from the old wrapper is **not** carried over
(write-adjacent). That is a schema narrowing, not a domain-contract regression.

Option D does **not** re-own PL/24h domain rules. Empty required fields fail
early; Repo B remains authoritative for country/window validity.

---

## Generic client

```text
GENERIC_BOUNDED_CLIENT = PASS
```

One client (`standalone/powerunits/client.py`):

- caller contract: `operation_id` + typed JSON body
- route suffix comes only from the frozen registry
- HTTPS only; HTTP is refused and not upgraded
- exact hostname match (suffix hosts rejected)
- Bearer stays inside the client
- `X-Correlation-ID` generated and preserved
- response redaction + size limit + timeout
- structured safe errors (`unknown_operation_id`, host/https refusals)

Host-pinning reuses S0-C env names and semantics. The plugin default pin mode
is `enforce` (R2 contract). Core wrappers are unchanged and still default to
`warn`.

---

## R0 field compatibility

Compared against `tests/powerunits_golden/contracts.py` via
`handle_function_call` (not wrapper imports). HTTP mocked.

| operation | schema diff | response-field diff |
|---|---|---|
| coverage snapshot | `additionalProperties=false` | `chat_summary` kept; `effect_class=READ` added |
| coverage inventory | export/CSV persist removed | `chat_summary` + `hermes_statement` kept |
| BZN price readiness | `additionalProperties=false` | `correlation_id` + operator note kept |
| Option D readiness | no local domain authority | `correlation_id` kept |

```text
R0_FIELD_COMPATIBILITY = PASS
```

No material domain-contract regression. Implementation is not byte-identical.

---

## Registration and dispatch

Official path: `PluginManager.discover_and_load` → `register(ctx)` →
`ctx.register_tool(...)`.

Dispatch path: `model_tools.handle_function_call` after registration.

```text
PLUGIN_REGISTERED      = YES
PLUGIN_DISPATCH_PROVEN = YES
```

Registered surface (check_fn true when family gate + Base URL + secret are set):

| tool name | toolset | check_fn |
|---|---|---|
| `read_powerunits_coverage_snapshot_v1` | `powerunits_bounded_reads` | env gate + origin + secret |
| `inventory_powerunits_bounded_coverage_v1` | `powerunits_bounded_reads` | env gate + origin + secret |
| `read_powerunits_entsoe_bzn_price_readiness_v1` | `powerunits_bounded_reads` | env gate + origin + secret |
| `readiness_powerunits_option_d_bounded_window` | `powerunits_bounded_reads` | env gate + origin + secret |

Schemas: `additionalProperties: false`. No `url` / `host` / `route` / `path` / `sql`.

---

## Unpatched clamp — honest result

Tested against this fork **without** `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`,
i.e. the unpatched upstream enabled/disabled path. The future generic core
patch was **not** implemented.

```text
PLUGIN_VISIBLE_WHEN_EXPLICITLY_ALLOWED = YES
PLUGIN_VISIBLE_WHEN_NOT_DECLARED       = NO
PLUGIN_DEFAULT_SELF_EXPANSION          = YES
PLUGIN_CAP_RUNTIME                     = REQUIRES_KNOWN_THIN_CORE_PATCH
KNOWN_FINAL_CLAMP_PATCH_STILL_REQUIRED = YES
```

`get_tool_definitions(enabled=["memory","todo"])` hides the plugin toolset.
`hermes_cli.tools_config._get_platform_tools` still self-adds unknown plugin
toolsets (`known_plugin_toolsets` empty → default enabled). `--toolsets all`
(`enabled=None`) still reopens the full surface.

This is the R1 finding, now reproduced with a real plugin:

```text
MINIMUM_ENFORCEMENT_SEAM =
  model_tools._compute_tool_definitions
  FINAL POSITIVE INTERSECTION against a declared operator allowlist
  after normal enabled/disabled resolution and before registry definitions.
  Domain-agnostic. No PowerUnits / Telegram / Repo-B logic.
```

This does **not** invalidate the standalone plugin architecture.
It means GATE_2 stays pending the already-known XS clamp follow-up.

Do not claim the cap is enforced. It is not.

---

## Host / schema negatives

All HTTP mocked. No live Repo-B call.

| Case | Result |
|---|---|
| foreign host | `execute_target_host_refused` |
| evil suffix host (`allowed.evil.com`) | `execute_target_host_refused` |
| `http://` | `execute_target_https_required` |
| unknown `operation_id` | `unknown_operation_id` |
| `path` / `url` / `sql` in body | `unexpected_field`, no POST |
| arbitrary path | impossible — suffix is registry-only |

```text
HOST_PINNING            = PASS
ARBITRARY_URL_EXPOSED   = NO
ARBITRARY_PATH_EXPOSED  = NO
SQL_EXPOSED             = NO
LIVE_NETWORK_USED       = NO
PRODUCTION_CREDENTIALS_USED = NO
REPO_B_CHANGED          = NO
```

---

## Wrapper-collapse measurement

Old wrappers were **not** deleted.

```text
CURRENT_WRAPPER_FILES                      = 35
CURRENT_POWERUNITS_TOOL_FILES              = 55
R2_PLUGIN_SHARED_CLIENTS                   = 1
R2_PLUGIN_TOOL_FILES                       = 1
ESTIMATED_WRAPPERS_REPLACEABLE             = 35
ESTIMATED_SHARED_CORE_POWERUNITS_REDUCTION = 37
```

35 `tools/powerunits_*tool*.py` files each implement HTTP (httpx +
`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`). The complete bounded HTTP surface
can move onto this one-client pattern. Two shared support modules
(`powerunits_execute_base_url_v1.py`, `powerunits_bounded_family_gates.py`)
become unused once that move is complete. Remaining non-HTTP PowerUnits
tool files (workspace, docs, preflight, campaigns-as-loops) are later slices.

---

## Tests

```text
TESTS = tests/r2_powerunits_plugin
        32 passed
```

| File | Proof |
|---|---|
| `test_registration.py` | official `register(ctx)` + toolset discovery |
| `test_dispatch.py` | `handle_function_call` for all four tools |
| `test_client_security.py` | host / HTTP / unknown op / transport-field negatives |
| `test_schema_negatives.py` | no URL/host/path/SQL in schemas |
| `test_r0_compat.py` | R0 happy fields + `feature_disabled` |
| `test_clamp_visibility.py` | unpatched visibility + self-expansion |
| `test_wrapper_collapse.py` | measurement only |

---

## Security notes / rollback

```text
SECURITY_NOTES =
  model cannot choose host/path/URL/SQL;
  exact host pin; HTTPS only; bearer not returned;
  unknown fields rejected; Repo B remains authoritative.
ROLLBACK =
  remove standalone/powerunits and tests/r2_powerunits_plugin;
  production fork wrappers unchanged.
```

---

## Gate

```text
GATE_2_STATUS = PENDING_KNOWN_THIN_CLAMP
```

R2 PASSes as a standalone-plugin proof (acceptance 1–8). Formal GATE_2
closure waits for the already-identified domain-agnostic XS clamp patch.
That patch is **not** this slice.

```text
NEXT = THIN_CLAMP_XS
```

Do not start R3 from this slice.

---

## Handover

```text
R2_STATUS = PASS

BASE_SHA  = fc1700ccebe8a87f527084c7ba848aa8d0b7c692
FINAL_SHA = (set at commit)

PLUGIN_API      = ctx.register_tool
PLUGIN_LOCATION = standalone/powerunits

OPERATIONS      = read_powerunits_coverage_snapshot_v1,
                  inventory_powerunits_bounded_coverage_v1,
                  read_powerunits_entsoe_bzn_price_readiness_v1,
                  readiness_powerunits_option_d_bounded_window
OPERATION_COUNT = 4

GENERIC_BOUNDED_CLIENT = PASS

R0_FIELD_COMPATIBILITY = PASS
HOST_PINNING           = PASS
ARBITRARY_URL_EXPOSED  = NO
ARBITRARY_PATH_EXPOSED = NO
SQL_EXPOSED            = NO

PLUGIN_REGISTERED      = YES
PLUGIN_DISPATCH_PROVEN = YES

PLUGIN_VISIBLE_WHEN_EXPLICITLY_ALLOWED = YES
PLUGIN_VISIBLE_WHEN_NOT_DECLARED       = NO
PLUGIN_DEFAULT_SELF_EXPANSION          = YES
PLUGIN_CAP_RUNTIME                     = REQUIRES_KNOWN_THIN_CORE_PATCH

PLUGIN_API_CORE_PATCH_REQUIRED         = NO
KNOWN_FINAL_CLAMP_PATCH_STILL_REQUIRED = YES

CURRENT_WRAPPER_FILES          = 35
ESTIMATED_WRAPPERS_REPLACEABLE = 35
ESTIMATED_CORE_REDUCTION       = 37

LIVE_NETWORK_USED              = NO
PRODUCTION_CREDENTIALS_USED    = NO
REPO_B_CHANGED                 = NO

FILES_CHANGED =
  standalone/powerunits/
  tests/r2_powerunits_plugin/
  docs/architecture/hermes_r2_standalone_plugin_v1.md
TESTS          = tests/r2_powerunits_plugin (32 passed)
SECURITY_NOTES = see above
ROLLBACK       = delete the three trees; wrappers stay

GATE_2_STATUS = PENDING_KNOWN_THIN_CLAMP
PR_READY      = YES
NEXT          = THIN_CLAMP_XS
```
