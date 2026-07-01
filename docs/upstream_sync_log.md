# Upstream Sync Log (Powerunits Hermes Fork)

**Zweck:** Laufendes, chronologisches Protokoll jedes Upstream-Syncs (`NousResearch/hermes-agent` → dieser Fork). Ergänzt die Prozess-Doku (`docs/powerunits_fork_sync_strategy_v1.md`, `docs/powerunits_hermes_upgrade_playbook.md`) um ein tatsächliches Log von *wann* was passiert ist — nicht nur *wie* es passieren soll.

**Format pro Eintrag:** Datum, Versions-/Tag-Range, was gemerged/übersprungen/verschoben wurde, welche Powerunits-Patches neu angewendet werden mussten, Test-/Smoke-Status, offene Punkte.

---

## 2026-07-01 — Hotfix: v0.12.0-Merge-Regression in model_tools.py restauriert

**Kontext:** Beim ersten (abgebrochenen) v0.13.0-Merge-Versuch fiel per Symbol-Diff-Check (siehe vorheriger Eintrag) auf, dass `model_tools.py` bereits **beim ursprünglichen v0.12.0-Merge** stillschweigend regressiert wurde — ohne jeden Konfliktmarker. `git diff v2026.4.30 powerunits-internal-setup -- model_tools.py` zeigte: unser Fork-Stand hatte 602 Zeilen, die reine Upstream-v0.12.0-Baseline 811 Zeilen.

**Verlorene/rueckgaengig gemachte Upstream-v0.12.0-Fixes (jetzt restauriert):**

- **MCP-Tool-Discovery:** Der blockierende Modul-Level-Call `discover_mcp_tools()` war wieder aktiv — genau der Bug, den Upstream fuer Issue #16856 behoben hatte (blockiert bis zu 120s Discord/Telegram-Gateway-Heartbeats bei langsamem/unreachable MCP-Server). Per-Entry-Point-Discovery existierte in unserem Fork bereits an allen relevanten Stellen (`gateway/run.py`, `cli.py`, `tui_gateway/*`, `acp_adapter/*`), daher ist die Entfernung des Modul-Level-Calls ein reiner Fix ohne Funktionsverlust.
- **`_run_async`:** Vereinfachte Cancellation-Logik ohne Worker-Loop-Tracking wieder aktiv (potenzieller Thread-Leak bei 300s-Timeout im Gateway-/Async-Pfad) — robuste Version restauriert.
- **`get_tool_definitions`/`_compute_tool_definitions`-Cache-Split** (inkl. `_clear_tool_defs_cache`) fehlte — Performance- und Duplicate-Tool-Name-Fix (Issue #17335) restauriert.
- **`_schema_allows_null`, `_coerce_json`** fehlten komplett (JSON-String-Array/Object-Koerzierung, nullable-Schema-Handling) — restauriert.
- **`handle_function_call`:** `duration_ms`-Tracking, `transform_tool_result`-Plugin-Hook, und geloggte statt stillverschluckte Hook-Exceptions fehlten — restauriert. `logger.error` → `logger.exception` im Fehlerpfad (Stacktrace).
- **Echter Zusatzbefund waehrend der Restauration:** Ein `else`-Zweig, der `pre_tool_call` erneut feuerte wenn `skip_pre_tool_call_hook=True`, war (wieder) vorhanden — das ist der "klassische Double-Fire-Bug", fuer den es in `tests/test_model_tools.py::TestPreToolCallBlocking` bereits Regressionstests gibt. Diese Tests schlugen bei einem ersten Wiederherstellungsversuch fehl (ich hatte den `else`-Zweig faelschlich als bewusste Fork-Ergaenzung interpretiert) und haben den Fehler zuverlaessig gefangen. Endgueltiger Fix: Single-Fire-Contract wiederhergestellt.

**Bewusst NICHT angefasst (gehoert zum v0.13.0-Sync, nicht zu diesem Hotfix):**

- `disabled_toolsets` `elif`- statt `if`-Bug (Upstream-Issue #17309) — existierte bereits in der v0.12.0-Baseline selbst, keine Fork-Regression. Reale Exposure gering (Powerunits-Gateway-Pfad nutzt nur `enabled_toolsets`/`platform_toolsets`, nie `disabled_toolsets`).
- `discord`/`discord_admin`-Split vs. Upstreams vereinheitlichtes `discord_server`-Tool — unklar ob bewusste Powerunits-Entscheidung (granulare Rechtetrennung) oder Altlast; Discord ist als Plattform fuer Powerunits ohnehin vollstaendig deaktiviert (`docker/apply_powerunits_runtime_policy.py` `DISABLED_PLATFORMS`), daher keine reale Exposure. Wird beim v0.13.0-Sync erneut betrachtet.
- Die in v0.13.0 neu hinzugekommene `coerce_tool_args`-Array-Wrapping-Erweiterung — echtes v0.13-Feature, nicht Teil der v0.12.0-Baseline.

**Andere Hotspot-Dateien geprueft** (gleicher Symbol-/Zeilenzahl-Check): `AGENTS.md`, `gateway/config.py`, `toolsets.py`, `agent/transports/chat_completions.py` — **keine** versteckten Verluste gefunden, nur saubere, additive Powerunits-Ergaenzungen (`_powerunits_lockdown_enabled`, `_apply_powerunits_runtime_lockdown`, `_custom_base_url_accepts_ollama_think_extra_body`, first-safe Telegram-Toolset-Lockdown). `model_tools.py` war der einzige betroffene Fall.

**Verifikation:** `python -m ast`-Syntaxcheck, `tests/test_model_tools.py` (39/39), `tests/test_model_tools_async_bridge.py`, `tests/tools/test_registry.py`, `tests/hermes_cli/test_model_tools_telegram_bzn_entsoe_surface.py` — alle gruen.

**Branches:** `fix/model-tools-v012-regression-restore` → gemerged nach `powerunits-internal-setup` (`520055d78`), gepusht.

**Naechster Schritt:** v0.13.0-Merge (Tag `v2026.5.7`) erneut versuchen, jetzt mit korrigierter `model_tools.py`-Baseline und obligatorischem Symbol-Diff-Check vor jedem Merge-Commit.

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
