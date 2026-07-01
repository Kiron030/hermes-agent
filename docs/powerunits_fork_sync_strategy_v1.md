# Powerunits Hermes Fork Sync Strategy v1

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
