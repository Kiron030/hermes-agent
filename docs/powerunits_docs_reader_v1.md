# Powerunits Manifest-Keyed Docs Reader v1

## Before editing restatement

Hermes laeuft im **first-safe Telegram-Modus** stabil; das **Powerunits-Doku-Bundle** liegt unter `docker/powerunits_docs/` mit `MANIFEST.json`.

Der naechste Schritt ist ein **sicherer, manifest-keyed Reader** — **ohne** DB, **ohne** breites Repo-Browsen, **ohne** freie Dateipfade vom Modell.

---

## Part A — Reader contract (implementiert)

### Tool: `read_powerunits_doc`

- **Nur** Lesen aus dem gebündelten Verzeichnis (`docker/powerunits_docs/` relativ zur Hermes-Installation, im Container typisch `/opt/hermes/docker/powerunits_docs/`).
- **Keine** freien Pfadstrings: der einzige Selektor ist der **Manifest-Key** (flacher Dateiname, z. B. `implementation_state.md`).
- **Unbekannter Key** → JSON-Fehler mit `error_code: unknown_key_not_allowlisted`.
- **Key-Format** ungueltig (z. B. `..`, `/`) → `invalid_key_format`.
- **Datei fehlt** trotz Manifest → `missing_in_bundle`.
- **SHA256** weicht von `MANIFEST.json` ab → `integrity_failure` (Inhalt wird nicht zurueckgegeben).
- **Read-only**: kein Schreiben, kein Umbenennen.

### Ausgabe (action=read)

- UTF-8 Text mit `max_output_chars` (Default **16000**, hart begrenzt **32000**, Minimum **2000**).
- Bei Ueberlaenge: Abschneiden + klare Truncation-Markierung im Text.
- Rueckgabe als JSON-String mit Feldern u. a. `content`, `truncated`, `chars_returned`, `source_relative`, `sha256_verified`.

### Umgebung

- Optional: `HERMES_POWERUNITS_DOCS_BUNDLE` setzt den Bundle-Root (Tests, Sonderpfade).
- **Kein** Zugriff auf `HERMES_HOME`, Monorepo-Checkout oder beliebige Pfade.

Implementierung: `tools/powerunits_docs_tool.py`.

---

## Part B — Manifest-driven lookup

- `MANIFEST.json` ist die **einzige** Key-Quelle (`entries[].key`, `source_relative`, `sha256`, `bytes`).
- `action=list_keys` listet sortierte Keys aus dem Manifest — **ohne** Dateizugriff fuer die Namensliste, **ohne** Filesystem-Pfade in der Modell-Antwort (nur `keys`, `count`, optional `bundle_version` / `allowlist_version` aus dem Manifest).
- Direkte Pfad-Injektion aus User-Prompts ist wirkungslos: das Tool akzeptiert **keinen** Pfadparameter.

---

## Part C — Output shaping

- Groessenbegrenzung wie oben; Telegram-taugliche Defaults.
- Fehlercodes im JSON (`error_code`) zur Unterscheidung:
  - nicht allowgelistet vs. Bundle/Manifest-Problem vs. Integritaet.

---

## Part D — Hermes integration shape (first-safe)

- Eigenes **Toolset** `powerunits_docs` mit genau einem Tool `read_powerunits_doc`.
- In **first-safe** explizit erlaubt (neben `memory`, `session_search`, `todo`; **ohne** `clarify` im Telegram-Gateway) in:
  - `model_tools.py` (`_POWERUNITS_ALLOWED_TOOLSETS`)
  - `gateway/run.py` (`_POWERUNITS_ALLOWED_TELEGRAM_TOOLSETS`)
  - `docker/apply_powerunits_runtime_policy.py` (`ALLOWED_TELEGRAM_TOOLSETS`)
- `check_fn`: Tool erscheint nur, wenn Manifest **und** alle referenzierten Dateien im Bundle existieren — sonst ausgeblendet (**fail-closed**).
- Keine Skills-, File- oder Browser-Surface-Erweiterung.

---

## Part E — SOUL integration

`docker/SOUL.md` enthaelt einen kurzen Abschnitt **Bundled Powerunits documentation**: Nutzung von `read_powerunits_doc` nur mit Manifest-Keys, keine Ueberzeichnung von Faehigkeiten.

---

## Part F — Operator flow

### Bundle aktualisieren

Wie in `docs/powerunits_docs_read_surface_v1.md`: `scripts/bundle_powerunits_docs.py` gegen den Monorepo-Clone ausfuehren, committen, Image neu bauen, deployen.

### Manifest-Keys pruefen

- Im Container oder lokal: JSON lesen — `entries[].key`.
- In Telegram (wenn Modell Tools nutzen darf): z. B. Anweisung, `read_powerunits_doc` mit `action=list_keys` aufzurufen.

### Nachweis „nur allowgelistet“

- Modell kann **kein** `read_file` aufs Repo aus first-safe heraus aufrufen (weiterhin blockiert).
- Nur `read_powerunits_doc` mit erlaubten Keys; unbekannte Keys liefern `unknown_key_not_allowlisted`.

### Sicheres Testen via Telegram

1. Deploy mit neuem Image (Policy-Entrypoint setzt Telegram-Toolsets inkl. `powerunits_docs`).
2. Nachricht: z. B. „Rufe read_powerunits_doc mit action=list_keys auf und nenne die Keys.“
3. Danach: „Lese roadmap.md mit read_powerunits_doc (action read) und fasse in 5 Bulletpoints zusammen.“
4. Erwarten: keine Shell/File-Browsing-Tools; Antworten bleiben aus dem Bundle.

---

## Part G — One exact next recommendation

`Test Hermes with manifest-keyed Powerunits docs prompts next`

---

## Verknuepfungen

- Freshness contract (tiers, thresholds, manifest v2): `docs/powerunits_docs_freshness_v1.md`
- Bundle-Build: `docs/powerunits_docs_read_surface_v1.md`
- Allowlist-Design: `docs/powerunits_docs_allowlist_integration_v1.md`
- Runtime-Policy: `docs/powerunits_runtime_policy_v1.md`
- First-safe Review: `docs/powerunits_first_safe_telegram_review_v1.md`
