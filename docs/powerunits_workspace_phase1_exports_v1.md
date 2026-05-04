# Powerunits — Workspace exports posture (Phase 1A)

**Canonical roadmap:** **`docs/powerunits_hermes_progressive_posture_v1.md`** (Hermes progressive posture — dieses Dokument ist **nur** die vertiefende Export-/Workspace-Anleitung).

**Related:** [`powerunits_workspace_v1.md`](powerunits_workspace_v1.md) — allgemeiner Workspace-Vertrag (`analysis` / `notes` / `drafts` / `exports`).

**Scope:** Verbesserte **Konvention für `hermes_workspace/exports`** (ein Agent, keine Bounded-Family-Erweiterung, keine Curator-Schreibungen).

---

## Ziel von Phase 1A

- Gleiche Sicherheitsgrenze wie v1 (nur `.md` / `.txt` / `.csv`, keine Pfadescapes, weiterhin `save_hermes_workspace_note` + optional bestehende Tool-Exports).
- Klare **Benennungs- und Übersteuerungsregeln**.
- Operatorisch prüfbare **Hygiene-Hinweise** über das nur-lesende Tool **`summarize_powerunits_workspace_exports`**.
- Einmalig angelegter **Pointer unter `exports/`**, der zurück auf diese Doks zeigt (`EXPORTS_PHASE1_OPERATOR.txt`), ohne bestehende Dateien zu überschreiben.

---

## Verzeichnis- und Dateiregeln (`exports`)

| Regel | Bedeutung |
|-------|-----------|
| Root | **`$HERMES_HOME/hermes_workspace/exports`** (wie bisher). |
| **Flache Namen empfohlen** | Neuen Artefakten sollten **`dateiname`** ohne Unterordner gegeben werden (`inventory-YYYY-MM-DD-de.csv`). Tiefere Pfade können existieren oder manuell entstehen; die **Übersicht** listet rekursiv, begrenzte Tiefe (siehe Tool-Doku JSON). |
| Erlaubte Endungen | Wie Workspace v1: **`.csv`**, **`.md`**, **`.txt`**. |
| `overwrite_mode` | **`forbid`** (Standard): keine stillen Überwrites — passt zu reproduzierbaren Runs und „fehl wenn schon da“. **`overwrite`** nur bewusst setzen (z. B. Cron/Fixup). Repo B oder andere Kanons bleiben unberührt. |
| Operator-Pointer | **`EXPORTS_PHASE1_OPERATOR.txt`** — wird nur angelegt, wenn **nicht vorhanden**; nicht von Tools überschrieben ausgenommen ihr überschreibt explizit mit `overwrite`. |

---

## Namensführung (empfohlen, nicht enforced)

Vorschläge für lesbare Artefakte und einfacher Diff im Volume:

`{familie oder task}-{YYYYMMDD}-{kurz}-{version-or-run}.csv`  
Beispiele: `bounded-inventory-de-20260430-note.csv`, `rollout-matrix-20260430.csv`

Markdown-/Textexports analog: `*-YYYY-MM-DD-*.md` / `.txt`

Vermeiden: generische Namen wie `export.csv`, die Kollision und versehentliche Überwrites beim Wechsel von `overwrite` begünstigen.

---

## Bounded safety (unverändert)

- **`gateway/run.py`** / Bounded-Families / Repo B sind **nicht** durch Phase 1A erweitert.
- **`auxiliary.curator`**: keine Phase‑1A-Änderung — weiterhin Dokumentations- und Policy-Lage wie v0.12 Powerunits-Laufwerk.

---

## Watcher und Hygiene (operativ)

| Signal | Operational |
|--------|--------------|
| Anzahl Export-Dateien | `summarize_powerunits_workspace_exports` → **`file_count`**; bei **≥ 150** Dateien erscheint **`high_file_count:*`** in **`caution_flags`** |
| Gesamtbytes | **`total_bytes`**; bei **≥ 40 MiB** → **`high_total_bytes:*`** |
| Sehr große Einzeldateien | Eintrag in **`caution_flags`** `large_single_file:<name>:<bytes>` wenn **≥ 8 MiB** |
| Tiefe Pfade | Mehr als **8** Pfadsegmente relativ zu `exports/` → Dateien außerhalb der Zählung; Flag **`skipped_paths_over_depth_cap`** |
| Symlinks unter `exports/` | Nicht traversiert; Zähler **`skipped_symlinks:N`** in **`caution_flags`** |
| Unbekanntes Wachstum | Volume-Monitoring auf `HERMES_HOME` zusätzlich wie im Posture-Runbook |
| Verdacht „Sprawl“ | Viele kleine CSVs ohne Namenskonvention, oder gleiche Basenamen mit Zähler durch Retries |

**Verifikation ohne Code:** Nach Deploy `list_hermes_workspace(subdir=exports)` und **`summarize_powerunits_workspace_exports`** einmal gegen Baseline dokumentieren.

---

## Rollback

- Nur **Konvention/Hinweistext/Summary-Tool**: per **Git-Revert** des Hermes-Repos (Image neu bauen / deploy wie üblich).
- **Nutzer-Artefakte** im Volume nicht automatisch löschen; bei Bedarf manuell `exports/` aufräumen oder aus Backup zurückspielen gemäß Posture **`powerunits-tier0-baseline-*`** / Snapshot.

---

## Tool-Referenz (Phase 1A)

Bestehend:

- **`save_hermes_workspace_note`**, **`read_hermes_workspace_file`**, **`list_hermes_workspace`**

Phase 1A ergänzend:

- **`summarize_powerunits_workspace_exports`** — **read-only** JSON: Anzahl/Bytes/Stichworte **`caution`**, Rekursionstiefe gegen begrenzte Export-Tiefe, Symlink-/Escape-sicher relativ zum Workspace-Root.
