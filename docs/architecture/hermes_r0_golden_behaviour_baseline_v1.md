# R0 — Golden Behaviour Baseline

**Stichtag:** 2026-08-22  
**Slice:** R0  
**Base:** `origin/powerunits-internal-setup` @ `1ff57318b4da579448bc81a9a9dd34b822b66306`

```text
GOLDEN_BEHAVIOUR != GOLDEN_IMPLEMENTATION
```

R0 friert das **erhaltenswerte Verhalten** der heutigen Hermes/PowerUnits-Integration
ein — nicht die Wrapper-Struktur. R3 vergleicht CURRENT_FORK gegen MODERN_HERMES
anhand dieser Fixtures.

---

## Was R0 einfriert

| Fläche | Artefakt |
|---|---|
| Effektive callable Oberfläche Tiers 0–6 | `tests/powerunits_golden/fixtures/effective_surface.json` |
| catalogued vs requested vs callable | dieselben Snapshots |
| Effektklassen | `tests/powerunits_golden/fixtures/effect_classes.json` |
| Bounded HTTP Verträge | `tests/powerunits_golden/contracts.py` |
| Write-Security | `tests/powerunits_golden/test_write_security.py` |
| Host-Security | `tests/powerunits_golden/test_host_security.py` |
| Telegram-Semantik | `tests/powerunits_golden/test_telegram_contracts.py` |
| R3-Index | `tests/powerunits_golden/fixtures/manifest.json` |

## Was R0 absichtlich nicht einfriert

- Wrapper-Layout und Helper-Duplikation
- interne Funktionsaufrufreihenfolge
- Toolset-Namensschema als Selbstzweck
- Produktionshostname als Architektukonstante
- beliebige LLM-Prosa

Der Vertrag ist **exaktes Host-Pinning**, nicht „für immer `api.powerunits.io`“.
Tests nutzen synthetische Hosts (`bounded.example.test`, `allowed.example`).

---

## Env-Profil der Oberfläche

```text
env_profile = operator_ready_gates_on_synthetic
policy      = first_safe_v1
```

Alle bekannten `HERMES_POWERUNITS_*_ENABLED`-Gates sind im Test an.
Execute-Base-URL, Secret, Tavily- und GitHub-Token sind **synthetisch**.
Produktion `.env` wird weder gelesen noch geschrieben.

`check_fn == False` wird **nicht** in R0 repariert. Aktuell katalogisiert, aber
nicht callable unter diesem Profil:

- `vision_analyze` — `check_vision_requirements` (kein Vision-Key im hermetischen Test)

Das ist Baseline-Evidenz, kein Blocker.

---

## Aktuelle Zählungen

Effektive callable Toolnamen (Gates an, synthetische Creds):

| Tier | Callable |
|---|---|
| 0 | 57 |
| 1 | 59 |
| 2 | 64 |
| 3 | 70 |
| 4 | 76 |
| 5 | 84 |
| 6 | 92 |

Effektklassen (Registry, alle registrierten PowerUnits-Operationen):

| Klasse | Count |
|---|---|
| READ | 60 |
| READ_WITH_SIDE_EFFECT | 13 |
| BOUNDED_WRITE | 13 |
| BOUNDED_WRITE_AMPLIFYING | 2 |
| DESTRUCTIVE | 0 |

Bounded HTTP-Operationen: **37**  
Happy-Path-Fixtures: **37**  
Negative-Path-Fixtures: **37** (`feature_disabled` als bestehende Realität)

`READ_WITH_SIDE_EFFECT`: `validate_*`, `scan_*`, `research_powerunits_energy_web_v1`
plus lokale `ensure_*` (nur idempotentes Verzeichnis-/Pointer-Scaffolding).
Keine stille S0-B-Korrektur.

---

## Sicherheitsinvarianten

- `session_search` in keinem Tier 0–6 callable, auch bei expliziter Anforderung
- first_safe verweigert u. a. `read_file`, Terminal/Shell, Delegation, Browser,
  Computer-Use, Cron/Routines, freien SQL-/Repo-Pfad
- Write ohne Approval: `HTTP_POST_COUNT = 0`
- YOLO allein autorisiert keinen Write
- `cron_mode=approve` allein autorisiert keinen Write
- lokaler durable Writer: State unverändert bei Deny
- Campaign-Approval allein autorisiert keine Slices
- Distinct operation/country/window/resource → distinct approval identities
- HTTPS required; exact host match; Suffix-Host `allowed.example.evil.invalid` ≠ `allowed.example`
- Modell kann Host, URL und Route nicht liefern

---

## Suite ausführen

```text
pytest tests/powerunits_golden -q
```

Betroffene bestehende Regressionen (nicht umgeschrieben):

```text
pytest tests/hermes_cli/test_model_tools_telegram_session_search_surface.py tests/tools/test_powerunits_bounded_effects_v1.py tests/tools/test_powerunits_bounded_write_approval_v1.py tests/tools/test_powerunits_execute_base_url_v1.py -q
```

Keine Live-Netzwerkcalls. Kein `~/.hermes`. Kein Repo-B-Write.

---

## Bekannte Testschuld

```text
TEST_DEBT = TEST_ISOLATION/CACHE_DEBT
```

`tests/hermes_cli/test_tools_config.py` Gate-off-Fälle können in einem gemeinsamen
pytest-Prozess fehlschlagen, isoliert aber bestehen.
`get_tool_definitions(quiet_mode=True)` cached ohne Env-/Gate-Schlüssel.

Reproduktion:

```text
pytest tests/hermes_cli/test_tools_config.py
pytest tests/hermes_cli/test_tools_config.py::test_telegram_first_safe_bzn_not_in_schema_when_gate_off
```

Nicht in R0 gefixt — die Golden-Suite invalidiert Caches selbst.

POSIX/Windows: R0 vermeidet POSIX-only Pfadannahmen. Windows wird in dieser
Umgebung ausgeführt. Linux: `NOT_RUN`, sofern nicht separat belegt.

---

## Wie R3 diese Fixtures konsumiert

1. Dieselbe Operatorfrage / dieselbe Operation gegen modern Hermes stellen.
2. Callable-Namen gegen `tiers.*.callable` diffen.
3. Antwortfelder gegen `BOUNDED_HTTP_CONTRACTS.happy_fields` prüfen.
4. Security-Negatives aus `manifest.json` erneut ausführen.
5. Telegram: `disclaimer_de` + `sources_markdown` Semantik, nicht Wortlaut.

Nicht vergleichen: Modulpfade, Helper-Namen, interne Call-Order.
