# Powerunits Docs Allowlist Integration v1

## Before editing restatement

Hermes laeuft im first-safe Telegram-Modus stabil (Connectivity, Runtime, OpenAI-first).

Der naechste Schritt ist **nuetzlicher Powerunits-Kontext**, beginnend mit **read-only, strikt allowgelisteter Dokumentation** — ohne DB, ohne Repo-weites Browsen, ohne Capability-Erweiterung jenseits kontrollierten Doc-Lesens.

---

## Part A — Canonical integration shape (kleinster sicherer Pfad)

### Source of truth

- **Kanonisch** ist die **explizite Allowliste** (Versionskontrolle im Powerunits-Monorepo oder im Hermes-Fork als gebündeltes Artefakt), nicht „das ganze Repo“.
- Hermes sieht **nur** Dateien, die in dieser Liste stehen und physisch im **Docs-Staging-Verzeichnis** im Container vorliegen.

### Fail-closed Lesepfad

1. **Staging-Verzeichnis** (v3.6 kanonisch im Image): `/opt/hermes/docker/powerunits_docs/` (read-only Image-Layer). Alternativ historisch: separates `/opt/hermes/powerunits_docs/` nur wenn explizit per Volume nachgezogen.
2. **Manifest**: `docker/powerunits_docs/MANIFEST.json` mit erlaubten **Keys** (flache Staging-Namen), je Eintrag **SHA256**, `bytes`, `source_relative` (nur Metadaten/Audit, keine Laufzeit-Pfadwahl durch das Modell).
3. **Lese-API** (spaeter zu implementieren): ein einziges internes Hilfsmittel (Tool oder feste Prompt-Kontext-Injektion), das:
   - nur Keys aus dem Manifest akzeptiert,
   - **keine** freien Pfadstrings vom Modell annimmt,
   - `..`, absolute Pfade, Symlinks und alles ausserhalb des Staging-Roots **hart ablehnt**,
   - `.env`, Secrets, Keys, Deploy-Artefakte, `backend/`, `scripts/` mit Credentials, usw. **niemals** im Staging ablegt.

### Explizit ausgeschlossen

- `.env*`, `auth.json`, Railway/Vercel-Konfiguration, TLS/Keys, Connection-Strings
- breites Repo-Scannen (`rg`/`find` über Monorepo)
- Schreib- oder Patch-Pfade
- „Lies irgendeine Datei unter `/opt/data`“

### Auditing

- Jede Aenderung der Allowliste = **PR im Monorepo** (oder im Fork, wenn Bundle dort gepflegt wird) + Rebuild/Redeploy mit neuer Manifest-Version.
- CI kann `MANIFEST.yaml` gegen die kopierte Dateiliste pruefen (Mismatch → Build fail).

---

## Part B — Initial allowlist proposal (v1, klein)

Alle Pfade beziehen sich auf das **Powerunits-Monorepo** `EU-PP-Database` (Root-relativ). Beim Bundling werden sie unter flachen oder spiegelnden Namen ins Staging kopiert — **die Manifest-Eintraege sind die erlaubten Lesenamen**.

Optional pro Eintrag (Allowliste `scripts/powerunits_docs_allowlist.json`): `doc_class`, `freshness_tier`, `summary` — landen im gebundelten `MANIFEST.json` und im Reader; siehe `docs/powerunits_docs_freshness_v1.md`.

| Staging-Key (Beispiel) | Quelle (Monorepo) | Zweck |
|------------------------|-------------------|--------|
| `implementation_state.md` | `docs/implementation_state.md` | Plattform-Istzustand |
| `roadmap.md` | `docs/roadmap.md` | Uebergeordnete Phasen/Roadmap |
| `target_architecture_v0.4.md` | `docs/target_architecture_v0.4.md` | Zielarchitektur |
| `runbook.md` | `docs/runbook.md` | Operator-Runbook |
| `agent_repo_overview.md` | `docs/agent_repo_overview.md` | Repo-Orientierung fuer Agents |
| `README.md` | `docs/README.md` | Doc-Landkarte (Lesen, nicht schreiben) |
| `merit_order_roadmap_v1.md` | `docs/architecture/merit_order_roadmap_v1.md` | Merit-Order-Roadmap |
| `merit_order_model_readiness_gap_v1.md` | `docs/architecture/merit_order_model_readiness_gap_v1.md` | Modell-/Daten-Readiness |
| `ai_content_layer.md` | `docs/architecture/ai_content_layer.md` | AI-Content-Schicht |
| `f_track_country_weather_spatial_roadmap.md` | `docs/architecture/f_track_country_weather_spatial_roadmap.md` | F-Track / raeumliche Wetter-Roadmap |
| `ex_ante_ftrack_monthly_gaps.md` | `docs/operations/ex_ante_ftrack_monthly_gaps.md` | Ex-ante / F-Track Betrieb |

**Bewusst klein gehalten:** keine `backend/`, keine `artifacts/`, keine `AGENTS.md` (betriebliche Agent-Regeln koennen spaeter optional und separat entschieden werden), keine kompletten `docs/adr/`-Trees in v1.

---

## Part C — Integration method (empfohlen)

### Empfehlung: **Build-Zeit-Bundle + Manifest** (explizit, fail-closed)

1. Im **Hermes-Fork** ist umgesetzt: `scripts/bundle_powerunits_docs.py` mit Allowliste `scripts/powerunits_docs_allowlist.json`, Ausgabe nach `docker/powerunits_docs/` inkl. `MANIFEST.json` (SHA256 pro Datei), Abbruch bei fehlender Quelle (**fail-closed**). Details: `docs/powerunits_docs_read_surface_v1.md`.
2. **Dockerfile**: vollstaendiges `COPY . .` — Bundle liegt unter `/opt/hermes/docker/powerunits_docs/` (`.dockerignore` negiert diesen Tree fuer `*.md`).
3. Optional: Railway **kein** extra Secret; nur Image-Rebuild bei Doc-Updates.

### Alternativen (kurz)

| Methode | Wann sinnvoll |
|---------|----------------|
| Read-only Volume mit vorbereitetem Tree | Schnelle Operator-Iteration ohne Rebuild; Audit ueber externes Bundle-Repo |
| Submodule Monorepo im Hermes-Fork | Teurer Pflegeaufwand; nicht empfohlen fuer v1 |

---

## Part D — Operator flow

### Produktion des Doc-Subsets

1. Monorepo auf gewuenschten **Tag/Branch** auschecken.
2. Bundle-Skript ausfuehren → erzeugt/aktualisiert `docker/powerunits_docs/` + `MANIFEST.json` (siehe `docs/powerunits_docs_read_surface_v1.md`).
3. **PR** mit Diff der Allowliste und der geaenderten gebundelten Dateien (oder nur Manifest, wenn Binaer gefiltert).
4. **Image bauen** und auf Railway deployen.

### Refresh

- Jede inhaltliche Aenderung relevanter Docs im Monorepo: Bundle neu erzeugen, Version bump, **Redeploy**.
- Kein Hot-Reload von Produktionsdocs ohne Rebuild (verhindert Drift und „vergessene“ Manifest-Updates).

### Verifikation (Hermes sieht nur Allowlist)

1. Im Container (Railway Shell / lokal): `ls /opt/hermes/docker/powerunits_docs` — nur erwartete Dateien + `MANIFEST.json`.
2. Sicherstellen, dass **kein** Tool Zugriff auf `/opt/hermes` ausserhalb dieses Trees erlaubt (spaeter: Read-Tool nur mit Manifest-Key).
3. Negativtest: Anfrage nach nicht-manifestierter Datei → klare Ablehnung.

---

## Part E — One exact next recommendation (v3.5)

`Build the Powerunits docs-only read surface next` — umgesetzt in v3.6; siehe unten.

---

## Docs read surface linkage (v3.6)

- `docs/powerunits_docs_read_surface_v1.md`

## Docs reader linkage (v3.7)

- `docs/powerunits_docs_reader_v1.md`

---

## Verknuepfungen

- First-safe Uebersicht: `docs/powerunits_first_safe_telegram_review_v1.md`
- Runtime-Policy: `docs/powerunits_runtime_policy_v1.md`
- Railway-Bootstrap: `docs/powerunits_railway_bootstrap_v1.md`
