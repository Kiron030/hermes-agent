# Powerunits GitHub Docs Reader v1

## Scope

Kleinstmoegliche read-only GitHub-Dokuoberflaeche fuer Hermes:

- Repo: `Kiron030/Powerunits.io`
- Ref: gepinnter, reviewter Commit (`approved_ref`, 40 lowercase hex, plus `approved_ref_commit_time`) — **kein** beweglicher Branch. Jede Surface und jeder Repo-B-Eintrag traegt `ref`; fehlende, kurze oder Branch-Refs sowie gueltige SHAs ungleich `approved_ref` werden fail-closed ohne Netzwerkaufruf abgelehnt. Repin erfordert eine separate reviewte Entscheidung.
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
- Logging: erfolgreiche Reads loggen u. a. Repo, gepinnten Ref, Alias, relativen Pfad, Quelle (`github_primary` vs. `bundled_fallback`) und den Provenance-Block (nie den Token).

## Read provenance

Jede Read-/List-Antwort aller vier Tools (GitHub-Primary und Bundle-Fallback) enthaelt additiv:

- `read_sha` — der tatsaechlich angefragte gepinnte Commit (GitHub) bzw. `source_repo_commit` aus `MANIFEST.json` (Bundle); keine nachtraegliche Branch-Tip-Abfrage.
- `read_commit_time` — `approved_ref_commit_time` (GitHub; Loader lassen nur `ref == approved_ref` zu) bzw. `source_commit_time` (Bundle), sonst `null`. Kein `commits/<sha>`-Lookup.
- `read_age_days` — Tage von Commit-Zeit bis jetzt (UTC).
- `read_is_current_or_approved` — `read_provenance_complete` **und** `read_sha == approved_ref` (ein Bundle ohne `source_commit_time` ist nie approved).
- `read_source` — `github` | `bundle`.
- `read_provenance_complete` — `false`, wenn SHA, Commit-Zeit oder `approved_ref` fehlen.

Legacy-Felder (`branch`, `github_branch`, `commit_sha`, `github_commit_sha`, `branch_tip_sha`) bleiben erhalten und tragen jetzt den gepinnten Ref.

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
