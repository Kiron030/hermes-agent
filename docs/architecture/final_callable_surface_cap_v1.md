# Final Callable-Surface Cap — Design Note

Status: implemented
Config field: `agent.final_allowed_toolsets`
Core seam: `model_tools._compute_tool_definitions`

## Purpose

Hermes resolves a session's tool surface from several inputs that a deployment
operator does not fully control: the catalog default, caller-supplied
`enabled_toolsets`, the `all` / `*` alias, and plugin toolsets that
default-enable themselves when the operator never declared them. Each of those
is a legitimate feature. Together they mean there is no place an operator can
stand and say "whatever else happens, this session cannot call a shell."

`agent.disabled_toolsets` does not solve it: subtraction only removes what you
can enumerate ahead of time, and a plugin registered next week is not in that
enumeration.

This is a positive upper bound instead. It is deliberately small — one config
read and one set intersection at the point where the tool surface stops being
negotiable.

## Semantics

Normal resolution runs first and unchanged:

```
catalog defaults / enabled_toolsets  →  kanban injection  →  disabled_toolsets
```

Then, only if `agent.final_allowed_toolsets` is configured:

```
resolved_tools = resolved_tools ∩ tools(final_allowed_toolsets)
```

and the result goes to `registry.get_definitions`, which applies `check_fn` as
usual.

| Config value | Behaviour |
| --- | --- |
| key absent, or `null` | No cap. Upstream-equivalent. |
| list of toolset names | Surface is intersected with the tools those toolsets resolve to. |
| `[]` | A declared, empty allowlist. Surface is empty. |
| bare string | Treated as a single-entry list. |
| any other type | Empty allowlist, with a warning. Fail-closed. |
| entry naming no known toolset | Contributes no tools, with a warning. Never "allow everything". |
| `all` / `*` | Resolves to every toolset — equivalent to no cap. |

Legacy `*_tools` names resolve in the cap exactly as they do when enabling, so
the cap and the enable path never disagree about what a name means.

## Why the cap is read from config, not passed in

This is the load-bearing design decision, and it is the reason a config-only
solution was insufficient.

Every widening path the cap exists to bound arrives as an argument to
`get_tool_definitions` or as registry state:

- a caller constructing its own `enabled_toolsets` list,
- `--toolsets all`, which reaches the seam as `enabled_toolsets=None`,
- `hermes_cli.tools_config._get_platform_tools`, which adds plugin toolsets the
  operator never declared and hands the widened list to the gateway,
- any in-process consumer that calls `get_tool_definitions` directly.

A cap accepted as a parameter would be supplied by exactly the callers it is
meant to bound, so it would be a convention rather than a guarantee. Reading it
from config inside the seam makes it structurally impossible for a caller to
raise its own ceiling: there is no argument to pass, and the one code path that
produces tool definitions consults it unconditionally.

The corollary is that the enforcement is central rather than per-transport.
There is no Telegram case, no gateway case, no CLI case. `_compute_tool_definitions`
is the single producer of tool definitions, so capping it once covers every
consumer — including the `tool_search` bridge, which reads its catalog through
`get_tool_definitions(..., skip_tool_search_assembly=True)` and therefore
inherits the cap for both what it can surface and what it can invoke.

## Cache

No cache-key change was required.

`get_tool_definitions` memoizes on a key that already includes `cfg_fp`, a
`(st_mtime_ns, st_size)` fingerprint of the config file. The cap is read from
that same file, so editing it changes the fingerprint and misses the memo. This
is verified mechanically by `test_editing_the_cap_invalidates_the_memo`, which
does not clear the tool-definitions memo between the two reads.

The non-memoized path (`quiet_mode=False`) computes the cap on every call and is
covered by `test_cap_applies_without_quiet_mode`.

Prompt-cache invariants are unaffected: the cap is resolved during tool
resolution, not by rebuilding a toolset or prompt mid-conversation.

## Tests

- `tests/test_final_toolset_cap.py` — the generic contract: absent-cap
  equivalence, caller override, `all` / `*`, narrow-caller-stays-narrow,
  never-adds, disabled-not-resurrected, unknown and malformed entries, legacy
  names, the pre-assembly catalog consumer, memo invalidation, and a source-level
  check that the two cap helpers name no product domain.
- `tests/r2_powerunits_plugin/test_final_cap_integration.py` — acceptance
  against a real third-party plugin that default-self-expands: unlisted plugin
  disappears from the final surface (including under `--toolsets all` and via
  the self-expansion path), allowlisted plugin stays visible *and* dispatchable,
  and the no-cap case still reproduces the prior baseline.

Removing the intersection from `model_tools` fails twelve of the generic tests;
the ones that still pass are the absent-cap equivalence cases, which describe
upstream behaviour and are expected to hold either way.

## Scope

The cap is domain-agnostic. `model_tools._read_final_toolset_cap` and
`model_tools._resolve_final_allowed_tools` know only about config, toolsets, and
tool names.

This note does not change the pre-existing env-gated clamp in the same function
(`HERMES_POWERUNITS_RUNTIME_POLICY`). That clamp is a fork-local overlay with its
own domain imports and its own tests; it is untouched here, and collapsing it
onto this generic primitive is separate work.

## Upstreamability

**HIGH.** The feature is a general operator control with no fork-specific
concepts, it is inert unless configured, it adds one config key alongside the
existing `agent.disabled_toolsets`, and it needed no change to the cache key or
to any call site. The only fork-flavoured artifact is the acceptance test, which
uses a real plugin as a fixture and would be replaced by a synthetic plugin
upstream.
