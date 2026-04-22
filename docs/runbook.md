# Hermes Internal Runbook (Powerunits Docs Reader)

## Scope

Dieses Runbook beschreibt den **operativen Vertrag** fuer `read_powerunits_doc` im first-safe Powerunits-Betrieb.

- Keine Live-Monorepo-Lesezugriffe zur Runtime
- Keine DB-Integration
- Keine generischen File-Tools

Der Reader funktioniert ausschliesslich mit dem gebuendelten Deploy-Artefakt unter `docker/powerunits_docs/` plus `MANIFEST.json`.

## Public-safe vs internal artifact

- **Public-safe Repo-Code:** kann absichtlich ohne `docker/powerunits_docs/` ausgeliefert werden.
- **Interner Deploy mit Docs-Reader:** muss das private/bundled Docs-Artefakt enthalten.

Wenn das Artefakt fehlt, wird `read_powerunits_doc` fail-closed deaktiviert (Tool nicht exponiert).

## Deployment requirement (exact)

Fuer funktionierenden Docs-Reader muss das deployte Image enthalten:

1. `docker/powerunits_docs/MANIFEST.json`
2. alle in `MANIFEST.json` referenzierten Keys als Dateien unter `docker/powerunits_docs/`

Fehlt eines davon, deaktiviert `check_fn` den Reader.

## Recommended internal deployment pattern (current)

1. Monorepo-Checkout aktualisieren.
2. Im `hermes-agent`:
   - `python scripts/bundle_powerunits_docs.py --source-root "<EU-PP-Database path>"`
3. Validieren:
   - `docker/powerunits_docs/MANIFEST.json` existiert
   - alle Manifest-Keys existieren im Bundle-Verzeichnis
4. Erst danach Docker-Image bauen und nach Railway deployen.

### Railway local deploy from Windows (`railway up`)

Der Repo-`gitignore` schliesst `docker/powerunits_docs/` aus, damit gebuendelte interne Docs nicht versehentlich committet werden.
Fuer lokalen Railway-Deploy wird das ueber `.railwayignore` explizit wieder einbezogen.

Operator-Ablauf:

1. Bundle erzeugen (`scripts/bundle_powerunits_docs.py ...`).
2. Lokal pruefen: `docker/powerunits_docs/MANIFEST.json` + `.md` Dateien vorhanden.
3. `railway up` aus dem Repo-Root starten.

Wenn der Reader nach Deploy trotzdem fehlt, sind die ersten Checks:
- Deploy-Artefakt/Upload hat `docker/powerunits_docs/` nicht enthalten.
- Runtime-Warnung: "Powerunits docs tool disabled ..." (Bundle/Manifest fehlt oder inkonsistent).

## Runtime diagnostics

Bei fehlendem/ungueltigem Bundle wird eine Warnung geloggt, sinngemaess:

- Docs-Tool deaktiviert, Bundle-Verzeichnis fehlt
- oder Manifest/Entry inkonsistent

Damit ist fuer Operatoren sofort sichtbar: Deploy war erfolgreich, aber Docs-Reader ist nicht verfuegbar, weil das interne Bundle-Artefakt fehlt.

## Operator-managed GitHub read allowlist

Datei: `config/powerunits_repo_read_allowlist.json`

Schema pro Surface:

- `alias`
- `repo`
- `branch`
- `root_prefix`
- `allowed_extensions`
- `enabled`

### Surface hinzufuegen/entfernen

1. Eintrag in `surfaces` ergaenzen oder `enabled=false` setzen.
2. Deployen (kein Runtime-Write noetig).
3. Telegram testen mit `list_powerunits_roadmap_dir(alias=...)` und `read_powerunits_roadmap_file(alias=..., name=...)`.

Sicherheitsprinzip:

- Modell waehlt nur Alias.
- Repo/Branch/Root werden nie aus User-Input genommen.

## Railway workspace safe usage

Root: `/opt/data/hermes_workspace` mit nur:

- `analysis`
- `notes`
- `drafts`
- `exports`

Kein delete/rename/generische Pfadschreibrechte.

## Intentionally out of scope

- GitHub write (`POWERUNITS_GITHUB_TOKEN_WRITE`) bleibt ungenutzt.
- Keine PRs/Branch-Writes/Repo-Mutationen.
- Keine DB-Integration.
- Kein breites privates Repo-Browsing.

## Consolidated operator guide

Fuer den Gesamtueberblick (Ist-Zustand, Workflow, Grenzen, staged Roadmap):

- `docs/powerunits_operator_setup_and_roadmap_v1.md`
- `docs/powerunits_fork_sync_strategy_v1.md`

Hinweis zur Wartungspolitik: Upstream-Syncs bevorzugt release-/tag-basiert und weiterhin nur ueber Integrationsbranch + Validierung in den stabilen Powerunits-Zweig uebernehmen.

Praktisch: `scripts/sync_upstream_powerunits.ps1` unterstuetzt `-UpstreamRef <tag/ref>` und `-ConservativeMode`, inkl. Warnhinweisen fuer sensible Diff-Pfade (Workflows, Setup-/Install-Pfade).
