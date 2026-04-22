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
   - Allowlist funktioniert (`config/powerunits_repo_read_allowlist.json`)
   - Alias-basierte Reads funktionieren fail-closed
4. **Workspace**
   - `/opt/data/hermes_workspace` nutzbar
   - `analysis/notes/drafts/exports` vorhanden
   - save/read roundtrip funktioniert
5. **Telegram smoke**
   - read -> summarize -> save -> read back
   - keine Clarify-Loop/Tool-Narrationsregression

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
