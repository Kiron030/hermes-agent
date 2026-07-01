# Powerunits Hermes Fork Sync Strategy v1

> **Vor Beginn eines neuen Sync-Schritts ZUERST
> [`docs/powerunits_fork_sync_preflight_checklist.md`](./powerunits_fork_sync_preflight_checklist.md)
> lesen.** Kompakte, actionable Checkliste aus den v0.12.0-/v0.13.0-Sync-
> Vorfällen (Dependency-Sync-Falle, Symbol-/Intra-Funktions-Diff-Check,
> ProviderProfile-Falle, bekannte Windows-Testartefakte, Ablaufreihenfolge)
> — spart wiederholtes Neu-Entdecken derselben Fehler.

## 1) Current repo relationship

- **upstream**: `NousResearch/hermes-agent`
- **origin**: `Kiron030/hermes-agent`
- **aktive Powerunits-Branch**: `powerunits-internal-setup`

Ziel: Upstream-Verbesserungen aufnehmen, ohne die Powerunits-first-safe Sicherheitsgrenzen zu verlieren.

---

## 2) Safe upstream update workflow

### Maintenance policy (default)

- Standardquelle fuer Syncs ist **upstream Release/Tag**, nicht jeder neue Commit auf `upstream/main`.
- `upstream/main` wird nur selektiv verwendet (siehe unten), wenn ein konkreter Fix/Blocker frueh benoetigt wird.
- Ziel ist ein **kleiner, reviewbarer Delta-Umfang** pro Sync.

Wann `upstream/main` trotzdem ok ist:

- kritischer Fix ist noch nicht getaggt, aber fuer Stabilitaet/Sicherheit notwendig
- klar abgegrenzter Scope, der in einer Integrationsbranch pruefbar bleibt
- ausreichende Zeit fuer Konfliktloesung + Post-sync-Validierung ist eingeplant

Empfohlener Ablauf:

1. Fork lokal aktualisieren:
   - `git fetch upstream`
   - `git fetch origin`
2. Neue Integrationsbranch vom aktuellen Powerunits-Stand:
   - `git checkout powerunits-internal-setup`
   - `git pull origin powerunits-internal-setup`
   - `git checkout -b integration/upstream-sync-<date>`
3. Upstream einspielen:
   - `git merge upstream/main`
4. Konflikte gezielt in Powerunits-Schicht loesen (siehe Abschnitt 3).
5. Tests/Smoke-Checks laufen lassen (siehe Abschnitt 4).
6. Branch pushen und PR nach `powerunits-internal-setup`.

Hinweis: Keine direkten Pushes auf produktionsnahe Hauptbranches.

#### Supply-chain caution (praktisch, nicht alarmistisch)

Oeffentliche Upstream-Repos werden **nicht** pauschal als malizioes angenommen. Trotzdem erhoehen grosse, unauditierte Syncs das Regression- und Review-Risiko deutlich. Deshalb fuer Powerunits: lieber kleinere, nachvollziehbare, selektive Updates statt "immer alles sofort".

### Sync Quickstart (ca. 10 Befehle)

Im Repo-Root ausfuehren, **nicht** direkt auf `powerunits-internal-setup` mergen:

1. `git remote -v`
2. `git fetch upstream`
3. `git fetch origin`
4. `git checkout powerunits-internal-setup`
5. `git pull origin powerunits-internal-setup`
6. `git checkout -b integration/upstream-sync-YYYYMMDD`
7. `git merge upstream/main`
8. `git status`
9. `git push -u origin integration/upstream-sync-YYYYMMDD`
10. PR von `integration/upstream-sync-YYYYMMDD` nach `powerunits-internal-setup` erstellen und erst nach Validierung mergen (siehe Abschnitt 4).

#### Common mistakes to avoid

- Nicht direkt in `powerunits-internal-setup` mergen.
- Konflikte nicht pauschal mit "accept incoming" loesen; Powerunits-Guardrails pruefen.
- Keine Freigabe ohne Post-sync Validation (Abschnitt 4).

---

## 3) Likely conflict hotspots (Powerunits layer)

Konflikte sind am wahrscheinlichsten in Dateien, die die Runtime-Surface und Operator-Flows anpassen:

- `docker/entrypoint.sh`
- `docker/apply_powerunits_runtime_policy.py`
- `gateway/run.py`
- `model_tools.py`
- `toolsets.py`
- `tools/powerunits_*` (eigene Tooling-Layer)
- `docker/SOUL.md`
- Powerunits-Doku unter `docs/powerunits_*.md`
- Deploy-spezifische Dateien: `.dockerignore`, `.railwayignore`, ggf. `.gitattributes`, `Dockerfile`

Merge-Prinzip:

- Upstream-Bugfixes/Infra-Verbesserungen bevorzugt uebernehmen.
- Powerunits-spezifische Guardrails bewusst erhalten.
- Bei Unsicherheit: fail-closed Verhalten behalten.

---

## 4) Post-sync validation checklist

Mindestens diese Validierung nach jedem Upstream-Sync:

1. **Build/Startup**
   - Docker Build erfolgreich
   - Entrypoint startet ohne Permission-/Line-Ending-Probleme
2. **first-safe policy**
   - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` greift
   - Telegram-Toolset bleibt auf erlaubte Powerunits-Toolsets begrenzt
3. **GitHub read surfaces**
   - Allowlist funktioniert (`config/powerunits_github_knowledge.json`)
   - Alias-basierte Reads funktionieren fail-closed
4. **Workspace**
   - `/opt/data/hermes_workspace` nutzbar
   - `analysis/notes/drafts/exports` vorhanden
   - save/read roundtrip funktioniert
5. **Telegram smoke**
   - read -> summarize -> save -> read back
   - keine Clarify-Loop/Tool-Narrationsregression
6. **Symbol-Diff-Check auf Hotspot-Dateien (PFLICHT, seit v0.13-Sync-Vorfall 2026-07-01)**
   - Ein "clean auto-merge" (kein `<<<<<<<`-Marker) ist bei stark refaktorierten Dateien **kein** Beweis für Vollständigkeit. Git kann bei zeilenbasierten Diffs auf beiden Seiten geänderte Funktionen ohne Konfliktmarker einseitig "gewinnen" lassen und dabei Upstream-Funktionalität stillschweigend verwerfen.
   - Für jede Datei aus Abschnitt 3 (Hotspots), die im Merge angefasst wurde:
     1. `git show <merge-base>:<file>` (Basis), `git show <upstream-tag>:<file>` (Upstream-Ziel), Datei im Merge-Ergebnis — je in eine Datei umleiten (kein direktes Pipe von `git show` in andere Befehle verwenden, encoding-anfällig).
     2. Funktions-/Symbolliste extrahieren (z. B. `^def |^class |^    def `) und die drei Listen vergleichen.
     3. Jede Funktion/Signatur, die in Upstream-Ziel existiert, aber im Merge-Ergebnis fehlt oder von der Basis-Version übernommen wurde (statt der Upstream-Version), ist ein Kandidat für stillen Verlust — muss geprüft und ggf. nachgetragen werden.
     4. Zeilenzahl grob vergleichen (Basis + Upstream-Delta ≈ erwartete Ergebniszeilenzahl); große Abweichung nach unten ist ein Warnsignal.
   - Bei Verdacht auf stillen Verlust: **nicht** einfach die Konfliktmarker "accept theirs/ours" lösen. Stattdessen Datei aus der Upstream-Zielversion neu aufbauen und die Fork-spezifischen Anpassungen (ermittelt via `git diff <merge-base> <fork-branch> -- <file>`) gezielt nachziehen.
7. **Intra-Funktions-Diff-Check bei Methoden, die auf beiden Seiten strukturell umgebaut wurden (PFLICHT, seit v0.13-Sync chat_completions.py-Vorfall 2026-07-01)**
   - Der reine Symbol-/Funktionslisten-Vergleich (Punkt 6) prueft nur, ob eine Funktion/Methode **existiert** — nicht, ob ihr **Koerper** noch alle noetigen Zweige enthaelt. Wenn Upstream und Fork **dieselbe** Methode unabhaengig voneinander stark refaktorieren (z. B. weil Upstream eine neue Architektur einfuehrt, die alte Zweige "ueberfluessig" macht), kann Git Teile des Methodenkoerpers **ohne Konfliktmarker** rein nach der Upstream-Seite aufloesen — obwohl die Fork-spezifischen Zweige dort weiterhin gebraucht werden (z. B. weil noch nicht alle Call-Sites auf die neue Architektur migriert sind).
   - Konkret beobachtet: `agent/transports/chat_completions.py::build_kwargs()` verlor beim v0.13-Merge (upstream fuehrte einen neuen `ProviderProfile`-Pfad ein und vereinfachte den alten "Legacy"-Pfad radikal) mehrere Fork-spezifische Zweige **ersatzlos**, obwohl `build_kwargs` als Symbol unveraendert vorhanden blieb: Qwen-Message-Preprocessing (`qwen_prepare_fn`/`qwen_prepare_inplace_fn`, `is_qwen`-Definition), die komplette `Temperature`-Behandlung (`fixed_temperature`/`omit_temperature`), Qwen-`session_metadata` -> `api_kwargs["metadata"]`, sowie drei `max_tokens`-Sonderfaelle (`is_nvidia_nim` -> 16384, `is_qwen` -> 65536, `is_kimi` -> 32000). Erst ein fehlgeschlagener Testlauf (`NameError: name 'is_qwen' is not defined`) deckte das erste Symptom auf; eine vollstaendige Line-by-Line-Rekonstruktion gegen den Pre-Merge-Stand von `HEAD` war noetig, um alle stillschweigend entfernten Zweige zu finden.
   - Regel: Wenn eine Methode/Funktion aus den Hotspot-Dateien **beidseitig substanziell umgebaut** wurde (nicht nur additiv erweitert), reicht der Symbol-Diff nicht. Zusaetzlich noetig:
     1. Vollstaendigen Methodenkoerper aus `HEAD` (Pre-Merge Fork-Stand) extrahieren.
     2. Jede logische Verzweigung/jeden Parameter-Handling-Block (`if params.get(...)`, providerspezifische Sonderfaelle etc.) einzeln gegen das Merge-Ergebnis abgleichen.
     3. Bei jedem fehlenden Zweig pruefen, ob die neue (Upstream-)Architektur ihn tatsaechlich funktional ersetzt (z. B. ueber einen neuen Abstraktions-Layer wie `ProviderProfile`) — und ob **alle** relevanten Call-Sites im Fork bereits durch diesen neuen Layer abgedeckt sind. Ist das nicht der Fall (z. B. Call-Sites, die den neuen Layer bewusst umgehen — Summary-/Retry-Pfade, die kein `provider_profile` aufloesen), muss der alte Zweig als expliziter Fallback erhalten bleiben, inkl. Kommentar, der auf den neuen Layer und den Grund fuer den Fallback verweist.
   - Test-getriebene Absicherung ist hier der zuverlaessigste Fruehindikator: volle Testsuite fuer die betroffene Datei laufen lassen, **bevor** der Merge als geloest gilt, nicht erst am Ende des gesamten Sync-Schritts.

---

## 5) Recommended branch strategy

- **Stabiler Betriebszweig**: `powerunits-internal-setup`
- **Integrationszweige**:
  - `integration/upstream-sync-YYYYMMDD`
  - `feature/<small-scope-change>`
- **Optional Release-Cut** (spaeter): `release/powerunits-internal-vX`

Regel:

- Upstream-Syncs immer in dediziertem Integrationszweig.
- Erst nach Review + Smoke-Validierung in den stabilen Betriebszweig mergen.
- Integrationszweige bleiben auch bei Release-Tag-Syncs verpflichtend (kein Direkt-Merge in `powerunits-internal-setup`).
- Betreiberregel: **stabile, selektive, reviewbare Updates** vor "latest chasing".

Warum Integrationsbranch + Validierung zwingend bleiben:

- trennt Upstream-Import klar vom stabilen Deploy-Zweig
- macht Konflikte in Powerunits-Guardrails sichtbar und gezielt pruefbar
- reduziert Ausfallrisiko fuer Railway-/Telegram-first-safe Betrieb
- verhindert, dass ungetestete Provider-/Runtime-Aenderungen direkt in den Live-Pfad gehen

---

## 6) Powerunits-specific layers to protect during merges

Diese Bereiche sind sicherheits- und betriebskritisch und sollten bei Konflikten bewusst geschuetzt werden:

- First-safe Toolset-Begrenzung (keine ungewollte Surface-Erweiterung)
- Read-only GitHub-Docs-Reader mit Alias-Allowlist
- Bounded Workspace-Schreibpfad unter `/opt/data/hermes_workspace`
- Token-Trennung (`POWERUNITS_GITHUB_TOKEN_READ`, kein Write-Pfad)
- Railway-Deploy-Hardening (Entrypoint Permissions, CRLF/LF Robustheit)
- Dokumentierte fail-closed Betriebsregeln in Powerunits-Doku

Kurz: Upstream modernisieren, Powerunits-Grenzen bewahren.

---

## 7) Operator sync helper script

Fuer einen wiederholbaren Safe-Flow gibt es:

- Script: `scripts/sync_upstream_powerunits.ps1`
- Config: `config/powerunits_fork_sync_config.json`

Beispiel:

- `pwsh ./scripts/sync_upstream_powerunits.ps1`
- `pwsh ./scripts/sync_upstream_powerunits.ps1 -DryRun`
- Release/Tag-first (empfohlen): `pwsh ./scripts/sync_upstream_powerunits.ps1 -UpstreamRef v0.10.0 -ConservativeMode`
- Optional mit explizitem Datum: `pwsh ./scripts/sync_upstream_powerunits.ps1 -DateStamp 20260421`

Was das Script macht:

1. prueft sauberen Working Tree
2. prueft erforderliche Remotes
3. fetched `upstream` (inkl. Tags) und `origin`
4. wechselt auf stabilen Branch und aktualisiert ihn
5. erstellt Integrationsbranch `integration/upstream-sync-YYYYMMDD`
6. merged bevorzugt den angegebenen Release/Tag-Ref (`-UpstreamRef`), sonst Config-Default
7. stoppt bei Konflikten (kein Auto-Resolve)
8. pusht Integrationsbranch zu `origin`
9. gibt Review-/Validierungs-Reminder aus
10. meldet sensible Diff-Pfade (z. B. `.github/workflows/*`, `hermes_cli/setup.py`, Install-Skripte)
11. mit `-ConservativeMode`: markiert Workflow-/Supply-Chain-sensitive Dateien explizit als "defer for later review"

Was das Script **nicht** macht (absichtlich):

- kein Auto-Merge nach `powerunits-internal-setup`
- kein Auto-Merge nach `main`
- kein Auto-Deploy
- kein automatisches Konflikt-Resolving

---

## 8) Lessons learned (first real sync)

Technisch:

- Merge kann formal "resolved" sein, obwohl Marker-Reste im File bleiben; daher nach Konfliktloesung immer Marker-Scan (`<<<<<<<`, `=======`, `>>>>>>>`) + Syntax-Check auf kritische Runtime-Dateien.
- Workflow-Diffs unter `.github/workflows/` und Supply-Chain-sensitive Pfade (z. B. `hermes_cli/setup.py`) brauchen explizite Sichtpruefung, auch wenn kein akuter Fehler sichtbar ist.
- Tag-first plus kleiner Scope reduziert Konfliktflaeche und vereinfacht Root-Cause-Analyse bei Runtime-Breaks.

### v0.13-Sync-Vorfall (2026-07-01): stiller Funktionsverlust ohne Konfliktmarker

Beim Versuch, `v2026.5.7` (v0.13.0) nach `integration/hermes-runtime-v0.13-bump` zu mergen, meldete Git nur 5 echte Konflikte (`AGENTS.md`, `agent/transports/chat_completions.py`, `gateway/config.py`, `model_tools.py` x2, `toolsets.py`). Eine Symbol-Diff-Pruefung (siehe Abschnitt 4, Punkt 6 — neu eingefuehrt als direkte Konsequenz) zeigte aber: **`model_tools.py` verlor beim Merge stillschweigend vier Upstream-Funktionen** (`_clear_tool_defs_cache`, `_compute_tool_definitions`-Refactor, `_schema_allows_null`, `_coerce_json`) sowie einen Bugfix fuer `disabled_toolsets`-Handling (Upstream-Issue #17309: `elif disabled_toolsets` -> `if disabled_toolsets` als unbedingter Subtraktions-Schritt), **ohne dass Git dafuer einen Konfliktmarker gesetzt hat**. Zeilenzahl-Check haette es fruehzeitig gezeigt: Basis (Upstream v0.12.0) 811 Zeilen, Merge-Ergebnis nur 670 — deutlich zu wenig fuer eine Datei, die eigentlich Basis + Upstream-Delta + Fork-Delta enthalten sollte.

Zusaetzlicher Befund: Der `disabled_toolsets`-Bug existierte bereits **vor** diesem Sync-Versuch im Fork-Stand (`elif disabled_toolsets:` statt `if disabled_toolsets:` in `get_tool_definitions()`) — vermutlich bereits beim v0.12.0-Merge stillschweigend verloren gegangen, ohne dass es bis jetzt aufgefallen ist. Sicherheitsrelevanz: `run_agent.py` ruft `get_tool_definitions(enabled_toolsets=..., disabled_toolsets=...)` mit beiden Parametern gleichzeitig auf; mit der `elif`-Logik wird `disabled_toolsets` ignoriert, sobald `enabled_toolsets` gesetzt ist. Reale Exposure zum Fundzeitpunkt: gering, da der Powerunits-Gateway-Pfad (`platform_toolsets`) ausschliesslich mit `enabled_toolsets`-Allowlisting arbeitet und `disabled_toolsets` im Live-Pfad nicht gesetzt wird — aber ein latenter Defekt, der bei zukuenftiger Nutzung von `agent.disabled_toolsets` in `config.yaml` als zusaetzliche Absicherung schweigend nicht greifen wuerde.

**Konsequenz fuer den Prozess:** "Kein Konfliktmarker" != "sicher gemergt" bei Dateien, die auf beiden Seiten (Upstream und Fork) substanziell refaktoriert wurden. Ab sofort verpflichtend: Symbol-Diff-Check (Abschnitt 4.6) fuer alle Hotspot-Dateien, bevor ein Merge als "konfliktfrei geloest" gilt — unabhaengig davon, ob Git Konfliktmarker gesetzt hat oder nicht.

### v0.13-Sync-Vorfall Teil 2 (2026-07-01): stiller Zweig-Verlust *innerhalb* einer unveraendert vorhandenen Methode

Direkt im Anschluss an obigen Vorfall, beim Aufloesen des (diesmal echten, mit Konfliktmarkern versehenen) Konflikts in `agent/transports/chat_completions.py`: Upstream v0.13.0 fuehrte einen komplett neuen `ProviderProfile`-Architektur-Layer ein (`providers/` Package, `_build_kwargs_from_profile()`), der die Provider-Sonderfaelle (Nous, Qwen, Ollama, Kimi, NVIDIA...) aus der alten `build_kwargs()`-Methode in profilspezifische Objekte auslagert. `run_agent.py` versucht seit v0.13 zuerst `get_provider_profile(self.provider)` und delegiert bei Treffer vollstaendig dorthin; nur bei unbekanntem Provider (oder bei Call-Sites, die diesen Lookup gar nicht durchfuehren — z. B. die Retry-/Summary-Pfade `_tsum.build_kwargs()` / `_tretry.build_kwargs()` in `run_agent.py`) wird der alte "Legacy"-Zweig von `build_kwargs()` erreicht.

Der Konflikt selbst betraf nur einen kleinen Hunk (die `extra_body["reasoning"]`-Zuweisung). Die Entscheidung, dort die volle Fork-Logik (Nous-Sonderfall, Ollama-Guard) zu behalten statt Upstreams Ein-Zeiler zu uebernehmen, war richtig — aber ein direkt daneben liegender, **nicht als Konflikt markierter** Teil derselben Methode (Qwen-Preprocessing, Temperature-Handling, Qwen-Metadata, `max_tokens`-Sonderfaelle fuer NVIDIA/Qwen/Kimi) wurde von Git klammheimlich komplett durch Upstreams vereinfachte Version ersetzt, weil Upstream diese Zeilen ebenfalls entfernt hatte und der umgebende Kontext auf beiden Seiten weit genug auseinanderlief, dass kein Konfliktmarker gesetzt wurde. Erst der volle Testlauf von `tests/agent/transports/` deckte es auf (`NameError: name 'is_qwen' is not defined`, danach 30 weitere Folgefehler).

**Konsequenz fuer den Prozess:** Abschnitt 4, Punkt 7 (Intra-Funktions-Diff-Check) wurde direkt als Ergebnis dieses Vorfalls eingefuehrt. Zusaetzliche Lehre: nach Aufloesen *jedes* Merge-Konflikts in einer Datei mit stark umgebauten Methoden sofort die volle Testsuite fuer diese Datei laufen lassen — nicht erst am Ende, wenn alle vier/fuenf Konfliktdateien geloest sind. Ausserdem waehrend derselben Untersuchung entdeckt (unabhaengig vom Merge, aber durch die tiefe Diff-Analyse aufgedeckt): `toolsets.py`'s `hermes-discord`-Eintrag referenzierte den nicht-existenten Tool-Namen `discord_server` statt der tatsaechlich in `tools/discord_tool.py` registrierten Namen `discord`/`discord_admin` — vermutlich ein Ueberbleibsel eines nie abgeschlossenen internen Umbenennungsversuchs. Dieselbe Inkonsistenz fand sich auch in `model_tools.py`s dynamischer Schema-Rebuild-Logik fuer Discord (toter `if "discord_server" in available_tool_names:`-Zweig, der nie griff). Beides wurde im Rahmen dieses Syncs korrigiert; reale Exposure war gering, da die Discord-Plattform bei Powerunits deaktiviert ist.

Operativ:

- Integrationsbranch als Quarantaene fuer Upstream-Import hat sich bewaehrt; stabile Branch blieb bis zur Verifikation unberuehrt.
- Telegram/Railway-Smoke muss als Gate vor Merge in `powerunits-internal-setup` gelten.
- Sensible Diffs sollten bei Bedarf in separaten Folge-PRs isoliert werden statt im grossen Sync-PR mitzulaufen.

Empfohlene Branch-Strategie (clean):

- **Immer**: `integration/upstream-sync-YYYYMMDD` fuer Upstream-Import.
- **Dann**:
  - `integration/upstream-sync-YYYYMMDD` -> PR nach `powerunits-internal-setup` (nur nach Validierung).
  - optionale Folgebranches fuer Deferred-Themen, z. B. `integration/upstream-workflow-review-*`.

Wann Sync-Helper/Doku-Aenderungen wohin gehoeren:

- **Auf Integrationsbranch**, wenn die Aenderung aus dem aktuellen Sync gelernt wurde oder direkt zur sicheren Abarbeitung dieses Syncs gehoert (z. B. sensitive-path Warnungen, Tag-Ref Verhalten, Marker-Checks).
- **Auf Stable branch**, wenn die Verbesserung bereits durch den laufenden Sync verifiziert wurde, keinen zusaetzlichen riskanten Scope oeffnet und als neuer Betriebsstandard fuer den naechsten Sync gelten soll.
- Praktische Regel: erst im Integrationskontext beweisen, dann mit dem Sync oder unmittelbar danach gezielt nach `powerunits-internal-setup` uebernehmen.
