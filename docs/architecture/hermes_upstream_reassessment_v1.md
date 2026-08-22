# PowerUnits × Hermes: Upstream Reassessment v1

**Stichtag:** 2026-08-21  
**Status:** kanonische Architekturentscheidung  
**Scope:** Repo A (`hermes-agent`), Repo B (`EU-PP-Database`) und offizieller Upstream `NousResearch/hermes-agent`  
**Nicht im Scope:** Runtime-/Produktänderungen, Railway-/DNS-/Secret-Mutationen, Customer-Feature-Implementierung

## 0. Executive Summary

### Urteil

**Primärurteil: `SPLIT_ARCHITECTURE`.**

Der heutige Fork war als schnell abgesicherter interner Operator-Pfad nachvollziehbar. Als langfristige Plattform ist er nicht mehr die beste Architektur:

- Seine wertvollsten Eigenschaften sind **PowerUnits-eigene Capability-Grenzen**, nicht Änderungen am Hermes-Agent-Core.
- Von 220 lokal-only Commits bleiben nach 74 Merges und weiterem Rauschen 117 sinntragende commitbasierte Patchkandidaten. Diese sind nicht nur kosmetische Fork-Metadaten.
- 255 der 275 seit dem gemeinsamen v0.19.0-Stand veränderten Dateien sind nach reproduzierbarer Pfad-/Diff-Semantik PowerUnits-spezifisch.
- Ein nichtdestruktiver `git merge-tree` gegen Hermes v0.20.5 erzeugt 21 reale Konfliktdateien, darunter `gateway/run.py`, `model_tools.py`, `toolsets.py`, Provider-/Transportcode und Lockfiles.
- Gleichzeitig hat Upstream in einem Monat 7.852 Commits und 7.382 geänderte Pfade gegenüber dem gemeinsamen Release-Commit aufgenommen. Das macht einen tiefen Core-Fork zu einer dauerhaften Innovationssteuer.

Das Zielbild ist daher:

1. **Upstream-nahes Hermes für interne Operatoren und Entwickler**  
   Agent Loop, Profile, Sessions, Desktop, Bot Mode, Skills, Memory, read-only Delegation und Provideradapter werden von einem gepinnten und intern freigegebenen Upstream-Release konsumiert.

2. **PowerUnits-eigene Capability Plane**  
   Ein schmaler Policy-/Tool-Gateway besitzt Operationen, Rollen, Scopes, Länder-/Fenstergrenzen, Effekte, Approvals, Idempotenz, Rate Limits, Egressregeln, Result-Firewall und Audit. Hermes ist ein Client, nicht die Policy-Autorität.

3. **Repo-B-nativer Customer Copilot**  
   Customer Auth, Tenant-/Entitlement-Prüfung, Customer Sessions/Memory, durable Workflows und Fact Packs bleiben im Produkt. Hermes Desktop oder Bot Mode werden nicht zur Customer-Sicherheitsgrenze umgedeutet.

4. **Ephemere Execution Plane**  
   Browser, Terminal und Computer Use laufen nur in isolierten Jobs ohne Produktionssecrets, mit restriktiven Mounts, Ressourcenlimits und Egress-Allowlist.

### Direkte Antworten auf die Leitfragen

**Würden wir bei null versunkenen Kosten den heutigen Fork erneut bauen?**  
**Nein.** Wir würden die bounded Repo-B-Verträge, Fail-closed-Gates, Negativtests, Runbooks und progressive Capability-Ladder wieder bauen. Wir würden nicht erneut 49+ PowerUnits-Toolsets, dieselbe Policy in Entrypoint/Gateway/Env/Toolchecks und Produktwissen im Hermes-Core verteilen.

**Welche lokale Hermes-Codeklasse würden wir freiwillig neu schreiben?**  
**Die PowerUnits Capability-/Bounded-Client-Schicht**: `first_safe_v1`, `powerunits_*`-Toolwrapper, Env-Gating und Gateway-Cap. Sie sollte als deklaratives Capability-Manifest plus PowerUnits-owned Gateway neu entstehen. Agent Loop, Desktop, Profile, Sessions, Memory, Cron, Delegation und Browser würden wir nicht neu schreiben.

### Statuswerte

- `FORK_NECESSITY = PARTLY`
- `GUARDRAIL_ASSESSMENT = MIXED`
- `UPSTREAM_PRODUCTION_FIT = PARTIAL`
- `DESKTOP_INTERNAL_FIT = FIT_WITH_CONTROLS`
- `BOT_MODE_ARCHITECTURAL_VALUE = HIGH`
- `BOT_MODE_CUSTOMER_FIT = NOT_AS_SECURITY_BOUNDARY`
- `MIGRATION_MAGNITUDE = SUBSTANTIAL`
- `COMMERCIAL_USE_BLOCKER = NOT_VERIFIED`
- `RECOMMENDED_ARCHITECTURE = SPLIT_ARCHITECTURE`

---

## 1. Ground Truth und Evidenzstandard

### 1.1 Unveränderliche Bezugspunkte

| System | Referenz | SHA / Digest | Rolle |
|---|---|---|---|
| Repo A | lokaler `HEAD` | `c6e43b514eeaf6549b074073fa06b3c4e67e0384` | aktueller PowerUnits-Hermes-Fork |
| Gemeinsame Basis | Upstream `v2026.7.20`, Projektversion 0.19.0 | `3ef6bbd201263d354fd83ec55b3c306ded2eb72a` | nachgewiesener Merge-Base |
| Upstream-Release | CalVer-Tag `v2026.8.19`, Projektversion 0.20.5 | `fcbd1076a93841fa88855acce810e342a5b78101` | heutige Release-Basis |
| Upstream-Tagobjekt | `v2026.8.19` | `b05e680e63d39d5a8e3ec0f5842a41d1c4209c03` | annotiertes, aber unsigniertes Tag |
| Upstream `main` | Stichtags-Snapshot | `fd3a783a3edbbda611cbc4e38d70202dca7b5852` | nur Capability-/Issue-Research, nicht Produktionspin |
| Repo B | `origin/main` | `4128efac044e1d310f351853634d20c1c77980fd` | kanonischer Produkt-/Datenstand |
| Offizielles OCI-Image | Multi-Arch | `sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09` | bevorzugtes unveränderliches Upstream-Artefakt |

### 1.2 Evidenztags

- `VERIFIED`: Quellcode, Commitobjekt, reproduzierbarer Test oder Primärquelle belegt.
- `PARTIAL`: ein Teil der Boundary ist belegt, aber nicht vollständig gleichwertig oder nicht produktionsnah getestet.
- `INFERRED`: aus Code-/Architekturstruktur abgeleitet, ohne vollständigen Laufzeitbeweis.
- `NOT_VERIFIED`: nicht belastbar belegt oder durch bekannte Gegenbeispiele widerlegt.

### 1.3 Grenzen dieser Prüfung

- Keine Live-Inspektion von Railway-Deployment, Firewall, Secret Store, DNS, realen Providerverträgen oder Produktivlogs.
- Keine destruktiven Merge-/Checkout-Operationen. Der v0.20.5-Merge wurde in einem temporären, danach gelöschten Audit-Clone mit `git merge-tree --write-tree --messages` simuliert.
- Repo-B-Analyse erfolgte am kanonischen Gitobjekt `origin/main`, nicht am abweichenden lokalen Working-Tree-HEAD.
- Upstream-Issues sind Hinweise auf reale offene Risiken; ein Issue allein beweist keine Ausnutzbarkeit in jeder PowerUnits-Konfiguration.

---

## 2. Current Architecture

### 2.1 Ist-Datenfluss

Die deklarierte Betriebsstufe ist **Stage 1: Trusted Analyst** und damit ein interner, read-first Operatorpfad — kein Customer-Agent.

```text
Interner Operator
  → Telegram Gateway in Repo A
  → first_safe_v1: Plattform- und Toolset-Cap
  → env-gated PowerUnits-Tool
  → fest verdrahteter POST /internal/hermes/bounded/v1/<operation>
  → Shared-Bearer POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET
  → Repo-B FastAPI Router
  → Repo-B Service-Validator
  → kanonischer Data-Ingestion-Job / deterministischer Read-Service
  → PostgreSQL/Timescale und data_pipeline_runs
  → minimierte JSON-Antwort mit correlation_id / pipeline_run_id
  → Modell und Operator
```

Nebenpfade:

- Repo-A-Timescale-Read führt feste parametrisierte SQL-Muster gegen genau eine View aus; kein freies SQL.
- Repo-B-File-Read nimmt nur einen Allowlist-Key an und löst Repo/Branch/Pfad aus `config/powerunits_repo_b_read_allowlist.json` auf; kein freier Pfad.
- Dokument- und Workspace-Tools haben eigene Caps und Größenlimits.
- Web-/Research-Tools öffnen Netzwerkzugriff mit toolseitigen Eingabegrenzen, sind aber keine generelle Egress-Firewall.
- HTTP-Tools verdrahten den Route-Suffix fest und bieten dem Modell keinen URL-Parameter. Die operatorseitige Base-URL besitzt jedoch keine Host-Allowlist und läuft nicht durch `url_safety`.

### 2.2 Repo A: tatsächliche Security- und Capability-Grenzen

**Finaler Callable Cap (`VERIFIED`)**

- `model_tools.get_tool_definitions()` schneidet die finale Toolmenge bei `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` auf die Union von `expected_telegram_toolsets_first_safe(tier)`.
- Das geschieht nach der normalen Toolset-Auflösung und reduziert auch vom Caller angeforderte Toolsets.
- `tests/tools/test_powerunits_docs_tool.py` beweist unter anderem, dass `read_file` selbst bei expliziter Anforderung nicht exponiert wird.
- Eine All-Toolset-Laufzeitreproduktion ergab neun tatsächlich verfügbare Tools und kein Terminal, Process, File, Web, Browser, Code Execution, Delegation, Cron oder Skill-Tool.
- Einschränkung: Availability-/Tooldefinitions-Caches sind nicht profilbezogen. In der BZN-Reproduktion blieb ein zuvor verfügbares Tool nach Entfernen beziehungsweise Falschsetzen seines Env-Gates sichtbar.

**Gateway Lockdown (`VERIFIED`)**

- `gateway.run._apply_powerunits_runtime_lockdown_to_user_config()` überschreibt die effektive Plattformkonfiguration zuletzt.
- `_enforce_powerunits_toolsets()` liefert außerhalb Telegram eine leere Toolsetliste.
- Skill-Sync und Slash-Skill-Dispatch sind im Lockdown deaktiviert.
- `gateway.config._apply_powerunits_runtime_lockdown()` deaktiviert alle bekannten Plattformen außer Telegram.
- Laufzeitreproduktionen ließen aus einer Konfiguration mit allen Plattformen nur Telegram aktiv, lieferten für Discord keine Tools und für das Gateway-Skill-Menü keine Skill-/Plugin-Einträge.
- Plugin-Discovery selbst bleibt aktiv. Der Lockdown begrenzt Model-Callable-Tools, sandboxed aber keinen bereits vertrauten In-Process-Plugin-Code.

**Bootstrap-Policy (`VERIFIED` im Source, `NOT_VERIFIED` im lokalen Venv-Test)**

- `docker/apply_powerunits_runtime_policy.py` setzt Telegram-Toolsets, deaktiviert andere Plattformen, erzwingt `approvals.mode=manual`, `approvals.cron_mode=deny` und leert `command_allowlist`.
- Die 15 fokussierten Policytests wurden in der vorhandenen Windows-Venv wegen fehlendem `yaml` vollständig übersprungen. Der Sourcebeleg bleibt, der aktuelle Venv-Laufzeitbeleg fehlt.

**Capability-Tiers und Env-Gates (`VERIFIED`)**

- Tier 0–6 fügt progressive Toolsets ein.
- Jedes relevante Tool besitzt zusätzlich ein Feature-Env-Gate und, bei HTTP-Ausführung, Base-URL-/Secret-Anforderungen.
- Diese Mehrfachgates sind Defense-in-depth, aber auch eine Driftquelle.
- Der aktuelle First-Safe-Basiskatalog enthält 55 Toolsets, davon 49 PowerUnits-spezifische; ältere Policytexte beschreiben noch eine deutlich kleinere Oberfläche.

**Profile, Workspace und Credentials (`PARTIAL`)**

- Gateway-Sessionkeys enthalten Profil, Plattform, Chat, Thread und standardmäßig Participant-Scope; Session-IDOR-, Busy-Session-, Approval-State- und Cross-User-Tests bestanden.
- Gegenbeleg: Im aktiven `profile-a` zeigte `get_hermes_home()` korrekt auf Profil A, `powerunits_workspace_tool._workspace_root()` aber weiter auf das globale `HERMES_HOME/hermes_workspace`.
- `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` und `DATABASE_URL_TIMESCALE` sind nicht Teil der generischen Subprocess-Provider-Blocklist oder dynamischen Secretklassifikation.
- `tui_gateway/host_supervisor.py` ergänzt nach dem sanitisierten Env-Aufbau erneut `os.environ`; damit können zuvor entfernte Secrets wieder eingebracht werden.
- First-Safe entfernt Terminal und Delegation aus der Modelloberfläche, aber das ersetzt weder Profilscoping noch eine Prozess-/Plugin-Secret-Boundary.

### 2.3 Repo B: die autoritative Boundary

Am SHA `4128efac` existieren **31 interne POST-Routen** unter `/internal/hermes/bounded/v1/*`, registriert über 15 Routermodule in `backend/main.py`.

Gemeinsame Eigenschaften:

- Pydantic-Requests verwenden `ConfigDict(extra="forbid")`.
- Alle Routen verlangen einen Shared Bearer.
- Ist `POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET` nicht konfiguriert, antwortet die Boundary mit 404.
- Tokenvergleich erfolgt mit `secrets.compare_digest`.
- Slice-/Länder-/Versions-/Fensterregeln werden serverseitig nochmals und damit autoritativ geprüft.
- Jobs und Datenbankzugriffe bleiben in Repo B.
- Fehlertexte werden vor Clientantworten begrenzt und insbesondere um DB-URLs bereinigt.

Nicht vorhanden:

- kein Customer-/Tenant-/User-Kontext,
- keine feingranulare Operation-/Rollen-AuthZ am HTTP-Layer,
- keine Rate Limits für `/internal/hermes/*`,
- keine wirksame Request-Idempotenz; `idempotency_key` ist in v1 reserviert und ignoriert,
- keine Router-Level-Deduplizierung paralleler Runs,
- kein eigener Hermes-Request-Auditdatensatz jenseits Korrelation, Logs und Pipeline-Run-Tracking.

**Folgerung:** Repo B stellt einen **internen Operator-Bridge** bereit, keine Customer-SaaS-Agent-API.

### 2.4 Customer-Frontend

Die Suche in `app/` und `frontend/` am kanonischen Repo-B-SHA fand keinen Hermes-, Agent-, Assistant- oder Chat-Pfad. Vorhanden sind Analytics-Flächen und statische Readiness-/Snapshot-Darstellungen.

`CUSTOMER_HERMES_UI = ABSENT_VERIFIED`

Das ist architektonisch relevant: Ein Customer Copilot muss nicht „nur angeschlossen“ werden. Auth, Tenant-, Session-, Memory-, Retention-, Entitlement- und Product-UX-Boundaries fehlen absichtlich und müssen als Produktarchitektur entstehen.

### 2.5 Wo Komplexität notwendig ist

Muss PowerUnits besitzen:

- serverseitige Domainvalidierung,
- deterministische Queries, Jobs und DB-Transaktionen,
- Länder-/Zeitfenster-/Versionsgrenzen,
- Provenienz und Pipeline-Run-State,
- Fehlerbereinigung,
- Credentials externer Datenquellen,
- fachliche Response-Verträge.

Ist vermeidbare technische Schuld:

- etwa zwölffach kopierte Bearer-Auth- und Correlation-ID-Helpers in Repo-B-Routern,
- nahezu 1:1 gespiegelte Repo-A-Toolwrapper pro HTTP-Operation,
- dieselbe Capability-Policy in Bootstrap, Gateway, Overlay, Env-Gates und Toolbeschreibungen,
- Tier-/Toolset-Dokumentation, die dem realen 55er-Basis-Toolsetkatalog hinterherläuft.

---

## 3. Fork Divergence und Wartungskosten

### 3.1 Definitionen und Messwerte

| Kennzahl | Definition | Ergebnis |
|---|---|---:|
| `LOCAL_ONLY_COMMITS` | alle Commits seit dem gemeinsamen v0.19.0-Commit | 220 |
| `LOCAL_ONLY_NON_MERGE_COMMITS` | Patchcommits ohne 74 Merge-/Integrationscommits | 146 |
| `LOCAL_ONLY_MEANINGFUL_PATCHES` | Non-Merges ohne 7 leere Redeploys, 20 reine Docs, 1 Lockfile-only und 1 Release-Metadaten-Bump | 117 |
| `MATERIALLY_DIVERGED_FILES` | gemeinsame Repo-A/Upstream-Code-/Config-/Runtime-Pfade nach Abzug von Tests, `AGENTS.md` und `uv.lock`; alle 29 Blobs divergieren | 29 |
| `HIGH_CHURN_NON_DOC_TEST_FILES` | lokale Nicht-Docs/Test/Lock-Dateien mit mindestens 20 geänderten Zeilen | 101 |
| `POWERUNITS_SPECIFIC_FILES` | Pfad oder Netto-Diff enthält PU-/first-safe-/Repo-B-/ENTSO-E-/ERA5-/Option-D-Semantik, plus zwei forkspezifische Cursor-Indizes | 255 von 275 |
| `SECURITY_SPECIFIC_LOCAL_PATCHES` | unabhängige semantische Security-/Policy-Familien | 8 |
| `UPSTREAM_NOW_SUPERSEDES_LOCAL_PATCHES` | symbolisch verifizierte historische Fixfamilien | 3 |
| `PATCHES_STILL_WITHOUT_UPSTREAM_EQUIVALENT` | fortbestehende semantische Funktionsfamilien | 11 |
| `UPSTREAM_CHANGED_FILES` | alle Pfade zwischen v0.19.0-Base und v0.20.5 | 7.382 |
| `PATH_OVERLAP` | Pfade, die sowohl lokal als auch upstream geändert wurden | 44 |
| `MERGE_TREE_CONFLICT_FILES` | echte Konflikte im nichtdestruktiven Dreifachmerge Local HEAD ↔ v0.20.5 | 21 |

Netto-Diff Merge-Base → Repo-A-HEAD: 275 Dateien, 49.325 Einfügungen und 1.668 Löschungen.

Die acht Securityfamilien sind: First-Safe Clamp; Capability-/Profilgates; Env-Fingerprint gegen stale Toolsets; allowlistete Reads; bounded Web-/Scope-Warnungen; Pfadcontainment/Review-Governance; gestufte Human Gates; Docker-Ownership-Reconciliation.

### 3.2 Konflikthotspots gegen v0.20.5

Die 21 simulierten Konflikte betreffen:

- Kern: `model_tools.py`, `toolsets.py`, `tools/registry.py`
- Gateway: `gateway/run.py`, `gateway/slash_commands.py`
- Provider/Transport: `agent/chat_completion_helpers.py`, `agent/transports/chat_completions.py`, `hermes_cli/runtime_provider.py`
- Packaging/Deployment: `pyproject.toml`, `uv.lock`, `docker/stage2-hook.sh`
- CLI: `hermes_cli/banner.py`, `hermes_cli/commands.py`
- sieben zugehörige Testdateien sowie `AGENTS.md`

Ein Rebase ist damit technisch machbar, aber kein mechanischer Versionsbump. Gerade die Security-Cap-Pfade überlappen mit den am schnellsten evolvierenden Upstream-Seams.

Eine vorgelagerte Hunk-Risikoanalyse markierte 16 hohe Hotspots. Vier davon (`Dockerfile`, `hermes_cli/setup.py`, `hermes_cli/tools_config.py`, `plugins/model-providers/custom/__init__.py`) auto-mergen im konkreten v0.20.5-Dreifachmerge, bleiben aber semantisch prüfpflichtig.

### 3.3 Lokale Patchfamilien, die Upstream heute weitgehend ersetzt

`UPSTREAM_NOW_SUPERSEDES_LOCAL_PATCHES = 3`:

1. **Supply-Chain-Install-Hook-Scope**  
   Lokal `cb3c099b…`; Upstream `be89c2e4…`. Upstream besitzt heute die strengere, am Repository-Root verankerte Detection.
2. **Asynchrones Channel Directory und Azure-URL-Erkennung**  
   Lokal `c3637fd4…`; upstream insbesondere `802c7acb…`. Die Funktionalität liegt bereits in der Upstream-Ancestry; lokal bleiben vor allem Regressionstests.
3. **Tool-Definitions-Cache**  
   Lokal wiederhergestellt in `81964328…`; Upstream-Ursprung `9f004b6d…`, später weiter gehärtet. v0.20.5 besitzt Cache, Lock und Größenbegrenzung.

Breitere Upstream-Primitives wie Profile, Desktop, Bot Mode, Observability und Delegation ersetzen weitere gewünschte Eigenentwicklung, sind aber keine patchgenaue Äquivalenz dieser drei historischen Fixfamilien.

### 3.4 Patches ohne gleichwertiges Upstream-Pendant

`PATCHES_STILL_WITHOUT_UPSTREAM_EQUIVALENT = 11`:

1. PowerUnits-Domainadapter für ENTSO-E, ERA5, Preise, Forecasts, Outages, Coverage und Remediation.
2. Manifest-/Allowlist-basierte Repo-B-, Timescale-, Docs- und Workspace-Leser.
3. First-Safe Runtime Clamp in Bootstrap, Gateway, `model_tools.py` und `toolsets.py`.
4. Capability-Tier-/Profil-Overlays einschließlich Telegram-Exposition.
5. Env-gesteuerte Cache-Invalidierung via `ToolRegistry.requires_env_binding_fingerprint()` und Gateway-Cachefingerprint.
6. Pfadcontainment und Draft-/Review-Governance.
7. energiebezogene Tavily-Begrenzung und Scope-Asymmetrie-Warnungen.
8. Option-D-/Tier-4B-/Tier-5A-Preflight-, Validate- und Human-Gate-Workflows.
9. Custom-Provider-/OpenAI-Kompatibilität für `think`, `reasoning_effort`, Token-Caps und stale `api_mode`.
10. Railway-/Docker-Kompatibilität einschließlich lokaler Behandlung von `VOLUME ["/opt/data"]` und Ownership-Reconciliation.
11. lokale Modell-/Kostenpolicy einschließlich Primary Model, Reasoning und Auxiliary-/Tool-Output-Caps.

Im Zielbild wandern 1–8 und 11 in Capability Plane, dünnen Client oder Model Gateway. Familie 9 wird als kleiner, upstreamfähiger Providerpatch qualifiziert. Familie 10 bleibt ein Deploymentpatch mit Exit-Kriterium. Repo-B-Domainvalidierung und Jobs sind keine Forkpatchfamilie und bleiben unabhängig davon in Repo B.

### 3.5 Jährlicher Forkpreis

Der Preis ist nicht nur Mergezeit:

- Security-Patches kommen verspätet oder kollidieren mit lokalen Guardrails.
- Provider-/API-Änderungen müssen erneut qualifiziert werden.
- Desktop/Bot-Mode-Innovation ist blockiert, bis der Core-Port abgeschlossen ist.
- Jeder neue lokale Toolwrapper vergrößert Prompt-, Test-, Gate- und Dokumentationsflächen.
- Ein Merge kann Schutz scheinbar erhalten, aber semantisch verschieben; dafür braucht es Golden- und Negativtests, nicht nur grüne Unit Tests.
- Der Fork besitzt heute lokale Testschulden: Zwei BZN-Negativtests sind in-file order-/cache-abhängig; mehrere File-Safety-Tests machen auf Windows POSIX-Annahmen.

**Fork-Weiterführung ist nur dann rational, wenn die verbleibenden Core-Patches nach Extraktion klein, ausdrücklich befristet und durch Upstream-PRs mit Exit-Kriterium belegt sind.**

---

## 4. Upstream Modern State

### 4.1 Reife Capability-Primitives

Am Release v0.20.5 sind folgende Primitives real und wiederverwendbar:

- Profile mit getrenntem `HERMES_HOME`
- Gateway, Dashboard/Serve und OpenAI-kompatibler API Server
- native Desktop-App
- Bot Mode mit Bots, Routines und Groups als UX-Komposition
- Toolsets, Plugins und MCP
- Skills und Skills Hub
- Memory-Backends und Memory-Review
- Cron/Routines
- Delegation und Subagent-Gruppen
- Browser-/Computer-Use-Backends
- Observer-/Tool-Hooks und Observability
- Terminal-/Browser-Sandbox-Backends

### 4.2 Was diese Primitives nicht garantieren

- Ein Profile ist ein Zustandsverzeichnis, keine OS-, Filesystem-, Credential-, Netzwerk- oder Tenant-Sandbox.
- Ein Toolset ist Model-Surface-Komposition, keine vollständige Produkt-AuthZ.
- Ein Bot ist Profile plus UI; kein eigener Security Principal.
- Eine Routine ist Cron-UX; keine produktseitige durable Workflow-State-Machine.
- Bot Groups sind UI-Orchestrierung; nicht gleichbedeutend mit dauerhafter, transaktionaler Delegation.
- Desktop besitzt Maschinenfähigkeiten und ist deshalb kein sicherer Customer-Webclient.
- Ein Terminal-Sandbox schützt nicht automatisch In-Process-Plugins, MCP, Python-Hooks, Browser oder Provideraufrufe.

### 4.3 Offene upstream Security-/Reliability-Grenzen am Stichtag

Primärquellen, jeweils offen:

- [#91308](https://github.com/NousResearch/hermes-agent/issues/91308): Auxiliary Custom-Endpoint kann `OPENAI_API_KEY` an fremden Host senden.
- [#87779](https://github.com/NousResearch/hermes-agent/issues/87779): `session_search` ohne Chat-/Profile-Ownership-Scoping.
- [#87724](https://github.com/NousResearch/hermes-agent/issues/87724): Computer-Use-Mutationen können headless ohne Approval-Callback fail-open laufen.
- [#91415](https://github.com/NousResearch/hermes-agent/issues/91415): Multiplex API Server ignoriert per-profile Toolsets/Disabled-Toolsets.
- [#91654](https://github.com/NousResearch/hermes-agent/issues/91654): MCP Session-/Circuit-Breaker-Registries kollidieren bei multiplexed Profiles.
- [#90699](https://github.com/NousResearch/hermes-agent/issues/90699): TUI-Profile-Parameter kann den Profiles-Root verlassen.
- [#87419](https://github.com/NousResearch/hermes-agent/issues/87419): Windows-Destruktivbefehle sind bei Approval-off/`--yolo` nicht hardline.
- [#84248](https://github.com/NousResearch/hermes-agent/issues/84248): fehlgeschlagene Docker-cgroup-Probe entfernt Ressourcenlimits.
- [#90415](https://github.com/NousResearch/hermes-agent/issues/90415): Run-Status-Lesen ist bei Multiplex-Profils nicht isoliert.

Upstream selbst dokumentiert Hermes in `SECURITY.md` als Single-Tenant Personal Agent. Deshalb ist v0.20.5 **kein unverändert einsetzbarer Customer-Multi-Tenant-Agent-Service**.

### 4.4 Konkreter PowerUnits-Nutzen

| Capability | Konkreter PowerUnits-Workflow | Wert | Blocker / notwendige Kontrolle |
|---|---|---|---|
| Desktop | interner Operator-Cockpit für Sessions, Tools, Artefakte und Runs | hoch | read-only Pilot, keine freie Capability-Administration |
| Bot Mode | Data Health, Coverage, Forecast und Research als getrennte Operatorpersönlichkeiten | mittel–hoch | UI ist keine Policy; Credentials/Tools serverseitig pinnen |
| Profiles | getrennte Analyst-/Research-/Repair-Kontexte | hoch | getrennte Instanzen/Credentials statt Tenant-Isolation zu behaupten |
| API Server | interne Automationen und kontrollierter Desktopzugriff | hoch | hinter VPN/OIDC/mTLS; Issue #91415 blockiert Multiplex-Policyvertrauen |
| Remote MCP / Plugin | ein wiederverwendbarer PowerUnits Capability Gateway | sehr hoch | Tool Identity, Workload Identity, Scopes und Result-Firewall |
| Skills | reviewbare Analysten- und Repair-Runbooks | hoch | signieren/pinnen; keine autonome Promotion |
| Memory | Operatorpräferenzen und lokale Arbeitskonventionen | mittel | keine Secrets/Fakten-SoT; TTL und Review |
| Routines | tägliche read-only Coverage-/Data-Health-Briefs | hoch | Writes bleiben im Repo-B-Scheduler |
| Delegation | parallele read-only Länder-/Quellenanalyse | mittel–hoch | Tiefe/Parallelität/Kosten begrenzen; keine Writes |
| Browser | regulatorische und Quellenrecherche | mittel | ephemer, Egress-Allowlist, keine Customer-Cookies |
| Observability | Kosten, Toolentscheidungen, Approvals und Provenienz | sehr hoch | PowerUnits-owned, metadata-first |

**Capability-Upside ist real, aber konzentriert sich zuerst auf interne Operatoren und Entwickler.** Für Customer SaaS sind dieselben Primitives nur verborgene Runtime-Bausteine.

### 4.5 Capability-Upside nach Betriebsmodus

Nutzen 1–10 bewertet den erwarteten Workflowgewinn; „direkt fit“ bewertet die unveränderte Upstream-Capability, nicht das kontrollierte Zielbild.

| Capability | Customer Nutzen / direkt fit | Internal Nutzen / direkt fit | Developer Nutzen / direkt fit | Hauptprivileg |
|---|---|---|---|---|
| Profiles | 7 / nein | 8 / mit Instanztrennung | 9 / ja | State, Credentials |
| API/Serve | 9 / nein | 8 / mit privatem Ingress | 9 / Loopback/VPN | Netzwerk, Secrets |
| Desktop UI | 3 / nein | 8 / Pilot | 9 / ja | Maschine, Terminal |
| Bot Mode UI | 6 / nein | 8 / Pilot | 7 / ja | Profile, Credentials |
| Toolsets | 8 / nein | 9 / mit externer Policy | 9 / ja | Capability-Auswahl |
| Plugins/MCP | 9 / nein | 10 / out-of-process bevorzugt | 9 / trusted only | Code, Netzwerk, Secrets |
| Skills | 7 / signiert/minimiert | 9 / reviewed | 9 / reviewed | Prompt-/Workflowcode |
| Memory | 9 / Product Store nötig | 6 / begrenzt | 7 / mit Review | persistente Daten |
| Routines/Cron | 8 / Repo-B-Scheduler | 8 / read-only | 7 / ja | autonome Ausführung |
| Delegation | 6 / nein | 7 / read-only | 9 / budgetiert | Kosten, Toolvererbung |
| Browser/Computer Use | 5 / nein | 6 / Sandbox | 8 / Sandbox | Egress, Cookies, Side Effects |
| Observability | 10 / PU-owned | 10 / PU-owned | 8 / lokal | sensitive Payloads |
| Sandboxes | 10 / ephemer Pflicht | 9 / Pflicht für breite Tools | 10 / untrusted Code | OS-/Netzgrenze |

Priorität aus Nutzen und Risiko:

1. Capability Gateway und Observability,
2. interner read-only Desktop-/Bot-Pilot,
3. signierte Skills und read-only Routines,
4. begrenzte read-only Delegation,
5. erst danach Browser; Computer Use nicht im Operator-/Customerpfad,
6. Customer Sessions/Memory/Routines ausschließlich produktseitig.

---

## 5. Guardrail Ledger und Security-Äquivalenz

`CONTROL_EQUIVALENCE` bewertet nicht Namensähnlichkeit, sondern ob v0.20.5 ohne lokalen Patch dieselbe wirksame Boundary liefert.

| Kontrolle | Lokale Wirkung | Upstream v0.20.5 | `CONTROL_EQUIVALENCE` | Zielentscheidung |
|---|---|---|---|---|
| Finaler `first_safe_v1` Callable Cap | schneidet finale Tools nach Auflösung; Laufzeitrepro blockiert breite Tools | konfigurierbare Toolsets und bessere Profilcaches; API-Multiplex kann Toolpolicy laut #91415 ignorieren | `PARTIAL` | externen Policy-Compiler + Runtime-Acceptance-Test behalten |
| Telegram-only Plattformlockdown | andere Plattformen leer/deaktiviert | Plattformconfig vorhanden, aber keine PowerUnits-immutable Policy | `PARTIAL` | Ingress am Deployment/Gateway besitzen |
| Capability-Tiers | progressive PU-Scopes | keine PU-Domainsemantik | `NOT_VERIFIED` | als Capability-Manifest neu modellieren |
| Env-Gates je Tool | fail-closed Featurefreigabe; lokaler Availability-Cache kann nach Gatewechsel stale bleiben | allgemeine Requirements/Toolchecks mit profilbezogeneren Caches | `PARTIAL` | Service Identity + zentrale Policy statt Env allein |
| Fester HTTP-Pfad/Schema | kein modellseitiger URL-Parameter; Base-URL operatorseitig ohne Host-Allowlist | allgemeine HTTP/MCP/Pluginmechanismen | `PARTIAL` | in PU Gateway behalten; Host und Route gemeinsam autorisieren |
| Repo-B-Servervalidierung | Länder, Version, Fenster, Job | außerhalb Hermes | `NOT_VERIFIED` | unverändert autoritativ in Repo B |
| Kein generisches SQL | feste Queries/Jobs; Ausnahme: feste Timescale-Patterns | Terminal/Plugins können generisch arbeiten | `NOT_VERIFIED` | nur Capability API, kein DB-Credential für Hermes |
| Repo-B-Key-Allowlist | kein freier Repo-/Branch-/Pfadparameter | allgemeine File/Git/GitHub-Tools breiter | `NOT_VERIFIED` | Capability API / signed manifest |
| File-Write Safe Root/Denylist | schützt File-Tools; first-safe exponiert sie nicht | ähnliche/weiterentwickelte File-Safety | `PARTIAL` | zusätzlich OS-Mounts; Tool nicht exponieren |
| Manual Approval / Cron deny | Bootstrap pinnt Manual/Deny; PU-HTTP-Execute hat kein Per-Call-Approval; Workspace-Overwrite ist approvalfrei | Approval-System vorhanden; Computer Use und Windows-Hardline haben offene Lücken | `PARTIAL` | Approval im PU Gateway; keine `--yolo`-Produktion |
| Secret Redaction | Core + toollokale DB-URL-Redaction | breitere Redaction, aber #91308 zeigt Provider-Leak | `PARTIAL` | Secret Broker und Host-Allowlist, Redaction nur letzte Linie |
| Secret-Injection | Bearer erst im Toolclient; PU-Secrets fehlen in generischer Subprocess-Blocklist und können im Host-Supervisor wieder geerbt werden | allgemeine Provider-/Secret-Sources; derselbe Host-Supervisor-Env-Reimport | `PARTIAL` | target-bound short-lived credentials; Spawn-Env-Allowlist |
| Profile-/Session-Isolation | Gateway-Sessions gut gescopt, aber PU-Workspace global und Credentials prozessglobal | moderne Profiles, aber #87779/#90415/#91654 | `PARTIAL` | keine Tenant-Konsolidierung in einem Prozess |
| Plugin/MCP/Skill-Supply-Chain | Skill-Sync im first-safe aus; Plugins werden weiter entdeckt | Registry-Härtungen, aber In-Process-Code bleibt privilegiert | `PARTIAL` | nur signierte Allowlist; bevorzugt out-of-process |
| Netzwerk/Egress | Terminal/Browser aus; Web-/Research und feste HTTP-Tools erlaubt | URL-Guards und Sandboxes, keine universelle Prozess-Egresspolicy | `NOT_VERIFIED` | Netzwerkpolicy außerhalb Agentprozess |
| Rate/Concurrency/Idempotenz | Toolfenster begrenzt, aber kein zentrales Budget | allgemeine Agentbudgets, keine PU-Jobidempotenz | `NOT_VERIFIED` | PU Gateway + Repo-B Run-State |
| Audit/Provenienz | correlation/pipeline IDs und Logs | Observability-Hooks vorhanden | `PARTIAL` | PU-owned Audit, metadata-first, durable operation ID |

### 5.1 Repräsentative lokale Verhaltensevidenz

Portable und isolierte Sicherheitsauswahlen:

- Fork: 443 bestanden, 15 übersprungen.
- Upstream v0.20.5: 241 gleichartige Basiskontrollen bestanden.
- PowerUnits-Workspace: 7 bestanden.
- Coverage-Surface frisch: 3 bestanden.
- BZN-Surface: 1 bestanden, 2 fehlgeschlagen.
- Zusätzliche fokussierte lokale Läufe: 16/16 First-Safe-/Overlaytests und 22/22 plattformrelevante Safe-Root-/Denylisttests bestanden.
- Breitere Läufe erreichten im Fork 556 und upstream 334 bestandene Tests; verbleibende generische Windowsfehler waren überwiegend POSIX-Pfad-/Dateimode-Annahmen.
- 15 Policytests wurden in der vorhandenen Windows-Venv wegen fehlendem `yaml` übersprungen.

Reproduzierte Schwächen:

- Die zwei BZN-Negativfehler belegen einen stale Tool-/Availability-Cache nach Env-Gate-Wechsel innerhalb des Prozesses.
- PowerUnits-Workspace bleibt trotz aktivem Profile auf dem globalen Workspace-Root.
- PowerUnits-Bearer und Timescale-URL sind nicht durch die generische Subprocess-Secretklassifikation abgedeckt.
- PU-Execute ist bei eingeschaltetem Deployment-Gate nicht durch eine deterministische Human-Confirmation pro Call geschützt.
- Die Base-URL ist nicht host-allowlisted; das Modell kann sie nicht wählen, die Deploymentkonfiguration aber schon.
- Ein All-Toolset-Repro löste Auxiliary-Verfügbarkeitsprüfungen mit Auth-/Payment-Logs aus. „Keine ausgehenden Provider-Probes“ ist deshalb nicht belegt.

Interpretation:

- Der entscheidende **finale Tool-Cap** hat positive und negative Verhaltensbelege.
- Es gibt **keinen vollständigen Security-Equivalence-Beweis** gegen v0.20.5.
- Das Gesamturteil ist `CONTROL_EQUIVALENCE = PARTIAL`.
- Grüne Teiltests dürfen Profile-, MCP-, Provider-, Plugin-, Egress- oder OS-Boundaries nicht repräsentieren.
- Die Testportabilitäts- und Cacheprobleme sind Wartungsschuld und müssen vor einer Migrationsfreigabe bereinigt werden, aber sie ändern dieses Architektururteil nicht.

### 5.2 Threat Models

#### A. Personal / Developer Agent

Angreifer:

- untrusted Repositoryinhalt,
- Web-Prompt-Injection,
- kompromittiertes Skill/Plugin/MCP,
- bösartiges Dependency-/Updateartefakt.

Akzeptabel:

- breite Werkzeuge, wenn Benutzer und Host dieselbe Vertrauensdomäne teilen,
- Profile für UX-/State-Trennung,
- lokaler Desktop.

Pflicht:

- keine Produktionssecrets,
- ephemere Sandbox für untrusted Code,
- signierte/pinned Plugins und Skills,
- Approval für Side Effects,
- getrennte Browserprofile.

#### B. Internal Operator Agent

Angreifer:

- untrusted externe Inhalte,
- Prompt-Injection in Datenquellen,
- kompromittierter Operatoraccount,
- gestohlener Shared Bearer,
- fehlerhafte/breit konfigurierte Capability.

Pflicht:

- private Ingress-Boundary,
- Workload Identity statt globalem Long-Lived-Secret,
- feste Operationen und Scopes,
- read/write getrennte Principals,
- Idempotenz, Rate Limit, Approval und vollständiger Audit,
- getrennte Agentinstanz je Trust Domain.

#### C. Customer-facing SaaS Agent

Zusätzlich:

- bösartiger oder neugieriger Tenant,
- Cross-Tenant-Data-Exfiltration,
- Kosten-/Run-Amplifikation,
- Jailbreak/Persistence über Session/Memory,
- Retention-/Consent-/Deletion-Verstöße,
- Produkt-Entitlement-Bypass.

Nicht ausreichend:

- Hermes Profiles,
- Toolset-Config,
- Desktop/Bot-UI,
- ein gemeinsamer API-Key,
- Shared Bearer,
- Prompt-Instruktionen.

Pflicht:

- Product AuthN/AuthZ und Tenant Authority in Repo B/BFF,
- objekt-/zeilenbezogene Data Selection vor dem Modell,
- tenant-spezifische Session/Memory Stores,
- per-request Capability Token,
- ephemere Execution,
- Provider-/Datenklassifikation,
- durable Workflows und Budgetierung.

---

## 6. Desktop und Bot Mode

### 6.1 Desktop

**Für interne Operatoren:** `FIT_WITH_CONTROLS`

Geeignet für:

- Session- und Artefaktnavigation,
- visuelle Tool-/Run-Transparenz,
- read-only Operatorprofile,
- Entwicklerworkflows.

Nicht als Customer-Produkt übernehmen:

- Desktop besitzt Maschinen-, Filesystem-, Git-, Terminal- und Credential-Seams.
- Lokaler Zustand und Profile erfüllen keine Customer-Tenant-Anforderungen.
- Upstream liefert am Release keine offiziellen Desktop-Installer; Desktop-E2E war im Hauptworkflow deaktiviert.

### 6.2 Bot Mode

**Architektonischer Wert:** hoch  
**Wert der konkreten UI für Customer SaaS:** niedrig bis mittel

Wiederverwendbare Primitives:

- `PROFILE`: zustandsbezogener Agentkontext
- `GATEWAY`: Transport und Zustellung
- `SESSION`: Conversation/Runtime/Lineage-Identitäten
- `TOOLSET`: Surface-Komposition
- `SKILL`: versioniertes Workflowwissen
- `MEMORY`: persistenter Kontext
- `ROUTINE`: Cron-Darstellung
- `DELEGATION`: Child-Agent-Kontext
- `CAPABILITY_POLICY`: muss PowerUnits besitzen

Nicht wiederverwenden als Security Contract:

- `BOT_MODE_UI`,
- `DESKTOP_UI`,
- Groups als durable Orchestrierung,
- Profile als Tenantgrenze,
- Tool-Toggles als AuthZ.

### 6.3 Surface-Empfehlung

- **Internal Operator:** Desktop-/Bot-Mode-Pilot, read-only und hinter privatem Gateway.
- **Developer:** Desktop, TUI und API-Server auf Loopback/VPN.
- **Customer:** Repo-B-native Weboberfläche; Hermes bleibt optionaler Worker hinter BFF und Capability Gateway.

---

## 7. Model Provider und Data Trust Boundaries

### 7.1 Providerklassen

- `L0`: PowerUnits-kontrollierte lokale/self-hosted Inferenz.
- `E1`: vertraglich freigegebener Enterprise-Provider mit DPA, Region, No-Training und definierter Retention.
- `E2`: allgemeiner Aggregator, Browser-/Search-SaaS oder öffentlicher Provider; nur öffentliche/minimierte Daten.

Browser-, MCP-, Search-, Observability- und Modelprovider sind **getrennte Empfänger**. Ein freigegebener Modellprovider legitimiert keine Weitergabe an einen Cloud-Browser oder Telemetrieanbieter.

| Datenklasse | E2 | E1 | L0 | Pflichtkontrolle |
|---|---|---|---|---|
| generische Systemprompts | ja | ja | ja | keine interne Methodik im Prompt |
| PowerUnits-Promptlogik | nur veröffentlicht | minimiert/freigegeben | ja | Version/Klassifikation |
| proprietärer Kontext | nein | taskbezogener Ausschnitt | ja | ACL, DLP, Zweckbindung |
| öffentliche Marktdaten | ja | ja | ja | Quellen-/Lizenzprovenienz |
| rohe lizenzierte/interne Marktdaten | nein | nur vertraglich erlaubt | ja | Aggregation, Field-/Row-Filter |
| Methodik/Scoring | nein | nur explizit freigegeben | ja | Methodik-Registry |
| interne Dokumente/Runbooks | nein | minimale Chunks | ja | Dokument-ACL |
| Toolresultate | öffentliche Aggregate | bounded/redacted | ja | Result-Firewall |
| Logs/Traces | technische Metriken | metadata-first | vollständig möglich | Payload standardmäßig aus |
| Memory | nur provider-safe | eigener E1-Scope | sensitiv möglich | Consent, TTL, Delete |
| Secrets | niemals | niemals | niemals im Prompt | Secret Broker |

### 7.2 Verdeckte Modellaufrufe

Die Policy muss auch gelten für:

- Title Generation,
- Context Compression/Summary,
- Memory Review,
- Skill Review/Curator,
- Delegation/Subagents,
- Fallbackmodelle,
- Vision-/Browser-Modelle.

Ein Provider-Fallback darf nie still in eine schwächere Trust Class wechseln. `#91308` zeigt konkret, warum Base URL, Zielhost und Credentialbindung gemeinsam autorisiert werden müssen.

### 7.3 PowerUnits-owned Controls

PowerUnits muss selbst besitzen:

1. Identity und Tenant Authority
2. Capability Registry
3. Model Routing Policy
4. Secret Broker
5. Fact-Pack Builder
6. Memory Governance
7. Tool-Result Firewall
8. Approval + Durable Execution
9. Audit/Observability
10. signierte Skill-/Plugin-/MCP-Supply-Chain

---

## 8. Upstream Supply Chain und kommerzielle Nutzung

### 8.1 Lizenz

- Hermes-Kern: MIT; kommerzielle Nutzung, Modifikation und Distribution sind erlaubt.
- `plugins/security-guidance`: Apache-2.0 mit eigenem `NOTICE`; Attribution muss bei Distribution erhalten bleiben.
- Bot-Mode-Desktop-Plugin: MIT.
- Desktop-Dependencybaum enthält unter anderem MPL-2.0-, Apache-2.0- und CC-BY-4.0-Komponenten. Ein releasefähiges zentrales Third-Party-Notice-Bundle wurde nicht gefunden.
- `iron-proxy` v0.39.0: Apache-2.0.
- Bitwarden `bws` v2.0.0: proprietäre Bitwarden SDK License; interne Nutzung und Distribution hängen vom bezahlten Vertrag und Nutzungsszenario ab.

Deshalb:

`COMMERCIAL_USE_BLOCKER = NOT_VERIFIED`

Das bedeutet **nicht**, dass Hermes-Kern kommerziell blockiert ist. Der Kern ist MIT. Nicht verifiziert ist die vollständige gewählte Distribution inklusive optionalem Bitwarden und Desktop-Notices. Wird Bitwarden deaktiviert und keine Desktop-Distribution vorgenommen, sinkt das Lizenzrisiko wesentlich.

### 8.2 Release-Provenienz

- Commit und annotiertes Tag sind `verified=false`, `reason=unsigned`.
- GitHub-Release ist `immutable=false`.
- Keine Projektchecksummen, SBOM, Cosign-Signatur oder SLSA-Provenienz als Releaseasset.
- PyPI hatte am Stichtag kein `hermes-agent==0.20.5`.
- Das offizielle OCI-Image existiert und sein Revision-Label verweist auf `fcbd1076…`.

### 8.3 Build- und CI-Befunde

Positiv:

- `uv.lock` enthält Artefakt-Hashes.
- direkte Python- und Node-Abhängigkeiten sind überwiegend exakt gepinnt.
- Docker nutzt `uv sync --frozen`.
- Haupt-CI, Docker Push und Release-Docker-CI waren grün.

Grenzen:

- Release-Install/Update-E2E hatte sechs von zehn rote Matrix-Legs.
- Ein Fallback löste trotz Lockproblem frei aus PyPI auf; das ist für kontrollierte Produktion unzulässig.
- Desktop-E2E war deaktiviert.
- OSV war detection-only (`fail-on-vuln: false`).
- Docker-Build ist wegen Distribution/APT und einzelner Downloads nicht vollständig reproduzierbar.
- Root-Frontend nutzt `npm install` statt strikt `npm ci`.
- Runtime-Lazy-Install darf in Produktion nicht aktiv sein.

### 8.4 `SAFE_UPSTREAM_CONSUMPTION_MODEL`

1. Release, Commit, Tagobjekt und Tree gemeinsam erfassen.
2. Wegen fehlender Upstream-Signatur internen Zwei-Personen-Intake und intern signierten Tag erzeugen.
3. OCI ausschließlich per Digest beziehen und in interne Registry spiegeln.
4. Revision-Label prüfen, SBOM/Scan erzeugen und Image intern signieren.
5. Python-/npm-/OS-Artefakte spiegeln; kein Runtime-Lazy-Install.
6. `uv lock --check`, `uv sync --frozen` und `npm ci` ohne freien Netzwerkfallback.
7. Bitwarden nur nach Vertragsfreigabe; sonst deaktivieren.
8. PowerUnits-Acceptance-Suite inklusive Guardrail-Golden-Tests, Profile-/Session-Negativtests, Gateway-Auth, Provider-Hostbindung und Repo-B-Operationen.
9. Staging + eine isolierte read-only Canary-Instanz, 24–72 Stunden Soak.
10. Rollout per identischem Digest; vorheriger Digest und kompatibler State-Snapshot bleiben rollbackfähig.

---

## 9. Architekturvarianten A–G

### 9.1 Definitionen

- **A — Current Fork:** heutigen All-in-one-Fork fortführen.
- **B — Rebased Deep Fork:** auf v0.20.5 rebasen, lokale Core-Patches weitgehend behalten.
- **C — Thin Fork / In-Process Plugin:** Core-Diff minimieren, PowerUnits als Python-Plugin/kleine Patchserie.
- **D — Upstream + External Capability Gateway:** Hermes upstream-nah; PU-Tools out-of-process via schmaler API/MCP.
- **E — Repo-B-native Customer Copilot:** Customerfläche ohne Hermes-Produktautorität; LLM-Orchestrierung produktseitig.
- **F — Full Custom Agent Runtime:** eigenen Agent Loop, Profile, UI, Sessions, Tools und Provider neu bauen.
- **G — Split:** D für Internal/Developer plus E für Customer SaaS.

### 9.2 Scoring

Skala: 1 = ungünstig, 10 = günstig.  
Bei „Migration ease“ bedeutet 10 einfach; bei „Migration risk“ bedeutet 10 niedriges Risiko.

| Dimension | A | B | C | D | E | F | G |
|---|---:|---:|---:|---:|---:|---:|---:|
| Security | 6 | 6 | 7 | 9 | 9 | 6 | 9 |
| Upstream compatibility | 2 | 5 | 8 | 9 | 10 | 10 | 9 |
| Maintainability | 3 | 4 | 7 | 8 | 8 | 2 | 8 |
| Feature velocity | 3 | 6 | 8 | 8 | 8 | 3 | 9 |
| Operational simplicity | 5 | 5 | 6 | 7 | 7 | 2 | 7 |
| SaaS production fit | 3 | 4 | 5 | 6 | 9 | 7 | 9 |
| Data/secret isolation | 5 | 5 | 6 | 9 | 9 | 8 | 9 |
| Observability/auditability | 4 | 5 | 6 | 9 | 9 | 7 | 9 |
| Dev/operator UX | 5 | 7 | 8 | 8 | 8 | 4 | 9 |
| Migration ease | 10 | 4 | 5 | 4 | 4 | 1 | 3 |
| Migration risk | 7 | 4 | 5 | 5 | 5 | 2 | 4 |
| Scalability | 6 | 6 | 7 | 8 | 9 | 6 | 9 |
| Low lock-in | 3 | 4 | 7 | 9 | 8 | 8 | 9 |
| **Ungewichteter Mittelwert** | **4,8** | **5,1** | **6,5** | **7,6** | **7,9** | **5,1** | **8,1** |

Interpretation:

- A ist kurzfristig am einfachsten, aber strategisch schwach.
- B ist ein notwendiger technischer Zwischenschritt, keine Zielarchitektur.
- C ist ein guter Übergang, aber In-Process-Plugin-Code teilt weiterhin Blast Radius und Secrets.
- D ist die beste interne Plattformgrenze.
- E ist die richtige Customer-Produktgrenze.
- F baut nicht-differenzierende Agentinfrastruktur neu und wird verworfen.
- G kombiniert D und E und gewinnt trotz hoher Migrationslast klar.

### 9.3 Aktuell vs. empfohlen

**Aktuelle Architektur:** 4,8/10

Stärken:

- gute interne Domainbegrenzung,
- echte Fail-closed-Gates,
- Repo B bleibt SoT,
- nachvollziehbarer Operatorweg.

Schwächen:

- tiefe Upstreamkopplung,
- Policy-/Toolkatalogdrift,
- kein Customer-SaaS-Sicherheitsmodell,
- Shared Bearer ohne Rate/Idempotenz/Tenant,
- hohe Innovationsteuer.

**Empfohlenes Split-Zielbild:** 8,1/10

Der Abstand kommt nicht von „mehr Features“, sondern von klarer Autorität:

- Upstream besitzt Agentruntime und UX.
- PowerUnits besitzt Capability-, Identity-, Daten- und Model-Trust-Policy.
- Repo B besitzt Produkt- und Datenwahrheit.

---

## 10. Recommended Architecture

### 10.1 Product Plane — Repo B

Besitzt:

- Customer AuthN/AuthZ, Tenant und Entitlements,
- PostgreSQL/Timescale und fachliche Wahrheit,
- deterministische Evaluatoren und Fact Packs,
- Customer Sessions und Memory,
- durable Jobs/State Machine,
- Provenienz, Model-/Prompt-Version, Datenfenster und Content Hash,
- Customer UI und BFF.

### 10.2 Internal Agent Plane — upstream-nahes Hermes

Besitzt:

- Agent Loop,
- Profile/Sessions,
- Desktop/TUI/CLI/Bot Mode,
- Skills und operatorbezogenes Memory,
- read-only Delegation,
- Provideradapter.

Besitzt ausdrücklich nicht:

- Customer-/Tenant-Autorität,
- Pipeline-SoT,
- Produkt-Workflow-State,
- Secrets im Prompt,
- Definition erlaubter PowerUnits-Side-Effects.

### 10.3 PowerUnits Capability Plane

Ein deklaratives `PowerUnitsCapabilityManifest` beschreibt je Operation:

- stabile `operation_id`,
- `effect = read | bounded_write | forbidden`,
- Rollen und Scopes,
- Länder/Familien/Zeitfenster,
- Approval-Anforderung,
- Idempotenzschlüssel,
- Rate-/Concurrency-/Budgetgrenzen,
- Input-/Output-Schema,
- Egress- und Providerklasse,
- Audit-/Provenienzfelder.

Der Gateway setzt durch:

- OIDC/mTLS/Workload Identity,
- kurzlebige Capability Tokens,
- serverseitige AuthZ,
- Result-Firewall,
- kein freies SQL/Filesystem/Repo/HTTP,
- vollständige Audit-Events.

Repo B validiert weiterhin alle fachlichen Regeln nochmals.

### 10.4 Execution Plane

Terminal, Browser und Computer Use:

- ephemer pro Job,
- ohne Produktionssecrets,
- read-only Mounts,
- CPU/RAM/Zeitlimits,
- Egress-Allowlist,
- getrennte Browserprofile,
- Artefaktübergabe statt gemeinsamem Host-Dateisystem.

### 10.5 Ingress

- Internal: privates Netzwerk, OIDC/mTLS, Rollenbindung.
- Developer: Loopback/VPN.
- Customer: ausschließlich Repo-B-BFF; kein direkter Hermes API-/Gatewayzugang.

---

## 11. Migration Roadmap und Rollback

### Phase 0 — Freeze und Golden Baseline

Akzeptanz:

- SHAs/Digests und Konfiguration inventarisiert.
- effektive Toolnamen pro Tier als Golden Behavior erfasst.
- alle bestehenden bounded Happy-/Negative-Paths pro Operation aufgezeichnet.
- Testportabilitäts- und Cachefehler klassifiziert.

Rollback:

- keine Produktionsänderung.

### Phase 1 — Sichere v0.20.5 Intake-Umgebung

Akzeptanz:

- intern gespiegeltes und signiertes OCI-Image,
- SBOM/Scans/Notices,
- keine Lazy Installs,
- keine Bitwarden-Integration ohne Lizenzfreigabe,
- Gateway nicht öffentlich.

Rollback:

- vorheriger bekannter Repo-A-Digest und State-Snapshot.

### Phase 2 — Read-only Capability Gateway

Akzeptanz:

- zunächst Docs, Coverage, Data Health, Readiness und Summaries,
- duale Ausführung Altwrapper ↔ Gateway liefert semantisch gleiche Ergebnisse,
- mTLS/OIDC, Operation IDs, Rate Limits, Audit,
- kein freier Pfad, SQL oder Endpoint.

Rollback:

- pro Operation Featureflag auf bestehenden Wrapper.

### Phase 3 — Internal Desktop/Bot Pilot

Akzeptanz:

- ausschließlich read-only Operatorprofile,
- separate Instanz/Credentials je Trust Domain,
- keine freie Plugin-/Skillinstallation,
- keine Computer-Use- oder Terminal-Capability,
- beobachtbare Kosten/Egress/Toolentscheidungen.

Rollback:

- UI abschalten; Telegram/read-only Gateway bleibt.

### Phase 4 — Bounded Writes

Akzeptanz:

- Approval Token, Idempotency Key, Run-State und Replay-Schutz,
- write-spezifischer Principal,
- Repo-B-Deduplizierung und Concurrency-Vertrag,
- End-to-End-Audit bis `pipeline_run_id`.

Rollback:

- Writeoperation einzeln deaktivieren; Readiness/Validation bleibt.

### Phase 5 — Repo-B-native Customer Copilot

Voraussetzungen:

- Customer Auth/Tenant/Entitlements,
- BFF und Fact Packs,
- Customer Session/Memory Governance,
- DPA-/Providerfreigabe,
- Cross-Tenant-/Deletion-/Retention-/Budgettests.

Rollback:

- Customer-Featureflag; keine Auswirkung auf internen Operatorpfad.

### Phase 6 — Forkabbau

Akzeptanz:

- PowerUnits-Domaincode aus Agent-Core entfernt,
- verbleibende Patchserie klein und befristet,
- jeder Patch besitzt Upstream-PR/Issue oder dokumentierten dauerhaften Grund,
- v0.20.5+ Upgrades laufen über automatisierte Acceptance Suite.

Rollback:

- letzte dünne Forkversion bleibt N−2 intern verfügbar.

---

## 12. SaaS Production Readiness

| Bereich | Heute | Mindestziel |
|---|---|---|
| Customer AuthN | fehlt im Hermespfad | OIDC/JWT am BFF |
| Tenant AuthZ | fehlt | objekt-/zeilenbezogen |
| Entitlements | nicht mit bounded routes verbunden | operation-/scope-basiert |
| Session Ownership | Hermes-intern | Product-owned |
| Memory Governance | nicht customerfähig | Tenant, TTL, Export, Delete |
| Rate Limits | fehlen | Tenant/User/Operation |
| Idempotenz | v1 ignoriert Key | durable dedupe |
| Audit | Korrelation + Logs | unveränderliches Operation-Audit |
| Provider Policy | Runtimeconfig | task-/datenklassengebunden |
| Secret Isolation | Shared Bearer | short-lived target-bound identity |
| Execution Isolation | allgemeine Runtime | ephemer pro Job |
| Egress | nicht universell | Netzwerkpolicy |
| Supply Chain | unsigned Release | mirrored, scanned, signed |
| Rollback | manuell/branch-orientiert | digest + State-Snapshot |

**`UPSTREAM_PRODUCTION_FIT = PARTIAL`**

- Fit für internen single-tenant Betrieb hinter zusätzlichen Kontrollen.
- Nicht fit als unveränderter öffentlicher Multi-Tenant-SaaS-Agent.
- Customer SaaS wird erst durch die PowerUnits Product-/Capability-/Execution-Planes produktionsfähig.

---

## 13. Verbleibende Unsicherheiten

1. Live-Railway-Firewall, Network Egress und tatsächlich aktive Runtimekonfiguration wurden nicht geprüft.
2. Provider-DPA, Region, Retention und No-Training-Status sind nicht belegt.
3. Bitwarden-Vertrags-/Entitlementstatus ist unbekannt.
4. Kein produktionsnaher Penetrationstest für Prompt-Injection → Tool → Repo-B.
5. Kein Cross-Tenant-Test möglich, weil der aktuelle Pfad kein Tenantmodell besitzt.
6. Keine vollständige Golden-Suite zwischen lokalem v0.19-Fork und v0.20.5 ausgeführt.
7. Die 21 Merge-Konflikte messen syntaktische Konflikte; semantische Regressionsrisiken können darüber hinausgehen.
8. Repo-B-Shared-Bearer-Rotation, Exposure und Loghygiene wurden nicht live verifiziert.
9. Customer-Produktanforderungen für Consent, Retention, Export und Delete sind noch nicht spezifiziert.

Diese Unsicherheiten ändern das Split-Urteil nicht; sie sind Gates für die jeweilige Migrationsphase.

---

## 14. Evidence Appendix

### 14.1 Lokale Primärdateien Repo A

- `model_tools.py`
- `toolsets.py`
- `powerunits_telegram_overlays.py`
- `powerunits_bounded_profiles_v1.py`
- `powerunits_capability_tier.py`
- `gateway/run.py`
- `gateway/config.py`
- `docker/apply_powerunits_runtime_policy.py`
- `tools/powerunits_option_d_execute_tool.py`
- `tools/powerunits_timescale_read_tool.py`
- `tools/powerunits_repo_b_read_tool.py`
- `tools/registry.py`
- `ACCESS_MATRIX.md`
- `docs/powerunits_runtime_enforcement_v2.md`
- `docs/powerunits_hermes_integration_pattern_v1.md`
- `docs/upstream_sync_log.md`

### 14.2 Repo-B-Primärdateien am SHA `4128efac`

- `backend/main.py`
- `backend/routers/internal_hermes_bounded*.py`
- `backend/services/internal/hermes_bounded_*.py`
- `backend/services/data_ingestion/jobs/*`
- `backend/services/data_ingestion/common/pipeline_run.py`
- `backend/settings.py`
- `backend/services/hermes_internal_read_adapter.py`
- `docs/architecture/internal_hermes_bounded_operating_model_v1.md`
- `docs/architecture/analytical_product_architecture_v1.md`

### 14.3 Upstream-Primärquellen

- [Release v2026.8.19 / Hermes 0.20.5](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.19)
- [Commit fcbd1076](https://github.com/NousResearch/hermes-agent/commit/fcbd1076a93841fa88855acce810e342a5b78101)
- [LICENSE](https://github.com/NousResearch/hermes-agent/blob/fcbd1076a93841fa88855acce810e342a5b78101/LICENSE)
- [SECURITY.md](https://github.com/NousResearch/hermes-agent/blob/fcbd1076a93841fa88855acce810e342a5b78101/SECURITY.md)
- [Profiles](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/website/docs/user-guide/profiles.md)
- [API Server](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/website/docs/user-guide/features/api-server.md)
- [Desktop](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/website/docs/user-guide/desktop.md)
- [Bot Mode](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/website/docs/user-guide/bot-mode.md)
- [MCP](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/website/docs/user-guide/features/mcp.md)
- [Delegation](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/website/docs/user-guide/features/delegation.md)
- [Observability](https://github.com/NousResearch/hermes-agent/blob/v2026.8.19/docs/observability/README.md)
- [Docker Hub v2026.8.19](https://registry.hub.docker.com/v2/repositories/nousresearch/hermes-agent/tags/v2026.8.19)

### 14.4 Reproduzierbare Auditbefehle

```powershell
git merge-base c6e43b514eeaf6549b074073fa06b3c4e67e0384 fcbd1076a93841fa88855acce810e342a5b78101
git rev-list --left-right --count c6e43b514eeaf6549b074073fa06b3c4e67e0384...fcbd1076a93841fa88855acce810e342a5b78101
git cherry v2026.7.20 HEAD
git diff --numstat 3ef6bbd201263d354fd83ec55b3c306ded2eb72a...HEAD
git merge-tree --write-tree --messages refs/audit/local fcbd1076a93841fa88855acce810e342a5b78101
```

Der Merge-Tree-Befehl wurde in einem isolierten Clone ausgeführt, weil das aktuelle Upstreamobjekt nicht in Repo A lag. Der Clone wurde anschließend entfernt.

---

## 15. Terminal Summary

```text
HERMES_REASSESSMENT = PASS
FINAL_VERDICT = SPLIT_ARCHITECTURE
FORK_NECESSITY = PARTLY
GUARDRAIL_ASSESSMENT = MIXED
CONTROL_EQUIVALENCE = PARTIAL
UPSTREAM_PRODUCTION_FIT = PARTIAL
DESKTOP_INTERNAL_FIT = FIT_WITH_CONTROLS
BOT_MODE_ARCHITECTURAL_VALUE = HIGH
CUSTOMER_HERMES_UI = ABSENT_VERIFIED
MIGRATION_MAGNITUDE = SUBSTANTIAL
COMMERCIAL_USE_BLOCKER = NOT_VERIFIED

REPO_A_SHA = c6e43b514eeaf6549b074073fa06b3c4e67e0384
REPO_B_SHA = 4128efac044e1d310f351853634d20c1c77980fd
UPSTREAM_RELEASE = v2026.8.19 / hermes-agent 0.20.5
UPSTREAM_RELEASE_SHA = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_IMAGE_DIGEST = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09

LOCAL_ONLY_COMMITS = 220
LOCAL_ONLY_NON_MERGE_COMMITS = 146
LOCAL_ONLY_MEANINGFUL_PATCHES = 117
ALL_CHANGED_FILES = 275
POWERUNITS_SPECIFIC_FILES = 255
MATERIALLY_DIVERGED_FILES = 29
HIGH_CHURN_NON_DOC_TEST_FILES = 101
SECURITY_SPECIFIC_LOCAL_PATCHES = 8_FAMILIES
UPSTREAM_NOW_SUPERSEDES_LOCAL_PATCHES = 3_FAMILIES
PATCHES_STILL_WITHOUT_UPSTREAM_EQUIVALENT = 11_FAMILIES
UPSTREAM_CHANGED_FILES = 7382
PATH_OVERLAP = 44
MERGE_TREE_CONFLICT_FILES = 21

CURRENT_ARCHITECTURE_SCORE = 4.8/10
RECOMMENDED_ARCHITECTURE_SCORE = 8.1/10

ZERO_SUNK_COST_REBUILD_CURRENT_FORK = NO
VOLUNTARY_REWRITE = POWERUNITS_CAPABILITY_AND_BOUNDED_CLIENT_LAYER

NEXT_ACTION_1 = Freeze golden behavioral contracts for the effective first_safe surface
NEXT_ACTION_2 = Intake v0.20.5 by immutable digest into an isolated non-production environment
NEXT_ACTION_3 = Extract a read-only PowerUnits Capability Gateway
NEXT_ACTION_4 = Pilot Desktop/Bot Mode only for internal read-only profiles
NEXT_ACTION_5 = Build Customer Copilot as a Repo-B-native product boundary
```

