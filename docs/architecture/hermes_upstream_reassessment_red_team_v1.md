# PowerUnits × Hermes: Red-Team Review v1

**Stichtag:** 2026-08-21  
**Gegenstand:** `docs/architecture/hermes_upstream_reassessment_v1.md`  
**Auftrag:** Decisive Claims falsifizieren, nicht den Primärbericht bestätigen.  
**Methode:** gezielte Angriffe auf Urteil, Sequenz, Security, Kosten und PowerUnits-Wert. Kein zweites Full Audit.

## Unveränderliche Evidenzbasis

| System | Referenz | SHA | Nutzung hier |
|---|---|---|---|
| Repo A | lokaler `HEAD` | `c6e43b514eeaf6549b074073fa06b3c4e67e0384` | `VERIFIED` |
| Gemeinsame Basis | Upstream v0.19.0 | `3ef6bbd201263d354fd83ec55b3c306ded2eb72a` | `VERIFIED` lokal vorhanden |
| Upstream-Release | `v2026.8.19` / 0.20.5 | `fcbd1076a93841fa88855acce810e342a5b78101` | Objekt lag in Repo A **nicht**; Claims dazu über Primärbericht + offizielle Issues/Docs |
| Repo B kanonisch | `origin/main` zum Report-Stichtag | `4128efac044e1d310f351853634d20c1c77980fd` | `VERIFIED` als Git-Objekt; Working-Tree-HEAD war `2f80ce9c…` und wurde **nicht** als Wahrheit verwendet |
| Repo B `origin/main` jetzt | nach dem Report-SHA | `86e82e1788d6100b4e268da2c1a4ac348a331773` | nur Drift-Hinweis; keine stille Entwertung |

`REPORT_DATE_EVIDENCE` und `CURRENT_UPSTREAM_EVIDENCE` fallen für die geprüften Issues auf denselben Kalendertag (2026-08-21). Wo ein Issue nach Report-Erstellung einen Fix-PR hat, ist das als offener Stand plus laufender Fix gekennzeichnet, nicht als nachträgliche Widerlegung.

---

## 1. Red-Team-Urteil

`SPLIT_ARCHITECTURE` überlebt als **langfristige Autoritätsgrenze**, nicht als **jetzt zu bauende Plattform**.

Der Primärbericht liegt in der Kernrichtung richtig: PowerUnits-Policy darf nicht dauerhaft in Hermes-Core-Patches leben, und Customer-Sicherheit darf nicht an Desktop/Bot/Profiles hängen. Er überschätzt aber den heutigen Forkpreis, unterschätzt den bereits vorhandenen Repo-B-Gateway und zieht ein Customer-SaaS-Zielbild in eine interne Operator-Migration.

Die günstigere, gleich sichere 12-Monats-Entscheidung ist:

```text
thin lockdown patches
+ standalone PowerUnits plugin / generic bounded client
+ bestehende Repo-B-Routen als Capability Gateway
+ isolated upstream proof vor Plattformbau
```

nicht:

```text
OIDC + mTLS + Capability Tokens + Result-Firewall
+ Execution Plane + Customer Copilot als Phase 5
+ Fork-Retirement als Teil derselben Roadmap
```

```text
RED_TEAM_VERDICT = AFFIRM_SPLIT_BUT_SIMPLIFY
```

---

## 2. Stärkste Teile des Primärberichts

Diese Claims wurden angegriffen und **nicht** falsifiziert:

1. **Repo B ist die autoritative Domaingrenze.** 15 Router unter `/internal/hermes/bounded/v1/*`, Shared Bearer, `extra="forbid"`, serverseitige Länder-/Fenster-/Versionsprüfung. `LOCAL_REPO_B` `4128efac` `backend/main.py`, `backend/settings.py`.
2. **Customer-Hermes-UI fehlt, und Profiles/Toolsets sind keine Tenantgrenze.** Das ist architektonisch korrekt und bleibt bindend, sobald ein Customer-Agent überhaupt existiert.
3. **Der finale `first_safe_v1`-Cap in `model_tools.py` ist der lokale Schutz, den Upstream nicht ersetzt.** `LOCAL_REPO_A` `model_tools.py:448-457`. Ohne diesen Cap oder ein externes Äquivalent ist ein Upstream-Intake unsicher.
4. **In-Process-Plugin/MCP teilt Blast Radius.** Das widerlegt Thin Fork nicht für einen Trusted Operator, begrenzt ihn aber als Dauerzustand für Writes und untrusted Content.
5. **Zero-sunk-cost: den heutigen All-in-one-Fork würden wir nicht erneut bauen.** Die 1:1-HTTP-Wrapper und die mehrfach kopierte Policy sind echte Schuld. Der Fehler des Berichts liegt in der **Größe der Ersatzarchitektur**, nicht in der Diagnose.

---

## 3. Findings, die die Entscheidung ändern können

### Finding 1 — Fork-Schuld ist additiv, nicht invasiv

```text
FINDING = 229 von 275 seit Merge-Base geänderten Dateien sind Adds; der teure Kern sind ~31 nicht-testbezogene Shared Files
SEVERITY = HIGH
EVIDENCE = LOCAL_REPO_A VERIFIED
  git diff --name-status 3ef6bbd2...c6e43b51
  TOTAL=275 ADDED=229 MODIFIED=46 DELETED=0
  ADDED tools/powerunits*=69 docs=71 tests=55
  MODIFIED_CORE ohne tests: 31 Dateien
ORIGINAL_CLAIM = 255 PowerUnits-Dateien plus 117 Patches machen einen tiefen Fork untragbar; Split ist nötig
RED_TEAM_CHALLENGE = Additive Dateien mergen fast kostenlos. Official Plugin-API registriert Toolsets ohne toolsets.py.
IMPACT_IF_TRUE = Rebase/Thin-Fork ist für 12 Monate billiger als Capability-Plane-Bau
RECOMMENDED_CHANGE = Fork-Schuld auf die 21 Konflikt-/29 Shared-Files begrenzen; 255 nicht als Invasionsbeleg nutzen
```

`OFFICIAL_DOC` `website/docs/developer-guide/plugins/index.md` (lokal, Fork-Kopie der Upstream-Doktrin): `ctx.register_tool(name=..., toolset=...)` und ausdrückliche Policy, Produktintegrationen als **standalone Plugin-Repos** zu halten, nicht in den Core-Tree.

Die 11 lokalen Familien ohne Upstream-Äquivalent sind überwiegend **neue Dateien** (Domainadapter, Allowlists, Option-D, Tiers). Invasiv sind vor allem Familie 3 (Clamp), 5 (Registry-Fingerprint), 9 (Provider) und 10 (Docker/Railway). Das ist ein Thin-Fork-Profil, kein Deep-Fork-Zwang.

```text
FORK_DEBT_CLAIM = OVERSTATED
```

### Finding 2 — Die Capability Plane ersetzt einen bereits vorhandenen Gateway

```text
FINDING = Repo B ist heute schon das Capability Gateway; der Bericht entwirft eine zweite AuthZ-Plattform
SEVERITY = HIGH
EVIDENCE = LOCAL_REPO_B VERIFIED 4128efac
  backend/main.py include_router(internal_hermes_bounded_*)
  backend/settings.py POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET
  require_hermes_internal_execute_auth + secrets.compare_digest
  LOCAL_REPO_A tools/powerunits_*_tool.py: feste _PATH, kein URL-Parameter
ORIGINAL_CLAIM = Ein neues Manifest mit Rollen, Tokens, Firewall, OIDC/mTLS ist die Vereinfachung
RED_TEAM_CHALLENGE = Für einen Trusted Operator braucht die erste Read-Migration keine neue Plane
IMPACT_IF_TRUE = Implementierungskosten fallen von XL auf S–M; Split bleibt Richtung, nicht Bauprogramm
RECOMMENDED_CHANGE = Bestehende Bounded-API härten und Wrapper kollabieren, statt Parallelplattform
```

```text
CAPABILITY_PLANE = RIGHT_DIRECTION_OVERBUILT_INITIAL_SLICE
```

### Finding 3 — Customer Copilot in dieser Migration verzerrt das Urteil

```text
FINDING = Phase 5 und Variante G ziehen ein when-ready Produkt in eine interne Runtime-Migration
SEVERITY = HIGH
EVIDENCE = LOCAL_REPO_B VERIFIED 4128efac
  docs/architecture/saas_ai_evolution_backlog_v1.md Status = Backlog / when-ready
  Theme 5: Internal today → product read API → SaaS copilot when multi-tenant ships
  Auth/Billing/Multi-Tenant = separate product decisions / target_architecture non-goals
  LOCAL_REPO_A docs/powerunits_platform_evolution_backlog_v1.md
    Theme 5: Do not widen Telegram to customer-facing copilot
ORIGINAL_CLAIM = G = D+E ist klar besser (8,1) als D (7,6) oder C (6,5)
RED_TEAM_CHALLENGE = Es gibt keine Customer-UI, kein Tenantmodell, keinen Product-Auftrag in dieser Migration
IMPACT_IF_TRUE = G verliert den Vorsprung; D oder vereinfachtes D ist das echte Ziel
RECOMMENDED_CHANGE = Customer Copilot als zukünftige Grenze dokumentieren, nicht als Phase 5
```

```text
CUSTOMER_COPILOT_IN_CURRENT_MIGRATION = DOCUMENT_AS_FUTURE_BOUNDARY
```

### Finding 4 — Ungewichtetes Scoring macht Split unvermeidlich

Die Lücke 4,8 → 8,1 entsteht fast vollständig aus fünf Annahmen, nicht aus gemessener Runtime-Sicherheit. Details in §13.

### Finding 5 — Proof-before-Platform fehlt, obwohl der Bericht selbst Unsicherheit zugibt

Phase 1 verlangt bereits intern signiertes OCI, SBOM, Notices, keine Lazy Installs. Phase 2 verlangt mTLS/OIDC, Operation IDs, Rate Limits, Audit — **bevor** bewiesen ist, dass modernes Hermes den konkreten Operator-Workflow trägt.

Der Bericht selbst: keine Live-Railway-Egress-Prüfung, kein vollständiger Equivalence-Beweis, Desktop-E2E upstream deaktiviert, 15 Policytests in der lokalen Venv übersprungen.

```text
FINDING = Die Roadmap committet Plattformkosten vor einem Entscheidungstor
SEVERITY = HIGH
EVIDENCE = REPORT §11, §13; LOCAL_REPO_A keine v0.20.5-Objekte im Fork
ORIGINAL_CLAIM = Intake → Capability Gateway → Desktop/Bot → Writes → Customer → Forkabbau
RED_TEAM_CHALLENGE = Isolierter Proof + 3–5 Read-Ops + Shadow-Compare senkt Risiko und kann Split/Thin-Fork noch kippen
IMPACT_IF_TRUE = Ein großer Teil von Phase 1–2 ist optional oder später
RECOMMENDED_CHANGE = Decision Gate nach Shadow-Compare; erst dann Gateway-Härtung
```

---

## 4. Security-Regressionen / Angriffsketten

Der Bericht warnt korrekt, dass Upstream den `first_safe`-Cap nicht ersetzt. Die gefährlichere Lücke ist: **mehrere zitierte Upstream-Schwächen treffen den geplanten Zielpfad, teilweise schon die heutige first_safe-Fläche.**

### Finding 6 — `session_search` ist first_safe und upstream ungescopt

```text
FINDING = first_safe erlaubt session_search; Upstream #87779 beschreibt Cross-Chat/Cross-Profile-Leak
SEVERITY = HIGH
LIKELIHOOD = MEDIUM  (hoch, sobald Profiles/Desktop wie empfohlen genutzt werden; niedrig bei einem Telegram-Chat)
EVIDENCE =
  LOCAL_REPO_A powerunits_telegram_overlays.py TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1 enthält "session_search"
  UPSTREAM_ISSUE https://github.com/NousResearch/hermes-agent/issues/87779  OPEN, P2, needs-repro
  PR #87847 referenziert, nicht als gemergt in v0.20.5 belegt
ORIGINAL_CLAIM = Profiles sind hoch-wertig; first_safe bleibt die lokale Grenze
RED_TEAM_CHALLENGE = first_safe schließt diesen Leak nicht. Profiles vergrößern ihn.
IMPACT_IF_TRUE = Desktop/Profile-Pilot ohne session_search-Disable oder Fix ist ein Policy-Bypass
RECOMMENDED_CHANGE = session_search im internen Pilot disable oder Ownership-Fix vor Profile-Konsolidierung
```

Plausible Kette, nur Quellinspektion, keine Ausnutzung:

```text
untrusted web/research content
→ prompt injection
→ session_search(profile=… | session_id=…)
→ fremde Transcripts / Memory
→ Präzisierung weiterer bounded execute/read Calls
```

`ACCESS_MATRIX.md` behauptet „General web … **Not** in first_safe“. Der Code erlaubt `web` und `search` in `TELEGRAM_BASE_TOOLSETS_FIRST_SAFE_V1`. Der Primärbericht folgt dem Code; die Matrix ist driftend. `PARTIAL` als Produktionsbeleg, weil Env-`check_fn` die effektive Toolzahl weiter senkt.

### Finding 7 — Write-Tools ohne Per-Call-Approval sind schon da

```text
FINDING = first_safe-BASE enthält mehrere execute_*-Toolsets; HTTP-Execute hat kein deterministisches Human-Gate
SEVERITY = HIGH
LIKELIHOOD = MEDIUM  wenn die zugehörigen *_EXECUTE_ENABLED Gates live sind; sonst LOW
EVIDENCE =
  LOCAL_REPO_A powerunits_telegram_overlays.py: option_d_execute, market_*_execute, entsoe_*_execute, era5_*_execute, outage_repair_execute
  LOCAL_REPO_A tools/powerunits_option_d_execute_tool.py: ein POST, kein Approval-Token
  REPORT §5: „PU-Execute … nicht durch deterministische Human-Confirmation pro Call geschützt“
  docker/apply_powerunits_runtime_policy.py setzt approvals.mode=manual, cron_mode=deny — gilt nicht für diese HTTP-Wrapper
ORIGINAL_CLAIM = Stage 1 ist Trusted Analyst / read-first; Writes kommen erst in Phase 4
RED_TEAM_CHALLENGE = Die Write-Fläche ist katalogisch schon Stage 1, nur env-gated
IMPACT_IF_TRUE = Capability-Plane-Approvals lösen ein heutiges Problem; sie sind aber zuerst ein Repo-B-/Gate-Fix, kein Hermes-Rewrite
RECOMMENDED_CHANGE = Execute-Gates als Write-Principal behandeln; Approval in Repo B oder Featureflag, nicht in einer neuen Plane
```

Kette:

```text
untrusted content (web | energy_web_research | docs)
→ prompt injection
→ execute_powerunits_*  (wenn Gate+Bearer gesetzt)
→ Shared Bearer
→ Repo-B Job / bounded write
```

Das ist **keine** Migrationserfindung. Eine Upstream-Migration ohne Cap macht sie schlimmer (Terminal/File/Browser). Eine Migration mit Desktop/Browser/MCP bei offenem Execute-Gate ebenfalls.

### Weitere Regressionskandidaten

| Kontrolle | Verlust ohne lokalen Patch | SEVERITY | LIKELIHOOD | Muss außerhalb Hermes |
|---|---|---|---|---|
| Finaler Tool-Cap | Upstream Toolsets/API können Fläche öffnen; #91415 ignoriert `disabled_toolsets` auf multiplex `api_server` | HIGH | HIGH ohne Clamp; LOW mit Clamp + ohne Multiplex | Ja: Acceptance-Test + Clamp oder externes Policy-Compile |
| Feste Repo-B-Routen | MCP/HTTP-Plugin mit URL-Parameter | HIGH | MEDIUM falls MCP als „Gateway“ naiv genutzt | Ja: Route nur serverseitig |
| Kein freies SQL | Terminal/Plugin mit `DATABASE_URL_TIMESCALE` im Prozess | HIGH | MEDIUM sobald Terminal/Desktop frei | Ja: kein DB-Credential im Agentprozess |
| Repo/Pfad-Allowlist | generische Git/File-Tools | HIGH | MEDIUM | Ja: Capability-API |
| Plattform-Lockdown | Discord/API/Desktop-Ingress | MEDIUM | HIGH bei Desktop-Pilot | Ja: Deployment-Ingress |
| Env-Gates | Availability-Cache kann stale bleiben (Bericht, BZN) | MEDIUM | MEDIUM | Ja: Fingerprint oder Prozess-Recycle |
| Manual Approval | Computer Use / `--yolo` / Windows-Hardline #87419, #87724 | HIGH | LOW im Telegram-first_safe; HIGH bei Computer Use | Ja: Write-Approval in Repo B |
| Secret-Isolation | Shared Bearer + Timescale-URL im Prozess; #91308 Auxiliary-Key an fremden Host | HIGH | MEDIUM | Ja: Host-Bindung, keine PU-Secrets in Subprocess-Env |
| Profile-Grenzen | Workspace liest `os.getenv("HERMES_HOME")` nicht `get_hermes_home()` | MEDIUM | HIGH sobald Profiles live | Ja: Workspace-Root an Profil binden |
| Plugin/MCP/Skills | `ctx.dispatch_tool("terminal")` umgeht Model-Cap | HIGH | LOW heute; MEDIUM mit freien Plugins | Ja: signed allowlist, kein dispatch auf verbotene Tools |
| Netzwerk | Base-URL ohne Host-Allowlist | MEDIUM | LOW (Operator-Config, nicht Modell) | Ja: Allowlist an Deployment |

#91415 ist `OPEN` am Stichtag, PR #91422 existiert. Für **Telegram-only + Clamp** ist es wenig relevant. Es blockiert nur dann Policyvertrauen, wenn der Pilot multiplex API-Server nutzt. Der Bericht empfiehlt selbst getrennte Instanzen — dann ist #91415 kein Desktop-Killer.

**Was außerhalb Hermes erzwungen werden muss** (Attack 5, überlebt):

- Operation, Effektklasse, Länder/Fenster, Host+Route
- Credentials (kein langlebiger Bearer im Modellkontext; mindestens kein Timescale-DSN im Agent)
- Write-Approval und Idempotenz
- Ergebnisminimierung (heute schon teilweise in Repo B)
- Egress für Browser/MCP, falls jemals exponiert

Hermes **darf** Parameter vorschlagen. Repo B **muss** sie verwerfen können. Das ist heute schon so. Eine neue Token-Maschine ändert das nicht.

---

## 5. Overengineering

Kontrollen, die der Bericht als Zielbild setzt, obwohl Threat Model B **ein interner Operator** ist:

### Heute nötig (Trusted Operator, read-first)

- Fail-closed Featuregates
- Feste Routen + `extra="forbid"`
- Serverseitige Domainvalidierung
- Finaler Callable Cap
- Telegram-/privater Ingress
- Kein freies SQL / freier Repo-Pfad
- Host-Allowlist auf `POWERUNITS_INTERNAL_EXECUTE_BASE_URL`
- Golden Negativtests
- `approvals.mode=manual` für echte Hermes-Side-Effects; Execute-Gates als Writes behandeln

### Später (Customer Copilot / Multi-Tenant)

- OIDC/mTLS/Workload Identity
- kurzlebige Capability Tokens
- Rollen/Scopes als Produkt-AuthZ
- Result-Firewall als eigenes System
- dedizierter Audit-Store
- ephemere Execution Plane
- Egress-Firewall für Browser/Computer Use
- signierte Skills/Plugins als Supply-Chain-Produkt
- Customer Session/Memory Governance

```text
MINIMUM_VIABLE_CAPABILITY_GATEWAY
  1. Bestehende Repo-B POST /internal/hermes/bounded/v1/<operation>
  2. Ein generischer Hermes-Client: operation_id + JSON, kein URL-Feld
  3. Shared Bearer + Env-Gate (Ist-Zustand)
  4. Host-Allowlist auf Base-URL
  5. 3–5 read-only Operationen: coverage-snapshot, data-health/summary, docs/repo-b-read, bzn-prices
  6. Shadow-Compare Alt-Wrapper vs. Client
  7. Kein OIDC, kein mTLS, kein Token-Broker, keine Result-Firewall-Appliance
```

Der Bericht fragt richtig „würden wir 49 Toolsets neu bauen?“ und antwortet mit einer Enterprise-AuthZ-Fläche. Die sparsame Antwort ist: **ein Client, 31 vorhandene Routen, 49 Dateien löschen.**

---

## 6. Underengineering / verpasste Upside

```text
FINDING = first_safe ist inkonsistent konservativ: breite HTTP-Write-Kataloge, enge UX-Primitives
SEVERITY = MEDIUM
EVIDENCE = LOCAL_REPO_A overlays vs ACCESS_MATRIX vs 4 lokale skills/productivity/powerunits-*
ORIGINAL_CLAIM = Desktop/Bot/Skills/Delegation erst nach Capability Plane und Execution Plane
RED_TEAM_CHALLENGE = Read-only Desktop auf bestehendem Bounded-API + Clamp ist kleiner als die Plane
IMPACT_IF_TRUE = 12-Monats-Wert von Upstream ist ohne Plattformbau hebbar
RECOMMENDED_CHANGE = Read-only Desktop/Telegram auf v0.20.5 mit Clamp und ohne MCP/Browser als Proof erlauben
```

Weitere verpasste Vereinfachungen:

- Upstream-Plugin statt `toolsets.py`-Patch für alle `powerunits_*`-Einträge.
- Standard-Toolsets `memory` / `todo` existieren schon; lokale Skill-Runbooks existieren schon.
- Ein separates Gateway ist für read-only Coverage/Docs **unnötig**.
- Interne Bots dürfen mehr sehen als ein Customer-Agent, solange Writes env-closed bleiben.
- `first_safe` als unveränderliches Dogma nach einem erfolgreichen Proof konserviert Wrapper-Schuld.

Attack 6 ändert das Langfristurteil nicht: Hermes soll Policy nicht besitzen. Es ändert die **Reihenfolge**.

---

## 7. Fork-Debt-Challenge

| Frage | Antwort | Evidenz |
|---|---|---|
| Ist Rebase/Thin Fork billiger als Extraktion? | **Ja für 12 Monate**, wenn Tools ins Plugin wandern und nur Clamp/Provider/Docker bleiben | 21 Konfliktdateien vs. neue Plane; Plugin-API `VERIFIED` |
| Wie schädlich sind die 255 PU-Dateien? | Überwiegend **nicht** | 229 Adds |
| Sind viele additiv statt invasiv? | **Ja** | `tools/`, `docs/`, `tests/`, `config/`, `skills/` |
| Reicht Upstream + kleines Plugin? | **Für Read-only Internal: ja, mit Clamp-Patch** | Official plugin guide; In-Process-Limit bleibt |
| Verwechselt der Bericht Upstream-Tempo mit lokalem Unterhalt? | **Teilweise** | 7.852 Commits sind kein lokaler Aufwand, solange Shared Files klein bleiben |

Die 29 Shared Files und 21 Konflikte sind real. Sie sitzen auf `model_tools.py`, `gateway/run.py`, `toolsets.py`, Providern. Das ist der **einzige** belastbare Forkpreis. Ihn mit 255 Dateien und 7.382 Upstream-Pfaden zu multiplizieren ist rhetorisch, nicht ökonomisch.

Drei der 11 Familien sind laut Bericht bereits upstream überholt. Die restlichen Domainfamilien gehören nicht in Hermes-Core — das rechtfertigt Plugin-Extraktion, nicht sofort OIDC.

```text
FORK_DEBT_CLAIM = OVERSTATED
```

Ein dauerhafter Deep Fork bleibt trotzdem unklug. `FORK_NECESSITY = PARTLY` überlebt. Die Folgerung „also Split-Plattform jetzt“ nicht.

---

## 8. Capability-Upside-Challenge

Wert für die **wahrscheinlichen ersten 12 Monate**: ein interner Telegram-Operator, Stage-1-Gates, Repo-B-Jobs. Nicht ein neues Agent-Produkt.

| Capability | 12-Monats-Wert | Begründung |
|---|---|---|
| Desktop | NICE_TO_HAVE | Telegram-Pfad existiert; kein offizieller Installer; E2E deaktiviert. Entwickler-UX ja, Operator-Muss nein |
| Bot Mode UI | NICE_TO_HAVE | Ein Bot trägt den heutigen Workflow |
| Profile-Primitive | HIGH_VALUE | Sinnvoll für Analyst/Research — aber erst nach session_search/workspace-Fix |
| Session-Primitive | HIGH_VALUE | Schon in Nutzung; Upgrade nicht transformativ |
| Skills | NICE_TO_HAVE | 4 lokale PowerUnits-Skills existieren bereits |
| Memory | NICE_TO_HAVE | Bereits in first_safe; Review/TTL nützlich, nicht migrationswürdig |
| Routines | HIGH_VALUE | Tägliche Coverage-Briefs; Writes bleiben Repo-B-Scheduler |
| Delegation | LOW_VALUE | Ein Operator, Kostenrisiko, keine Writes |
| Browser | DISTRACTION | Injection-Oberfläche; Execution Plane wäre die teure Voraussetzung |
| Observability | HIGH_VALUE | Kosten/Tool-Entscheidungen; geht ohne Split via Hooks/Logs |
| moderne Provider | NICE_TO_HAVE | Lokale Providerpatches existieren; Familie 9 ist ein kleiner Patch |
| zukünftige Upstream-Verbesserungen | MODERATE als Optionswert | Nur wertvoll, wenn Shared Diff klein bleibt |

Dieselben Kernworkflows (Coverage, BZN-Read, Docs, bounded execute) laufen **heute** im Fork. Upstream kauft UX und Tempo, nicht die PowerUnits-Differenzierung.

```text
UPSTREAM_CAPABILITY_UPSIDE = MODERATE
```

Der Bericht bewertet mehrere Zeilen mit „hoch“ / „sehr hoch“, weil das Feature existiert. Das ist Feature-Existenz, nicht PowerUnits-Nutzen.

---

## 9. Desktop / Bot Mode Challenge

Versuch, `FIT_WITH_CONTROLS` und `HIGH` zu kippen:

- Desktop als Customer-Client: bereits verworfen, bleibt verworfen.
- #91415, #91654, #90415, #90699 betreffen **Multiplex/API/TUI-Profile-Escape**. Relevant nur, wenn der Pilot genau das einschaltet. Der Bericht empfiehlt getrennte Instanzen — dann sind das keine Desktop-Falsifikationen.
- Fehlende offizielle Installer und deaktiviertes Desktop-E2E senken **Lieferreife**, nicht die interne Tauglichkeit.
- Bot Mode ist Profile+UI, kein Security Principal. Das widerlegt nicht den Kompositionswert.

Nicht falsifiziert:

```text
DESKTOP_INTERNAL_VERDICT = FIT_WITH_CONTROLS
BOT_MODE_INTERNAL_VERDICT = PRIMITIVES_HIGH_UI_NICE_TO_HAVE
```

Korrektur: `BOT_MODE_ARCHITECTURAL_VALUE = HIGH` darf nicht als „Bot Mode jetzt bauen“ gelesen werden. Die Primitives (Profile, Session, Skill, Routine) sind hoch; die UI ist für 12 Monate optional. Desktop ist fit, aber **kein migrationsleitender Nutzen**.

---

## 10. Customer-Copilot-Scope

Produktbelege am SHA `4128efac`:

- Kein Hermes-/Chat-Pfad in `app/` / `frontend/` laut Primärbericht; Red Team hat das nicht vollständig neu gescannt (`PARTIAL`, akzeptiert).
- Backlog Theme 5 ist **when-ready**, Stage 3 an Multi-Tenant gebunden, Auth ist Non-Goal.
- Repo-A-Backlog: Customer Copilot explizit **nicht** auf Telegram erweitern.

Die Richtung „Customer = Repo-B-BFF, nicht Hermes-UI“ ist richtig und soll bleiben. Sie gehört **nicht** in dieselbe Roadmap wie v0.20.5-Intake.

Phase 5 verzerrt Security-Pflichtkatalog, Scoring und Teamfokus. Ein interner Agent braucht keine Tenant-Memory-Governance, um Coverage-Reads zu migrieren.

```text
CUSTOMER_COPILOT_IN_CURRENT_MIGRATION = DOCUMENT_AS_FUTURE_BOUNDARY
```

---

## 11. Kosten- / Komplexitätsmatrix

| Komponente | IMPLEMENTATION_COST | ONGOING_COST | SECURITY_VALUE | PRODUCT_VALUE | NEEDED_NOW |
|---|---|---|---|---|---|
| Immutable upstream intake (digest pin) | S | LOW | HIGH | LOW | YES |
| Internal artifact mirroring | M | MEDIUM | MEDIUM | LOW | NO (nach erfolgreichem Proof) |
| Internal release signing | M | MEDIUM | MEDIUM | LOW | NO |
| SBOM | S | LOW | LOW | LOW | NO |
| OIDC | L | MEDIUM | LOW intern / HIGH customer | LOW | NO |
| mTLS | L | MEDIUM | LOW intern hinter privatem Netz | LOW | NO |
| Short-lived capability tokens | L | HIGH | MEDIUM | LOW | NO |
| Capability Manifest (voll) | L | HIGH | MEDIUM | MEDIUM | NO |
| Result-Firewall als System | L | HIGH | MEDIUM | LOW | NO (Repo-B Response-Minimize reicht) |
| Dedizierter Audit-Store | M | MEDIUM | MEDIUM | LOW | NO (Logs + pipeline_run_id zuerst) |
| Ephemere Execution | XL | HIGH | HIGH nur mit Browser/Terminal | LOW | NO |
| Egress-Firewall | L | HIGH | HIGH nur mit Browser/MCP | LOW | NO |
| Signierte Skills/Plugins | M | MEDIUM | MEDIUM | LOW | NO (pin + review reicht) |
| Customer Session/Memory Governance | XL | HIGH | HIGH | HIGH wenn Produkt existiert | NO |
| Thin first_safe Clamp + Policytests | S | LOW | HIGH | HIGH | YES |
| Generic bounded client / Plugin | M | LOW | HIGH | HIGH | YES |
| Host-Allowlist Base-URL | S | LOW | MEDIUM | LOW | YES |
| Isolated v0.20.5 proof | M | LOW | HIGH | HIGH | YES |

Rücksichtslos zu streichen oder zu verschieben: OIDC, mTLS, Token-Broker, SBOM-als-Gate, Signing-als-Gate, Execution Plane, Customer-Governance, volle Manifest-OS.

Behalten: Digest-Pin, Clamp, feste Routen, Shadow-Tests, privater Ingress.

---

## 12. Migrationsreihenfolge

Vorgeschlagen im Bericht:

```text
0 Golden → 1 Intake+Signing+SBOM → 2 Gateway+OIDC → 3 Desktop/Bot → 4 Writes → 5 Customer → 6 Fork-Ende
```

Billiger und sicherer:

```text
0 Golden baseline der echten first_safe-Tools
→ 1 isolierter v0.20.5-Proof ohne PU-Secrets
     Telegram oder ein Desktop-Fenster, Clamp-Port, keine MCP/Browser/Computer Use
→ 2 drei bis fünf read-only Repo-B-Operationen über generischen Client
→ 3 old-vs-new Shadow-Compare
→ 4 DECISION GATE
     A: Thin Fork + Plugin reicht
     B: Wrapper-Kollaps auf bestehendem Repo-B-Gateway
     C: erst jetzt schmales Gateway-Härtung (Rate limit / Audit / write principal)
→ 5 optional read-only Desktop/Bot
→ 6 bounded writes einzeln
→ ∞ Customer Copilot als eigenes Produktprogramm
```

Proof-before-Platform senkt das Risiko materiell: Desktop-E2E ist upstream unsicher, Policytests waren lokal übersprungen, Equivalence ist `PARTIAL`, Railway-Egress ist `NOT_VERIFIED`. Ein gescheiterter Proof kostet Wochen. Eine gebaute Plane kostet Quartale.

---

## 13. Scoring-Sensitivität

### Annahmen, die 4,8 vs 8,1 tragen

1. **Customer SaaS ist Teil dieser Entscheidung** — Dimension „SaaS production fit“ 3 vs 9.
2. **Ungewichtetes Mittel** — Migration ease 10 vs 3 und risk 7 vs 4 werden von acht „Zukunfts“-Dimensionen ertränkt.
3. **In-Process-Isolation ist erstordig** für einen Trusted Operator — isolation 5 vs 9.
4. **Upstream-Velocity muss jetzt fließen** — velocity 3 vs 9, obwohl 12-Monats-Nutzen `MODERATE` ist.
5. **255 PU-Dateien = schlechte Maintainability** — maint 3 vs 8; 229 davon sind Adds.

### Wenn diese Annahmen falsch sind

Ohne SaaS / Scalability / Low-lock-in, 10 Dimensionen:

| Variante | Mittel |
|---|---|
| A Current Fork | 5,0 |
| C Thin Fork | 6,6 |
| D External Gateway | 7,7 |
| G Split | 7,6 |

Mit doppeltem Gewicht auf Migration ease + risk:

| Variante | Mittel |
|---|---|
| A | ~5,6 |
| C | ~6,3 |
| D | ~7,2 |
| G | ~6,9 |

**Split (G) gewinnt dann nicht mehr gegen D.** C wird für 12 Monate konkurrenzfähig. A bleibt strategisch schwach, aber nicht 4,8-katastrophal.

Wenn Annahme 5 korrigiert wird (Maint A = 5): A steigt nur leicht. Der Fork verliert weiter auf Kompatibilität, nicht auf Dateizählung.

**Gewinnt Split trotzdem?**  
Als **Autoritätsschnitt** (Hermes ≠ Policy, Customer ≠ Hermes): ja.  
Als **Variante G inkl. Customer-Phase**: nein.  
Als **sofortiges Bauprogramm**: nein.

---

## 14. Korrigierte Architekturempfehlung

```text
LANGFRIST = D intern  (Hermes client, Repo B authority)
           + E nur wenn ein Customer-Produkt existiert
SOFORT    = C-lite / D-lite
            thin first_safe patches
            + standalone plugin oder generic bounded client
            + bestehende 31 Routen
NICHT JETZT = neue Capability-OS, Execution Plane, Customer Copilot, Fork-Retirement
```

Varianten neu gelesen:

- **A** behalten: nur als Produktionsstand bis zum Proof, nicht als Ziel.
- **B** Deep Rebase aller 49 Wrapper: vermeidbare Steuer.
- **C** Thin Fork: **empfohlener Übergang**, offiziell upstream-konform.
- **D** External Gateway: **Ziel**, aber initial = gehärtetes Repo B, nicht neues Produkt.
- **E/G**: Dokumentationsgrenze, kein Phase-5-Commit.

`MIGRATION_MAGNITUDE` für den korrigierten Pfad: **MODERATE**, nicht `SUBSTANTIAL`.  
`SUBSTANTIAL` gilt nur, wenn man G wörtlich baut.

---

## 15. Minimaler nächster Schritt

Nicht Phase-1-Signing, nicht Gateway-Gerüst.

1. Golden Liste der **effektiv sichtbaren** Tools (nicht der 55 Katalognamen) inkl. Env-Gates.
2. Isolierten v0.20.5-Prozess ohne `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` und ohne `DATABASE_URL_TIMESCALE` starten.
3. Clamp-Port als ≤20-Zeilen-Patch oder äquivalentes `enabled_toolsets`-Acceptance-Test beweisen.
4. Drei read-only Calls gegen bestehende Repo-B-Routen: Coverage-Snapshot, eine Summary, eine Docs/Allowlist-Read.
5. Shadow-Diff und dann erst entscheiden: Plugin-Thin-Fork oder Client-Kollaps.

```text
CHEAPEST_SAFE_NEXT_STEP =
  isolated v0.20.5 proof + 3 read-only bounded ops + shadow compare + decision gate
```

---

## 16. Evidence Appendix

### Lokal Repo A `c6e43b51`

- `model_tools.py:448-457` — `first_safe_v1` Intersection-Cap
- `powerunits_telegram_overlays.py:54-112` — BASE enthält `web`, `search`, `session_search` und alle execute-Familien
- `gateway/run.py:1643-1671` — Plattform-Lockdown / Telegram-only Enforce
- `docker/apply_powerunits_runtime_policy.py:231-237` — `approvals.mode=manual`, `cron_mode=deny`
- `tools/powerunits_workspace_tool.py:55-57` — `os.getenv("HERMES_HOME")`, nicht `get_hermes_home()`
- `tools/powerunits_option_d_execute_tool.py` und Geschwister — feste `_PATH`, Shared Bearer, kein Approval
- `tools/registry.py:666-682` — `requires_env_binding_fingerprint`
- `website/docs/developer-guide/plugins/index.md:41-43, 262-275` — standalone plugins, `ctx.register_tool`
- `ACCESS_MATRIX.md:30` — drift gegen Code (`web` verboten behauptet)
- `docs/powerunits_platform_evolution_backlog_v1.md:19, 64` — Customer Copilot deferred
- `docs/powerunits_hermes_integration_pattern_v1.md` — additives Wrapper-Muster, nicht Core-Rewrite
- Merge-Base-Diff: 275 Pfade, 229 Adds, 46 Modifies, 0 Deletes

### Lokal Repo B `4128efac`

- `backend/main.py` — 15 `internal_hermes_bounded_*` Router
- `backend/settings.py` — `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET`
- `backend/routers/internal_hermes_bounded_*.py` — `require_hermes_internal_execute_auth`, `compare_digest`
- `docs/architecture/saas_ai_evolution_backlog_v1.md` — Theme 5 when-ready; Auth Non-Goal

Nicht als Report-Evidenz verwendet: Working-Tree `2f80ce9c`, `origin/main` `86e82e17`.

### Upstream / offiziell

- Plugin-Doktrin: Produktintegrationen außerhalb des Core-Trees
- [Issue #87779](https://github.com/NousResearch/hermes-agent/issues/87779) OPEN — `session_search` Ownership
- [Issue #91415](https://github.com/NousResearch/hermes-agent/issues/91415) OPEN — multiplex `api_server` ignoriert `disabled_toolsets`; PR #91422
- Issues #91308, #87724, #91654, #90699, #87419, #84248, #90415: im Primärbericht zitiert; hier nur verwendet, wo der PowerUnits-Pfad sie wirklich trifft
- Upstream-SHA `fcbd1076` war in Repo A nicht vorhanden; kein stiller Re-Audit des Release-Trees

### Bewusst nicht getan

- kein destruktiver Merge/Rebase
- keine breiten Test-Suiten
- keine Live-Railway- oder Secret-Inspektion
- keine vollständige Dateiinventur über den Add/Modify-Count hinaus
- kein Customer-Frontend-Rescan

---

## Abschlussblock

```text
RED_TEAM_VERDICT =
  AFFIRM_SPLIT_BUT_SIMPLIFY

PRIMARY_REPORT_CONFIDENCE = 6.5/10
FORK_DEBT_CLAIM = OVERSTATED
CAPABILITY_PLANE = RIGHT_DIRECTION_OVERBUILT_INITIAL_SLICE
UPSTREAM_CAPABILITY_UPSIDE = MODERATE
DESKTOP_INTERNAL_VERDICT = FIT_WITH_CONTROLS
BOT_MODE_INTERNAL_VERDICT = PRIMITIVES_HIGH_UI_NICE_TO_HAVE
CUSTOMER_COPILOT_IN_CURRENT_MIGRATION = DOCUMENT_AS_FUTURE_BOUNDARY

CRITICAL_FINDINGS = 0
HIGH_FINDINGS = 6
MEDIUM_FINDINGS = 3

TOP_3_REPORT_STRENGTHS =
1. Repo B bleibt autoritative Domaingrenze; Hermes darf sie nicht ersetzen.
2. first_safe-Cap und Plattform-Lockdown sind echte lokale Schutzgüter ohne Upstream-Äquivalent.
3. Customer-Sicherheit an Desktop/Bot/Profiles zu hängen wäre ein Architekturfehler.

TOP_3_RED_TEAM_CHALLENGES =
1. 229 Adds sind kein Deep-Fork-Zwang; Thin Fork + Plugin ist der offizielle, billigere Pfad.
2. Die Capability Plane und Phase 5 Customer Copilot sind für den heutigen Trusted Operator übergebaut und verzerren das Scoring.
3. Proof-before-Platform muss vor OIDC/mTLS/Tokens/Execution Plane stehen; sonst ist Split ein Quartalsprogramm ohne Nutzenbeweis.

CONTROLS_TO_KEEP_NOW =
1. Finaler callable Cap / Telegram-Lockdown plus Golden Negativtests
2. Feste Repo-B-Routen, extra=forbid, kein freies SQL, Allowlist-Reads
3. Host-Allowlist auf die Execute-Base-URL; Execute-Gates als Writes behandeln

CONTROLS_TO_DEFER =
1. OIDC, mTLS, short-lived capability tokens
2. Result-Firewall, dedizierter Audit-Store, ephemere Execution, Egress-Firewall
3. Signierte Supply-Chain-OS und Customer Session/Memory Governance

CHEAPEST_SAFE_NEXT_STEP =
  isolated v0.20.5 proof + 3 read-only bounded ops + shadow compare + decision gate
```
