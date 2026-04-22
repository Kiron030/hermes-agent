# Powerunits GitHub Docs Reader v1

## Scope

Kleinstmoegliche read-only GitHub-Dokuoberflaeche fuer Hermes:

- Repo: `Kiron030/Powerunits.io`
- Branch: `starting_the_seven_phases`
- **Zentrale Konfiguration:** `config/powerunits_github_knowledge.json`
  - Feld `surfaces`: aliasgebundene `root_prefix`-Roots (z. B. `powerunits_docs -> docs`, `powerunits_roadmap -> docs/roadmap`, `powerunits_architecture -> docs/architecture`).
  - Feld `doc_key_allowlist_relative`: Pfad zur Manifest-Key-Datei (Standard: `scripts/powerunits_docs_allowlist.json`) fuer `read_powerunits_doc` (GitHub-primary + Bundle-Fallback).

**Primary vs. Fallback (Hermes Growth v1):**

- **Primary:** `read_powerunits_doc` liest bei gesetztem `POWERUNITS_GITHUB_TOKEN_READ` und gueltiger Config zuerst von **GitHub** (allowlistete `source_relative`-Pfade).
- **Fallback / degraded:** gebundeltes Snapshot unter `docker/powerunits_docs/` nur wenn GitHub fehlschlaegt oder kein Token konfiguriert ist (`knowledge_actual_source=bundled_fallback`).

Keine Writes, keine freie Repo-/Branch-/Path-Wahl durch das Modell.

## Operator-Konfiguration

- **Immer:** `config/powerunits_github_knowledge.json` (Surfaces + optional `HERMES_POWERUNITS_GITHUB_KNOWLEDGE_CONFIG` fuer Override-Pfad).
- **Doc-Keys:** `scripts/powerunits_docs_allowlist.json` oder Override `HERMES_POWERUNITS_DOC_KEY_ALLOWLIST` (absolute Pfade erlaubt).
- **Modus:** `HERMES_POWERUNITS_DOCS_SOURCE` = `auto` (Default), `github`, oder `bundle`.

## Tools

### GitHub directory / file (alias-scoped)

- `list_powerunits_roadmap_dir(subpath?, alias?)`
- `read_powerunits_roadmap_file(name, max_output_chars?, alias?)`

Beide nutzen dieselbe zentrale Config; `alias` muss in `surfaces` existieren und `enabled=true` sein.

### Manifest-key reader (`read_powerunits_doc`)

- `action=list_keys` / `action=read` mit flachem Key (`implementation_state.md`, …).
- Keys stammen aus der Doc-Key-Allowlist; GitHub ist Primary, Bundle expliziter Fallback.

## Runtime env contract

- **GitHub (Primary):** `POWERUNITS_GITHUB_TOKEN_READ` (Fine-grained read-only, minimal auf Repo begrenzt).
- Legacy: `POWERUNITS_GITHUB_DOCS_TOKEN`
- Ohne Token: `read_powerunits_doc` nutzt nur Bundle, sofern gebaut; GitHub-spezifische Tools bleiben disabled (`check_fn`).

## Safety controls

- Modell kann repo/branch/root nicht zur Laufzeit ausserhalb der Config waehlen.
- `subpath`/`name` Validierung: kein `..`, keine absoluten Pfade, kein Root-Escape.
- Lesen nur fuer konfigurierte Dateiendungen (typisch `.md`/`.txt`).
- Logging: erfolgreiche Reads loggen u. a. Repo, Branch, Commit-SHA (falls API liefert), Alias, relativen Pfad, Quelle (`github_primary` vs. `bundled_fallback`).

## Telegram validation prompts

1. `Nutze list_powerunits_roadmap_dir mit alias="powerunits_roadmap" und gib die Eintraege aus.`
2. `Nutze list_powerunits_roadmap_dir mit alias="powerunits_architecture" und gib die Eintraege aus.`
3. `Nutze read_powerunits_doc mit action=list_keys und dann action=read mit key=implementation_state.md.`
4. `Versuche read_powerunits_roadmap_file mit alias="powerunits_architecture" und name="../secret.md" (soll fail-closed invalid_name).`
5. `Versuche read_powerunits_roadmap_file mit alias="powerunits_architecture" und name="some.json" (soll fail-closed invalid_name).`

## Docs-to-workspace usage pattern

Bei expliziter Operator-Anweisung soll Hermes ohne Meta-Schleifen:

1. aus allowgelistetem Alias/Datei lesen,
2. knapp zusammenfassen,
3. in `powerunits_workspace` speichern,
4. kurz bestaetigen mit Quelle (`knowledge_actual_source` + Pfad/Key) und gespeichertem Workspace-Pfad.

Bei expliziter Vergleichsanfrage:

1. Datei aus Alias A lesen,
2. Datei aus Alias B lesen,
3. kurze Vergleichssynthese (Alignment/Gaps/Risks/Next actions),
4. in `analysis/` speichern und Pfad kurz bestaetigen.
