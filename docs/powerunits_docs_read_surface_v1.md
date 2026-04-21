# Powerunits Docs-Only Read Surface v1

## Before editing restatement

Hermes ist in Telegram und Runtime **betriebsfaehig** (first-safe, OpenAI-first).

Der naechste Schritt ist eine **sichere, docs-only Powerunits-Kontextschicht**: gebündelte, allowgelistete Markdown-Dateien mit **manifestgesteuertem** Lesecontract — **keine** DB, **kein** breites Repo- oder Code-Browsen.

---

## Part A — Build-time bundle mechanism (implementiert)

### Artefakte im Hermes-Fork

| Pfad | Rolle |
|------|--------|
| `scripts/powerunits_docs_allowlist.json` | Kanonische Allowliste: `key` → `source_relative` (Monorepo-Root relativ) |
| `scripts/bundle_powerunits_docs.py` | Kopiert jede Quelle ins Bundle, bricht bei fehlender Datei ab (**fail-closed**) |
| `docker/powerunits_docs/*.md` | Gestufte Kopien (flache Keys, nur `.md`) |
| `docker/powerunits_docs/MANIFEST.json` | Stabile Keys, `source_relative`, `sha256`, `bytes`, optionale `doc_class` / `freshness_tier` / `summary`, Bundle-Provenance (`bundle_version` 2); siehe `docs/powerunits_docs_freshness_v1.md` |

### Skriptverhalten

1. Laedt die Allowliste (JSON).
2. Prueft jeden `key` gegen ein strenges Muster (kein `/`, kein `..`, Endung `.md`).
3. Prueft `source_relative` auf verbotene `..`-Segmente und absolute Pfade.
4. Liest aus `--source-root` / `POWERUNITS_REPO_ROOT`; Zielpfad muss **unter** dem Monorepo-Root liegen (`resolve` + `relative_to`).
5. Kopiert nach `docker/powerunits_docs/<key>`; fehlende Quelle → **Exit 1**.
6. Schreibt `MANIFEST.json` mit sortierten `entries`.

### Docker-Image

`Dockerfile` kopiert das gesamte Repo nach `/opt/hermes`. Das Bundle liegt im Image unter:

`/opt/hermes/docker/powerunits_docs/`

`.dockerignore` schliesst global `*.md` aus; fuer dieses Bundle gilt eine **explizite Negation** von `docker/powerunits_docs/**`, damit die gestuften Dateien im Build-Context ankommen.

---

## Part B — No broad path access

Das Bundle-Skript ist **nur Build-Zeit**; es liest ausschliesslich konfigurierte `source_relative`-Pfade unter einem vom Operator gesetzten Monorepo-Root.

Die **Laufzeit-Oberflaeche** (v3.7) ist das Tool **`read_powerunits_doc`** (`docs/powerunits_docs_reader_v1.md`). Es erfuellt:

- **keine** vom Modell gelieferten Pfadstrings,
- nur **Manifest-Keys**,
- Dateien **nur** unter dem Bundle-Root (Pfad-Escape abgelehnt),
- kein Zugriff auf `/opt/data`, Host-Repo oder Monorepo.

---

## Part C — Read surface contract (implementiert in v3.7)

1. **Lookup** ausschliesslich per **Manifest-Key** (z. B. `implementation_state.md`), nicht per Dateisystempfad.
2. **Read-only**: kein Schreiben, kein Umbenennen, kein Loeschen.
3. **Unbekannter Key** oder fehlender Manifest-Eintrag → **fester Fehler** (JSON mit `error_code`).
4. **Ausgabe begrenzt** (`max_output_chars`, Default 16000, Cap 32000) fuer Telegram-taugliche Antworten.

Manifest (`MANIFEST.json`) ist die **einzige** authoritative Key-Liste fuer erlaubte Dokumente im Bundle.

---

## Part D — Operator flow

### Erwarteter Powerunits-Quellpfad

Lokaler Clone des Monorepos **EU-PP-Database** (beliebiger Pfad), z. B.:

- `W:\Workbench\EU-PP-Database`
- oder `~/src/EU-PP-Database`

Der Pfad wird **nicht** im Railway-Image mitgeliefert; er wird nur beim Bundling auf der Maschine oder in CI benoetigt.

### Bundle erzeugen

Im **hermes-agent**-Repo:

```powershell
python scripts/bundle_powerunits_docs.py --source-root "W:\Workbench\EU-PP-Database"
```

Alternativ:

```powershell
$env:POWERUNITS_REPO_ROOT = "W:\Workbench\EU-PP-Database"
python scripts/bundle_powerunits_docs.py
```

### Refresh

1. Monorepo auf gewuenschten Commit/Branch aktualisieren.
2. Skript erneut ausfuehren (ueberschreibt gestufte Dateien + `MANIFEST.json`).
3. Aenderungen committen, Image **neu bauen**, Railway **redeploy**.

### Verifikation

- Lokal: `Get-ChildItem docker\powerunits_docs` — 11 `.md` + `MANIFEST.json`.
- `MANIFEST.json`: `entries`-Laenge muss Allowlisten-Laenge entsprechen; `sha256` optional gegen CI-Check.
- Im Container (nach Deploy): `ls /opt/hermes/docker/powerunits_docs` — gleiche Dateimenge.
- Sicherstellen, dass `.dockerignore` die Negation fuer `docker/powerunits_docs/` noch enthaelt.

---

## Part E — Railway implications

- **Keine** zusaetzlichen Railway-Umgebungsvariablen fuer docs-only v1 erforderlich.
- Das Bundle ist **im Image**; Aktualisierung = **Rebuild + Deploy**, kein Runtime-Download aus dem Monorepo.

---

## Part F — One exact next recommendation (v3.6)

`Add a manifest-keyed docs reader for Hermes next` — umgesetzt in v3.7; siehe unten.

---

## Docs reader linkage (v3.7)

- `docs/powerunits_docs_reader_v1.md`

---

## Verknuepfungen

- Allowlist-Design (v3.5): `docs/powerunits_docs_allowlist_integration_v1.md`
- Railway-Bootstrap: `docs/powerunits_railway_bootstrap_v1.md`
- First-safe Telegram: `docs/powerunits_first_safe_telegram_review_v1.md`
