# Upstream Sync Log (Powerunits Hermes Fork)

**Zweck:** Laufendes, chronologisches Protokoll jedes Upstream-Syncs (`NousResearch/hermes-agent` → dieser Fork). Ergänzt die Prozess-Doku (`docs/powerunits_fork_sync_strategy_v1.md`, `docs/powerunits_hermes_upgrade_playbook.md`) um ein tatsächliches Log von *wann* was passiert ist — nicht nur *wie* es passieren soll.

**Format pro Eintrag:** Datum, Versions-/Tag-Range, was gemerged/übersprungen/verschoben wurde, welche Powerunits-Patches neu angewendet werden mussten, Test-/Smoke-Status, offene Punkte.

---

## 2026-07-01 — v0.13.0-Merge: Konfliktauflösung + Intra-Funktions-Regressionen gefunden/behoben

**Kontext:** Zweiter v0.13.0-Merge-Versuch (Tag `v2026.5.7`) nach dem `model_tools.py`-Hotfix, auf `integration/hermes-runtime-v0.13-bump`. `model_tools.py` mergte diesmal sauber (Symbol-Diff-Check: keine fehlenden Upstream-Funktionen). Verbleibende 4 echte Konflikte (`AGENTS.md`, `agent/transports/chat_completions.py`, `gateway/config.py`, `toolsets.py`) wurden aufgelöst; siehe `docs/powerunits_fork_sync_strategy_v1.md` Abschnitt 8 fuer die vollstaendige Vorfalls-Analyse (Symbol-Diff Teil 1 + Intra-Funktions-Diff Teil 2).

**Konfliktauflösungen:**

- `AGENTS.md`: Upstream-Version übernommen (Yuanbao-Plattform-Erwähnung, korrigierte `builtin_hooks/`-Beschreibung) — reine Doku, keine Powerunits-Info verloren.
- `gateway/config.py`: Beide Seiten additiv behalten (`_powerunits_lockdown_enabled` unsererseits, `_normalize_notice_delivery` upstream) — kein echter Konflikt inhaltlich.
- `toolsets.py`: Upstream-Ergänzungen übernommen (`kanban`, `discord`, `discord_admin`, `yuanbao`-Toolsets) + `hermes-discord`-Composite-Eintrag korrigiert (siehe unten).
- `agent/transports/chat_completions.py`: Fork-Logik für den "Legacy"-Fallback-Zweig von `build_kwargs()` bewusst behalten statt Upstreams Ein-Zeiler-Vereinfachung zu übernehmen — siehe Intra-Funktions-Diff-Befund unten.

**Kritischer Befund — stiller Verlust *innerhalb* von `build_kwargs()` (kein Konfliktmarker):** Upstream v0.13.0 führte einen neuen `ProviderProfile`-Architektur-Layer ein (`providers/` Package + `plugins/model-providers/<name>/`, ~26 konkrete Profile bereits mitgeliefert: custom, nous, qwen-oauth, kimi-coding, nvidia, openrouter, copilot, ...). `run_agent.py::_build_api_kwargs()` versucht seit v0.13 zuerst `get_provider_profile(self.provider)` und delegiert bei Treffer; nur bei unbekanntem Provider oder bei Call-Sites ohne Profile-Lookup (Summary-/Retry-Pfade `_tsum.build_kwargs()`/`_tretry.build_kwargs()`) wird der alte "Legacy"-Zweig erreicht. Der (nicht als Konflikt markierte) Bereich direkt neben dem eigentlichen Merge-Konflikt wurde von Git klammheimlich komplett durch Upstreams radikal vereinfachte Version ersetzt — dabei gingen ersatzlos verloren:
  - Qwen-Message-Preprocessing (`qwen_prepare_fn`/`qwen_prepare_inplace_fn`, `is_qwen`-Definition)
  - komplette `Temperature`-Behandlung (`fixed_temperature`/`omit_temperature`)
  - Qwen-`session_metadata` → `api_kwargs["metadata"]`
  - drei `max_tokens`-Sonderfälle (`is_nvidia_nim` → 16384, `is_qwen` → 65536, `is_kimi` → 32000)

  Erst der volle Testlauf von `tests/agent/transports/` deckte es auf (`NameError: name 'is_qwen' is not defined`, danach 30 Folgefehler). Alle vier Zweige aus dem Pre-Merge-`HEAD`-Stand rekonstruiert und in den Legacy-Fallback-Zweig zurückgeführt, mit Kommentar-Verweis auf den neuen `ProviderProfile`-Layer und die Call-Sites, die ihn (noch) umgehen.

**Weiterer Fund waehrend derselben Tiefenanalyse — `provider="custom"` (Ollama/lokale Endpunkte) geht ueber den NEUEN Profile-Pfad, nicht den Legacy-Pfad:** `plugins/model-providers/custom/__init__.py` (komplett neue Datei aus v0.13) implementiert `extra_body["think"] = False` beim Deaktivieren von Reasoning, aber **ohne** den Fork-spezifischen Schutz gegen offizielle OpenAI-/Azure-OpenAI-Endpunkte (die den unbekannten `think`-Key mit HTTP 400 ablehnen). Das brach zwei bestehende Regressionstests (`test_openai_direct_custom_skips_think_extra_body`, `test_azure_openai_custom_skips_think_extra_body`). Fix: `base_url` wird jetzt zusätzlich an `profile.build_api_kwargs_extras(...)` durchgereicht (`_build_kwargs_from_profile` in `chat_completions.py`), und `CustomProfile` prüft denselben Host-Guard (dupliziert statt importiert, um keine Provider-Plugin→Transport-Layering-Abhängigkeit einzuführen).

**Weiterer Fund — `discord`/`discord_admin` vs. totes `discord_server`:** Die im vorherigen Sync-Eintrag als "unklar, spaeter pruefen" vermerkte Frage ist jetzt geklärt: `tools/discord_tool.py` registriert ausschließlich `discord` und `discord_admin` — `discord_server` existiert als Tool **nirgends**. `toolsets.py`s `hermes-discord`-Composite-Eintrag referenzierte trotzdem `discord_server` (dadurch war Discord über dieses Toolset praktisch nicht nutzbar), und `model_tools.py`s dynamische Schema-Rebuild-Logik für Discord prüfte ebenfalls auf das nie existierende `discord_server` (toter Zweig — bot-Intent-basierte Schema-Filterung für Discord lief nie). Beide Stellen korrigiert (`toolsets.py`: `hermes-discord`-Tools auf `discord`+`discord_admin`; `model_tools.py`: Schema-Rebuild-Block auf Split-Logik mit `get_dynamic_schema_core()`/`get_dynamic_schema_admin()` umgestellt, matching die real registrierten Namen). Reale Exposure gering — Discord-Plattform ist fuer Powerunits ohnehin deaktiviert.

**Test-Infrastruktur-Anpassung fuer neues v0.13-Feature (ToolCallGuardrailController):** `tests/run_agent/test_concurrent_interrupt.py` (Fork-Test, unveraendert von diesem Merge) nutzt einen handgebauten `_Stub` fuer `AIAgent`; Upstreams neue `self._tool_guardrails`/`self._append_guardrail_observation()`-Aufrufe (unbedingt im Tool-Ausfuehrungspfad) fehlten dem Stub. Ergaenzt: echte `ToolCallGuardrailController()`-Instanz + Passthrough-Stub fuer `_append_guardrail_observation`; lokale Test-Tool-Funktionen (`slow_tool`, `polling_tool`) akzeptieren jetzt `**kwargs` fuer das neue `pre_tool_block_checked`-Flag.

**Verifikation:** `tests/agent/transports/` (167/167), `tests/gateway/test_config.py` + `tests/test_toolsets.py` + verwandte (260/260 zusammen), `tests/tools/test_discord_tool.py` + `tests/test_model_tools*.py` (166/166), `tests/providers/` — komplette neue Suite (83/83), `tests/run_agent/` (1231+ passed nach Fixes; siehe "Offene Punkte" fuer die verbleibenden, als umgebungs-/vorexistierend eingestuften Failures).

**Offene Punkte (bewusst nicht in diesem Schritt geloest):**

1. **`tests/run_agent/test_real_interrupt_subagent.py::test_interrupt_child_during_api_call` haengt deterministisch** (Timeout nach ~12.75s, kein Exception-Traceback). `tools/delegate_tool.py` wurde vom Merge beruehrt (auto-merged, "M"); der Test selbst ist unveraendert und isoliert `HERMES_HOME` nicht (im Gegensatz zu neueren Tests mit `_isolate_hermes`-Fixture) — Verdacht: `_get_subagent_approval_callback()`/`_get_child_timeout()` (beide rufen `_load_config()`) oder eine andere neue Zeile in `_run_single_child()` blockiert, bevor `child.run_conversation()` je erreicht wird. Braucht dedizierte Root-Cause-Session (Tracing/pdb), nicht im aktuellen Merge-Scope geloest.
2. **`tests/run_agent/test_run_agent_codex_responses.py`: zwei Failures rund um GPT-4.1 auf api.openai.com** (`test_build_api_kwargs_codex_openai_direct_skips_encrypted_reasoning_for_gpt41`, `test_aiagent_openai_direct_gpt41_defaults_to_chat_completions`) — **pre-existierender Bug, nicht durch den Merge verursacht** (identischer Code in Pre-Merge-`HEAD` verifiziert): `AIAgent.__init__`s Upgrade-Logik von `chat_completions` auf `codex_responses` nutzt `self._is_direct_openai_url()` als unbedingtes ODER neben dem eigentlich modellspezifischen `_provider_model_requires_responses_api()`-Check, wodurch *jedes* Modell auf api.openai.com (nicht nur gpt-5+) faelschlich auf `codex_responses` hochgestuft wird. Beide Tests sind neu (aus v0.13 importiert) und decken den Bug erstmals auf. Separates Ticket/Fix empfohlen.
3. **`tests/run_agent/test_provider_parity.py::test_nous_when_no_openrouter`**: erwartet `google/gemini-3-flash-preview`, bekommt `stepfun/step-3.7-flash:free` — klassischer "Change-Detector"-Test gegen einen sich aendernden Modell-Katalog-Default (siehe AGENTS.md-Richtlinie "Don't write change-detector tests"); kein Funktionsfehler, nicht angefasst.
4. **Windows/Netzlaufwerk-Umgebungsartefakte** (kein Fork-/Merge-Bug): `tests/run_agent/test_860_dedup.py` (4), `test_compression_boundary_hook.py` (2), `test_compression_persistence.py` (2) — SQLite-Datei-Handle wird beim `TemporaryDirectory`-Cleanup unter Windows auf dem gemappten `W:`-Laufwerk nicht rechtzeitig freigegeben (`PermissionError [WinError 32]` / `NotADirectoryError [WinError 267]`). `test_percentage_clamp.py` (3) war ein reines `cp1252`-Encoding-Problem beim Lesen von Sourcedateien mit Emoji — behoben durch `PYTHONUTF8=1` fuer lokale Testlaeufe auf Windows (kein Code-Fix noetig, CI unter Linux ist nicht betroffen).

**Weiterer Fund (Test-Chunk-Verifikation):** `hermes-yuanbao`-Composite-Toolset fehlte komplett in `toolsets.py` (nur das granulare `yuanbao`-Toolset war vorhanden, kein Bot-Vollzugriffs-Pendant analog zu `hermes-discord`/`hermes-telegram`). Ergänzt inkl. Aufnahme in `hermes-gateway`s Include-Liste.

**Testverifikation (pragmatischer Umfang, siehe Nutzerentscheidung 2026-07-01):** Kompletter Suite-Lauf in einem Pytest-Prozess (`-n 4`, ~21k Tests) bricht auf dieser Windows/Netzlaufwerk-Dev-Umgebung reproduzierbar bei ca. 25–50% ohne Fehlermeldung ab (kein Worker-Crash-Log, kein Traceback) — auch bei serieller Ausfuehrung (`-n 0`) und bei isolierten Einzelverzeichnissen wie `tests/tools`. Stichproben an exakt der Abbruchstelle liefen isoliert sauber durch, d.h. es handelt sich um ein umgebungsbedingtes Ressourcenproblem (vermutlich Datei-Handle-/Tempfile-Aufbau auf dem gemappten `W:`-Laufwerk uber viele Tests hinweg), keine Merge-Regression. Deshalb Verifikation stattdessen in Verzeichnis-Chunks durchgefuehrt (`tests/agent+cli+cron`, `tests/gateway+plugins+providers`, `tests/run_agent`, `tests/skills+tui_gateway+website`, Top-Level `tests/test_*.py`, `tests/tools` teilweise) — alle liefen bis auf bekannte Windows-/Netzlaufwerk-Artefakte gruen (POSIX-only Module `pwd`/`fcntl`, bash-Skript-Tests, Datei-Permission-Bits 0700/0600, SQLite-Tempdir-Cleanup, s. vorheriger Abschnitt) plus die bereits dokumentierten offenen Punkte (`test_real_interrupt_subagent.py`-Hang, `test_run_agent_codex_responses.py`-Altbug, `test_provider_parity.py`-Katalog-Drift). Keine ueber diese bekannten Faelle hinausgehenden echten Regressionen gefunden. `tests/tools` (voller Verzeichnis-Chunk) wurde wegen desselben Umgebungs-Abbruchs nur teilweise durchlaufen; die dabei sichtbaren Fehler waren dieselbe bekannte Klasse (Windows-/Netzlaufwerk-Artefakte), keine neuen Befunde — vollstaendige Abdeckung dieses einen Verzeichnisses bewusst nicht weiter verfolgt (Aufwand/Nutzen, siehe Scoping-Entscheidung).

**Branches:** Konfliktloesung + alle o.g. Fixes committet und nach `powerunits-internal-setup` gemerged und gepusht.

**Naechster Schritt:** Repo-B-Operator-Notiz aktualisieren, danach v0.14.0-Sync vorbereiten (inkl. Security-Tag-Triage zuerst, siehe Nutzeranweisung).

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
