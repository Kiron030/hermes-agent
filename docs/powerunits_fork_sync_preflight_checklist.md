# Powerunits Hermes Fork — Sync Preflight Checklist

**ZUERST LESEN, bevor ein neuer Upstream-Sync-Schritt begonnen wird.**

Dies ist eine kompakte, actionable Checkliste, destilliert aus den v0.12.0-
und v0.13.0-Sync-Vorfällen (siehe `docs/upstream_sync_log.md` und Abschnitt 8
von `powerunits_fork_sync_strategy_v1.md` für die vollen Incident-Writeups).
Ziel: den nächsten Sync-Schritt schneller und mit weniger wiederholten
Fehlern durchziehen, nicht jeden Vorfall erneut selbst entdecken müssen.

---

## 0. Test-Standard für diesen Prozess (User-Vorgabe)

**Pragmatisch, nicht perfektionistisch.** Ziel ist ein solider, für den
normalen Hermes-Betrieb funktionsfähiger Merge — keine Jagd nach den
letzten Prozentpunkten Testabdeckung.

- **Hotspot-Dateien** (Abschnitt 3 der Strategie-Doku): sorgfältig prüfen,
  Symbol-Diff-Check + Intra-Funktions-Diff-Check sind Pflicht (siehe unten).
- **Rest der Testsuite**: nur grob im Verzeichnis-Chunk-Verfahren laufen
  lassen. Bekannte Umgebungsartefakte (Abschnitt 3 unten) pauschal abhaken,
  nicht einzeln debuggen.
- Bricht ein Chunk-Lauf mittendrin ohne Fehlermeldung ab: **nicht
  bisektieren**. Als Umgebungsartefakt vermerken, nächster Chunk.

---

## 1. Vor dem Merge: venv-Dependencies synchronisieren

Ein Upstream-Merge bringt fast immer neue/geänderte Einträge in
`pyproject.toml`/`uv.lock` mit (neue optionale Provider-Plugins, neue
Platform-Adapter-Deps, etc.). Wird das übersehen, sehen fehlende
Dependencies wie Merge-Regressionen aus (Massen an `ImportError`/
`ModuleNotFoundError` bei der Testcollection), sind aber nur ein
Sync-Schritt, der vergessen wurde.

**Richtig (schnell, ~15s):**

```powershell
uv pip install -e ".[all,dev]" --python .venv\Scripts\python.exe
```

**Falsch:**

- `pip install -e ".[all,dev]"` — legacy-Resolver kann **>20 Minuten**
  brauchen oder scheinbar hängen (kein Output sichtbar wegen Shell-Pipe-
  Buffering) bei diesem Extras-Umfang. Wenn schon gestartet und hängt:
  killen, auf `uv pip install` wechseln.
- `uv sync --all-extras` — bricht mit einem Resolver-Fehler ab, weil die
  `yc-bench`-Extra einen `python_version >= '3.12'`-Marker hat, die
  aktuelle venv aber 3.11 ist. `.[all,dev]` umgeht das (yc-bench ist
  nicht Teil von `all`).

Konkret beobachtet beim v0.13-Sync: `agent-client-protocol` (Modulname
`acp`) und `pywinpty` waren neue Deps hinter der `acp`/`pty`-Extra; ohne
Sync schlugen `tests/acp/*`, `tests/acp_adapter/*` u.a. mit
`ModuleNotFoundError` fehl — sah wie ~130 neue Testfehler aus, war aber
nur eine fehlende venv-Sync.

---

## 2. Hotspot-Dateien: Symbol-Diff-Check + Intra-Funktions-Diff-Check

Für jede Hotspot-Datei (Abschnitt 3 der Strategie-Doku), die der Merge
anfasst — **Pflicht**, unabhängig davon ob Git einen Konfliktmarker
gesetzt hat:

1. **Symbol-Diff-Check** (Details: Abschnitt 4, Punkt 6 der Strategie-Doku)
   — Funktions-/Klassenlisten von Basis, Upstream-Ziel und Merge-Ergebnis
   vergleichen; fehlende oder falsch übernommene Symbole finden.
2. **Intra-Funktions-Diff-Check** (Details: Abschnitt 4, Punkt 7) — wenn
   eine Methode auf **beiden** Seiten strukturell umgebaut wurde, reicht
   der Symbol-Diff nicht: Git kann Teile des Methodenkörpers ohne
   Konfliktmarker rein nach einer Seite auflösen. Methodenkörper Zeile für
   Zeile / Zweig für Zweig gegen den Pre-Merge-Fork-Stand abgleichen.
3. Nach Auflösen jedes Konflikts in einer Datei mit stark umgebauten
   Methoden: **sofort** die volle Testsuite für diese Datei laufen lassen
   — nicht erst warten, bis alle Konfliktdateien gelöst sind.

**"Clean auto-merge" (kein Konfliktmarker) ist kein Beweis für
Vollständigkeit** — das war die Kernursache beider v0.13-Vorfälle.

---

## 3. ProviderProfile-Architektur-Falle (seit v0.13)

Upstream hat mit v0.13 einen neuen Abstraktions-Layer (`providers/`,
`ProviderProfile`) eingeführt, der providerspezifische Sonderfälle
(Nous, Qwen, Ollama, Kimi, NVIDIA, ...) aus alten "Legacy"-Methoden
(z. B. `chat_completions.py::build_kwargs()`) in eigene Profil-Objekte
auslagert. Dieses Muster wird sich in künftigen Versionen wahrscheinlich
fortsetzen (weitere Provider wandern in eigene `plugins/model-providers/*`).

**Bei jedem zukünftigen Sync prüfen:**

- Baut Upstream eine Methode/Datei um, die auf einen neuen
  Abstraktions-/Plugin-Layer umsteigt?
- Falls ja: sind **alle** Fork-spezifischen Call-Sites bereits über den
  neuen Layer abgedeckt? Insbesondere Summary-/Retry-Pfade oder andere
  Stellen, die den neuen Layer bewusst umgehen (kein Profile-Lookup
  durchführen), brauchen weiterhin den alten Fallback-Zweig — mit
  Kommentar, der auf den neuen Layer und den Grund für den Fallback
  verweist.
- Neue `plugins/model-providers/<name>/__init__.py`-Dateien auf
  Fork-spezifische Guards prüfen, die im alten Legacy-Pfad existierten
  (z. B. Host-Guards, die verhindern, dass ein Parameter an einen
  Endpunkt geschickt wird, der ihn nicht versteht — siehe
  `_accepts_ollama_think_extra_body`-Vorfall in
  `plugins/model-providers/custom/__init__.py`).

---

## 4. Bekannte Windows/Netzlaufwerk-Testartefakte (NICHT jedes Mal neu untersuchen)

Diese Fehlerklassen sind **umgebungsbedingt** (Windows + gemapptes
Netzlaufwerk als Dev-Setup), keine Merge-Regressionen. Pauschal abhaken:

- **POSIX-only Module** (`pwd`, `fcntl`) — schlagen auf Windows immer mit
  `ModuleNotFoundError` fehl (z. B. `tests/hermes_cli/test_gateway_service.py`).
- **bash-Shebang-Skripte** in Tests (`#!/usr/bin/env bash`) — brauchen
  eine Bash, die auf nativem Windows i. d. R. fehlt/anders reagiert.
- **Datei-Permission-Bits** (0700/0600-Checks) — NTFS hat kein POSIX-Modell,
  diese Assertions schlagen auf Windows grundsätzlich fehl.
- **SQLite-Tempdir-Cleanup auf Netzlaufwerken** — `PermissionError
  [WinError 32]` / `NotADirectoryError [WinError 267]` beim
  `tempfile.TemporaryDirectory`-Cleanup, weil Datei-Handles auf dem
  gemappten Laufwerk nicht rechtzeitig freigegeben werden.
- **`cp1252`-Encoding-Fehler** beim Lesen von Testdateien mit Emoji/Unicode
  — mit `$env:PYTHONUTF8="1"` vor dem Testlauf beheben (kein Code-Fix
  nötig, CI unter Linux ist nicht betroffen).
- **Voll-Suite-Absturz**: ein einzelner `pytest`-Lauf über die komplette
  Suite (~21k Tests, `-n 4` **und** seriell `-n 0`) stirbt reproduzierbar
  irgendwo zwischen 25–50% Fortschritt, ohne Fehlermeldung/Traceback/
  Worker-Crash-Log. Isolierte Stichproben genau an der Abbruchstelle
  laufen sauber durch — vermutlich Ressourcenerschöpfung (Datei-Handles/
  Tempfiles auf dem Netzlaufwerk), kein Code-Bug. **Nicht bisektieren.**
  Workaround: in Verzeichnis-Chunks testen, z. B.:
  - `tests/agent tests/cli tests/cron`
  - `tests/gateway tests/plugins tests/providers`
  - `tests/run_agent` (mit bekannten Deselects, siehe Sync-Log)
  - `tests/hermes_cli`
  - `tests/tools`
  - `tests/skills tests/tui_gateway tests/website`
  - Top-Level `tests/test_*.py`
  - Stirbt ein Chunk selbst mittendrin: nicht weiter bisektieren, als
    bekanntes Artefakt vermerken, nächster Chunk.

---

## 5. Ablaufreihenfolge (Kurzfassung)

1. Konflikte lösen (Integrationsbranch `integration/hermes-runtime-vX.Y-bump`
   von `powerunits-internal-setup`).
2. Symbol-/Intra-Funktions-Diff-Check auf Hotspot-Dateien (Abschnitt 2 oben).
3. venv-Deps syncen (`uv pip install -e ".[all,dev]" --python .venv\Scripts\python.exe`).
4. Tests in Verzeichnis-Chunks (Abschnitt 4 oben), Umgebungsartefakte
   pauschal abhaken.
5. `docs/upstream_sync_log.md`-Eintrag schreiben (kompakt: was gemerged,
   welche echten Konflikte/Regressionen gefunden+gefixt, grobe Testlage,
   offene Punkte — kein Roman).
6. Scratch-/Temp-Dateien aufräumen (`_*.log`, `_*.txt` im Repo-Root),
   bevor committet wird.
7. Merge auf Integrationsbranch committen.
8. Nach `powerunits-internal-setup` mergen und pushen — **nur** wenn keine
   sicherheitsrelevanten offenen Fragen bestehen (first-safe policy,
   Telegram-first, kein Shell/SSH/Docker/Code-Exec-Ausbau, keine
   Bucket-Credentials, keine schreibfähige Produktions-DB-URL, keine
   Worker/Deploy-Controls). Sonst: als Blocker zurückmelden, nicht selbst
   mergen.
9. Repo-B-Operator-Notiz aktualisieren, falls relevant.
10. Nächste Version vorbereiten.
