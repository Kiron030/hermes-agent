# PowerUnits × Hermes: Modernisierungs-Execution-Roadmap v1

**Stichtag:** 2026-08-22  
**Status:** kanonische Ausführungsroadmap (Umsetzungsplan, keine dritte Architekturbewertung)  
**Grundlagen:** [`hermes_upstream_reassessment_v1.md`](hermes_upstream_reassessment_v1.md), [`hermes_upstream_reassessment_red_team_v1.md`](hermes_upstream_reassessment_red_team_v1.md)  
**Scope:** Repo A (`hermes-agent`) Runtime-Modernisierung, interne Operator- und Entwicklerpfade  
**Nicht im Scope:** Customer Copilot, Tenant-Architektur, Runtime-/Produktänderungen in diesem Dokument

> Dieses Dokument **plant**. Es implementiert nichts. Es ändert weder die kanonische Reassessment noch den Red-Team-Report, weder Runtime-Code noch Produktionskonfiguration.

---

## 1. Executive Direction

Die Architekturfrage ist entschieden und wird hier nicht neu geöffnet:

```text
RED_TEAM_VERDICT = AFFIRM_SPLIT_BUT_SIMPLIFY
```

Gelesen als: **Split ist eine Autoritätsgrenze, kein Bauprogramm.** Hermes darf PowerUnits-Policy nicht besitzen; Repo B bleibt autoritativ. Daraus folgt aber *nicht*, jetzt eine Enterprise-Capability-Plane zu bauen.

Die Richtung dieser Roadmap:

```text
CURRENT_DIRECTION =
  MODERN_UPSTREAM_NEAR_HERMES
  + STANDALONE_POWERUNITS_INTEGRATION
  + EXISTING_REPO_B_BOUNDED_BOUNDARY
```

Drei Leitsätze, die jede Scheibe dieser Roadmap dominieren:

1. **Proof before Platform.** Bevor OIDC, mTLS, Capability-Tokens, Result-Firewall, Audit-Store oder Execution Plane gebaut werden, muss bewiesen sein, dass modernes Hermes + standalone PowerUnits-Integration den realen Operator-Workflow *besser* trägt. Ein gescheiterter Proof kostet Wochen; eine gebaute Plane kostet Quartale.
2. **Core-Ownership minimieren, nicht Zero-Fork-Ideologie.** Ziel ist die kleinste wirtschaftlich begründete PowerUnits-Eigentumsfläche am Hermes-Core — nicht „null Fork um jeden Preis“.
3. **Bestehende Grenzen wiederverwenden.** Die 31 bounded Repo-B-Routen liefern heute schon feste Operationen, serverseitige Validierung, typisierte Schemata, kein freies SQL. Der erste Proof konsumiert sie, statt sie zu duplizieren.

Drei kleine Sicherheitsbefunde werden **vor bzw. parallel zum Proof** behandelt (S0-A bis S0-C). Sie sind Sicherheitsscheiben, kein Sicherheitsprogramm.

```text
OVERENGINEERING_GUARD = PROOF_BEFORE_PLATFORM
CUSTOMER_COPILOT = FUTURE_SEPARATE_INITIATIVE
```

---

## 2. Was entschieden ist

Diese Punkte gelten als beschlossen und werden in dieser Roadmap nicht mehr diskutiert:

| Entscheidung | Konsequenz für die Roadmap |
|---|---|
| Repo B bleibt autoritativ für Schema, Pipelines, Domainvalidierung, Jobs | Keine Domainvalidierung in Hermes nachbauen; Hermes darf Parameter *vorschlagen*, Repo B muss sie *verwerfen* können |
| PowerUnits-Policy gehört nicht dauerhaft in Hermes-Core-Patches | PowerUnits-Integration wandert Richtung standalone Plugin / dünner Client |
| Moderne Upstream-Nähe ist das bevorzugte Zielbild für internes Hermes | Gepinnter Upstream-Release/Digest als Intake-Basis |
| Der bestehende bounded Repo-B-Vertrag ist die erste Capability-Grenze | Keine neue Capability Plane als erste Scheibe |
| Die wertvollen aktuellen Sicherheitsverträge bleiben erhalten | Finaler Callable Cap, feste Routen, `extra="forbid"`, kein freies SQL, Allowlist-Reads, Fail-closed-Gates |
| Fork-Schuld war überzeichnet | Migrationsschuld = geteilte Core-Dateien und echte Konflikte, nicht 275 Dateien oder Upstream-Commit-Distanz |
| Customer Copilot ist nicht Teil dieser Migration | Nur als Zukunftsgrenze dokumentiert, keine Implementierungsscheiben |
| Profiles sind keine Tenant-/Sicherheitsgrenze | Materiell unterschiedliche Trust Domains bekommen getrennte Instanzen/Credentials |
| Desktop ist intern tauglich, aber kein Migrationstreiber | Desktop ist `OPTIONAL`, Telegram wird nicht ersetzt |

---

## 3. Was offen ist

Diese Fragen werden **absichtlich** nicht heute entschieden. Jede hat eine zugeordnete Scheibe, die sie beantwortet:

| Offene Frage | Entscheidet | Gate |
|---|---|---|
| Trägt modernes Hermes den realen Operator-Workflow besser? | R3 Shadow Comparison | GATE_3 |
| `ZERO_CORE_FORK` oder `THIN_FORK`? | R1 (Clamp-Äquivalenz) + R2 (Plugin-Tragfähigkeit) + R3 | GATE_3 |
| Genügt Konfiguration (`enabled_toolsets` / `disabled_toolsets` + Acceptance-Test) als Ersatz für den lokalen First-Safe-Clamp? | R1 | GATE_1 |
| Kann eine standalone Plugin-Registrierung den Clamp respektieren? | R2 | GATE_2 |
| Wird Desktop intern übernommen? | R4 | GATE_4 |
| Welche Writes wandern auf die moderne Integration? | R6 | GATE_5 |
| Welche Core-Patches bleiben dauerhaft? | R7 | GATE_6 |
| Reicht Container-/Workspace-Isolation für Developer Hermes? | R5 | (kein Produktionsgate) |

```text
CORE_FORK_END_STATE = TO_BE_PROVEN
```

---

## 4. Aktuelle Architektur (verdichtet, nur soweit die Roadmap sie braucht)

Betriebsstufe ist **Stage 1 Trusted Analyst**: ein interner, read-first Telegram-Operatorpfad.

```text
Interner Operator
  → Telegram Gateway (Repo A)
  → first_safe_v1 Plattform- und Toolset-Cap
  → env-gated PowerUnits-Tool
  → fest verdrahteter POST /internal/hermes/bounded/v1/<operation>
  → Shared Bearer
  → Repo-B Router + Service-Validator
  → Job / deterministischer Read-Service
  → PostgreSQL/Timescale, data_pipeline_runs
  → minimierte JSON-Antwort mit correlation_id
```

Vier Eigenschaften, die die Roadmap erhalten muss:

1. **Finaler Callable Cap.** `model_tools.py:448-457` schneidet die finale Toolmenge unter `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` per Intersection auf `expected_telegram_toolsets_first_safe(tier)` — *nach* der normalen Auflösung, also auch gegen vom Caller angeforderte Toolsets.
2. **Plattform-Lockdown.** `gateway/run.py` und `gateway/config.py` erzwingen Telegram-only und deaktivieren Skill-Sync/Slash-Skill-Dispatch.
3. **Feste Operationen.** Jedes bounded Tool verdrahtet seinen Route-Suffix als Konstante (`_SNAPSHOT_PATH`, `_EXECUTE_PATH`, …) und bietet dem Modell **keinen** URL-Parameter.
4. **Fail-closed Env-Gates.** Pro Familie ein `HERMES_POWERUNITS_*_ENABLED`, plus Base-URL- und Secret-Anforderung im `check_fn`.

Drei strukturelle Schwächen, die die Roadmap adressiert:

- **Wrapper-Duplikation.** Rund 30 Tools implementieren dieselbe HTTP-Mechanik (Base-URL-Auflösung, Bearer-Header, Correlation-ID, Redaction, Timeout) je einmal. `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` wird in jedem Tool separat gelesen und ohne Host-Prüfung mit dem Pfad konkateniert.
- **Telegram-gebundene Policy.** Der Clamp heißt `expected_telegram_toolsets_first_safe`; `_enforce_powerunits_toolsets()` liefert außerhalb Telegram eine leere Liste. Für Desktop/CLI existiert damit heute **kein** äquivalenter Policy-Pfad.
- **Prozessglobale Credentials.** `tui_gateway/host_supervisor.py:313-314` baut ein sanitisiertes Env und ruft danach `env.update(os.environ)` — entfernte Secrets können so wieder einwandern. In-Process-Redaction ist deshalb keine Credential-Grenze.

---

## 5. Vereinfachte Zielarchitektur

```text
              Desktop (OPTIONAL)
                 │
Telegram ────────┼──────── CLI/TUI
                 │
                 ▼
          Modern Hermes
          upstream-near, gepinnter Digest
                 │
        standalone PowerUnits
        Plugin / dünner Client
        (operation_id + JSON, kein URL-Feld)
                 │
                 ▼
 bestehende bounded Repo-B-Routen
 /internal/hermes/bounded/v1/<operation>
                 │
                 ▼
             Repo B
       Daten, Jobs, Wahrheit
```

Autoritätsschnitt:

| Ebene | Besitzt | Besitzt ausdrücklich nicht |
|---|---|---|
| Modern Hermes | Agent Loop, Sessions, Profile, Oberflächen, Prompting, Modellwahl | PowerUnits-Domainwahrheit, erlaubte Side Effects, Länder-/Fenster-Regeln |
| PowerUnits Plugin | Operationsidentität, typisierte Schemata, fester Zielhost, Effektklasse, Approval-Auslösung | Domainvalidierung, DB-Zugriff, Jobsteuerung |
| Repo B | Schema, Validierung, Jobs, Pipeline-Run-State, Response-Minimierung | Agent-UX, Prompting |

Der zweite Hermes-Pfad daneben, ohne Produktionsautorität:

```text
Developer Hermes
  = mächtig im Workspace (Repo A/B read/write, Git, Tests, Terminal, Websuche, Skills)
  + kein Produktionscredential
  + kein destruktives Produktionsrecht
```

---

## 6. Sicherheitsbefunde mit Sofortbedarf

Drei kleine Befunde, jeder mit Repo-Evidenz, jeder als eigene winzige Scheibe. **Keine Sicherheitsplattform.**

### 6.1 S0-A — `session_search`

**Evidenz (`VERIFIED`):**

- `powerunits_telegram_overlays.py:54-56` — `session_search` ist Teil von `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`.
- `tools/session_search_tool.py:631-676` — das **Modell** kann einen `profile`-Parameter setzen; `_resolve_profile_db()` öffnet die `state.db` eines anderen Profils read-only.
- `tools/session_search_tool.py:885-893` — `profile` ist im Toolschema exponiert und dokumentiert.
- `tools/session_search_tool.py:695-707` — bei einem Miss scannt `_locate_session_db()` **jedes** Profil, auch ohne `profile`-Argument.
- Der Discovery-Pfad sucht die gesamte `state.db`; es gibt keine Chat-/Participant-Einschränkung im Tool (Gateway-Session-Scoping wirkt auf Sessions, nicht auf diese Suche).
- Upstream [#87779](https://github.com/NousResearch/hermes-agent/issues/87779) ist am Stichtag offen (fehlendes Ownership-Scoping).

**Bewertung für unsere heutige Konfiguration:** Cross-Profile-Exposition ist heute klein, solange nur `default` existiert; die Cross-Chat-Exposition innerhalb derselben `state.db` ist dagegen real, sobald mehr als ein Operator-Chat dieselbe Instanz nutzt. Die Exposition **wächst genau dort**, wo diese Roadmap hin will: Profile, Desktop, mehrere Oberflächen.

```text
S0_A_TREATMENT = DISABLE
```

Begründung der Wahl: `DISABLE` ist eine Ein-Zeilen-Änderung in einer PowerUnits-eigenen Datei, erzeugt **null** zusätzliche Shared-Core-Schuld und ist sofort reversibel. `PATCH`/`SCOPE` würden `tools/session_search_tool.py` — eine Upstream-Datei — anfassen und damit Migrationsschuld erzeugen, für einen Nutzen, den `memory` heute weitgehend abdeckt.

`SCOPE` bleibt als spätere Variante dokumentiert (Entfernen der `profile`-Property aus dem Schema plus Verweigerung des Cross-Profile-Fallbacks unter `first_safe_v1`) und ist ein guter Upstream-PR-Kandidat. Exit-Kriterium für die Wiederaufnahme: Ownership-Scoping im Intake-Release verifiziert.

### 6.2 S0-B — Execute-Boundary

**Evidenz (`VERIFIED`):** Der First-Safe-Basiskatalog enthält Execute-Familien; die zugehörigen Tools senden einen einzelnen POST mit Shared Bearer und **ohne** deterministische Human-Confirmation pro Call. `docker/apply_powerunits_runtime_policy.py:231-240` setzt `approvals.mode=manual` und `approvals.cron_mode=deny` — das greift für Hermes-eigene gefährliche Aktionen, **nicht** für diese HTTP-Wrapper.

Effektklassifikation der heute katalogisierten PowerUnits-Oberfläche (Pfadkonstanten und Tool-Semantik als Belegquelle):

| Effektklasse | Operationen (Auswahl, nach registriertem Toolnamen) | Beleg |
|---|---|---|
| `READ` | `read_powerunits_coverage_snapshot_v1` (`/coverage-snapshot`), `inventory_powerunits_bounded_coverage_v1` (`/coverage-inventory`), `read_powerunits_worker_country_coverage_freshness_v1`, `read_powerunits_entsoe_bzn_prices_v1`, `read_powerunits_entsoe_bzn_price_readiness_v1`, `read_powerunits_multi_country_data_health_v1`, alle `readiness_*` (`/readiness-window`), alle `summarize_*` (`/summary-window`), `preview_powerunits_baseline_layer_coverage_de`, `governance_powerunits_bounded_rollout_read_v1`, `plan_powerunits_de_stack_remediation`, `read_powerunits_doc`, `read_powerunits_roadmap_file`, `read_powerunits_repo_b_allowlisted`, `read_powerunits_timescale_dataset`, `list_hermes_workspace`, `read_hermes_workspace_file`, alle `preflight_*` (lokal, kein HTTP) | `VERIFIED` über Pfadkonstanten bzw. fehlenden HTTP-Aufruf |
| `READ_WITH_SIDE_EFFECT` | alle `validate_*` (`/validate-window`), `scan_*_coverage_*` (`/coverage-scan`), `research_powerunits_energy_web_v1` (externer Egress, kostenpflichtige Quote) | `INFERRED` — Validierung/Scan erzeugen Pipeline-Run-/Kostenspuren; in R0 gegen Repo B zu bestätigen |
| `BOUNDED_WRITE` | `execute_powerunits_option_d_bounded_slice`, `execute_powerunits_market_features_bounded_de_slice`, `execute_powerunits_market_driver_features_bounded_de_slice` (`/…/recompute`), `execute_powerunits_entsoe_market_bounded_slice`, `execute_powerunits_entsoe_forecast_bounded_slice`, `execute_powerunits_era5_weather_bounded_slice`, `execute_powerunits_outage_repair_bounded_slice`; lokal: `save_hermes_workspace_note` mit `overwrite_mode=overwrite` | `VERIFIED` über `_EXECUTE_PATH` bzw. `overwrite_mode` |
| `BOUNDED_WRITE_AMPLIFYING` | `campaign_powerunits_entsoe_market_bounded_de`, `campaign_powerunits_era5_weather_bounded_de` (Mehr-Slice-Schleifen über Execute) | `VERIFIED` über separate `*_CAMPAIGN_ENABLED`-Gates und Tool-Semantik |
| `DESTRUCTIVE` | **keine gefunden.** Kein Delete-/Drop-/Truncate-Pfad in der bounded Routenfläche | `VERIFIED` im Umfang der Pfadkonstanten |

Verstärkend: Repo B ignoriert `idempotency_key` in v1 und dedupliziert parallele Runs nicht am Router. Wiederholte oder parallele `recompute`-Aufrufe sind damit die realistische Schadensform — nicht Löschung.

**Kleinste ausreichende Härtung (drei Teile, alle in PowerUnits-eigenen Dateien):**

1. **Eine deklarative Effekt-Registry** (`tools/powerunits_bounded_effects_v1.py`), plus ein Test, der fail-closed verlangt, dass **jedes** registrierte `powerunits_*`-Tool eine Effektklasse besitzt. Neue Tools ohne Klassifikation brechen die Suite.
2. **Wiederverwendung des bereits vorhandenen Human-Gates.** `tools/approval.py:2940` stellt `request_tool_approval(tool_name, reason, *, rule_key=...)` bereit: dieselbe Maschinerie wie ein Tier-2-Dangerous-Command — Session-/Permanent-Allowlist, CLI-Prompt, Gateway-`submit_pending`, `cron_mode`, **fail-closed ohne Menschen**. Ein gemeinsamer Helper ruft das vor dem POST für `BOUNDED_WRITE` und `BOUNDED_WRITE_AMPLIFYING` auf. `rule_key` enthält Operation **plus** Land **plus** Fenster, damit ein `[a]lways` niemals die ganze Familie freigibt.
3. **Yolo-Hardline für Writes.** `request_tool_approval` gibt in einer Yolo-Session `approved: True` zurück (`tests/tools/test_request_tool_approval.py:158-167`). Für `BOUNDED_WRITE` verweigert der Helper deshalb explizit, statt sich auf die Bootstrap-Policy zu verlassen.

Kein neues Gateway, kein Token-Broker, keine Capability-Plane. Der Approval-Weg existiert bereits und ist getestet.

### 6.3 S0-C — PowerUnits-Zielhost

**Evidenz (`VERIFIED`):** Jedes bounded Tool liest `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` selbst und bildet `f"{base}{_PATH}"` (z. B. `tools/powerunits_bounded_coverage_snapshot_tool.py:67-71`). Es gibt keine Host-Allowlist, keine Schema-Erzwingung und keinen `url_safety`-Durchlauf. Das Modell kann die Base-URL nicht wählen — die Deploymentkonfiguration aber schon, und der Wert wird an ~30 Stellen unabhängig konsumiert.

**Kleinste wirksame Korrektur:** ein einziger PowerUnits-eigener Resolver (`tools/powerunits_execute_base_url_v1.py`), der `https` erzwingt und den Host gegen eine Allowlist prüft, mit zwei Modi:

```text
POWERUNITS_INTERNAL_EXECUTE_HOST_PIN_MODE = warn | enforce
```

`warn` loggt eine Abweichung, `enforce` schlägt fail-closed fehl. Ausgeliefert wird `warn` als Code-Default, `enforce` wird in der Deploymentkonfiguration gesetzt, nachdem ein Mensch den Produktionshost bestätigt hat. So ist die Scheibe klein, sofort reversibel und kann den laufenden Betrieb nicht durch einen Tippfehler stilllegen.

```text
S0_C_TREATMENT = PIN_VIA_SINGLE_RESOLVER_WARN_THEN_ENFORCE
```

---

## 7. Roadmap S0 – R7

Jede Scheibe trägt denselben Feldsatz. Kennzahlen am Ende jeder Scheibe:

```text
SIZE = XS | S | M | L
EXPECTED_CURSOR_AUTO_FIT = HIGH | MEDIUM | LOW
RISK = LOW | MEDIUM | HIGH
ROLLBACK_DIFFICULTY = LOW | MEDIUM | HIGH
```

---

### S0-A — `session_search` aus der First-Safe-Oberfläche entfernen

**Ziel.** Die Cross-Chat-/Cross-Profile-Leseflanke schließen, bevor Profile oder weitere Oberflächen sie vergrößern.

**Warum jetzt.** Der Befund ist belegt, die Korrektur ist eine Zeile, und jede spätere Scheibe (Profile, Desktop, mehrere Oberflächen) verschlechtert die Ausgangslage. Außerdem muss S0-A **vor** R0 landen, sonst friert die Golden Baseline eine Oberfläche ein, die unmittelbar danach geändert wird.

**Repo.** Repo A.

**Wahrscheinliche Dateien/Flächen.** `powerunits_telegram_overlays.py` (Basistuple); `tests/test_powerunits_telegram_overlays_stage1_v1.py`; ggf. `docs/powerunits_runtime_enforcement_v2.md` und `ACCESS_MATRIX.md` als Dokumentationsabgleich.

**Umfang.** `session_search` aus `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` entfernen. Negativtest ergänzen: unter `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` erscheint `session_search` **nicht** in der finalen Toolmenge, auch wenn das Toolset explizit angefordert wird. Kurzer Vermerk mit Exit-Kriterium in der Runtime-Enforcement-Doku.

**Ausdrücklich nicht im Scope.** Kein Eingriff in `tools/session_search_tool.py`. Kein Redesign der Session-Infrastruktur. Kein Memory-/Recall-Ersatzfeature.

**Tests/Evidenz.** Positiv-/Negativtest im Muster von `tests/hermes_cli/test_model_tools_telegram_coverage_snapshot_surface.py`; erwartete Toolanzahl in der Overlay-Suite aktualisieren.

**Akzeptanzkriterien.** (a) Effektive Telegram-Toolmenge enthält `session_search` in keinem Tier 0–6. (b) Explizite Anforderung des Toolsets wird durch den Clamp verworfen. (c) Overlay-Ordnungstests bleiben grün (Tier-Overlays weiter direkt nach `powerunits_workspace`).

**Rollback.** Eine Zeile wieder einfügen; Konfigurationsänderung nicht erforderlich.

**Abhängigkeiten.** Keine.

**Menschliche Handlung.** Bestätigen, dass Operatoren auf Verlaufssuche verzichten können; `memory` bleibt verfügbar.

```text
SIZE = XS
EXPECTED_CURSOR_AUTO_FIT = HIGH
RISK = LOW
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Trägt zu `GATE_0` bei.

---

### S0-B — Effektklassifikation und deterministisches Write-Gate

**Ziel.** Jede exponierte PowerUnits-Operation besitzt eine explizite Effektklasse, und `BOUNDED_WRITE` erhält eine deterministische, fail-closed Human-Confirmation pro Call.

**Warum jetzt.** Die Write-Fläche ist katalogisch bereits Stage 1 und nur env-geschlossen. Solange das so bleibt, ist jede Erweiterung (Desktop, Plugins, mehr Oberflächen) eine Risikoerhöhung ohne Gegengewicht. Das benötigte Human-Gate existiert bereits im Repo und ist getestet — es wird nur nicht aufgerufen.

**Repo.** Repo A (Repo B unverändert).

**Wahrscheinliche Dateien/Flächen.** Neu: `tools/powerunits_bounded_effects_v1.py` (Effekt-Registry) und ein kleiner Approval-Helper. Aufrufstellen: die sieben `*_execute_tool.py` sowie `powerunits_entsoe_market_bounded_campaign_tool.py` und `powerunits_era5_weather_bounded_campaign_tool.py`. Bestehende Basis: `tools/approval.py` (`request_tool_approval`, `_run_approval_gate`).

**Umfang.**
1. Effekt-Registry als Daten (`operation_id → effect`), plus Test „jedes registrierte `powerunits_*`-Tool hat genau eine Klasse“ (fail-closed).
2. Gemeinsamer Helper, der vor dem POST `request_tool_approval()` mit `rule_key = <operation>:<land>:<fenster>` aufruft und bei `approved=False` einen strukturierten, modelllesbaren Fehler zurückgibt.
3. Yolo-Hardline für Write-Klassen.
4. `READ_WITH_SIDE_EFFECT` wird zunächst nur klassifiziert und geloggt, **nicht** gegated.

**Ausdrücklich nicht im Scope.** Keine Capability-Manifest-Sprache, keine Rollen/Scopes, keine Tokens, kein Audit-Store, keine Idempotenz-Implementierung (die gehört zu R6 und in Repo B), keine Änderung an Repo-B-Routen.

**Tests/Evidenz.** Approval-Verweigerung blockiert den POST (HTTP-Poster wird nicht aufgerufen); Approval-Erteilung lässt genau einen POST durch; Gateway-Pfad erzeugt `status="approval_required"`; nicht-interaktiver Nicht-Cron-Kontext schlägt fail-closed fehl; `rule_key` unterscheidet Länder und Fenster; Registry-Vollständigkeitstest.

**Akzeptanzkriterien.** (a) Kein `BOUNDED_WRITE` erreicht Repo B ohne Approval-Entscheidung. (b) Ein `[a]lways` für eine Slice-Identität approbiert keine andere. (c) Yolo umgeht das Gate nicht. (d) Read-Pfade bleiben verhaltensgleich (Golden-Reads unverändert).

**Rollback.** Helper-Aufruf pro Tool entfernen oder per Env-Flag deaktivieren; Registry ist inert, wenn niemand sie liest.

**Abhängigkeiten.** Keine harte; profitiert von R0, wenn R0 zuerst läuft.

**Menschliche Handlung.** Entscheiden, ob Telegram-Approvals betrieblich gewünscht sind (Antwortlatenz) und für welche Familien Writes überhaupt aktiv bleiben.

```text
SIZE = S
EXPECTED_CURSOR_AUTO_FIT = MEDIUM
RISK = MEDIUM
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Trägt zu `GATE_0` bei.

---

### S0-C — Zielhost über einen einzigen Resolver pinnen

**Ziel.** Die Execute-Base-URL wird an genau einer Stelle aufgelöst und gegen eine Host-Allowlist geprüft.

**Warum jetzt.** Der Wert wird derzeit an rund 30 Stellen unabhängig gelesen. Vor jeder Umstellung auf eine moderne Runtime ist ein einziger validierender Resolver die Voraussetzung dafür, dass die Hostbindung überhaupt migrierbar ist — und sie ist die Kontrolle, die der Red Team explizit als „jetzt nötig“ eingeordnet hat.

**Repo.** Repo A.

**Wahrscheinliche Dateien/Flächen.** Neu: `tools/powerunits_execute_base_url_v1.py`. Optional `config/powerunits_execute_allowed_hosts.json`. Aufrufstellen: die bounded Tools, die heute `_BASE_ENV` selbst lesen — inkrementell, beginnend mit den R2-Kandidaten.

**Umfang.** Resolver mit `https`-Zwang, Host-Allowlist aus Env (kommaseparierte Hostliste), Modus `warn|enforce`, klarer strukturierter Fehler. Umstellung der Aufrufstellen ohne Verhaltensänderung im Erfolgsfall.

**Ausdrücklich nicht im Scope.** Keine allgemeine Egress-Policy, keine `url_safety`-Integration für alle Tools, keine Netzwerk-Firewall, kein Secret Broker, keine Änderung an `.env` oder Railway durch diese Roadmap.

**Tests/Evidenz.** Erlaubter Host passiert; fremder Host wird in `enforce` verweigert und in `warn` geloggt; `http`-Schema wird verweigert; fehlende Konfiguration erzeugt denselben `read_config_incomplete`-Vertrag wie heute.

**Akzeptanzkriterien.** (a) Genau ein Modul löst die Base-URL auf. (b) In `enforce` ist kein Nicht-Allowlist-Host erreichbar. (c) Bestehende Golden-Reads bleiben byte-nah gleich.

**Rollback.** Modus auf `warn` zurückstellen; Resolver fällt auf heutiges Verhalten zurück.

**Abhängigkeiten.** Keine.

**Menschliche Handlung.** Produktionshost bestätigen und `enforce` in der Deploymentkonfiguration setzen. **Der Agent liest oder schreibt `.env` nicht.**

```text
SIZE = S
EXPECTED_CURSOR_AUTO_FIT = HIGH
RISK = MEDIUM
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Schließt gemeinsam mit S0-A und S0-B `GATE_0`.

---

### R0 — Golden Behaviour Baseline

**Ziel.** Das erhaltenswerte **Verhalten** des heutigen Forks einfrieren — nicht seine Implementierungsstruktur.

**Warum jetzt.** Ohne diese Baseline ist R3 nicht messbar und jede Migration wäre eine Meinungsfrage. Die Baseline ist außerdem das Instrument, mit dem sich später beweisen lässt, dass eine Vereinfachung nichts Nützliches verloren hat.

**Repo.** Repo A (Aufzeichnung), Repo B nur lesend als Vertragsquelle.

**Wahrscheinliche Dateien/Flächen.** Neu: `tests/powerunits_golden/` mit Fixtures und Snapshot der effektiven Oberfläche; Aufzeichnungsartefakt unter `docs/` oder `tests/powerunits_golden/`. Bestehende Muster: `tests/hermes_cli/test_model_tools_telegram_*_surface.py`, `tests/test_powerunits_telegram_overlays_stage1_v1.py`.

**Umfang.**
1. **Effektive callable Oberfläche** pro Tier 0–6, aufgezeichnet mit realistischen Env-Gate-Kombinationen — die tatsächlich sichtbaren Toolnamen, nicht die Katalognamen.
2. **Bounded Operationen**: pro Operation ein Happy Path (Anfrageform, erwartete Feldmenge, `correlation_id`-Vertrag) und mindestens ein Negativpfad (`feature_disabled`, `invalid_window`, `invalid_country_codes`, `read_config_incomplete`).
3. **Telegram-Verhalten**: `chat_summary`-Struktur, Disclaimer-/Quellenpflicht bei `research_powerunits_energy_web_v1`, Fehlerdarstellung.
4. **Safety-Erwartungen** als Negativtests: kein `read_file`, kein Terminal, keine Delegation, kein freies SQL, kein freier Repo-Pfad, `session_search` nach S0-A abwesend, Write ohne Approval blockiert.
5. **Bekannte Testschuld klassifizieren**: die order-/cacheabhängigen BZN-Negativtests und die POSIX-Annahmen in File-Safety-Tests als „vor Migrationsfreigabe zu bereinigen“ markieren.
6. `READ_WITH_SIDE_EFFECT`-Annahmen aus S0-B gegen die Repo-B-Routen bestätigen oder korrigieren.

**Ausdrücklich nicht im Scope.** Keine Erhaltung von Wrapper-Struktur, Toolnamen-Kosmetik oder Toolset-Namensschema als Selbstzweck. Keine Live-Produktionsläufe gegen Repo B ohne Freigabe; HTTP wird über den bereits vorhandenen `_http_post`-Injektionspunkt gemockt.

**Tests/Evidenz.** Die Golden-Suite selbst ist die Evidenz. Sie muss lokal ohne Netzwerk und ohne Schreibzugriff auf `~/.hermes/` laufen.

**Akzeptanzkriterien.** (a) Ein Diff der effektiven Oberfläche ist maschinell erkennbar. (b) Jede bounded Operation hat mindestens einen Happy- und einen Negativpfad. (c) Suite läuft reproduzierbar auf Windows und Linux. (d) Kein Test schreibt nach `~/.hermes/`.

**Rollback.** Reine Testergänzung; Löschen genügt.

**Abhängigkeiten.** S0-A (sonst friert die Baseline eine Oberfläche ein, die sich sofort ändert). S0-B/S0-C sind willkommen, aber nicht blockierend — ihre Negativtests können nachgezogen werden.

**Menschliche Handlung.** Freigeben, welche Env-Gate-Kombinationen als „repräsentativ produktionsnah“ gelten.

```text
SIZE = S
EXPECTED_CURSOR_AUTO_FIT = HIGH
RISK = LOW
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Voraussetzung für `GATE_1`; liefert die Messlatte für `GATE_3`.

---

### R1 — Modern Hermes Intake / isolierte Proof-Runtime

**Ziel.** Eine reproduzierbare, isolierte Nicht-Produktionsumgebung auf dem gewählten modernen Upstream-Release, ohne PowerUnits-Produktionssecrets.

**Warum jetzt.** Alle weiteren Aussagen über Nutzen, Kosten und Fork-Ende hängen davon ab, dass modernes Hermes bei uns überhaupt startet und sich policy-konform kappen lässt. Das ist die billigste Stelle, an der die Migration scheitern darf.

**Repo.** Repo A (nur Dokumentation, Skripte, Tests). **Keine** Produktionsdeploymentänderung.

**Wahrscheinliche Dateien/Flächen.** Neu: `docs/architecture/` Intake-Notiz mit Release, Commit-SHA, Tagobjekt und Image-Digest; ein lokales Compose-/Runscript unter `docker/` oder `scripts/`; ein Smoke-Test-Ziel. Bezugspunkte im Repo: `docker/entrypoint.sh`, `docker/apply_powerunits_runtime_policy.py`, `pyproject.toml`, `uv.lock`.

**Umfang.**
1. Unveränderlicher Pin: Release-Tag **und** Image-Digest **und** Commit-SHA gemeinsam notiert; Bezug ausschließlich per Digest.
2. Reproduzierbarer Install: `uv sync --frozen`; **keine** Runtime-Lazy-Installs.
3. Isolation: eigenes `HERMES_HOME`, kein `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`, kein `DATABASE_URL_TIMESCALE`, keine Railway-/Vercel-Credentials, private/lokale Exposition (Loopback), kein öffentlicher Ingress.
4. Smoke-Tests: Prozess startet, ein Modellaufruf gegen einen Nicht-Produktionsprovider funktioniert, Toolliste ist inspizierbar.
5. **Clamp-Äquivalenzprüfung** — die eigentliche Erkenntnisfrage: Erreicht `enabled_toolsets`/`disabled_toolsets` plus Acceptance-Test dieselbe finale Oberfläche wie der lokale Intersection-Clamp? Ergebnis wird als `CLAMP_EQUIVALENCE = CONFIG_SUFFICIENT | PATCH_REQUIRED` notiert. Diese Antwort ist der wichtigste Einzelinput für `ZERO_CORE_FORK` vs `THIN_FORK`.
6. Ausdrücklich **kein** Multiplex-API-Server im Proof (Upstream-Ignoranz gegenüber `disabled_toolsets` bei Multiplex-Profilen ist ein bekanntes offenes Risiko).

**Ausdrücklich nicht im Scope.** Keine interne Registry-Spiegelung, kein internes Release-Signing, kein SBOM-Gate, keine Zwei-Personen-Intake-Zeremonie, keine Bitwarden-Integration, keine Desktop-Distribution, keine Produktionsdeploymentänderung. Diese Punkte sind erst nach `GATE_3` wirtschaftlich begründbar.

**Tests/Evidenz.** Smoke-Suite; Aufzeichnung der finalen Toolnamen im Proof-Setup; Gegenüberstellung mit der R0-Baseline (nur Oberfläche, noch nicht Verhalten).

**Akzeptanzkriterien.** (a) Umgebung ist aus dem notierten Digest reproduzierbar neu erzeugbar. (b) Kein Produktionssecret im Prozess-Env — belegt durch eine Env-Assertion, nicht durch Zusicherung. (c) Kein Lazy Install im Startpfad. (d) `CLAMP_EQUIVALENCE` ist beantwortet und belegt. (e) Nichts hört auf einer öffentlichen Adresse.

**Rollback.** Umgebung löschen. Produktion bleibt unberührt, weil sie nie angefasst wurde.

**Abhängigkeiten.** R0 (Vergleichsbasis).

**Menschliche Handlung.** Upstream-Release/Digest auswählen und freigeben; einen Nicht-Produktions-Modellprovider-Key für die Proof-Umgebung bereitstellen.

```text
SIZE = M
EXPECTED_CURSOR_AUTO_FIT = LOW
RISK = LOW
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Schließt `GATE_1`.

---

### R2 — Standalone PowerUnits Plugin / dünner Adapter

**Ziel.** Drei bis fünf **read-only** PowerUnits-Operationen laufen auf der modernen Runtime über eine **standalone** Integration gegen die bestehenden bounded Repo-B-Routen.

**Warum jetzt.** Das ist der eigentliche Architekturbeweis: Wenn die offizielle Erweiterungsmechanik trägt, sinkt die PowerUnits-Eigentumsfläche am Core drastisch — ohne neue Plattform. Upstream-Doktrin unterstützt das ausdrücklich: Produktintegrationen gehören als eigenständige Plugin-Repos außerhalb des Core-Trees (`website/docs/developer-guide/plugins/index.md:41-43`), Registrierung über `ctx.register_tool(name=..., toolset=..., schema=..., handler=..., check_fn=...)` (ebd. `:262-275`, `:547-558`).

**Repo.** Neu: eigenständiges PowerUnits-Plugin-Repo (oder zunächst ein isoliertes Verzeichnis außerhalb des Core-Trees). Repo A nur als Referenz. Repo B **unverändert**.

**Wahrscheinliche Dateien/Flächen.** Plugin: `plugin.yaml` (`provides_tools`, `requires_env`), `schemas.py`, `client.py` (**ein** generischer bounded Client: `operation_id` + JSON-Body, kein URL-Feld), `tools.py`, `__init__.py` mit `register(ctx)`. Referenzvorlagen im Fork: `tools/powerunits_bounded_coverage_snapshot_tool.py` (Antwortvertrag, Redaction, Correlation-ID), `tools/powerunits_bounded_family_gates.py` (Gate-Semantik), `tools/powerunits_execute_base_url_v1.py` aus S0-C (Hostbindung).

**Operationskandidaten (alle read-only, alle durch bestehende Routen gedeckt).** Minimum drei, maximal fünf:

| Kandidat | Route | Domainwert |
|---|---|---|
| `read_powerunits_coverage_snapshot_v1` | `/internal/hermes/bounded/v1/coverage-snapshot` | Coverage + Pipeline-Freshness (Data Health) |
| `inventory_powerunits_bounded_coverage_v1` | `/internal/hermes/bounded/v1/coverage-inventory` | Coverage-Familienmatrix |
| `read_powerunits_entsoe_bzn_price_readiness_v1` | `/internal/hermes/bounded/v1/entsoe-bzn-price-readiness/read` | Forecast-/Preis-Readiness |
| `readiness_powerunits_option_d_bounded_window` | `/internal/hermes/bounded/v1/market-features-hourly/readiness-window` | Fenster-Readiness der Modellierungsschicht |
| `read_powerunits_doc` | lokal, allowlistbasiert | Methodik/Doku ohne freien Pfad |

**Umfang.**
1. **Ein** generischer Client: feste Hostbindung, feste Operationsidentität, typisiertes Schema, Bearer nur im Client, Redaction und Größenlimit wie heute.
2. Registrierung über die offizielle Plugin-API mit eigenem Toolset-Namensraum und `check_fn` für Env-Gates.
3. Nachweis, dass der Policy-Cap Plugin-Tools erfasst: Plugin-Toolsets laufen durch die normale Toolset-Auflösung (`model_tools.py:459-463`), müssen also im Cap gelistet sein, um sichtbar zu sein — und dürfen ohne Listung **nicht** sichtbar sein.
4. Antwortverträge bleiben feldkompatibel zur R0-Baseline, damit R3 überhaupt vergleichen kann.

**Ausdrücklich nicht im Scope.** Kein Write, kein Execute, kein Campaign. Kein freies SQL. Kein freier Repo-/Dateipfad. Kein URL-Parameter. Keine Duplizierung der Repo-B-Domainvalidierung im Plugin — Plausibilitätsprüfungen dürfen nur *früh scheitern*, nie *autoritativ erlauben*. Kein `ctx.dispatch_tool()` auf Tools, die der Cap verbietet (das wäre eine Umgehung des Model-Caps). Keine Änderung an Repo-B-Routen oder -Schemata.

**Tests/Evidenz.** Plugin-Unit-Tests mit gemocktem HTTP; Test „Operation ohne Cap-Listung ist unsichtbar“; Test „fremder Host wird verweigert“; Test „kein URL-Feld im Schema“; Feldkompatibilität gegen die R0-Fixtures.

**Akzeptanzkriterien.** (a) Drei bis fünf Read-Operationen liefern in der Proof-Runtime semantisch dieselben Felder wie die Fork-Wrapper. (b) Kein Core-Patch war für die Registrierung nötig — oder der benötigte Patch ist benannt, minimal und begründet. (c) Modellseitig existiert kein Weg zu Host, Pfad, SQL oder Dateipfad. (d) Ein Wrapper-Kollaps ist quantifiziert: wie viele Repo-A-Dateien könnten entfallen.

**Rollback.** Plugin deinstallieren. Der Fork bleibt der Produktionsstand.

**Abhängigkeiten.** R1 (`GATE_1`), S0-C (Hostbindung als wiederverwendbares Muster).

**Menschliche Handlung.** Entscheiden, ob das Plugin ein eigenes Repo erhält (empfohlen) oder zunächst lokal lebt; Nicht-Produktions-Repo-B-Zielumgebung oder Mock-Backend für den Proof freigeben.

```text
SIZE = M
EXPECTED_CURSOR_AUTO_FIT = MEDIUM
RISK = LOW
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Schließt `GATE_2`.

---

### R3 — Shadow Comparison und Migrations-Entscheidungstor

**Ziel.** Repräsentative Aufgaben laufen durch `CURRENT_FORK` und `MODERN_HERMES_PROOF`, und die Migration wird auf Basis von Messwerten entschieden — nicht auf Basis von Architekturvorliebe.

**Warum jetzt.** Dies ist das wichtigste Tor der Roadmap. Alles danach ist teuer; alles davor ist billig. Ein materiell gescheiterter Proof beendet die Migration hier, und das ist ein gutes Ergebnis, nicht ein schlechtes.

**Repo.** Repo A (Harness und Bericht), Plugin-Repo, Repo B nur lesend.

**Wahrscheinliche Dateien/Flächen.** Neu: Vergleichsharness (`scripts/` oder `tests/powerunits_golden/shadow/`), Bericht unter `docs/architecture/`. Eingaben: R0-Fixtures, R2-Plugin, R1-Runtime.

**Umfang.** Ein Aufgabenkorpus aus echten Operatorfragen (Coverage, Data Health, Readiness, Preise, Methodikfrage), jeweils **äquivalent** gestellt, plus Auswertung entlang folgender Dimensionen:

| Dimension | Messweise |
|---|---|
| Korrektheit | Feld-/Wertgleichheit gegen R0-Fixtures |
| PowerUnits-Domainverhalten | Länder/Fenster/Version korrekt gebunden; Provenienzfelder vorhanden |
| Sicherheit | Negativtests: kein verbotenes Tool sichtbar, kein Write ohne Approval, kein fremder Host |
| Toolexposition | Diff der effektiven Toolnamen |
| Prompt-Robustheit | Verhalten bei mehrdeutiger und bei injektionsartiger Eingabe |
| Latenz | Zeit bis erste Antwort und bis Abschluss, pro Aufgabe |
| Modell-/Tokenkosten | Prompt-/Completion-Tokens und Aux-Aufrufe pro Aufgabe |
| Wartbarkeit | Zeilen/Dateien PowerUnits-Code je Operation; Anzahl Policy-Kopien |
| Developer Experience | Aufwand für „eine neue Read-Operation hinzufügen“, gemessen an einem echten Versuch |
| Upstream-Feature-Zugang | Welche gewünschten Primitives sind ohne Eigenbau erreichbar |

**Ausdrücklich nicht im Scope.** Keine Produktionsumstellung. Keine Writes im Vergleich. Kein Ausbau der Proof-Umgebung zur Plattform, um besser abzuschneiden.

**Tests/Evidenz.** Der Harness-Output ist die Evidenz. Jede Dimension braucht mindestens eine objektive Zahl oder einen belegten Diff; „fühlt sich besser an“ zählt nicht.

**Akzeptanzkriterien.** Ein Bericht, der explizit setzt:

```text
MODERN_HERMES_PROOF = FAIL | PROMISING | PASS
```

mit dieser Lesart:

- `PASS` — Korrektheit und Sicherheit gleichwertig oder besser, Kosten/Latenz nicht materiell schlechter, Wartbarkeit klar besser.
- `PROMISING` — Korrektheit/Sicherheit gleichwertig, aber mindestens eine Dimension braucht Nacharbeit; Fortsetzung nur mit benannten Nacharbeiten.
- `FAIL` — Korrektheit, Domainverhalten oder Sicherheit sind schlechter, oder der Aufwand pro Operation steigt. **Dann endet die Migration hier**, S0 bleibt bestehen, und der Fork bleibt Produktionsstand.

Anschließend wird gesetzt:

```text
FUTURE_CORE_STRATEGY =
  RETAIN_CURRENT_FORK | REBASE_DEEP_FORK | THIN_FORK | ZERO_CORE_FORK
```

**Rollback.** Reines Analyseartefakt; nichts umzustellen.

**Abhängigkeiten.** R0, R1, R2. Optional R5 als Beitrag zur Dimension Developer Experience.

**Menschliche Handlung.** Aufgabenkorpus freigeben, Bericht abnehmen, Verdikt setzen. Diese Entscheidung ist ausdrücklich menschlich.

```text
SIZE = M
EXPECTED_CURSOR_AUTO_FIT = MEDIUM
RISK = LOW
ROLLBACK_DIFFICULTY = LOW
```

**Gate.** Schließt `GATE_3`. **Kein späterer Abschnitt gilt als beschlossen, bevor dieses Tor passiert ist.**

---

### R4 — Interne Operator-Erfahrung

**Ziel.** Feststellen, wie Telegram, CLI/TUI und optional Desktop **dieselbe** PowerUnits-Integration konsumieren, statt je eine eigene zu unterhalten.

**Warum jetzt.** Erst nach `GATE_3` sinnvoll — vorher würde Oberflächenarbeit einen unbewiesenen Kern verteuern. Danach ist es der eigentliche Nutzenhebel für Operatoren.

**Repo.** Repo A und Plugin-Repo.

**Wahrscheinliche Dateien/Flächen.** `gateway/run.py` und `gateway/config.py` (Plattform-/Toolsetdurchsetzung), `hermes_cli/tools_config.py` (`_get_platform_tools`), `powerunits_telegram_overlays.py` bzw. dessen Nachfolger, `docker/apply_powerunits_runtime_policy.py`.

**Zentrale Erkenntnis, die R4 lösen muss.** Die heutige Policy ist **oberflächengebunden**: Der Clamp heißt `expected_telegram_toolsets_first_safe`, und `_enforce_powerunits_toolsets()` liefert außerhalb Telegram eine leere Toolsetliste. Desktop läuft am Gateway vorbei. Wer Desktop oder CLI als Operatoroberfläche zulässt, braucht deshalb **eine oberflächenparametrisierte Policyquelle** — sonst gibt es entweder keine Tools oder keinen Cap.

**Umfang (zwei Unterscheiben).**

- **R4a — Oberflächenunabhängige Exposition.** Eine Policyquelle, die pro Oberfläche eine erlaubte Toolsetmenge liefert (`telegram`, `cli`, `desktop`), plus je Oberfläche ein Acceptance-Test auf die finale Toolmenge. Danach Telegram-Parität auf der modernen Runtime nachweisen. `SIZE = S`, `AUTO_FIT = MEDIUM`.
- **R4b — Desktop-Read-only-Pilot.** Eine separate Instanz mit eigenem `HERMES_HOME`, read-only Operatorprofil, ohne Write-Gates, ohne MCP/Browser/Computer Use, ohne Multiplex-API-Server. `SIZE = M`, `AUTO_FIT = LOW`.

**Ausdrücklich nicht im Scope.** Telegram wird **nicht** ersetzt. Desktop ist **nicht** erforderlich. Profiles werden **nicht** als Tenant-/Sicherheitsgrenze behandelt. Kein Multiplex-API-Server für Policyvertrauen. Keine öffentliche Exposition. Keine Bot-Mode-UI als Sicherheitsvertrag.

**Tests/Evidenz.** Pro Oberfläche ein Positiv-/Negativtest der finalen Toolmenge; Nachweis, dass eine deaktivierte Familie auf **allen** Oberflächen verschwindet; Beleg, dass materiell unterschiedliche Trust Domains getrennte Instanzen/Credentials nutzen.

**Akzeptanzkriterien.** (a) Genau eine PowerUnits-Integration versorgt alle genutzten Oberflächen. (b) Jede Oberfläche hat einen erzwungenen, getesteten Cap. (c) Telegram-Verhalten bleibt gegen R0 gleichwertig. (d) Desktop bleibt read-only und optional.

**Rollback.** Desktop-Instanz abschalten; Telegram-Pfad bleibt unberührt.

**Abhängigkeiten.** `GATE_3`.

**Menschliche Handlung.** Entscheiden, ob Desktop überhaupt eingeführt wird; Instanz-/Credentialtrennung je Trust Domain freigeben.

```text
SIZE = M
EXPECTED_CURSOR_AUTO_FIT = MEDIUM
RISK = MEDIUM
ROLLBACK_DIFFICULTY = MEDIUM
```

**Gate.** Schließt `GATE_4`.

---

### R5 — Developer Hermes

**Ziel.** Eine bewusst **mächtige** Entwicklerinstanz, die im Workspace viel darf und in der Produktion nichts.

**Warum jetzt.** R5 hängt nur an `GATE_1`, nicht an `GATE_3`: Eine Instanz ohne Produktionsautorität kann keine Produktionswirkung haben und darf deshalb parallel laufen. Sie beschleunigt zusätzlich alle übrigen Scheiben und liefert Messwerte für die Developer-Experience-Dimension in R3.

**Repo.** Repo A (Profil-/Containerdefinition, Dokumentation). Kein Produktionsdeployment.

**Wahrscheinliche Dateien/Flächen.** Eigenes `HERMES_HOME`/Profil, Container-/Devcontainer-Definition, `docs/agent_context/` Ergänzung; Referenz für die Credentialgrenze: `tui_gateway/host_supervisor.py:313-314`.

**Umfang.** Instanz mit Repo-A/B-Lese- und -Schreibrecht im Workspace, Codesuche, Git, Tests, Terminal, Websuche, Skills; später kontrollierte Delegation mit Budget. Sicherheitsziel:

```text
POWERFUL_IN_WORKSPACE
NOT_POWERFUL_IN_PRODUCTION
```

Die Trennung erfolgt **an der Prozess-/Containergrenze**, nicht per Datei-Allowlist:

| Getrennt | Umsetzung |
|---|---|
| Repo-/Workspace-Rechte | Container-Mount des Arbeitsbaums, schreibbar |
| Produktions-DB-Credentials | `DATABASE_URL_TIMESCALE` existiert im Container nicht |
| Repo-B-Execute-Secret | `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` existiert nicht |
| Railway-/Vercel-Credentials | nicht vorhanden; Deployments bleiben menschlich |
| Destruktive Produktionsaktionen | technisch unerreichbar, nicht nur unerlaubt |

Warum Env-**Abwesenheit** und nicht Redaction: Der Host-Supervisor baut ein sanitisiertes Env und ruft danach `env.update(os.environ)`. In-Process-Redaction ist damit nachweislich keine Credentialgrenze — die Grenze muss außerhalb des Prozesses liegen.

**Ausdrücklich nicht im Scope.** Keine Nachbildung des stark eingeschränkten Operator-Hermes für Entwicklerarbeit. Keine tausenden Datei-/Pfad-Allowlist-Einträge. Kein Produktionszugriff „nur zum Debuggen“. Keine autonome Delegation ohne Budget.

**Tests/Evidenz.** Env-Assertion: die vier Produktionscredential-Namen sind im Developer-Container nicht gesetzt. Negativtest: ein bounded Execute-Tool ist mangels Secret/Gate nicht verfügbar. Nachweis, dass ein Workspace-Schreibvorgang das Produktionssystem nicht erreichen kann.

**Akzeptanzkriterien.** (a) Entwickler arbeiten ohne Einzelfreigaben produktiv. (b) Kein Produktionscredential im Prozess. (c) Die Isolationsgrenze ist Container/Workspace, belegt durch Test, nicht durch Policy-Text.

**Rollback.** Instanz löschen; keine Produktionswirkung möglich.

**Abhängigkeiten.** `GATE_1`.

**Menschliche Handlung.** Vertrauensdomäne bestätigen; Container-/Sandboxform wählen; klarstellen, dass Deployments menschlich bleiben.

```text
SIZE = M
EXPECTED_CURSOR_AUTO_FIT = MEDIUM
RISK = MEDIUM
ROLLBACK_DIFFICULTY = MEDIUM
```

**Gate.** Kein Produktionsgate. Liefert Evidenz für `GATE_3` und beschleunigt R2/R4/R7.

---

### R6 — Bounded Writes

**Ziel.** Ausgewählte bestehende PowerUnits-Write-/Execute-Fähigkeiten auf die moderne Integration bringen, mit Kontrollen **proportional zum realen Risiko**.

**Warum jetzt.** Erst nachdem read-only modernes Hermes nachweislich nützlich ist. Writes zuerst zu migrieren würde Risiko ohne belegten Nutzen kaufen.

**Repo.** Plugin-Repo (Auslösung, Identität, Approval), Repo B (Idempotenz/Dedupe, falls erforderlich).

**Wahrscheinliche Dateien/Flächen.** Plugin-Client und -Schemata; die Effekt-Registry aus S0-B als Quelle der Effektklasse; Repo-B-Router/Service nur, wenn Idempotenz nachweislich gebraucht wird.

**Umfang (zwei Unterscheiben).**

- **R6a — Eine einzige Write-Operation.** Die risikoärmste `BOUNDED_WRITE`-Operation (ein einzelner Slice-`recompute`) mit expliziter Operationsidentität, serverseitiger Validierung (unverändert Repo B), Human-Approval über den bereits vorhandenen Gate-Pfad und Audit-Korrelation über `correlation_id`/`pipeline_run_id`. `SIZE = S`, `AUTO_FIT = MEDIUM`.
- **R6b — Idempotenz nur bei Bedarf.** Nur wenn R6a einen realen Doppellauf- oder Parallelitätsschaden zeigt: durable Deduplizierung in Repo B (der `idempotency_key` ist heute reserviert und wirkungslos). `SIZE = M`, `AUTO_FIT = LOW`, Repo B.

Reihenfolge der Kandidaten: einzelne Slice-Executes vor Campaign-Operationen. `BOUNDED_WRITE_AMPLIFYING` (Campaigns) migriert **zuletzt** und nur mit Slice-Budget.

**Ausdrücklich nicht im Scope.** Keine write-spezifischen Credentials, kein dedizierter Audit-Store, keine Capability-Tokens, keine Result-Firewall — **es sei denn**, R6a zeigt eine konkrete Bedrohung oder eine betriebliche Notwendigkeit. Kontrollen ohne belegten Anlass werden nicht gebaut.

**Tests/Evidenz.** Approval-Verweigerung blockiert den Write; Doppelaufruf-Verhalten dokumentiert; Audit-Kette von der Operatoranfrage bis `pipeline_run_id` nachvollziehbar; Negativtest gegen falsches Land/Fenster (Repo B verwirft).

**Akzeptanzkriterien.** (a) Kein Write ohne Approval-Entscheidung. (b) Effekt- und Operationsidentität sind explizit. (c) Audit-Korrelation ist Ende-zu-Ende belegbar. (d) Jede zusätzliche Kontrolle hat einen benannten Anlass.

**Rollback.** Write-Operation einzeln per Gate deaktivieren; Readiness/Validate bleiben verfügbar.

**Abhängigkeiten.** `GATE_3`, `GATE_4`, S0-B.

**Menschliche Handlung.** Freigabe der ersten Write-Operation; Entscheidung über Approval-Kanal und Reaktionszeit.

```text
SIZE = M
EXPECTED_CURSOR_AUTO_FIT = LOW
RISK = HIGH
ROLLBACK_DIFFICULTY = MEDIUM
```

**Gate.** Schließt `GATE_5`.

---

### R7 — Fork-Reduktion / Retirement

**Ziel.** Die PowerUnits-Eigentumsfläche am Hermes-Core auf das kleinste wirtschaftlich begründete Maß senken — nicht auf Null um jeden Preis.

**Warum jetzt.** Erst nachdem modernes Hermes Parität oder Überlegenheit gezeigt hat. Vorher wäre Forkabbau ein Rückbau der einzigen funktionierenden Produktionsbasis.

**Repo.** Repo A, Plugin-Repo, Upstream (PRs).

**Umfang.** Jeder verbleibende Core-Patch erhält genau eine Klasse:

```text
DELETE | MOVE_TO_PLUGIN | UPSTREAM_PR | TEMPORARY_THIN_FORK | PERMANENT_LOCAL_PATCH
```

Weil R7 als Ganzes zu groß für eine fokussierte PR ist, wird es in vier Unterscheiben zerlegt:

- **R7a — Patch-Ledger.** Vollständige Klassifikation aller verbleibenden Patchfamilien mit Begründung. Reines Dokument. `SIZE = S`, `AUTO_FIT = HIGH`, `RISK = LOW`.
- **R7b — `DELETE` und `MOVE_TO_PLUGIN` in Familienbatches.** Eine PR pro Familie, jede gegen die R0-Golden-Suite abgesichert. `SIZE = S` pro Batch, `AUTO_FIT = MEDIUM`, `RISK = MEDIUM`.
- **R7c — Upstream-PRs.** Für generisch nützliche Patches (env-getriebene Cache-Invalidierung, Provider-/Kompatibilitätsverhalten, `session_search`-Ownership-Scoping als `SCOPE`-Variante aus S0-A). `SIZE = S` pro PR, `AUTO_FIT = MEDIUM`, `RISK = LOW`.
- **R7d — Charta der behaltenen Patches.** Für jeden verbleibenden Patch: Grund, Owner, Tests, erwartete Lebensdauer, Exit-Kriterium. `SIZE = XS`, `AUTO_FIT = HIGH`, `RISK = LOW`.

Arbeitsklassifikation als Startpunkt für R7a (aus der Reassessment-Familienliste, zu bestätigen):

| Familie | Klasse | Zielklasse |
|---|---|---|
| PowerUnits-Domainadapter (ENTSO-E, ERA5, Preise, Forecasts, Outages, Coverage, Remediation) | `ADDITIVE_POWERUNITS_CODE` | `MOVE_TO_PLUGIN` |
| Allowlist-/Manifest-Leser (Repo B, Timescale, Docs, Workspace) | `ADDITIVE_POWERUNITS_CODE` | `MOVE_TO_PLUGIN` |
| First-Safe Clamp (Bootstrap, Gateway, `model_tools.py`, `toolsets.py`) | `SHARED_CORE_PATCHES` | `PATCHES_THAT_MAY_STILL_REQUIRE_THIN_FORK` — entscheidet R1 (`CLAMP_EQUIVALENCE`) |
| Capability-Tier-/Oberflächen-Overlays | `ADDITIVE_POWERUNITS_CODE` + kleiner Configanteil | `MOVE_TO_PLUGIN` |
| Env-getriebene Cache-Invalidierung / Registry-Fingerprint | `SHARED_CORE_PATCHES` | `UPSTREAM_PR` |
| Pfadcontainment und Draft-/Review-Governance | `ADDITIVE_POWERUNITS_CODE` | `MOVE_TO_PLUGIN` |
| Energiebezogene Web-Recherche-Begrenzung und Scope-Warnungen | `ADDITIVE_POWERUNITS_CODE` | `MOVE_TO_PLUGIN` |
| Option-D-/Tier-4B-/Tier-5A-Workflows und Human Gates | `ADDITIVE_POWERUNITS_CODE` | `MOVE_TO_PLUGIN` (Approval via vorhandenes Gate bzw. `pre_tool_call`-Hook) |
| Provider-/OpenAI-Kompatibilität | `SHARED_CORE_PATCHES` | `UPSTREAM_PR` |
| Railway-/Docker-Kompatibilität | `TEMPORARY_COMPATIBILITY_PATCHES` | `PERMANENT_LOCAL_PATCH` mit Exit-Kriterium, bevorzugt Deployment-Layer |
| Modell-/Kostenpolicy | überwiegend Konfiguration | `DELETE` (nach Configumzug) |

**Ausdrücklich nicht im Scope.** Kein Rebase eines tiefen Forks als Selbstzweck. Kein Löschen von Patches ohne Golden-Suite-Absicherung. Keine Nullfork-Erzwingung gegen wirtschaftliche Vernunft.

**Tests/Evidenz.** R0-Golden-Suite nach jedem Batch grün; effektive Oberfläche unverändert; Zählung der PowerUnits-eigenen Core-Zeilen vor/nach.

**Akzeptanzkriterien.** (a) Kein PowerUnits-Domaincode mehr im Agent-Core. (b) Jeder behaltene Patch hat Grund, Owner, Tests, Lebensdauer und — wo möglich — Exit-Kriterium. (c) Upstream-Upgrades laufen über die automatisierte Acceptance-Suite.

**Rollback.** Die letzte funktionierende Forkversion bleibt intern verfügbar (mindestens N−2), inklusive kompatiblem State-Snapshot.

**Abhängigkeiten.** `GATE_3`, plus `GATE_5` für alles, was Write-Pfade berührt.

**Menschliche Handlung.** Owner je behaltenem Patch benennen; Upstream-PR-Strategie freigeben.

```text
SIZE = L (deshalb in R7a–R7d zerlegt; jede Unterscheibe XS–S)
EXPECTED_CURSOR_AUTO_FIT = MEDIUM
RISK = MEDIUM
ROLLBACK_DIFFICULTY = MEDIUM
```

**Gate.** Schließt `GATE_6`.

---

## 8. Decision Gates

Kein Abschnitt gilt als beschlossen, bevor sein Vorgängertor passiert ist.

| Gate | Bedeutung | Geschlossen durch | Objektives Kriterium | Wer entscheidet |
|---|---|---|---|---|
| `GATE_0` | aktuelle Sicherheit akzeptabel | S0-A, S0-B, S0-C | `session_search` nicht exponiert; jede Operation klassifiziert; kein Write ohne Approval; Zielhost über einen Resolver geprüft | Security-Owner |
| `GATE_1` | modernes Hermes läuft isoliert | R1 | reproduzierbar aus Digest; kein Produktionscredential im Prozess; `CLAMP_EQUIVALENCE` beantwortet | Runtime-Owner |
| `GATE_2` | standalone PU-Plugin funktioniert | R2 | 3–5 Read-Ops feldkompatibel; kein Core-Patch nötig oder minimal begründet; kein Host-/Pfad-/SQL-Freiheitsgrad | Runtime-Owner |
| `GATE_3` | Shadow-Vergleich rechtfertigt Migration | R3 | Bericht mit `MODERN_HERMES_PROOF` und `FUTURE_CORE_STRATEGY`, jede Dimension belegt | Mensch, ausdrücklich |
| `GATE_4` | interne Desktop-/Telegram-Architektur tragfähig | R4 | eine Integration, pro Oberfläche erzwungener und getesteter Cap, Telegram-Parität | Operations-Owner |
| `GATE_5` | bounded Writes ausreichend sicher | R6 | Approval erzwungen, Audit Ende-zu-Ende, Doppellaufverhalten dokumentiert | Security- + Data-Owner |
| `GATE_6` | alter Core-Fork reduzierbar/abbaubar | R7 | Golden-Suite grün, kein Domaincode im Core, Charta für behaltene Patches | Runtime-Owner |

Abbruchregeln:

- `MODERN_HERMES_PROOF = FAIL` → Migration endet. S0 bleibt, Fork bleibt Produktionsstand, R5 darf weiterlaufen.
- `CLAMP_EQUIVALENCE = PATCH_REQUIRED` → `ZERO_CORE_FORK` ist ausgeschlossen; `THIN_FORK` wird der Zielkorridor.
- Scheitert R2 an der Plugin-Mechanik → zurück auf Wrapper-Kollaps im bestehenden Fork; die Autoritätsgrenze bleibt trotzdem gültig.

---

## 9. Desktop- und Telegram-Strategie

Die Zielfrage lautet: Wie erreichen wir eine Welt, in der Desktop, Telegram und CLI/TUI **alternative interne Oberflächen über derselben** Integration sind?

Die Antwort hat drei Bedingungen, und alle drei sind konkret:

1. **Genau ein Integrationsartefakt.** Die PowerUnits-Operationen leben in **einem** standalone Plugin (R2). Oberflächen konsumieren es; keine Oberfläche bringt eigene PowerUnits-Implementierung mit. Das ist der wichtigste Einzelpunkt — heute existieren rund 30 nahezu identische Wrapper, und jede weitere Oberfläche würde diese Zahl sonst vervielfachen.
2. **Oberflächenparametrisierte Policy statt Telegram-Sonderfall.** Der heutige Cap ist an Telegram gebunden, und außerhalb Telegram liefert die Gateway-Durchsetzung eine leere Toolsetliste; Desktop läuft am Gateway ohnehin vorbei. R4a ersetzt das durch eine Policyquelle mit Oberflächenschlüssel und je Oberfläche einem Acceptance-Test auf die **finale** Toolmenge. Ohne diesen Schritt bekommt Desktop entweder gar keine Tools oder keinen Cap — beides unbrauchbar.
3. **Getrennte Instanzen statt Multiplex.** Materiell unterschiedliche Trust Domains erhalten eigene Instanzen und Credentials. Multiplex-API-Server werden im Operatorpfad nicht genutzt, solange per-Profile-Toolsetdurchsetzung dort nicht belastbar ist. Profiles bleiben ein Zustands- und UX-Konstrukt, keine Sicherheitsgrenze.

Positionen:

```text
TELEGRAM = KEEP        # bleibt die primäre Operatoroberfläche, wird nicht ersetzt
DESKTOP  = OPTIONAL    # read-only Pilot erlaubt, nie Voraussetzung
CLI/TUI  = KEEP        # Entwickler- und Betriebswerkzeug
```

Die Architektur muss beides **erlauben** und nichts davon **erzwingen**. Eine Oberfläche darf nur dann Operatorstatus erhalten, wenn ihr Cap getestet und ihr Ingress privat ist.

---

## 10. Developer-Hermes-Strategie

Das Ziel ist ausdrücklich **nicht**, den stark eingeschränkten Operator-Hermes für Entwicklerarbeit zu reproduzieren.

```text
Zielbild = trusted development workspace
         + sandbox boundary
         + no production authority
```

Warum grobkörnige Isolation die richtige Wahl ist:

- **Tausende Einzelfreigaben sind kein Sicherheitsmodell.** Sie erzeugen Drift, veralten und suggerieren Kontrolle, die eine Datei-Allowlist gegen In-Process-Code (Plugins, Hooks, MCP) ohnehin nicht liefert.
- **Die reale Grenze liegt am Prozess.** Belegt: der Host-Supervisor überschreibt sein sanitisiertes Env mit `os.environ`. Ein Secret, das im Container existiert, ist erreichbar. Also darf es dort nicht existieren.
- **Der Blast Radius wird durch Abwesenheit begrenzt, nicht durch Verbote.** Ohne Timescale-DSN gibt es kein freies SQL. Ohne Execute-Secret gibt es keinen bounded Write. Ohne Railway-Token gibt es kein Deployment.

Was Developer Hermes darf: Repo A und B lesen und schreiben, Codesuche, Git, Tests ausführen, Terminal, Websuche, Skills, später budgetierte Delegation.

Was er strukturell nicht kann: Produktions-DB berühren, bounded Writes auslösen, Infrastruktur mutieren, Produktionssecrets lesen.

Für den **Operatorpfad** gilt bewusst das Gegenteil: dort bleiben bounded Business-Operationen die Zugriffsform — kein breiter Filesystem- oder Datenbankzugriff. Die zwei Pfade werden nicht vereinheitlicht; sie haben unterschiedliche Bedrohungsmodelle.

```text
DEVELOPER_HERMES_TARGET = POWERFUL_WORKSPACE_AGENT
```

---

## 11. Thin Fork vs Zero Fork — Entscheidungsrahmen

Heute wird **nicht** entschieden. Entschieden wird nach Messwerten aus R1–R3.

Klassifikationssprache für jeden lokalen Patch:

```text
ADDITIVE_POWERUNITS_CODE            → gehört ins Plugin, kostet beim Merge fast nichts
SHARED_CORE_PATCHES                 → der eigentliche Forkpreis
TEMPORARY_COMPATIBILITY_PATCHES     → Deployment-/Plattformkompatibilität mit Exit-Kriterium
PATCHES_THAT_CAN_MOVE_TO_PLUGIN     → Reduktionskandidaten
PATCHES_THAT_MAY_STILL_REQUIRE_THIN_FORK → begründete Restfläche
```

Entscheidungsregel:

| Bedingung | Ergebnis |
|---|---|
| `CLAMP_EQUIVALENCE = CONFIG_SUFFICIENT` **und** R2 ohne Core-Patch **und** Provider-/Deploymentbedarf per Konfiguration lösbar | `ZERO_CORE_FORK` möglich |
| Clamp braucht Patch, aber die Restfläche ist klein, testabgedeckt und upstream-fähig | `THIN_FORK` |
| Restfläche bleibt groß oder berührt schnell bewegte Upstream-Nähte | `REBASE_DEEP_FORK` nur als Zwischenschritt, nie als Ziel |
| `MODERN_HERMES_PROOF = FAIL` | `RETAIN_CURRENT_FORK`, Migration endet |

Ökonomische Leitlinie: Migrationsschuld wird an **geteilten Core-Dateien und echten Konflikten** gemessen — nicht an der Gesamtzahl geänderter Dateien und nicht an der Upstream-Commit-Distanz. Additive Dateien sind billig; geteilte Nähte sind teuer.

Für jeden behaltenen Patch gilt ohne Ausnahme: Grund, Owner, Tests, erwartete Lebensdauer, Exit-Kriterium wo möglich.

---

## 12. Future / Not Part of This Roadmap

Diese Themen bleiben gültige Zukunftsbeschränkungen. Sie erhalten hier **keine** Implementierungsscheiben und dürfen die laufende Migration nicht vergrößern.

```text
FUTURE_SEPARATE_INITIATIVE
```

- **Customer Copilot** — eigenes Produktprogramm, produktseitige Grenze, nicht Hermes-UI.
- **Tenant-Architektur** und Mandantenautorität.
- **Customer Sessions und Memory**, inklusive Consent, Retention, Export, Löschung.
- **Customer Entitlements** und Verknüpfung mit Operationen.
- **Öffentliches Multi-Tenant-Hermes**.
- **Vollständige Enterprise-Identity-Plane** (OIDC, mTLS, Workload Identity, kurzlebige Capability-Tokens).
- **Umfangreiche Artefakt-/Signing-Infrastruktur** (interne Registry-Spiegelung, Release-Signing, SBOM als Gate) — erst wenn nach `GATE_3` begründet.
- **Result-Firewall als eigenes System**, dedizierter Audit-Store, ephemere Execution Plane, allgemeine Egress-Firewall.

Grund für die Zurückstellung ist nicht Zweifel an ihrer Richtigkeit, sondern Reihenfolge: Ein interner Agent braucht keine Tenant-Memory-Governance, um Coverage-Reads zu migrieren.

---

## 13. Kosten- und Komplexitätsüberblick

| Scheibe | Ziel in einem Satz | SIZE | AUTO_FIT | RISK | ROLLBACK | Gate |
|---|---|---|---|---|---|---|
| S0-A | `session_search` aus First-Safe entfernen | XS | HIGH | LOW | LOW | GATE_0 |
| S0-B | Effektklassen + deterministisches Write-Gate | S | MEDIUM | MEDIUM | LOW | GATE_0 |
| S0-C | Zielhost über einen Resolver pinnen | S | HIGH | MEDIUM | LOW | GATE_0 |
| R0 | Golden Behaviour Baseline | S | HIGH | LOW | LOW | → GATE_1 |
| R1 | isolierte moderne Proof-Runtime | M | LOW | LOW | LOW | GATE_1 |
| R2 | standalone PU-Plugin, 3–5 Read-Ops | M | MEDIUM | LOW | LOW | GATE_2 |
| R3 | Shadow-Vergleich und Entscheidungstor | M | MEDIUM | LOW | LOW | GATE_3 |
| R4a | oberflächenparametrisierte Exposition | S | MEDIUM | MEDIUM | LOW | → GATE_4 |
| R4b | Desktop-Read-only-Pilot | M | LOW | MEDIUM | MEDIUM | GATE_4 |
| R5 | Developer Hermes | M | MEDIUM | MEDIUM | MEDIUM | — |
| R6a | eine bounded Write-Operation | S | MEDIUM | HIGH | MEDIUM | → GATE_5 |
| R6b | Idempotenz nur bei Bedarf (Repo B) | M | LOW | HIGH | MEDIUM | GATE_5 |
| R7a | Patch-Ledger | S | HIGH | LOW | LOW | → GATE_6 |
| R7b | `DELETE`/`MOVE_TO_PLUGIN` je Familie | S | MEDIUM | MEDIUM | MEDIUM | → GATE_6 |
| R7c | Upstream-PRs | S | MEDIUM | LOW | LOW | → GATE_6 |
| R7d | Charta behaltener Patches | XS | HIGH | LOW | LOW | GATE_6 |

Beobachtungen zur Kostendisziplin:

- Alles bis `GATE_3` ist **XS–M** und passt in einzelne fokussierte PRs. Das ist Absicht: Der teure Teil beginnt erst nach dem Nutzenbeweis.
- Keine Scheibe verlangt eine neue Plattform. Die einzigen `HIGH`-Risiken sind Write-Pfade, und die kommen zuletzt.
- Niedriger `AUTO_FIT` konzentriert sich auf Umgebungs-, Container- und Deploymentarbeit — dort ist menschliche Hand ohnehin nötig.
- Bewusst **nicht** gebaut: OIDC, mTLS, Token-Broker, Result-Firewall, Audit-Store, Execution Plane, Egress-Firewall, Signing-Gates. Jede dieser Positionen wartet auf einen konkreten Anlass.

---

## 14. Empfohlene erste Implementierungsscheibe

**S0-A — `session_search` aus der First-Safe-Oberfläche entfernen.**

Begründung: höchste Sicherheitswirkung pro Aufwand im gesamten Plan. Eine Zeile in einer PowerUnits-eigenen Datei plus zwei Tests, keine Shared-Core-Schuld, sofort reversibel, und sie muss ohnehin **vor** R0 landen, damit die Golden Baseline nicht eine Oberfläche einfriert, die unmittelbar danach geändert wird.

Unmittelbar danach **R0 — Golden Behaviour Baseline**, weil ohne diese Messlatte keine der folgenden Scheiben bewertbar ist.

S0-B und S0-C können parallel zu R0/R1 laufen; sie blockieren nichts, schließen aber gemeinsam `GATE_0`.

Was in der ersten PR **nicht** passieren darf: kein Eingriff in `tools/session_search_tool.py`, keine Änderung an Repo-B-Routen, keine Deployment- oder `.env`-Änderung, keine Erweiterung des Toolkatalogs.

---

## 15. Handover-Prompt-Outline für den nächsten Agenten

Der Folgeauftrag ist **eine Implementierungsscheibe**, nicht die Roadmap. Vorgeschlagene Struktur:

```text
# Mission
Implementiere Scheibe S0-A aus docs/architecture/hermes_modernisation_execution_roadmap_v1.md.
Führe keine Architekturbewertung durch. Implementiere keine andere Scheibe.

# Kontext (verbindlich, nicht neu zu untersuchen)
- Roadmap: docs/architecture/hermes_modernisation_execution_roadmap_v1.md
- Entscheidungsgrundlage: hermes_upstream_reassessment_v1.md + _red_team_v1.md
- RED_TEAM_VERDICT = AFFIRM_SPLIT_BUT_SIMPLIFY
- S0_A_TREATMENT = DISABLE

# Aufgabe
1. session_search aus TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1 entfernen
   (powerunits_telegram_overlays.py).
2. Negativtest: unter HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1 ist
   session_search in keinem Tier 0-6 in der finalen Toolmenge, auch bei
   expliziter Toolset-Anforderung.
3. Overlay-Ordnungstests und erwartete Toolanzahlen angleichen.
4. Kurzen Vermerk mit Exit-Kriterium in der Runtime-Enforcement-Doku ergänzen.

# Ausdrücklich verboten
- tools/session_search_tool.py ändern
- Repo-B-Routen, Deployment, .env, Secrets berühren
- weitere Tools/Toolsets hinzufügen oder entfernen
- Prompt-Caching-Invarianten brechen

# Evidenzpflicht
- Testlauf des kleinsten relevanten Ziels zeigen (Overlay- + Surface-Tests)
- Diff der effektiven Toolnamen vor/nach im PR-Text

# Akzeptanz
- alle vier Aufgabenpunkte erfüllt
- Suite grün, kein Test schreibt nach ~/.hermes/
- Rollback = eine Zeile

# Danach vorschlagen (nicht ausführen)
- R0 Golden Behaviour Baseline als nächste Scheibe
```

Dieselbe Struktur passt für jede weitere Scheibe: Missionsatz, verbindlicher Kontext, numerierte Aufgabe, explizites Verbot, Evidenzpflicht, Akzeptanz, nächster Vorschlag ohne Ausführung.

---

## 16. Abschlussblock

```text
HERMES_MODERNISATION_ROADMAP = PASS

CURRENT_DIRECTION =
  MODERN_UPSTREAM_NEAR_HERMES
  + STANDALONE_POWERUNITS_INTEGRATION
  + EXISTING_REPO_B_BOUNDED_BOUNDARY

CUSTOMER_COPILOT = FUTURE_SEPARATE_INITIATIVE

FIRST_SLICE = S0-A  session_search aus der First-Safe-Oberflaeche entfernen
SECOND_SLICE = R0   Golden Behaviour Baseline
FIRST_MAJOR_DECISION_GATE = GATE_3  Shadow-Vergleich rechtfertigt Migration

DESKTOP_TARGET = OPTIONAL
TELEGRAM_TARGET = KEEP
DEVELOPER_HERMES_TARGET = POWERFUL_WORKSPACE_AGENT

CORE_FORK_END_STATE = TO_BE_PROVEN

S0_A_TREATMENT = DISABLE
S0_B_TREATMENT = EFFECT_REGISTRY + EXISTING_APPROVAL_GATE + YOLO_HARDLINE
S0_C_TREATMENT = SINGLE_RESOLVER_HOST_ALLOWLIST_WARN_THEN_ENFORCE
DESTRUCTIVE_TOOLS_IN_FIRST_SAFE = NONE_FOUND

OVERENGINEERING_GUARD = PROOF_BEFORE_PLATFORM

ROADMAP_CONFIDENCE = 7.5/10
```

Begründung der Konfidenz: Die S0-Befunde und die Effektklassifikation sind am Quellcode belegt, die Gate-Struktur ist objektiv prüfbar, und keine Scheibe vor `GATE_3` verlangt Plattformarbeit. Abzug, weil `CLAMP_EQUIVALENCE`, die Plugin-Tragfähigkeit und der Kosten-/Latenzvergleich unausgeführte empirische Fragen bleiben — genau deshalb sind sie als Tore modelliert und nicht als Annahmen.
