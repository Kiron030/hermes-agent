# Powerunits × Hermes Integration Pattern v1 — "Merging Pattern"

**Status:** Kanonisch, extrahiert aus einer bereits gemergten Implementierung (Tavily
`research_powerunits_energy_web_v1`, PRs #55/#56 auf `powerunits-internal-setup`).
Dieses Dokument beschreibt **kein neues Feature** — es dokumentiert das **wiederholbare
Muster**, nach dem neue externe/interne Bounded-Tools in Repo A (`hermes-agent`) auf den
Powerunits-Telegram-Layer aufgesetzt werden, damit künftige Integrationen (weitere Web-
Provider, weitere Repo-B-Slices, weitere Skills) nicht jedes Mal neu erfunden werden.

---

## 1. Zweck & wann verwenden

**Zweck:** Ein einheitliches, geprüftes Rezept dafür, wie ein neues Werkzeug — ob
externe API (Tavily, künftig ggf. weitere Web-/Daten-Provider) oder ein weiterer
bounded Read/Write-Zugriff auf Repo B — **additiv** in den bestehenden Hermes-Fork
eingehängt wird, ohne:

- die Upstream-Mechanik (Toolset-Registry, Slash-Commands, Gateway-Dispatch) zu
  verändern,
- eine zweite, parallele Autoritätsschicht für Repo-B-Daten zu erzeugen,
- den Telegram-"Trusted Analyst"-Kontrakt (`ACCESS_MATRIX.md`, `first_safe_v1`) zu
  brechen.

**Wann verwenden:**

- Ein neues externes Tool (Such-API, Datenanbieter, SaaS-Endpoint) soll dem Operator
  über Telegram zur Verfügung stehen.
- Ein neuer bounded Read/Write-Zugriff auf Repo B (`EU-PP-Database`) soll als
  eigenständiges Tool exponiert werden (analog zu den ~55 existierenden
  `powerunits_*`-Tools).
- Eine bestehende generische Fähigkeit (z. B. `web_search`) soll einen
  Powerunits-spezifischen Envelope (Guardrails, Disclaimer, Herkunfts-Markierung)
  bekommen, **ohne** die generische Fähigkeit selbst zu verändern.

**Wann NICHT verwenden:** Wenn es nur um eine Änderung an bestehenden Repo-B-Endpunkten
geht (das ist Repo-B-Scope, nicht Repo-A/Hermes) oder wenn die generische Upstream-
Fähigkeit (z. B. `web_search`) für den Anwendungsfall bereits ausreicht (siehe
Entscheidungsbaum, Abschnitt 4).

---

## 2. Repo-Split — Autorität Repo A vs. Repo B

| | **Repo A** (`hermes-agent`, dieses Repo) | **Repo B** (`EU-PP-Database`) |
|---|---|---|
| Rolle | Agent-Runtime, Tool-Calling-Oberfläche, Telegram-Gateway | Datenplattform: PostgreSQL/PostGIS/Timescale, FastAPI, ENTSO-E/ERA5/GEM-Ingestion |
| Owns Schema | Nein | Ja — alleinige Quelle der Wahrheit für Marktdaten, Assets, Wetter |
| Direkter DB-Zugriff aus Hermes | Nur eng bounded Read-Patterns (`powerunits_timescale_read` — eine fixe View, feste Query-Muster) | — |
| Schreibpfade | **Nie** direkte SQL-Writes aus Hermes. Jeder Write läuft über **eine** bounded HTTP-POST an Repo B's internes Execute-API (`POWERUNITS_INTERNAL_EXECUTE_BASE_URL` + `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`) | Alleiniger Ort für Schema-Migrationen, Job-Ausführung, Ingestion |
| Externe Web-/API-Provider (Tavily etc.) | **Ja** — das ist explizit Repo-A-Scope (Agent-Fähigkeit), siehe Abschnitt 3 | Nie — Repo B kennt keine externen Web-Provider |
| Dokumentations-Kanon für diese Integrationen | `docs/powerunits_*_v1.md`, `ACCESS_MATRIX.md`, `toolsets.py`-Beschreibungen | `docs/adr/*` für Schema/Architektur-Entscheidungen |

**Kernregel:** Ein neues Bounded-Tool in Repo A darf **niemals** eine zweite Kopie von
Repo-B-Logik (SQL, Job-Semantik, Validierungsregeln) implementieren. Es darf entweder
(a) **read-only** auf einen expliziten, schmalen Repo-B-Kanal zugreifen (View, Endpoint,
Allowlist-Datei) oder (b) **eine** HTTP-POST an eine Repo-B-eigene bounded Execute-Route
auslösen. Alles, was mehr Repo-B-Wissen bräuchte (z. B. eigene Validierungslogik für
`market_features_hourly`), gehört nach Repo B, nicht in ein Hermes-Tool.

Externe Provider (Tavily, künftige Such-/Daten-APIs) sind die **eine** Ausnahme: Sie
haben keine Repo-B-Autorität und werden komplett in Repo A verdrahtet — aber mit der
expliziten Herkunfts-Markierung aus Abschnitt 3.3, damit sie nie mit Repo-B-Daten
verwechselt werden.

---

## 3. Das wiederholbare Muster — Schritt für Schritt

Referenzimplementierung: `tools/powerunits_energy_web_research_tool.py`
(`research_powerunits_energy_web_v1`), `docs/powerunits_tavily_research_roadmap_v1.md`.

### 3.1 Doppel-Gate (Feature-Flag + Secret/Provider)

Jedes Bounded-Tool ist **fail-closed** hinter zwei unabhängigen Bedingungen:

1. **Feature-Flag** — ein eigener `HERMES_POWERUNITS_<TOOL>_ENABLED`-Env-Var (truthy
   check via `_truthy_env`), unabhängig von jedem anderen Tool/Toolset.
2. **Secret/Provider-Credential** — das tatsächliche Zugangsmittel (`TAVILY_API_KEY`,
   oder für Repo-B-Tools `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` +
   `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`).

Beide müssen erfüllt sein, sonst liefert die `check_powerunits_<tool>_requirements()`-
Funktion `False`, und der Tool-Aufruf gibt **sofort** einen `feature_disabled`-Fehler
zurück, **ohne** einen Outbound-Call zu versuchen:

```python
def check_powerunits_energy_web_research_requirements() -> bool:
    if not _truthy_env(_FEATURE_ENV):
        return False
    if not (os.getenv(_TAVILY_KEY_ENV) or "").strip():
        return False
    return True
```

Warum zwei Gates statt einem: Das Feature-Flag ist der **Operator-Schalter**
(bewusst pro Deployment togglebar, z. B. beim Umschalten `stage1_read_health` ↔
`stage1_operator_execute`), das Secret/Provider ist der **Infrastruktur-Schalter**
(kann versehentlich fehlen, z. B. nach einem Redeploy ohne Env-Var-Übernahme). Ein
einzelnes kombiniertes Flag würde diese beiden Fehlerklassen vermischen und im Posture-
Report (`summarize_powerunits_operator_posture`) schwerer diagnostizierbar machen.

### 3.2 Herkunfts-Markierung (`external_web_context` / `bounded_internal_context`)

Jede Response trägt ein **explizites, maschinenlesbares** Herkunfts-Flag, damit das
Modell (und jeder nachgeschaltete Consumer) nie raten muss, woher ein Datum kommt:

- Externe Provider (Tavily etc.) → `"external_web_context": true`
- Bounded interne Repo-B-Zugriffe → analog ein `bounded_internal_context`-artiges Signal
  (z. B. `promotes_tier1`, `bounded_internal_statement`, `prices_contract` je Tool —
  siehe `ACCESS_MATRIX.md`-Zeilen zu `read_powerunits_entsoe_bzn_prices_v1`).

Diese Flags sind **immer präsent**, auch im Fehlerfall, und werden **nicht** aus dem
Response-Envelope entfernt oder umbenannt, wenn das Tool weiterentwickelt wird (additive
Evolution, siehe AGENTS.md API-Freeze-Prinzip — hier intern auf Tool-Envelopes
übertragen, nicht nur auf die öffentliche FastAPI).

### 3.3 Guardrails + Warnings + Operator Notice + Disclaimer DE

Vierstufige, bewusst redundante Guardrail-Struktur (aus echtem Telegram-Smoke-Test-
Feedback entstanden, siehe Changelog in `docs/powerunits_tavily_research_roadmap_v1.md`):

| Feld | Zielgruppe | Zweck |
|---|---|---|
| `warnings: list[str]` | Modell (maschinenlesbar) | Eine Warnung pro Aspekt (Topic-Guardrail, Naming-Kollision, Numeric-Crosscheck, leere Ergebnisse …) |
| `operator_notice: str` | Modell → Operator (konsolidiert) | Ein zusammengefasster Block, der die `warnings` in Fließtext bündelt, für den Fall, dass das Modell nur ein Feld liest |
| `disclaimer_de: str` | Operator direkt (Telegram-Chat) | Kurzer, deutscher, **verbatim** an den Operator auszugebender Disclaimer |
| `hermes_operator_note_v1: str` | Modell (immer präsent, auch im Fehlerfall) | Englischsprachige Kontrakt-Erinnerung: read-only, kein Repo-B-Call, keine Jobs |

Grundsatz: **Lieber doppelt dokumentiert als einmal vergessen.** Wenn nur eines der
Felder vom Modell gelesen/zitiert wird, muss die Kernaussage trotzdem durchkommen.

### 3.4 Telegram-Overlay-Instruktionen im Tool-Schema

Die Anweisung *"zeige dem Operator immer X"* darf nicht nur in einer Doku stehen — sie
muss **im Tool-Schema selbst** (`description`-Feld) stehen, weil das die einzige Stelle
ist, die auf **jeder** Oberfläche erreicht wird, auf der das Tool registriert ist
(Telegram, CLI, ACP, …). Muster: eine einzige Quelle der Wahrheit in
`powerunits_telegram_overlays.py`, importiert in die Schema-Beschreibung:

```python
# powerunits_telegram_overlays.py
ENERGY_WEB_RESEARCH_TELEGRAM_OVERLAY_INSTRUCTIONS_V1: str = (
    "Whenever `research_powerunits_energy_web_v1` returns a result to you, ALWAYS "
    "surface to the operator, verbatim and in full: (1) the `disclaimer_de` string "
    "..."
)

def energy_web_research_telegram_overlay_instructions() -> str:
    return ENERGY_WEB_RESEARCH_TELEGRAM_OVERLAY_INSTRUCTIONS_V1
```

```python
# tools/powerunits_energy_web_research_tool.py
from powerunits_telegram_overlays import energy_web_research_telegram_overlay_instructions

ENERGY_WEB_RESEARCH_SCHEMA_V1 = {
    "name": "research_powerunits_energy_web_v1",
    "description": (
        "... "
        f"**Operator-facing requirement:** {energy_web_research_telegram_overlay_instructions()}"
    ),
    ...
}
```

**Nicht** die Instruktion an mehreren Stellen duplizieren — importieren, nicht kopieren.

### 3.5 Caps & Read-only-Kontrakt

Jedes neue Tool bringt **eigene, engere** Caps mit, unabhängig von den Defaults der
zugrunde liegenden Bibliothek/API:

- Harte Obergrenzen für Ergebnisanzahl, Extraktionsanzahl, Inhaltslänge
  (`_MAX_RESULTS_CAP`, `_EXTRACT_TOP_URLS_CAP`, `_EXTRACT_CONTENT_CHAR_CAP`).
- Eingaben werden **geklemmt (clamped), nicht abgelehnt** (`_clamp_int`) — robuster für
  ein LLM, das gelegentlich außerhalb des Bereichs anfragt.
- Jede Response enthält einen `caps_applied`-Block, der die effektiv angewendeten Werte
  transparent macht.
- **Nie** beliebige, vom Aufrufer gelieferte URLs/Parameter direkt an einen Fetch/Execute
  weiterreichen, wenn eine engere Alternative existiert (hier: `extract_top_urls`
  extrahiert **nur** aus den eigenen Suchergebnissen, nicht aus Operator-Input — kleinere
  SSRF-adjazente Angriffsfläche als das generische `web_extract`).
- **Read-only per Default.** Schreibpfade (falls überhaupt nötig) sind ein bewusst
  separates, eigenes Tool mit eigenem Gate — kein implizites Upgrade eines Read-Tools.

### 3.6 Tool-Registrierung (`toolsets.py`, `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`)

Zwei getrennte, beide notwendige Registrierungsschritte:

1. **`toolsets.py`** — das Tool bekommt einen eigenen Toolset-Eintrag mit
   Beschreibung, `"tools": [...]`-Liste und ggf. `"includes"`. Das ist die
   Registry-Wahrheit, die z. B. CLI, ACP und Telegram gemeinsam konsumieren.
2. **`powerunits_telegram_overlays.TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`** — das
   Toolset muss **zusätzlich** in dieses Tuple aufgenommen werden, sonst ist es zwar
   registriert, aber auf der Telegram-"Trusted Analyst"-Oberfläche **nicht erreichbar**.
   Dies ist die **einzige Quelle der Wahrheit**, aus der sich
   `gateway/run.py::_powerunits_allowed_telegram_toolsets()`,
   `model_tools.get_tool_definitions()`'s Hard-Cap-Allowlist-Sync und
   `docker/apply_powerunits_runtime_policy.py`'s `ALLOWED_TELEGRAM_TOOLSETS` ableiten —
   **keine** dieser drei Stellen separat editieren.

Reihenfolge in der Praxis (aus der Referenz-PR): neu direkt nach `"vision"` einsortiert,
also bei den anderen Hermes-Core-Read-Toolsets, nicht irgendwo mitten in der
Repo-B-Bounded-Liste.

### 3.7 `ACCESS_MATRIX.md`-Zeile

Eine neue Zeile in der Tabelle in `ACCESS_MATRIX.md`, nach dem etablierten Muster:

```
| **<Kurzname>** (`<tool_name>`) | Allowed **only** when gated | **`<FEATURE_ENV>`** + **`<CREDENTIAL_ENV>`**; <eine-Satz-Beschreibung des Outbound-Calls> — **no** <was es explizit nicht tut>. |
```

Pflichtbestandteile: beide Gate-Variablen fett, der genaue Outbound-Call (wie viele
HTTP-Calls, an welchen Endpoint), und eine explizite Negativliste (keine Jobs, keine
Ingestion, keine Writes, kein Ersatz für Tool X).

### 3.8 Mocked Tests

Kein Tool ohne `tests/tools/test_<tool>.py` mit **vollständig gemocktem** Backend
(Dependency Injection über Funktionsparameter, z. B. `_search_fn` / `_extract_fn`, oder
`_http_post` bei den Repo-B-Bounded-Tools). Kein echter Netzwerk-Call, kein echter API-
Key in CI. Mindestabdeckung, nach Referenzmuster:

- Gate aus (Flag fehlt) → `feature_disabled`
- Secret fehlt trotz Flag an → `check_*_requirements()` liefert `False`
- Ungültige/leere Eingabe → typisierter `error_code`
- Happy Path inkl. Guardrail-Text/Envelope-Feldern
- Cap-Clamping (min/max)
- Backend-Fehler (nicht-fatal, landet als `warnings`-Eintrag wo sinnvoll, sonst
  typisierter Fehler)
- Schema-Form (`ENERGY_WEB_RESEARCH_SCHEMA_V1`-artige Konstante)
- Registry-Discovery (`registry.register` greift, Tool ist auffindbar)
- Präsenz im Telegram-First-Safe-Base-Toolset (Regressionsschutz gegen "registriert,
  aber auf Telegram unsichtbar")

### 3.9 Railway-Env-Vars

Pro neuem Tool: Feature-Flag + Credential auf dem Hermes-Railway-Service setzen, **kein**
weiterer Infra-Change nötig, wenn das Muster eingehalten wurde. Beispiel aus der
Referenzintegration:

```text
HERMES_POWERUNITS_ENERGY_WEB_RESEARCH_ENABLED=1
TAVILY_API_KEY=...
```

Hinweis: Wenn das Credential bereits für eine andere (generische) Fähigkeit existiert
(hier: `TAVILY_API_KEY` wird auch von `web_search`/`web_extract` genutzt), wird **kein
neues Secret** eingeführt — nur ein zusätzliches Feature-Flag für den
Powerunits-spezifischen Envelope.

### 3.10 Smoke-Prompts

Vor "verified" in `ACCESS_MATRIX.md` gehört ein echter Telegram-Smoke-Test-Eintrag
(Operator-Note-Abschnitt), analog zum bestehenden Muster für
`read_powerunits_entsoe_bzn_prices_v1`: konkrete Parameter, beobachtete Response-Felder,
und eine kurze Interpretation, warum die Zahlen plausibel sind. Für ein neues Tool: das
ist ein bewusst **separater, späterer Schritt** (braucht echten Operator + echtes
Deployment) — nicht Teil des initialen Code-PRs, aber im Roadmap-Doc als "Deferred"
vermerkt (siehe Referenzdoc, Teil F).

---

## 4. Entscheidungsbaum — generisches `web_search` erweitern vs. neues Powerunits-Tool

```
Braucht der Anwendungsfall eine Powerunits-spezifische Herkunfts-Markierung,
einen domänenspezifischen Guardrail-Text, oder engere Caps als die generische
Fähigkeit bereits bietet?
│
├─ NEIN → generische Fähigkeit direkt nutzen (z. B. `web_search`/`web_extract`,
│         Toolset `web`/`search`). Kein neues Tool. Ggf. nur einen
│         System-Prompt-Hinweis ergänzen.
│
└─ JA
   │
   ├─ Ist die zugrunde liegende Fähigkeit bereits vorhanden (Adapter/Provider
   │  existiert schon in Repo A, z. B. `plugins/web/tavily/provider.py`)?
   │  │
   │  ├─ JA → **dünner Wrapper** um den existierenden Adapter (Muster aus
   │  │       Abschnitt 3), NICHT den HTTP-Client neu implementieren.
   │  │
   │  └─ NEIN → neuer Adapter nötig — größerer Scope, eigene Bewertung
   │            (eigenes Secret? eigene Rate-Limits? eigene ADR nötig, falls
   │            es eine neue Infrastruktur-Kategorie ist).
   │
   └─ Zusätzlich: berührt der Anwendungsfall Repo-B-Daten (Marktdaten, Assets,
      Wetter)? → Muss über einen bounded HTTP-Call an
      `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` laufen (Abschnitt 2), niemals über
      eine neu erfundene SQL-Verbindung aus Hermes.
```

Konkretes Beispiel aus der Referenzintegration: `research_powerunits_energy_web_v1`
wickelt **denselben** Tavily-Adapter ab, den `web_search`/`web_extract` bereits nutzen —
kein neuer HTTP-Client, kein neues Secret, nur ein zusätzlicher, opt-in Envelope. Das ist
der Regelfall dieses Musters, nicht die Ausnahme.

---

## 5. Anti-Patterns

- **Doppelte Repo-B-Autorität.** Ein Hermes-Tool, das eigene Validierungs-/
  Aggregationslogik für Repo-B-Tabellen implementiert, statt eine bounded Repo-B-Route
  aufzurufen. Repo B bleibt einzige Quelle der Wahrheit für Schema/Semantik.
- **Execute ohne Gate.** Irgendein Pfad, der einen POST an
  `POWERUNITS_INTERNAL_EXECUTE_BASE_URL` (oder einen externen Provider) auslösen kann,
  **ohne** vorherigen `check_powerunits_<tool>_requirements()`-Check. Das Doppel-Gate ist
  nicht optional, auch nicht "nur für den ersten Test".
  ```python
  # Anti-Pattern
  result = search_fn(query, max_results)   # kein check_*_requirements() vorher

  # Pattern
  if not check_powerunits_energy_web_research_requirements():
      return json.dumps({"success": False, "error_code": "feature_disabled", ...})
  result = search_fn(query, max_results)
  ```
- **Registriert, aber auf Telegram unsichtbar.** Toolset nur in `toolsets.py`
  eingetragen, aber vergessen in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` — Tool
  existiert, ist aber für den Operator nicht erreichbar (und das fällt oft erst beim
  Live-Smoke-Test auf, nicht in Unit-Tests, wenn der Test nicht explizit die
  Base-Toolset-Liste prüft — siehe Testpflicht in Abschnitt 3.8, letzter Punkt).
- **Herkunfts-Flag weglassen oder umbenennen.** `external_web_context` /
  vergleichbare Felder sind ein stabiler Vertrag — nicht in einem späteren Refactor
  entfernen oder in ein anderes Feld umbenennen, ohne Migrationspfad für bestehende
  Consumer/Tests.
- **Instruktionstext direkt in der Schema-`description` statt in
  `powerunits_telegram_overlays.py` pflegen.** Führt zu Drift zwischen mehreren
  Kopien derselben Anweisung, sobald das Tool auf mehreren Oberflächen läuft.
- **Ungeklammerte Nutzereingaben** an `max_results`/`extract_top_urls`-artige Parameter
  ohne Cap-Clamping durchreichen — ein LLM kann plausible, aber zu große Werte anfragen.
- **Blast-Radius-Verstoß.** Mehr als die in AGENTS.md vorgesehenen 3–5 Dateien ändern,
  ohne den Files-Limit-Hinweis im Roadmap-Doc zu dokumentieren (siehe
  `docs/powerunits_tavily_research_roadmap_v1.md`, Abschnitt "AGENTS.md file-limit
  note", als Vorbild für die Begründung, wenn 6 Dateien wirklich nötig sind).
- **Zwei nahezu identische Tools dauerhaft parallel pflegen**, ohne die
  Retire-Option zu prüfen. Der Referenz-Roadmap hält explizit fest, dass
  `research_powerunits_energy_web_v1` re-evaluiert werden soll, falls der
  Zusatznutzen gegenüber `web_search` + System-Prompt sich als gering erweist —
  das ist Teil des Musters, nicht ein nachträglicher Kompromiss.

---

## 6. Checklist-Template für neue Tool-PRs

```markdown
## Neues Powerunits-Bounded-Tool: <tool_name>

- [ ] Doppel-Gate implementiert: `HERMES_POWERUNITS_<X>_ENABLED` + Secret/Provider-Var,
      geprüft in `check_powerunits_<tool>_requirements()`, fail-closed vor jedem
      Outbound-Call.
- [ ] Herkunfts-Flag im Response-Envelope (`external_web_context: true` o. ä.), immer
      präsent, auch im Fehlerfall.
- [ ] `warnings[]`, `operator_notice`, `disclaimer_de` (falls Telegram-operator-facing),
      `hermes_operator_note_v1` gesetzt.
- [ ] Telegram-Overlay-Instruktion (falls nötig) als eigene Konstante/Funktion in
      `powerunits_telegram_overlays.py`, importiert in die Tool-Schema-`description` —
      nicht dupliziert.
- [ ] Harte Caps für alle numerischen/Listen-Parameter, `_clamp_int`-artiges Klemmen statt
      Ablehnen, `caps_applied`-Block in der Response.
- [ ] Read-only bestätigt (oder: falls Write, eigenes separates Tool mit eigenem Gate).
- [ ] `toolsets.py` — neuer Toolset-Eintrag mit Beschreibung + `"tools"`.
- [ ] `powerunits_telegram_overlays.TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1` — Toolset-Name
      ergänzt (sonst nicht auf Telegram erreichbar).
- [ ] `ACCESS_MATRIX.md` — neue Zeile mit beiden Gates fett, Outbound-Call-Beschreibung,
      Negativliste.
- [ ] `tests/tools/test_<tool>.py` — vollständig gemockt, deckt: Gate aus, Secret fehlt,
      ungültige Eingabe, Happy Path, Cap-Clamping, Backend-Fehler, Schema-Form,
      Registry-Discovery, Präsenz in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`.
- [ ] Railway-Env-Vars dokumentiert (Feature-Flag + Secret; kein neues Secret, falls
      Credential bereits existiert).
- [ ] Roadmap-/Integrationsdoc unter `docs/powerunits_<tool>_v1.md` mit: Assessment
      existierender Overlaps, Tool-Kontrakt-Tabelle, Guardrails, Rollout-Schritte,
      Testabdeckung, Deferred-Liste (inkl. Live-Smoke-Test als Deferred, falls noch
      nicht ausgeführt).
- [ ] Blast Radius ≤ 5 Dateien, oder explizite Begründung im Roadmap-Doc, falls mehr
      nötig (AGENTS.md-Eskalationspfad).
- [ ] Live-Telegram-Smoke-Test nach Deploy → Eintrag in `ACCESS_MATRIX.md` als
      "Operator note — verified Telegram smoke" (kann als separater Follow-up-PR
      erfolgen).
```

---

## 7. Referenzen

- `docs/powerunits_tavily_research_roadmap_v1.md` — vollständige Roadmap/Assessment der
  Referenzintegration (Tavily), inkl. Overlap-Verdict und Deferred-Liste.
- `docs/powerunits_setup_v2_sustainable_v1.md` — Gesamtinventar aller
  `powerunits_*`-Tools/Toolsets, Bounded-Profile (`stage1_read_health` /
  `stage1_operator_execute`), Telegram-Exposure-Tabelle.
- `ACCESS_MATRIX.md` — kanonische Zugriffstabelle (Allowed/Gated/Forbidden) für die
  Telegram-"Trusted Analyst"-Oberfläche.
- `docs/powerunits_bounded_flags_consolidated_v1.md` — Gate-Modell / Env-Var-Übersicht
  für alle bounded Tools.
- `powerunits_telegram_overlays.py` — Single Source of Truth für
  `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`, Capability-Tier-Overlays, und
  Telegram-Overlay-Instruktionstexte pro Tool.
- `docker/apply_powerunits_runtime_policy.py` — wendet die First-Safe-Policy (inkl.
  gemergter Telegram-Toolset-Liste) auf `config.yaml` beim Boot an.
- `gateway/run.py` (`_powerunits_allowed_telegram_toolsets`,
  `_enforce_powerunits_toolsets`) — Runtime-Enforcement der Telegram-Toolset-Allowlist.
- `docs/powerunits_hermes_progressive_posture_v1.md` — Capability-Tier-Roadmap
  (Tier 0–6), orthogonal zum Bounded-Profil.
