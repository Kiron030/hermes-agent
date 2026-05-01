# DE bounded stack — read-only remediation planner (Hermes + Repo B) — operator note v1

## What this is

Hermes tool **`plan_powerunits_de_stack_remediation`** issues **exactly one** authenticated POST to Repo B:

- **`POST /internal/hermes/bounded/v1/remediation/de-stack-plan`**

Repo B aggregates **existing** bounded read-only evaluators (coverage scans, baseline preview rolled signals, chunked **generation_outages / outage-awareness** summaries, market‑features / driver summaries, forecast validation outputs).  

**Hermes performs no SQL**, **starts no ingestion jobs**, **no campaigns**, **no orchestration**.

## Explicit non‑execution statement

- **Nothing** equivalent to **`entsoe_market_job`**, **`era5_weather_job`**, **`market_feature_job`**, **`market_driver_feature_job`**, **`entsoe_forecast_job`**, or **`expand_market_data`** runs as a consequence of planner HTTP alone.

Field **`hermes_statement`** on success is expected to equal **`read_only_remediation_plan_no_writes`** (Hermes echoes Repo B verbatim when present).

**`recommended_sequence[].tool_hint_hermes`** are **names** of bounded Hermes tools for **manual** follow‑up — not automatic chaining.

## Window contract (v1)

- **`country_code`**: **DE** only  
- **`version`**: **v1** only  
- **`window_start_utc`**: inclusive, timezone‑aware (**Z**)  
- **`window_end_utc`**: exclusive, timezone‑aware (**Z**)  
- Span **≤ 31 days** UTC (same bound as bounded coverage-scan / baseline preview windows)

Hermes validates the slice **locally** before HTTP (mirror of baseline‑preview span rules).

## Railway / Hermes env

| Variable | Role |
|---------|------|
| **`HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED`** | **Primary** planner gate (**must** be truthy). |
| **`POWERUNITS_INTERNAL_EXECUTE_BASE_URL`** | Repo B API origin (HTTPS). |
| **`POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`** | Bearer secret (**fail‑closed** if missing). |
| **`POWERUNITS_INTERNAL_EXECUTE_TIMEOUT_S`** | Optional HTTP read timeout (**long** windows near 31 d can exceed default — raise if timeouts occur). |

**Telegram (`first_safe_v1`):** Toolset **`powerunits_de_stack_remediation_planner`** must remain in **`gateway/run.py`** / **`model_tools.py`** / **`docker/apply_powerunits_runtime_policy.py`** allowlists alongside other bounded POST tools.

## Response shape (conceptual)

Top-level JSON (Repo B authoritative):

| Field | Role |
|--------|------|
| **`correlation_id`** | Request trace id (generated if header absent). |
| **`hermes_statement`** | Expected **`read_only_remediation_plan_no_writes`** on nominal path. |
| **`planner`** | Metadata (`id`, `grounding` string tying to repo evaluators only). |
| **`slice`** | Echo of DE / v1 / UTC window (**exclusive end**). |
| **`plan_outcome`** | **`ok` \| `repairable_gaps` \| `mixed_state` \| `not_ready_for_repair`** rollup. |
| **`family_states[]`** | **`family`**, **`status`** (`ok` \| `warnings` \| `gaps` \| `not_ready`), **`summary_code`**, **`key_findings[]`**. |
| **`recommended_sequence[]`** | **`step_index`**, **`family`**, **`action`**, **`rationale`**, **`tool_hint_hermes`** (nullable), **`blocking_dependencies[]`** (upstream **family ids**, not integers). |
| **`notes[]`** | Operator caveats (dependency semantics, rollup chunking hints). |

## Dependency semantics (v1)

Repo B ordering intent (see **`notes`** in live JSON):

1. Normalized **ENTSO‑E market** before **market_features** when demand / ENTSO-derived inputs are flagged.  
2. **ERA5** before **market_features** when weather gaps correlate with summaries (weather duplicate / missing semantics).  
3. **Generation outages** (``generation_outages`` family) — bounded **repair** hints can precede **market_features** when outage-awareness rollups indicate **missing/stale** hourly outage coverage (**read‑only** rollup inside planner; planner itself runs no jobs); duplicate merge-key scenarios suggest **read‑only outage awareness validate** rather than bounded repair execute.  
4. **Market features** before **market driver features** (`market_features_hourly` is the driver's sole compute input table).  
5. **Forecast** ingestion is treated as **parallel** / informational unless forecast validators report issues — forecast is **not** modeled as blocking the realized market stack in this v1 planner.

## Caveats

- **Latency:** For maximum span (31 d), Repo B runs internal rollups across many **≤24 h** feature/driver sub-windows plus coverage partitions — budget **timeouts** generously.  
- **Grounding:** Planner never invents telemetry; **`family_states`** are projections of evaluator outputs currently wired in Repo B **`hermes_bounded_de_stack_remediation_plan`**.  
- **Mixed states:** Operators should still read **`key_findings[]`** family-by-family — rollup **`plan_outcome`** is coarse.  
- **Outage duplication blockers:** `market_features` readiness **`outage_duplicate_keys`** cannot be cured by bounded outage execute — remediation recommends **`validate_powerunits_outage_awareness_bounded_window`**; bounded **`execute_powerunits_outage_repair_bounded_slice`** is for **missing/stale** outage hourly coverage (duplicate keys need DB reconciliation / ops). When outage interpretation is incomplete, **`generation_outages`** can appear **`before`** **`market_features_hourly`** in **`recommended_sequence`**; **`market_driver_features_hourly`** still depends on **`market_features_hourly`**.
