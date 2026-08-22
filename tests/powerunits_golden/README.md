# PowerUnits Golden Behaviour Baseline (R0)

`GOLDEN_BEHAVIOUR != GOLDEN_IMPLEMENTATION`

This suite freezes **operator-visible behaviour** of the current first_safe_v1
integration so R3 can compare CURRENT_FORK vs MODERN_HERMES without freezing
wrapper layout, helper names, or module paths.

## What is frozen

- Effective callable tool names, tiers 0–6 (`fixtures/effective_surface.json`)
- catalogued vs requested vs callable
- Effect-class inventory (`fixtures/effect_classes.json`)
- Bounded HTTP request/response field contracts
- `correlation_id` propagation
- S0-B write-security negatives
- S0-C host-pin negatives
- Telegram semantic contracts (chat_summary shape, model-readable errors,
  energy-web sources/disclaimer)

## What is not frozen

- Wrapper/module layout
- Duplicated HTTP helpers
- Function call order
- Incidental prose formatting
- Production hostname as an architecture constant

## How to run

From the repo root, with project `.venv`:

```text
pytest tests/powerunits_golden -q
```

Regenerate frozen snapshots after an intentional behaviour change:

```text
python -m tests.powerunits_golden.generate_fixtures
```

## Determinism

- No live network
- No production credentials
- `HERMES_HOME` redirected by `tests/conftest.py`
- Mock HTTP via `_http_post`
- Synthetic execute host `bounded.example.test`

## Known test debt

See `test_known_test_debt.py`.

```text
TEST_DEBT = TEST_ISOLATION/CACHE_DEBT
REPRO = pytest tests/hermes_cli/test_tools_config.py
```

Gate-off cases in `test_tools_config.py` can fail in a shared pytest process
because `get_tool_definitions(quiet_mode=True)` caches without env/gate keys.
Isolated execution passes. Not fixed in R0.

## R3 consumption

`fixtures/manifest.json` is the machine-readable index:

- compare `tiers.*.callable`
- compare `effect_classes.operations`
- replay `BOUNDED_HTTP_CONTRACTS`
- assert `security_negatives` and `telegram_contracts`
