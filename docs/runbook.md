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

## Runtime diagnostics

Bei fehlendem/ungueltigem Bundle wird eine Warnung geloggt, sinngemaess:

- Docs-Tool deaktiviert, Bundle-Verzeichnis fehlt
- oder Manifest/Entry inkonsistent

Damit ist fuer Operatoren sofort sichtbar: Deploy war erfolgreich, aber Docs-Reader ist nicht verfuegbar, weil das interne Bundle-Artefakt fehlt.
