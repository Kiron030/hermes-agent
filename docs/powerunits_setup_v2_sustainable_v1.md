# Powerunits Hermes Setup v2 — nachhaltiges Betriebsmodell (Audit v1)

**Datum:** 2026-07-14  
**Scope:** Repo A (`hermes-agent`) — Inventar, Redundanz, Cleanup-Plan, Railway-Template  
**Kontext:** Control Plane Repo B fertig; Backfill ~1 Woche; Railway bereits auf `stage1_operator_execute` bereinigt.

---

## 1. Executive Summary

| Metrik | Wert |
|--------|------|
| `powerunits_*.py` in `tools/` | **68** Dateien |
| Registrierte Tool-Module (`registry.register`) | **55** |
| Helper/Slice/Gates (kein Register) | **13** |
| Powerunits-Toolsets in `toolsets.py` | **54** |
| In `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` | **54** (Baseline/Governance + Hermes-Core `web`/`search`/`vision`) |
| Profil `stage1_read_health` Env-Keys | **26** |
| Profil `stage1_operator_execute` Env-Keys | **34** |

**Klassifikation (Dateiebene):**

| Klasse | Anzahl | Bedeutung |
|--------|--------|-----------|
| **ACTIVE** | 46 Module | Toolset in Telegram-Schema (`first_safe_v1`); Env-Gates filtern zur Laufzeit |
| **PROFILE_ONLY** | 7 Module | Registriert, Telegram nur via Capability-Tier-Overlay (Tier 1–5A) |
| **HELPER** | 13 Module | Slice/Countries/Gates — kein `registry.register` |
| **DEAD** | 1 Modul | `powerunits_market_features_bounded_de_slice.py` — absichtlich kein Register |

**Telegram-Overlay-Lücken (vor Fix):** `powerunits_baseline_layer_preview`, `powerunits_bounded_rollout_governance` — beide in `stage1_read_health`, aber nicht in Telegram-Base. **Fix in Branch `feature/powerunits-setup-v2-audit`.**

---

## 2. Vollständiges Tool-Inventar

### 2.1 Legende

- **Reg:** `registry.register` ja/nein  
- **TG:** in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` (Tier-Overlays separat)  
- **Profil RH:** Key in `stage1_read_health`  
- **Profil OE:** Key in `stage1_operator_execute` (superset von RH)  
- **Test:** dedizierte Testdatei vorhanden  

### 2.2 Helper-Module (HELPER — kein Tool)

| Datei | Rolle | Test |
|-------|-------|------|
| `powerunits_bounded_family_gates.py` | Zentrale Primary/Legacy-Gates pro Familie | ja |
| `powerunits_entsoe_market_bounded_slice.py` | Slice-Validierung ENTSO-E market | nein |
| `powerunits_entsoe_market_bounded_countries.py` | Tier-1 ISO2-Spiegel | nein |
| `powerunits_entsoe_forecast_bounded_slice.py` | Slice-Validierung Forecast | nein |
| `powerunits_entsoe_forecast_bounded_countries.py` | Forecast-Länderliste | nein |
| `powerunits_entsoe_empirical_candidate_countries.py` | DK/NO/IE Kandidaten | nein |
| `powerunits_era5_weather_bounded_slice.py` | ERA5-Slice-Validierung | nein |
| `powerunits_era5_tier1_countries.py` | ERA5 Tier-1 Bbox-Länder | ja |
| `powerunits_outage_awareness_bounded_slice.py` | Outage-Awareness-Slice | nein |
| `powerunits_outage_repair_bounded_slice.py` | Outage-Repair-Slice | nein |
| `powerunits_baseline_layer_preview_slice.py` | Baseline-Preview-Slice | nein |
| `powerunits_option_d_bounded_market_features.py` | Shared PL/DE HTTP-Client | ja |
| `powerunits_github_knowledge.py` | GitHub-Hilfsfunktionen | nein |
| `powerunits_market_features_bounded_de_slice.py` | DE-Slice (absichtlich kein Register) | nein |

### 2.3 Registrierte Tools — nach Familie

#### Kern / Posture / Workspace

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_operator_posture` | ja | — | — | ja |
| `powerunits_workspace` | ja | — | — | ja |
| `powerunits_docs` | ja | — | — | ja |
| `powerunits_github_docs` | ja | — | — | ja |
| `powerunits_repo_b_read` | ja | ja | ja | ja |
| `powerunits_timescale_read` | ja | ja | ja | ja |

#### Data-Health Triptychon + Governance

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_bounded_coverage_snapshot` | ja | ja | ja | ja |
| `powerunits_bounded_coverage_inventory` | ja | ja | ja | ja |
| `powerunits_worker_country_coverage_freshness` | ja | ja | ja | ja |
| `powerunits_multi_country_data_health` | ja | —* | —* | ja |
| `powerunits_baseline_layer_preview` | **ja†** | ja | ja | ja |
| `powerunits_bounded_rollout_governance` | **ja†** | ja | ja | ja |
| `powerunits_entsoe_empirical_candidate_validate` | ja | ja | ja | ja |
| `powerunits_entsoe_bzn_price_readiness` | ja | ja | ja | ja |
| `powerunits_entsoe_bzn_prices` | ja | ja | ja | ja |
| `powerunits_de_stack_remediation_planner` | ja | ja | ja | ja |

\* Orchestrator — benötigt alle drei Triptychon-Gates, kein eigener Profil-Key.  
† Nach Overlay-Fix in `feature/powerunits-setup-v2-audit`.

#### Market Features (DE) + Option D (PL)

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_market_features_bounded_de_execute` | ja | — | ja‡ | ja |
| `powerunits_market_features_bounded_de_validate` | ja | ja | ja | ja |
| `powerunits_market_features_bounded_de_readiness` | ja | ja | ja | ja |
| `powerunits_market_features_bounded_de_summary` | ja | ja | ja | ja |
| `powerunits_option_d_preflight` | ja | — | ja | ja |
| `powerunits_option_d_execute` | ja | — | ja | ja |
| `powerunits_option_d_validate` | ja | ja | ja | ja |
| `powerunits_option_d_readiness` | ja | ja | ja | ja |
| `powerunits_option_d_summary` | ja | ja | ja | ja |

‡ Via `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED`.

#### Market Driver (DE)

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_market_driver_features_bounded_de_execute` | ja | — | ja§ | ja |
| `powerunits_market_driver_features_bounded_de_validate` | ja | — | ja§ | ja |
| `powerunits_market_driver_features_bounded_de_readiness` | ja | — | ja§ | ja |
| `powerunits_market_driver_features_bounded_de_summary` | ja | — | ja§ | ja |

§ Via `HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED` (nur OE).

#### ENTSO-E Market

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_entsoe_market_bounded_preflight` | ja | — | ja¶ | ja |
| `powerunits_entsoe_market_bounded_execute` | ja | — | ja¶ | ja |
| `powerunits_entsoe_market_bounded_validate` | ja | ja | ja | ja |
| `powerunits_entsoe_market_bounded_summary` | ja | ja | ja | ja |
| `powerunits_entsoe_market_bounded_campaign` | ja | —** | —** | ja |
| `powerunits_entsoe_market_bounded_coverage_scan` | ja | —** | —** | ja |

¶ Via `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED`.  
** Separate Modifier-Env (`*_CAMPAIGN_ENABLED`, `*_COVERAGE_SCAN_ENABLED`) — nicht im Profil.

#### ENTSO-E Forecast

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_entsoe_forecast_bounded_preflight` | ja | — | ja¶ | ja |
| `powerunits_entsoe_forecast_bounded_execute` | ja | — | ja¶ | ja |
| `powerunits_entsoe_forecast_bounded_validate` | ja | ja | ja | ja |
| `powerunits_entsoe_forecast_bounded_summary` | ja | ja | ja | ja |

#### ERA5 Weather

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_era5_weather_bounded_preflight` | ja | — | ja¶ | ja |
| `powerunits_era5_weather_bounded_execute` | ja | — | ja¶ | ja |
| `powerunits_era5_weather_bounded_validate` | ja | ja | ja | ja |
| `powerunits_era5_weather_bounded_summary` | ja | ja | ja | ja |
| `powerunits_era5_weather_bounded_campaign` | ja | —** | —** | ja |
| `powerunits_era5_weather_bounded_coverage_scan` | ja | —** | —** | ja |

¶ Via `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED`.

#### Outage

| Toolset | TG | RH | OE | Test |
|---------|----|----|-----|------|
| `powerunits_outage_awareness_bounded_validate` | ja | ja | ja | ja |
| `powerunits_outage_awareness_bounded_summary` | ja | ja | ja | ja |
| `powerunits_outage_repair_bounded_execute` | ja | — | ja | ja |

#### Progressive Tier-Overlays (PROFILE_ONLY bis Tier gesetzt)

| Toolset | Tier | TG (dynamisch) | Test |
|---------|------|----------------|------|
| `powerunits_tier1_analysis` | ≥1 | nach `powerunits_workspace` | ja |
| `powerunits_tier2_allowlisted_read` | ≥2 | ja | ja |
| `powerunits_tier3_skills_integration` | ≥3 | ja | ja |
| `powerunits_tier4a_skill_draft_proposals` | ≥4 | ja | ja |
| `powerunits_tier4b_review_governance` | ≥5 | ja | ja |
| `powerunits_tier5a_bounded_workflow_scaffolding` | ≥6 | ja | ja |

---

## 3. Redundanz-Analyse

### 3.1 Preflight vs. Profil-Gates

| Aspekt | Preflight-Tools | Primary Profil-Gates |
|--------|-----------------|----------------------|
| HTTP | **Nein** (lokal) | Gates schalten Execute/Validate frei |
| Wert | Slice-Check, Operator-Hints, Rollback-SQL (Option D) | Fail-closed Enablement |
| ENTSO-E / ERA5 | Unter Primary-Gate mit enthalten | Ja — Preflight + Execute teilen Gate |
| Option D | Eigenes `OPTION_D_PREFLIGHT_ENABLED` | Ja im OE-Profil |

**Empfehlung:** Preflight **nicht** deprecaten.

- Option D: Preflight liefert einzigartige Rollback-SQL + CLI-Hints ohne Repo-B-Roundtrip.
- ENTSO-E/ERA5: Lokal billig; expliziter LLM-Workflow „preflight → execute → validate“ reduziert Fehl-POSTs.
- Profil-Gates ersetzen Preflight **nicht** — sie sind orthogonale Schichten (Exposure vs. Validation).

**Soft-Deprecation möglich (später):** Legacy per-step Keys (`*_PREFLIGHT_ENABLED` ohne Primary) — siehe §5.

### 3.2 Campaign vs. Execute + Validate

| | Campaign | Execute + Validate |
|--|----------|-------------------|
| Fenster | Bis 31d, ≤5 Sub-Windows | Ein ≤7d-Slice |
| Side Effects | Sequenzielle POSTs, fail-fast | Ein POST |
| Gate | Separates `*_CAMPAIGN_ENABLED` | Primary family gate |
| Superseded? | **Nein** | — |

Campaign ist **Orchestrierung**, kein Duplikat. Während Backfill **nicht** aktivieren (Modifier fehlt im Profil).

### 3.3 Coverage-Scan vs. Validate/Summary

Coverage-Scan = Multi-Window-Rollup **read-only** auf normalisierten Tabellen. Validate = Ein-Fenster-Semantik-Check. **Getrennt halten.**

### 3.4 Was zusammenführen vs. trennen

| Zusammenführen (Dokumentation) | Getrennt halten (Safety) |
|-------------------------------|--------------------------|
| Legacy `_DE_*_STEP_ENABLED` → Primary `*_BOUNDED_ENABLED` | Execute vs. Awareness vs. Repair (Outage) |
| Profil-Bundle statt 30+ Einzel-Flags | Campaign / Coverage-Scan Modifier |
| Mental Model: RH vs OE | Market Features vs. Market Driver vs. Option D |
| | Forecast vs. Market ENTSO-E Familien |

---

## 4. Cleanup-Plan (kein Code-Delete jetzt)

### 4.1 Sicher deprecaten / aus Railway entfernen

Legacy per-step Keys, wenn Primary gesetzt (Railway):

```text
HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_{EXECUTE,VALIDATE,READINESS,SUMMARY}_ENABLED
HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_DE_* (gleiches Muster)
HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_{PREFLIGHT,EXECUTE,VALIDATE,SUMMARY}_ENABLED
HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_* (gleiches Muster)
HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_* (gleiches Muster)
HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_{VALIDATE,SUMMARY}_ENABLED
HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_EXECUTE_ENABLED
```

### 4.2 Dateien — Lösch-Inventar (Cleanup v2)

| Ergebnis | Detail |
|----------|--------|
| **Gelöscht** | *keine* — alle 54 `*_tool.py` sind in `toolsets.py` registriert |
| **Nicht löschen** | `powerunits_market_features_bounded_de_slice.py` — **HELPER**, von Execute/Validate/Driver importiert (Audit „DEAD“ war falsch positiv) |
| **Regel** | Physisches Delete nur bei Zero-Referenzen außerhalb der Datei selbst |

### 4.3 Toolset-Konsolidierung (Dokumentation only)

**Ziel-Mental-Model:**

```
stage1_read_health  →  observe + validate + plan
stage1_operator_execute  →  + bounded writes (familienweise Primary-Gates)
Modifier-Envs  →  campaign / coverage_scan (Ron explizit)
Capability-Tier  →  workspace/skills/governance Overlays
```

### 4.4 Tests-Lücken (niedrige Priorität)

Einzelne bounded-Familien-Tests existieren als aggregierte `test_*_bounded_tools.py`. Kein Blocker.

---

## 5. Nachhaltiges Setup — Design für Ron

### A) Zwei Profile (klarer Switch)

Setze **genau eine** Variable auf Railway:

```text
HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health   # Default Backfill-Woche
HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_operator_execute   # Ron-Kampagnen
```

Alias: `stage1_analyst_read` = identisch zu `stage1_read_health`.

#### `stage1_read_health` — alle Env-Keys (26)

| Key | Wert |
|-----|------|
| `HERMES_POWERUNITS_BOUNDED_COVERAGE_SNAPSHOT_ENABLED` | 1 |
| `HERMES_POWERUNITS_BOUNDED_COVERAGE_INVENTORY_ENABLED` | 1 |
| `HERMES_POWERUNITS_WORKER_COUNTRY_COVERAGE_FRESHNESS_READ_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_BZN_PRICE_READINESS_READ_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_BZN_PRICES_READ_ENABLED` | 1 |
| `HERMES_POWERUNITS_REPO_B_READ_ENABLED` | 1 |
| `HERMES_POWERUNITS_TIMESCALE_READ_ENABLED` | 1 |
| `HERMES_POWERUNITS_BASELINE_LAYER_PREVIEW_ENABLED` | 1 |
| `HERMES_POWERUNITS_REMEDIATION_PLANNER_ENABLED` | 1 |
| `HERMES_POWERUNITS_BOUNDED_ROLLOUT_GOVERNANCE_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_EMPIRICAL_CANDIDATE_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ALLOWED_COUNTRIES` | DE,FR,IT,ES,NL,BE,PL,SE,NO,GB |
| `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_READINESS_ENABLED` | 1 |
| `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_DE_SUMMARY_ENABLED` | 1 |
| `HERMES_POWERUNITS_OPTION_D_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_OPTION_D_READINESS_ENABLED` | 1 |
| `HERMES_POWERUNITS_OPTION_D_SUMMARY_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_SUMMARY_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_SUMMARY_ENABLED` | 1 |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_SUMMARY_ENABLED` | 1 |
| `HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_VALIDATE_ENABLED` | 1 |
| `HERMES_POWERUNITS_OUTAGE_AWARENESS_BOUNDED_SUMMARY_ENABLED` | 1 |

**Kein Execute** — Primary-Gates für Writes sind **absent/falsy**.

#### `stage1_operator_execute` — zusätzliche Keys (+8 über RH)

| Key | Wert |
|-----|------|
| *(alle RH-Keys oben)* | *(vererbt)* |
| `HERMES_POWERUNITS_MARKET_FEATURES_BOUNDED_ENABLED` | 1 |
| `HERMES_POWERUNITS_OPTION_D_EXECUTE_ENABLED` | 1 |
| `HERMES_POWERUNITS_OPTION_D_PREFLIGHT_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_ENABLED` | 1 |
| `HERMES_POWERUNITS_ENTSOE_FORECAST_BOUNDED_ENABLED` | 1 |
| `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_ENABLED` | 1 |
| `HERMES_POWERUNITS_OUTAGE_REPAIR_BOUNDED_ENABLED` | 1 |
| `HERMES_POWERUNITS_MARKET_DRIVER_FEATURES_BOUNDED_ENABLED` | 1 |

**Explizit nicht im Profil** (Ron manuell, wenn gewünscht):

- `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED`
- `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_COVERAGE_SCAN_ENABLED`
- `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_CAMPAIGN_ENABLED`
- `HERMES_POWERUNITS_ERA5_WEATHER_BOUNDED_COVERAGE_SCAN_ENABLED`

---

### B) Telegram Tool Exposure

#### Bereits in `first_safe_v1` (Hermes-Core subset)

| Toolset | Tools |
|---------|-------|
| `memory` | Persistent memory |
| `session_search` | Verlaufssuche |
| `todo` | Planung |
| `web` | `web_search`, `web_extract` (kein Browser) |
| `search` | `web_search` (leichtgewichtig) |
| `vision` | `vision_analyze` (Screenshots/Diagramme) |

#### Powerunits Read — nach Overlay-Fix vollständig für RH

Triptychon + Baseline + Governance + BZN + Repo-B + Timescale + Multi-Country Health.

**Explizit NICHT** für Telegram `first_safe_v1`:

| Toolset | Grund |
|---------|-------|
| `terminal`, `code_execution` | Shell/Arbitrary Execution |
| `browser` | Automation + Exfil-Risiko |
| `file` (write/patch) | Unbounded Filesystem |
| `delegate_task` | Subagent-Spawning |
| `cronjob` | Scheduled Execution |
| `skills` → `skill_manage` | Mutation; Tier 3 observe reicht |

**Implementierung:** `web`, `search`, `vision` in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` (`feature/powerunits-internal-setup-v2-cleanup`).

---

### C) Capability Tier — „strong but safe“

| Tier | Empfehlung | Effekt |
|------|------------|--------|
| **0** | Backfill-Woche, konservativ | Nur Base-Overlays |
| **1** | **Empfohlen nach Backfill-Stabilisierung** | + Workspace-Analyse (`summarize_powerunits_workspace_full`, Textsuche) |
| **2** | Optional | + Allowlisted locals (structured/json/yaml reads) |
| **3–6** | Nur bei aktivem Skills/Governance-Bedarf | Drafts, Review, Workflow-Scaffolding |

```text
HERMES_POWERUNITS_CAPABILITY_TIER=1   # strong but safe
```

Tier ist **orthogonal** zum Bounded-Profil und zur Country-Scope.

---

### D) Railway Env Template (minimal)

#### Pflicht (immer)

```text
# Messaging
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_USERS=...

# LLM (Fork pinnt OpenAI chat_completions)
OPENAI_API_KEY=...

# Runtime policy
HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1

# Repo B bounded HTTP
POWERUNITS_INTERNAL_EXECUTE_BASE_URL=https://...
POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET=...

# Profil-Switch (EIN Wert)
HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health

# Capability
HERMES_POWERUNITS_CAPABILITY_TIER=0
```

#### Optional sinnvoll

```text
GITHUB_TOKEN=...                    # powerunits_repo_b_read + github_docs
DATABASE_URL_TIMESCALE=...          # timescale_read (read-only patterns)
HERMES_HOME=/opt/data               # Image-Default
```

#### Löschen / nicht setzen (Legacy-Noise)

- Alle einzelnen `HERMES_POWERUNITS_*_DE_*_ENABLED` wenn Profil aktiv
- Duplicate Primary + Legacy für dieselbe Familie
- `HERMES_POWERUNITS_ENTSOE_MARKET_BOUNDED_CAMPAIGN_ENABLED` während Backfill
- Platform-Keys für Discord/Slack/etc. (Policy disabled)
- `OPENROUTER_API_KEY` wenn OpenAI Primary (Fork-Default)

#### Posture-Check nach Deploy

Telegram: `summarize_powerunits_operator_posture` → `bounded_profile_v1`, `aligned`, `missing_truthy`.

---

### E) Railway-Profil JETZT (Backfill-Woche)

**Empfehlung: auf `stage1_read_health` wechseln.**

| Grund | Detail |
|-------|--------|
| Backfill läuft | Worker schreiben — Operator-Execute erhöht Kollisions-/Duplikat-Risiko |
| OE-Profil ist Superset | Execute-Tools erscheinen im Schema, sind aber gate-bar — verwirrend für LLM |
| RH reicht | Triptychon + Validate + Baseline + Governance + Remediation Planner |
| Kampagnen | Erst nach Backfill + explizitem Modifier-Env |

**Wechsel:**

```text
HERMES_POWERUNITS_BOUNDED_PROFILE=stage1_read_health
```

Redeploy abwarten → Posture-Tool prüfen → bei Bedarf temporär auf OE für **einzelne** bounded Repairs.

---

## 6. PR-Split (empfohlen)

| PR | Repo | Branch | Inhalt |
|----|------|--------|--------|
| **1 — Audit + Overlay-Fix** | A | `feature/powerunits-setup-v2-audit` | Dieses Doc + Telegram-Gaps (baseline, governance) |
| **2 — Hermes-Core Read** | A | `feature/powerunits-telegram-hermes-read-v1` | `web`, `vision` in Telegram-Base; Tests; Runbook |
| **3 — Profil-Härtung** | A | `feature/powerunits-profile-campaign-modifiers` | Optional CAMPAIGN/SCAN ins OE-Profil **aus** (Dokumentation) oder Ron-Opt-in Sub-Profile |
| **4 — Legacy-Flag-Deprecation** | A | `feature/powerunits-legacy-env-deprecation-doc` | Deprecation-Header in `bounded_flags_consolidated_v1.md` |
| **5 — Ops-Mirror** | B | `docs/operations/hermes_setup_v2_proposal_v1.md` | Kurzverweis auf Repo-A-Kanon (optional) |

---

## 7a. Merging Pattern für neue Tools (Verweis)

Für neue externe/interne Bounded-Tools (Web-Provider, weitere Repo-B-Slices) gilt ab
sofort das kanonische, wiederholbare Muster in
`docs/powerunits_hermes_integration_pattern_v1.md` (Doppel-Gate, Herkunfts-Markierung,
Guardrails/Disclaimer, Telegram-Overlay-Instruktionen, Caps, Registrierung in
`toolsets.py` + `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`, `ACCESS_MATRIX.md`-Zeile,
gemockte Tests) — extrahiert aus der Tavily-Integration (`research_powerunits_energy_web_v1`).
Neue Tool-PRs sollten die dortige Checklist referenzieren, statt das Muster erneut
herzuleiten.

## 7. Referenzen

- `powerunits_bounded_profiles_v1.py` — Profil-Expansion
- `powerunits_telegram_overlays.py` — Telegram-Base + Tier-Merge
- `docker/apply_powerunits_runtime_policy.py` — Policy-Apply
- `docs/powerunits_operator_env_cheat_sheet_v1.md` — Kurzreferenz
- `docs/powerunits_bounded_flags_consolidated_v1.md` — Gate-Modell
- `docs/powerunits_hermes_progressive_posture_v1.md` — Tier-Roadmap

---

*Erstellt durch Agent-Audit 2026-07-14. Branch: `feature/powerunits-setup-v2-audit`.*
