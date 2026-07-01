# Upstream Sync Log (Powerunits Hermes Fork)

**Zweck:** Laufendes, chronologisches Protokoll jedes Upstream-Syncs (`NousResearch/hermes-agent` → dieser Fork). Ergänzt die Prozess-Doku (`docs/powerunits_fork_sync_strategy_v1.md`, `docs/powerunits_hermes_upgrade_playbook.md`) um ein tatsächliches Log von *wann* was passiert ist — nicht nur *wie* es passieren soll.

**Format pro Eintrag:** Datum, Versions-/Tag-Range, was gemerged/übersprungen/verschoben wurde, welche Powerunits-Patches neu angewendet werden mussten, Test-/Smoke-Status, offene Punkte.

---

## 2026-07-01 — Bestandsaufnahme + v0.12.0 Versions-Metadaten-Korrektur

**Kontext:** Vorbereitung des inkrementellen Sync-Vorhabens v0.12.0 → v0.17.0 (5 Minor-Versionen, ~5.350 Commits upstream seit v0.12.0).

**Befund (Step 0 — Bestandsaufnahme vor jeder Änderung):**

- **v0.12.0 (Tag `v2026.4.30`) war bereits vollständig gemerged** — verifiziert via `git merge-base --is-ancestor v2026.4.30 HEAD` (Exit-Code 0). Vorherige Session-Artefakte (`RELEASE_v0.12.0.md`, vollständige Feature-Implementierungen: Curator, Yuanbao-Plattform, Spotify-/Teams-/Google-Meet-Plugins, LM Studio/GMI Cloud/Azure AI Foundry Provider) bestätigen dies zusätzlich auf Code-Ebene.
- **Repo-B-Notiz (`hermes_runtime_v012_repo_b_note.md`) war korrekt** — kein veralteter Stand, keine Vertrauenslücke.
- **Lücke gefunden:** `pyproject.toml` `[project].version` stand trotz vollzogenem Merge weiterhin auf `0.11.0` statt `0.12.0` (Playbook-Schritt "nach Merge Version bumpen" war nie nachgezogen worden). → **Behoben** in dieser Session (Branch `fix/pyproject-version-0.12.0-bump`, gemerged nach `powerunits-internal-setup`, gepusht).
- **Kein `integration/upstream-sync`-Branch existierte** — frühere Sync-Branches (`integration/upstream-sync-20260422`, `integration/hermes-v0.12-upgrade-prep`, `integration/hermes-runtime-v0.12-bump`) wurden nach erfolgreichem Merge gelöscht bzw. als `backup/integration-upstream-sync-20260422` gesichert.
- **Namenskonvention vereinheitlicht:** Ab sofort `integration/hermes-runtime-vX.Y-bump` pro Minor-Version (entspricht der real gelebten Praxis beim v0.12-Merge, nicht dem in `config/powerunits_fork_sync_config.json` dokumentierten `integration/upstream-sync-YYYYMMDD`-Schema — Doku-Korrektur folgt).

**Tooling-Hinweis (nicht prozessrelevant, aber zeitkritisch):** Die Shell-Ausführung hing zu Beginn dieser Session dauerhaft (`SandboxUnsupportedError` — Cursor-Windows-Sandbox unterstützt auf Netzlaufwerken keine Dateisystem-Isolation). Workaround: Shell-Aufrufe mit expliziter Sandbox-Deaktivierung für diesen Workspace.

**Ergebnis dieses Eintrags:**
- `pyproject.toml` → `0.12.0` (Commit `42702daa6`, gemerged `b06b44869`, gepusht nach `origin/powerunits-internal-setup`).
- Kein Code-Merge in diesem Eintrag — reine Metadaten-Korrektur.

**Nächster Schritt:** v0.13.0 (Tag `v2026.5.7`, 881 Commits seit v0.12.0) auf `integration/hermes-runtime-v0.13-bump`.

---

<!-- Neue Einträge oben anfügen, ältester Eintrag am Ende der Datei. -->
