# Powerunits Hermes Fork — Sync Preflight Checklist

**ZUERST LESEN, bevor ein neuer Upstream-Sync-Schritt begonnen wird.**

Dies ist eine kompakte, actionable Checkliste, destilliert aus den v0.12.0-,
v0.13.0- und v0.14.0-Sync-Vorfällen (siehe `docs/upstream_sync_log.md` und
Abschnitt 8 von `powerunits_fork_sync_strategy_v1.md` für die vollen
Incident-Writeups). Ziel: den nächsten Sync-Schritt schneller und mit
weniger wiederholten Fehlern durchziehen, nicht jeden Vorfall erneut selbst
entdecken müssen.

**Bewährt beim v0.14.0-Sync:** zweiter Durchlauf mit dieser Checkliste war
spürbar schneller — keine Dependency-Sync-Falle, kein
Vollsuite-Bisektions-Rabbit-Hole mehr. Prozess funktioniert, weiter so
anwenden.

**Bewährt beim v0.16.0-Sync:** bei einem sehr großen Release-Sprung (927
Commits, u. a. komplett neues Dashboard-Admin-Panel mit ~7400 geänderten
Zeilen in einer einzigen Datei) hat sich gezeigt, dass gezieltes
Stichproben-Gegenprüfen ("failing Test X — passt das schon auf dem
Pre-Merge-Stand?" via `git stash` + Testlauf) sehr viel schneller zur
Gewissheit "keine neue Regression" führt als jeden auffälligen Fehlschlag
einzeln bis auf Codezeilenebene zu analysieren. Siehe Abschnitt 6a unten.

---

## 0. Test-Standard für diesen Prozess (User-Vorgabe)

**Pragmatisch, nicht perfektionistisch.** Ziel ist ein solider, für den
normalen Hermes-Betrieb funktionsfähiger Merge — keine Jagd nach den
letzten Prozentpunkten Testabdeckung.

- **Hotspot-Dateien** (Abschnitt 3 der Strategie-Doku): sorgfältig prüfen,
  Symbol-Diff-Check + Intra-Funktions-Diff-Check sind Pflicht (siehe unten).
- **Rest der Testsuite**: nur grob im Verzeichnis-Chunk-Verfahren laufen
  lassen. Bekannte Umgebungsartefakte (Abschnitt 6 unten) pauschal abhaken,
  nicht einzeln debuggen.
- Bricht ein Chunk-Lauf mittendrin ohne Fehlermeldung ab: **nicht
  bisektieren**. Als Umgebungsartefakt vermerken, nächster Chunk.

---

## 1. Security-Tag-Triage zuerst (bewährtes Verfahren, jetzt Pflicht)

Bevor mit der eigentlichen Konfliktauflösung begonnen wird: Changelog/Commit-
Historie der neuen Upstream-Version nach `security`/CVE/GHSA-Tags
durchsuchen (z. B. `git log <alter-tag>..<neuer-tag> --grep -iE
"security|CVE-|GHSA-"` sowie Release Notes). Beim v0.14.0-Sync brachte das
den GHSA-76xc-57q6-vm5m-Fix (Ollama/OpenRouter-API-Key-Leak an
Lookalike-Domains) zuverlässig zuerst ans Licht.

- Sicherheitsrelevante Änderungen **vorrangig und besonders sorgfältig**
  prüfen — vor den funktionalen/kosmetischen Diffs.
- Fork-Ausnahmen (z. B. eigene Guards, die ein CVE bereits anders
  adressieren) explizit gegen den Upstream-Fix abgleichen, nicht einfach
  stillschweigend überschreiben lassen.
- Ergebnis der Triage im Sync-Log-Eintrag kurz vermerken, auch wenn nichts
  Sicherheitsrelevantes gefunden wurde.

---

## 2. Vor dem Merge: venv-Dependencies synchronisieren

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

## 3. Hotspot-Dateien: Symbol-Diff-Check + Intra-Funktions-Diff-Check

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
4. **Über die feste Hotspot-Liste hinausdenken:** Die Liste in Abschnitt 3
   der Strategie-Doku ist nicht vollständig — beim v0.14.0-Sync ging ein
   eigenständiger Fork-Fix (Commit `f609135`, GPT-4.1/`codex_responses`-
   API-Mode-Bug) unbemerkt unter, weil die betroffene Funktion beim
   Refactoring in eine andere Datei extrahiert wurde und so gar nicht mehr
   wie die "offizielle" Hotspot-Datei aussah. Deshalb zusätzlich: für
   Dateien, die der aktuelle Merge stark umbaut/verschiebt/extrahiert, per
   `git log --all --grep -iE "fix|hotfix" -- <Datei>` (bzw. `git branch
   --contains <Commit>` auf verdächtige Treffer) prüfen, ob dort
   eigenständige (nicht von upstream stammende) Fork-Fixes liegen, die das
   Refactoring stillschweigend verschluckt haben könnte — nicht nur die
   feste Liste abarbeiten.

**"Clean auto-merge" (kein Konfliktmarker) ist kein Beweis für
Vollständigkeit** — das war die Kernursache beider v0.13-Vorfälle.

---

## 4. ProviderProfile-Architektur-Falle (seit v0.13)

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

## 5. Composite-Toolset-/Aggregat-Verlust-Muster (wiederkehrend, jeden Sync prüfen)

Wiederholtes Fehlerbild über mehrere Syncs hinweg: aggregierende
Konfigurationsstellen verlieren beim Merge leise Einträge, ohne
Konfliktmarker. Bisherige Fälle: `hermes-discord`, `hermes-yuanbao`
(v0.13), `hermes-feishu` (v0.14) — jeweils Composite-Toolsets in
`toolsets.py`, die nach dem Merge weniger Tools enthielten als ihre
granularen Einzel-Toolsets zusammen hergeben. Dazu gesellen sich einzelne
verlorene Funktionen/Registrierungen an ähnlichen Aggregationsstellen
(`_gateway_platform_short_label`, `_model_section_has_credentials`,
`browser_dialog` in `_HERMES_CORE_TOOLS`, `acp_registry/agent.json`s
Versionsfeld).

**Nach jedem Merge, bevor committet wird:**

- Jeden `hermes-*`-Composite-Toolset-Eintrag in `toolsets.py` gegen die
  Summe seiner granularen Einzel-Toolsets/-Tools abgleichen (kleiner
  Einzeiler/Script reicht: pro Composite prüfen, ob jedes Tool aus den
  zugehörigen granularen Toolsets auch im Composite auftaucht).
- Dasselbe Prinzip auf andere aggregierende Register/Listen anwenden, die
  der Merge berührt hat: Tool-Registries (`_HERMES_CORE_TOOLS`),
  Provider-Kataloge, Capability-/Feature-Listen, Versions-Strings, die an
  mehreren Stellen dupliziert gepflegt werden (`pyproject.toml` vs.
  `acp_registry/agent.json`).
- Content-Level-Diff, nicht nur Zeilenzahl-Diff: ein Composite-Eintrag
  kann nach dem Merge syntaktisch unauffällig aussehen und trotzdem
  Einträge verloren haben.

---

## 6. Bekannte Windows/Netzlaufwerk-Testartefakte (NICHT jedes Mal neu untersuchen)

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

## 6a. Stichproben-Gegenprüfung statt Einzelfall-Analyse (neu seit v0.16.0)

Bei großen Release-Sprüngen (100+ Commits) ist die absolute Fehlschlag-Zahl
über alle Chunks hinweg oft sehr hoch (300-500+), ohne dass das eine echte
Merge-Regression bedeutet — die meisten Fehlschläge fallen in die
bekannten Umgebungsartefakt-Klassen aus Abschnitt 6. Statt jeden
auffälligen Einzelfall bis auf Codezeilenebene zu analysieren:

1. Fehlschlag isoliert laufen lassen (`pytest <eine Testid> -q`) — prüft,
   ob es sich um Testreihenfolge-/xdist-Kontamination handelt (isoliert
   grün = kein Bug, sondern Test-Isolationsproblem).
2. Falls isoliert weiterhin rot: **NICHT** `git stash` benutzen, solange ein
   `git merge --no-commit` noch offen ist (siehe **kritische Warnung**
   unten) — stattdessen `git worktree add ../hermes-agent-premerge-check
   <pre-merge-commit>` (z. B. der alte Branch-Tip vor dem Merge), denselben
   Test dort laufen lassen, danach `git worktree remove
   ../hermes-agent-premerge-check`. Schlägt der Test schon dort fehl →
   vorbestehend, keine neue Regression, kurz im Sync-Log vermerken und
   weiter.
3. Nur wenn ein Test isoliert UND auf dem Pre-Merge-Stand grün war, aber
   nach dem Merge rot ist, handelt es sich um eine echte Regression, die
   eine tiefere Analyse rechtfertigt.
4. Diese Methode ist besonders wertvoll für sicherheits-/fork-relevant
   *aussehende* Fehlschläge (Credential-Guards, Powerunits-Gate-Tests,
   Codex-Encrypted-Reasoning) — genau dort lohnt sich die 30-Sekunden-
   Gegenprobe, um echte Blocker von Altlasten zu unterscheiden.
5. Falls doch ein `git worktree` zu aufwendig ist und nur ein einzelner
   Dateiinhalt verglichen werden soll, reicht oft auch
   `git show <pre-merge-commit>:<pfad>` — das berührt den laufenden
   Merge-Zustand überhaupt nicht.

**KRITISCHE WARNUNG (Bug gefunden + gefixt im v0.17.0-Sync):** `git stash`
während einer offenen `git merge --no-commit --no-ff`-Session (auch nachdem
alle Konflikte bereits aufgelöst und gestaged wurden) kann `.git/MERGE_HEAD`
stillschweigend verwerfen. Der folgende `git commit` erzeugt dann einen
normalen Einzel-Parent-Commit statt eines echten Merge-Commits — der
Dateiinhalt ist zwar korrekt gemerged, aber die Commit-Historie verliert die
Ancestor-Beziehung zum upstream-Tag. Genau das ist beim v0.16.0-Sync
passiert (Merge-Commit `f0c344683` hatte nur einen Parent statt zwei), was
beim darauffolgenden v0.17.0-Sync-Versuch zu einem massiv aufgeblähten
Konfliktbild führte (489 statt der erwarteten ~15-20 Dateien), weil
`git merge-base` auf v0.15.0 statt v0.16.0 zurückfiel. Gefixt via
`git merge -s ours <übersprungener-Tag>` (leerer Merge, der nur die
Ancestor-Kante nachträgt, ohne den Dateibaum zu verändern) — siehe
Sync-Log-Eintrag v0.17.0. **Nach jedem Merge-Commit** (bevor der nächste
Sync-Schritt beginnt) kurz verifizieren:
`git merge-base --is-ancestor <upstream-tag> HEAD` muss Exit-Code 0 liefern
— das ist die 5-Sekunden-Gegenprobe, die diesen Bug beim nächsten Mal sofort
aufdecken würde, statt ihn erst einen Sync-Schritt später zu bemerken.

**Neue Windows-Testartefakt-Instanz (v0.16.0):** TOML-Konfigurationstests,
die einen Windows-`Path`/`WindowsPath` direkt in einen TOML-String
interpolieren (z. B. `output_directory = "{some_windows_path}"`), brechen
auf Windows, weil TOML-Basic-Strings Backslash als Escape-Zeichen
behandeln — betraf `tests/plugins/test_nemo_relay_plugin.py` beim
v0.16.0-Sync. Gehört zur allgemeinen Pfadseparator-Artefaktklasse aus
Abschnitt 6, aber mit einer TOML-spezifischen Ausprägung, die leicht wie
ein echter Plugin-Bug aussieht (stiller Parse-Fehler, keine offensichtliche
Windows-Fehlermeldung).

**Neuer Checkpunkt bei großen Feature-Releases (Dashboard/Admin-UI o. Ä.):**
Wenn ein Upstream-Release eine neue Bedienoberfläche mit administrativen
Fähigkeiten einführt (z. B. Dashboard-Admin-Panel mit Gateway-/Ops-Kontrolle),
gezielt prüfen: (a) ist die Oberfläche standardmäßig deaktiviert
(Env-Var-Gate), (b) bindet sie standardmäßig nur an Loopback oder verlangt
sie bei Nicht-Loopback-Bind eine Auth-Gate (fail-closed), (c) gibt es ein
`--insecure`-artiges Flag, das nur per explizitem Opt-in aktivierbar ist,
(d) setzt keine Docker-/Compose-/Railway-Konfigurationsdatei im Repo diese
Gates automatisch auf "an". Ergebnis kurz im Sync-Log vermerken, auch wenn
unauffällig — das ist der eigentliche Beleg, dass die Safety-Posture-Prüfung
für dieses Feature durchgeführt wurde.

---

## 6b. Pflicht-Syntaxscan nach jedem Merge, VOR dem Testlauf (neu seit v0.17.0)

Ein sauberer Merge ohne Konfliktmarker in einer Datei ist **kein** Beweis für
korrekten Code, wenn beide Seiten unabhängig voneinander die *gleiche*
Zeile an einer *leicht* unterschiedlichen Stelle einfügen (z. B. weil eine
Seite einen erklärenden Kommentar dazwischen hat). Git löst das dann als
"clean" 3-way-Merge auf, indem es **beide** Vorkommen behält — mit dem
Ergebnis eines doppelten Keyword-Arguments, einer doppelten Dict-Zuweisung
o. Ä. Passiert im v0.17.0-Sync konkret in
`agent/transports/chat_completions.py`: sowohl unser Fork (mit erklärendem
Kommentar) als auch der neue upstream-Commit fügten unabhängig
`base_url=params.get("base_url"),` an fast derselben Stelle ein → Git
behielt beide → `SyntaxError: keyword argument repeated: base_url` beim
Import, was **80+ Tests** in einer einzigen Datei mit Collection-Errors
zum Absturz brachte (sah nach einer großen Regression aus, war aber ein
einzeiliger Fix).

**Neuer Pflichtschritt, VOR dem ersten Test-Chunk-Lauf** (kostet nur
Sekunden, verhindert stundenlanges Fehlsuchen):

```bash
# Alle gegenüber dem upstream-Tag geänderten .py-Dateien syntaktisch prüfen
git diff --name-only <upstream-tag>...HEAD -- '*.py' > /tmp/changed.txt
python -c "
import ast
for f in open('/tmp/changed.txt', encoding='utf-8-sig').read().splitlines():
    f = f.strip()
    if not f:
        continue
    try:
        ast.parse(open(f, encoding='utf-8').read(), filename=f)
    except SyntaxError as e:
        print('SYNTAX ERROR', f, e)
"
```

Ergänzend: kurzer Import-Smoke-Test der Hotspot-Module
(`gateway.run`, `gateway.config`, `model_tools`, `run_agent`,
`hermes_cli.web_server`, ggf. neu entstandene Mixin-Module wie
`gateway.slash_commands`) — deckt auch Fälle ab, die `ast.parse` durchlässt
(z. B. fehlende Imports nach einer Funktionsverschiebung).

**PowerShell-Hinweis:** `git diff ... > datei.txt` schreibt UTF-16 mit BOM;
beim Einlesen in Python `encoding='utf-8-sig'` verwenden, sonst
`UnicodeDecodeError` beim ersten Byte.

---

## 6c. God-File-Extraktionen: verschobene Methoden erneut auf Fork-Gates prüfen (neu seit v0.17.0)

Upstream refactort laut eigenem Contribution-Rubrik (`AGENTS.md`, "Refactor
god-files into clean modules") aktiv große Dateien wie `gateway/run.py` in
Mixins (z. B. neu in v0.17.0: `gateway/slash_commands.py`,
`gateway/authz_mixin.py`). Wenn eine Methode, die eine unserer
Fork-Gates enthält (z. B. `_powerunits_lockdown_enabled()`), OHNE
Konfliktmarker in ein neues Modul verschoben wird, nimmt Git die
upstream-Version 1:1 mit — unser Fork-Gate fehlt dann im neuen Modul,
ohne dass ein Merge-Konflikt das anzeigt. Konkret im v0.17.0-Sync:
`_handle_help_command`/`_handle_commands_command` wurden nach
`gateway/slash_commands.py` verschoben und verloren dabei das
`{} if _powerunits_lockdown_enabled() else get_skill_commands()`-Gate.

**Vorgehen:** Nach dem Symbol-Diff-Check (Abschnitt 3) für jedes als
"verschwunden" markierte Symbol in einer Hotspot-Datei zuerst prüfen, ob es
tatsächlich gelöscht wurde oder nur an eine andere Datei verschoben wurde
(`git grep -n "def <name>"` über den ganzen Baum). Falls verschoben: am
neuen Ort gezielt nach den bekannten Fork-Gate-Funktionsnamen suchen
(`_powerunits_lockdown_enabled`, `_apply_powerunits_runtime_lockdown_*`,
`_enforce_powerunits_toolsets`) und vergleichen, ob sie an der neuen Stelle
noch vorkommen, wo sie im alten Code vorkamen.

---

## 6d. `stage2-hook.sh`: Fork-Denylist-Reconciliation vs. Upstream-Chown-Refactor (neu seit v0.18.0)

Upstream v0.18.0 refactort den `$HERMES_HOME`-Chown-Block (Symlink-Guards
via `path_has_symlink_component`/`refuse_symlinked_path`, `chown_hermes_tree`,
always-on profiles/cron/top-level-file-Blöcke) und behält dabei intern noch
ein **allowlist-/needs_chown-Gate** für Subdirs. Der Fork ersetzte das durch
eine **unconditional denylist-basierte Top-Level-Schleife** (2026-07-02
Railway-Incident, part 3). Beim Merge **beides kombinieren**, nicht
"incoming" blind nehmen:

- Fork-Schleife (`for entry in "$HERMES_HOME"/* ...`, `HERMES_DATA_DIR_CHOWN_EXCLUDE`,
  kein `needs_chown`) **beibehalten**, aber `chown -R` durch `chown_hermes_tree`
  ersetzen (Upstream-Symlink-Schutz).
- Upstreams always-on profiles/cron/top-level-file-Blöcke **additiv** drunter
  lassen (docker-exec-as-root-Härtung) — das widerspricht nicht der
  Denylist-Schleife.
- Contract-Tests in `tests/tools/test_stage2_hook_toplevel_chown.py` und
  `tests/test_docker_home_override_scripts.py` ggf. anpassen (erwarten
  `chown_hermes_tree`, nicht bare `chown -R`; profiles/cron-Blöcke dürfen
  wieder vorhanden sein).

---

## 6e. v0.19.0-Lektionen: schlanke Konfliktliste bei sauberer Ancestry (neu seit v0.19.0)

Bei **sauberer Merge-Ancestry** (`git merge-base --is-ancestor v2026.7.1 HEAD`
nach v0.18-Merge) brachte v0.19.0 nur **5** echte Konfliktdateien — trotzdem
hohe Risikodichte in genau diesen Dateien:

1. **`AGENTS.md`:** Upstream wächst massiv (TUI/Desktop/Dependency-Policy).
   Fork will schlank bleiben → **`git checkout --ours AGENTS.md`** ist oft
   korrekt; Upstream-Inhalt gehört in `hermes_development_guide.md`, nicht in
   Hard Invariants.
2. **`custom` ProviderProfile:** Upstream v0.19 fügt **`reasoning_effort`**
   top-level hinzu (Ollama #14820). Fork-Gate **`_accepts_ollama_think_extra_body`**
   für `think=False` **nicht** opfern — beides kombinieren.
3. **`hermes_cli/banner.py`:** Upstream baut Skills-Anzeige um (dynamische
   Terminalbreite). Fork first-safe hide braucht explizites
   `if _powerunits_lockdown … else …` — Auto-Merge erzeugt sonst doppelte
   `else`-Zweige (kaputte Struktur ohne SyntaxError, aber falsches UI).
4. **`providers/base.py`:** Upstream **`default_vision_model()`** additiv
   übernehmen; Fork-Parameter **`base_url`** auf `get_max_tokens` behalten.
5. **`chat_completions.py`:** Upstream vereinfacht `extra_body.reasoning` —
   Fork-Legacy-Block für Summary/Retry-Pfade behalten (ProviderProfile-Falle,
   Abschnitt 4).

**Safety-Tag vor Merge-PR:** Annotated Tag auf deploy branch **vor** dem
Merge (z. B. `powerunits-hermes-pre-v0.19.0-20260722`) — Rollback ohne
Ratespiel. Siehe `docs/powerunits_hermes_upgrade_playbook.md`.

**Test-Bundle (ausreichend für diesen Sprung):** Hotspot-Syntaxscan +
`test_apply_powerunits_runtime_policy` + `test_custom_profile` +
`test_chat_completions` + 3–4 Powerunits-Tools (~126 passed) — keine
Vollsuite-Jagd nötig, wenn Ancestry + Hotspot-Diff sauber.

---

## 7. Ablaufreihenfolge (Kurzfassung)

1. **Security-Tag-Triage zuerst** (Abschnitt 1 oben) — Changelog/Commits
   nach `security`/CVE/GHSA durchsuchen, vorrangig prüfen.
1a. **Safety-Tag** auf deploy branch **vor** Merge der Integration-PR
    setzen und pushen (Rollback-Anker; siehe Upgrade-Playbook + Abschnitt 6e).
2. Konflikte lösen (Integrationsbranch `integration/hermes-runtime-vX.Y-bump`
   von `powerunits-internal-setup`).
3. Symbol-/Intra-Funktions-Diff-Check auf Hotspot-Dateien **plus**
   fork-eigene Commit-Historie auf stark umgebauten Dateien prüfen
   (Abschnitt 3 oben) **plus** bei verschobenen Symbolen das neue Modul auf
   Fork-Gates prüfen (Abschnitt 6c oben).
3a. **Pflicht-Syntaxscan** aller geänderten `.py`-Dateien + Import-Smoke-Test
    der Hotspot-Module (Abschnitt 6b oben) — VOR dem ersten Testlauf.
4. venv-Deps syncen (`uv pip install -e ".[all,dev]" --python .venv\Scripts\python.exe`).
5. Composite-Toolset-/Aggregat-Abgleich (Abschnitt 5 oben) — vor dem
   Testlauf, da still verlorene Einträge sonst nicht auffallen.
6. Tests in Verzeichnis-Chunks (Abschnitt 6 oben), Umgebungsartefakte
   pauschal abhaken.
7. `docs/upstream_sync_log.md`-Eintrag schreiben (kompakt: was gemerged,
   Security-Triage-Ergebnis, welche echten Konflikte/Regressionen
   gefunden+gefixt, grobe Testlage, offene Punkte — kein Roman).
8. Scratch-/Temp-Dateien aufräumen (`_*.log`, `_*.txt` im Repo-Root),
   bevor committet wird.
9. Merge auf Integrationsbranch committen. **Sofort danach**:
   `git merge-base --is-ancestor <upstream-tag> HEAD` (Exit-Code 0 erwartet)
   — 5-Sekunden-Gegenprobe, dass der Merge-Commit wirklich zwei Parents hat
   und nicht durch eine zwischenzeitliche `git stash`-Aktion beschädigt wurde
   (siehe kritische Warnung in Abschnitt 6a).
10. Nach `powerunits-internal-setup` mergen und pushen — **nur** wenn keine
    sicherheitsrelevanten offenen Fragen bestehen (first-safe policy,
    Telegram-first, kein Shell/SSH/Docker/Code-Exec-Ausbau, keine
    Bucket-Credentials, keine schreibfähige Produktions-DB-URL, keine
    Worker/Deploy-Controls). Sonst: als Blocker zurückmelden, nicht selbst
    mergen.
11. Repo-B-Operator-Notiz aktualisieren, falls relevant.
12. Nächste Version vorbereiten.
