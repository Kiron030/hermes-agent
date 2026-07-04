# Powerunits Railway Bootstrap v1 (Official Hermes Fork)

## Before editing context

Dieses Repository ist jetzt der kanonische Hermes-Pfad fuer Powerunits (Powerunits-kontrollierter Fork von `NousResearch/hermes-agent`).

Der Auftrag ist bewusst **minimaler Railway-Bootstrap** fuer einen sicheren internen Start, nicht Capability-Erweiterung oder tiefe Produktintegration.

---

## Part A - Deployability inspection (official repo findings)

### Runtime entrypoint

- Offizieller CLI-Entrypoint ist vorhanden:
  - `pyproject.toml` -> `[project.scripts] hermes = "hermes_cli.main:main"`
  - Wrapper-Skript `hermes` ruft ebenfalls `hermes_cli.main:main` auf.

### Startmodus fuer Railway

- Fuer Cloud/Container-Run ist im Repo klar der Foreground-Gateway-Modus vorgesehen:
  - `hermes gateway run`
  - In `hermes_cli/main.py` ist `gateway run` explizit als empfohlen fuer Docker-Umgebungen markiert.
- Docker-Default ist jetzt repo-seitig explizit auf Gateway gesetzt:
  - `Dockerfile`: `CMD ["gateway", "run"]`
  - `docker/entrypoint.sh`: fallback auf `gateway run`, wenn kein Command uebergeben wurde.
  - Entrypoint wird im Image explizit mit `chmod 0755` gesetzt (unabhaengig vom Host-Git-Filemode, wichtig fuer Windows/`railway up`).

### Docker vs. non-Docker on Railway

- Repo enthaelt bereits einen produktionsnahen `Dockerfile` mit:
  - Python/Node-Abhaengigkeiten
  - `ENTRYPOINT ["/opt/hermes/docker/entrypoint.sh"]`
  - `HERMES_HOME=/opt/data`
  - `VOLUME ["/opt/data"]`
- Damit ist ein Docker-basierter Railway-Pfad in diesem Fork am klarsten und reproduzierbarsten.

### Persistenzpfad

- Offizieller Containerpfad ist `/opt/data` (nicht `/data`) laut Dockerfile + `docker/entrypoint.sh`.
- `entrypoint.sh` bootstrapt dort `.env`, `config.yaml`, `SOUL.md`, Skills-Sync und startet dann `hermes`.

### Runtime assumptions

- Python-Anforderung: `>=3.11` (aus `pyproject.toml`).
- Messaging/Telegram wird offiziell ueber Gateway unterstuetzt.

### Bereits vorhandene deploy-relevante Dateien

- `Dockerfile`
- `docker/entrypoint.sh`
- `.env.example`
- `cli-config.yaml.example`
- `pyproject.toml`

Fazit: Repo ist bereits grundsaetzlich deploybar; es braucht vorrangig einen klaren Powerunits-Bootstrap-Contract.

---

## Part B - Minimal Railway bootstrap contract (Powerunits)

1. **Source repo:** Powerunits-kontrollierter `hermes-agent` Fork.
2. **Branch:** `powerunits-internal-setup` fuer initialen Rollout (danach kontrollierter Release-Branch oder `main`).
3. **Railway scope:** separates Railway-Projekt + separater Hermes-Service.
4. **Deploy path:** Dockerfile-basierter Deploy aus dem Fork.
5. **Persistenz:** 1 Volume, gemountet auf `/opt/data`.
6. **Startverhalten:** Foreground Gateway via `hermes gateway run` (durch Entrypoint + Command).
7. **Telegram-first:** Telegram als einziges aktiviertes Messaging-Interface im ersten Schritt.
8. **Provider setup:** genau ein LLM-Provider-Key fuer Start (z. B. OpenRouter/OpenAI/Anthropic), kein Multi-Provider-Overhead initial.
9. **Internal-only posture:** erlaubte Nutzer explizit begrenzen; kein oeffentlicher Customer-Surface.
10. **Keine gefaehrlichen Extras:** keine Shell/SSH/Docker-Exec-Backends, keine Browser-Automation, keine optionalen Tool-Integrationen.

---

## Part C - Minimal repo-side bootstrap changes

### Was wirklich noetig war

- Dieses Runbook unter `docs/powerunits_railway_bootstrap_v1.md`.

### Was **nicht** zwingend noetig war (Stand v1)

- Kein `railway.toml` erforderlich:
  - Der Repo-Dockerfile ist bereits deployfaehig und definiert Entrypoint/State-Pfad.
- Keine neue `.env.example.powerunits` erforderlich:
  - `.env.example` existiert bereits; relevante Minimalvariablen werden unten klar eingegrenzt.

Optional spaeter (nur wenn Betrieb es verlangt):

- sehr kleine `railway.toml` zur expliziten Dokumentation von Build/Start/Healthcheck.

Railway-Kompatibilitaetshinweis:

- Dockerfile-`VOLUME` wird auf Railway nicht akzeptiert; Persistenz wird ausschliesslich ueber Railway-Volume-Mount auf `/opt/data` hergestellt.

---

## Part D.1 - Oeffentliche Railway-Domain und 502 (`Application failed to respond`)

**Ursache (Default-Deploy):** Das Image startet per [`Dockerfile`](../Dockerfile) **`CMD [ "gateway", "run" ]`** — also nur das **Messaging-Gateway** (z. B. Telegram **Long-Polling**). Es laeuft **kein** HTTP-Server auf der von Railway injizierten Umgebungsvariable **`PORT`**. Der Reverse-Proxy erreicht keinen Listener → **502 Bad Gateway**.

**Dashboard (Upstream v0.18+):** Die Web-UI ist ein **separater** Befehl (`hermes dashboard` → [`hermes_cli/web_server.py`](../hermes_cli/web_server.py)). Ab **v0.18** verweigert `start_server()` jeden **Nicht-Loopback-Bind** (`0.0.0.0`, Railway-`PORT`) **ohne registrierten Auth-Provider** — **`--insecure` ist tot** (Juni-2026-Hardening, siehe `hermes_cli/web_server.py`). Fehlermeldung im Deploy-Log:

```
Refusing to bind dashboard to 0.0.0.0 — the auth gate engages on non-loopback binds,
but no auth providers are registered.
```

**Empfohlener Start (Telegram-first / Powerunits first_safe_v1 — Option A):**

1. Railway **Start Command** (kein oeffentliches Dashboard noetig):
   `/opt/hermes/docker/railway_gateway.sh`
   — oder weiterhin `/opt/hermes/docker/railway_gateway_with_dashboard.sh` (startet seit v0.18-Fix **standardmaessig nur das Gateway**, siehe unten).
2. Env: `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` (im Image bereits gesetzt).
3. **Erwartetes Verhalten:** Die oeffentliche Railway-Domain kann **502** zeigen (kein HTTP auf `PORT`) — **normal und akzeptabel**, solange Telegram per Long-Polling laeuft. Railway-Status sollte **Running** sein (nicht Crashed).

**Optional — oeffentliches Dashboard (Option C, nur bei Bedarf):**

1. Start Command: `/opt/hermes/docker/railway_gateway_with_dashboard.sh`
2. Env **zusaetzlich**:
   - `HERMES_DASHBOARD=1`
   - Auth-Provider, z. B. `HERMES_DASHBOARD_BASIC_AUTH_USERNAME` + `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` (oder `_PASSWORD_HASH` + `_SECRET`)
   - optional `HERMES_POWERUNITS_DASHBOARD_MODE=observe` (sperrt mutierende `/api/*` HTTP-Calls)
3. **Nicht** mehr `--insecure` allein — das umgeht die Auth-Gate nicht mehr.

Skripte: [`docker/railway_gateway.sh`](../docker/railway_gateway.sh) (Gateway-only), [`docker/railway_gateway_with_dashboard.sh`](../docker/railway_gateway_with_dashboard.sh) (Gateway + optional Dashboard mit Auth).  
Erweiterte Lessons (**Dashboard + `HERMES_HOME` + bundled skills**): [`docs/powerunits_hermes_dashboard_skills_atlas_v1.md`](powerunits_hermes_dashboard_skills_atlas_v1.md).

### Vorfall v0.18 Dashboard-Auth-Gate (2026-07-04)

**Symptom:** Nach Deploy auf Hermes **v0.18** Railway-Status **Crashed**, Telegram antwortet nicht. Deploy-Log endet mit der obigen `Refusing to bind dashboard to 0.0.0.0`-Meldung.

**Root Cause:** Der bisherige Start Command `/opt/hermes/docker/railway_gateway_with_dashboard.sh` startete `hermes dashboard --host 0.0.0.0 --port $PORT --insecure`. Upstream v0.18 macht `--insecure` zu einem No-Op und bricht ohne konfigurierten Auth-Provider mit **exit 1** ab. Weil das Skript `exec hermes dashboard` als PID-1-Prozess nutzt, beendet der Dashboard-Abbruch den **gesamten Container** — auch das im Hintergrund gestartete Gateway stirbt mit.

**Fix (Repo A, Branch `powerunits-internal-setup`):**

- Neues Skript [`docker/railway_gateway.sh`](../docker/railway_gateway.sh): nur `hermes gateway run --replace` (+ stage2-bootstrap).
- [`docker/railway_gateway_with_dashboard.sh`](../docker/railway_gateway_with_dashboard.sh): **Default Gateway-only**; Dashboard auf `$PORT` nur wenn **`HERMES_DASHBOARD=1`** **und** ein Auth-Provider gesetzt ist.

**Operator-Aktion:** Image neu deployen (Redeploy / leerer Push). **Start Command muss nicht geaendert werden**, wenn bereits `railway_gateway_with_dashboard.sh` gesetzt ist — nach dem Fix startet Telegram wieder. Fuer explizite Klarheit empfohlen: Start Command auf `railway_gateway.sh` umstellen.

**Deaktivieren ohne Skriptwechsel:** `HERMES_DASHBOARD` unset lassen (Default). Es gibt **kein** `HERMES_DASHBOARD=0`-Spezialflag — alles ausser der truthy-Liste in `docker/s6-rc.d/dashboard/run` gilt als aus.

**Auth-Provider-Optionen (Upstream, falls Dashboard oeffentlich):**

| Option | Konfiguration |
|--------|----------------|
| basic_auth | `dashboard.basic_auth.username` + `password_hash` in `config.yaml`, oder `HERMES_DASHBOARD_BASIC_AUTH_*` env |
| OAuth (Nous) | `hermes dashboard register` → `HERMES_DASHBOARD_OAUTH_CLIENT_ID` |
| OIDC | `HERMES_DASHBOARD_OIDC_ISSUER` + `HERMES_DASHBOARD_OIDC_CLIENT_ID` |
| loopback only | `--host 127.0.0.1` + Tunnel (nicht fuer Railway-`PORT` geeignet) |

---

## Part D - Safety defaults (first internal rollout)

Setze fuer den ersten Rollout folgende sicheren Defaults:

1. Telegram only (keine weiteren Plattformen aktivieren).
2. Zunaechst ein interner Benutzer / enge Allowlist.
3. Keine optionalen Toolsets aktivieren.
4. Keine write-faehigen DB-Credentials.
5. Keine Infra/Admin-Tokens (Railway API, Cloud Control Plane).
6. Keine Bucket/Object-Storage Credentials.
7. Keine externen Control-Plane-Integrationen.
8. Keine customer-facing Kommunikation oder Produkt-Einbettung.

Ergaenzung fuer ersten Live-Rollout:

- tiered runtime policy aktivieren/halten (`HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`),
  damit die Telegram-Tooloberflaeche fail-closed eingeschraenkt bleibt.
- optional **Dashboard Stufe 1 (HTTP read-only):** `HERMES_POWERUNITS_DASHBOARD_MODE=observe`
  **zusaetzlich** zu `first_safe_v1` — blockiert mutierende REST-Aufrufe unter `/api/` (Details:
  [`powerunits_runtime_v0_12_integration.md`](powerunits_runtime_v0_12_integration.md) § *Hermes Dashboard*).

---

## Minimum env contract (v1 bootstrap)

Minimal noetige Variablen fuer den ersten Railway-Start:

- `TELEGRAM_BOT_TOKEN` (required)
- `TELEGRAM_ALLOWED_USERS` (required fuer internal-only gate)
- genau **ein** Provider-Key (required), z. B.:
  - `OPENROUTER_API_KEY` **oder**
  - `OPENAI_API_KEY` **oder**
  - `ANTHROPIC_API_KEY`
- optional fuer Webhook-Betrieb:
  - `TELEGRAM_WEBHOOK_URL`
  - `TELEGRAM_WEBHOOK_SECRET`

Hinweis:

- Wenn Polling-Modus genutzt wird, ist keine oeffentliche Webhook-URL zwingend.
- Keine weiteren Secrets initial setzen.

---

## Part E - Transition logic vs. third-party template

Aktueller Third-Party-Template-Deploy bleibt nur temporaer als Vergleichsartefakt.

Switch-Kriterium auf offiziellen Fork:

- Hermes startet stabil auf Railway aus dem Fork
- Telegram Nachrichtenaustausch funktioniert
- Persistenz unter `/opt/data` bleibt ueber Redeploys erhalten
- Safety-Defaults bleiben wirksam (internal-only, keine gefaehrlichen Extras)

Dann Third-Party-Pfad als nicht-kanonisch stilllegen.

---

## Exact next recommendation

`Switch Railway source from the third-party template to the Powerunits-controlled fork next`

---

## Switchover linkage (v2.3)

Der konkrete First-Switchover-Ablauf (Source-Switch + Post-Deploy-Checks) ist dokumentiert in:

- `docs/powerunits_railway_switchover_v1.md`

---

## Runtime verification linkage (v2.5)

Die Verifikation des Post-Policy Runtime-Zustands ist dokumentiert in:

- `docs/powerunits_runtime_verification_v1.md`

## Telegram connectivity debug linkage (v3.1)

Bei laufendem Service ohne Telegram-Antworten (z. B. `/start`, `/help`, Text),
siehe:

- `docs/powerunits_telegram_connectivity_debug_v1.md`

## Telegram gateway activation debug linkage (v3.2)

Wenn zwar Startup/Banner sichtbar ist, aber keine Telegram-Connection-Line erscheint,
siehe:

- `docs/powerunits_telegram_gateway_activation_v1.md`

## Primary provider routing linkage (v3.3)

Bei erfolgreicher Telegram-Connectivity aber 401-LLM-Fehlern (Provider/Model mismatch), siehe:

- `docs/powerunits_primary_provider_routing_v1.md`

## OpenAI request compatibility linkage (v3.4)

Bei HTTP 400 auf OpenAI (`include` / encrypted content) trotz gueltigem Key und korrektem Routing, siehe:

- `docs/powerunits_openai_request_compatibility_v1.md`

## Docs allowlist integration linkage (v3.5)

Erste sichere Powerunits-Wissensflaeche (nur explizit gebundelte Docs, kein breites Repo-Scannen), siehe:

- `docs/powerunits_docs_allowlist_integration_v1.md`

## Docs read surface linkage (v3.6)

Build-Zeit-Bundle (`scripts/bundle_powerunits_docs.py`), gestufte Dateien unter `docker/powerunits_docs/`, `.dockerignore`-Ausnahme fuer diesen Pfad, **keine** zusaetzlichen Railway-Env-Variablen fuer docs-only v1:

- `docs/powerunits_docs_read_surface_v1.md`

## Docs reader linkage (v3.7)

First-safe Telegram-Toolset um `powerunits_docs` / `read_powerunits_doc` erweitert; optional nur fuer Tests: `HERMES_POWERUNITS_DOCS_BUNDLE`.

- `docs/powerunits_docs_reader_v1.md`

## GitHub docs reader linkage

Narrow read-only GitHub docs tools (`powerunits_github_docs`) fuer genau einen allowgelisteten privaten Doku-Subtree:

- `docs/powerunits_github_docs_reader_v1.md`

## Workspace reader/writer linkage

Bounded persistent Hermes workspace unter `/opt/data/hermes_workspace` mit allowgelisteten Subdirs (`analysis|notes|drafts|exports`):

- `docs/powerunits_workspace_v1.md`

## Operator setup + staged roadmap

- `docs/powerunits_operator_setup_and_roadmap_v1.md`

## Internal deploy artifact contract (docs reader)

`read_powerunits_doc` funktioniert nur, wenn das Build-Artefakt `docker/powerunits_docs/` inkl. `MANIFEST.json` **im deployten Image enthalten** ist.

- Public-safe Code ohne dieses Artefakt bleibt deploybar, aber der Docs-Reader ist dann zur Laufzeit deaktiviert (Tool via `check_fn` versteckt, Warn-Log sichtbar).
- Das ist erwartetes fail-closed Verhalten; keine Live-Repo-/DB-Fallbacks.

Empfehlung fuer internen Betrieb: interner Build-Job erzeugt zuerst das Bundle (`scripts/bundle_powerunits_docs.py`), validiert `docker/powerunits_docs/MANIFEST.json`, baut dann erst das Railway-Image.

### Local `railway up` packaging note (Windows)

`docker/powerunits_docs/` bleibt in `.gitignore`, damit interne Docs nicht in den Public-Repo-Flow geraten.
Fuer lokalen Railway-Deploy wird das Bundle ueber `.railwayignore` explizit wieder eingeschlossen.

## s6-overlay migration: `config.yaml`/`gateway.lock` PermissionError (v3.8, incident 2026-07-02)

**UPDATE (gleicher Tag, nach Re-Test):** Die urspruengliche erste Diagnose in diesem
Abschnitt (`RAILWAY_RUN_UID=0` als alleiniger Fix) war **unvollstaendig/falsch** — der
User hat die Variable gesetzt und neu deployed, der exakt gleiche Fehler trat weiterhin
auf. Die echte Root Cause steht jetzt unten ("Tatsaechliche Root Cause"); die
`RAILWAY_RUN_UID`-Recherche bleibt als dokumentierter Nebenbefund stehen (nicht falsch,
nur nicht die eigentliche Ursache in diesem Fall).

**Symptom:** Nach dem Wechsel des Images auf die s6-overlay-Architektur (`/init` als PID 1,
Bootstrap in `docker/stage2-hook.sh`, eingefuehrt im v0.15.0-Upstream-Sync) crasht der
Container beim Start mit `PermissionError: [Errno 13] Permission denied` auf
`/opt/data/config.yaml` bzw. `/opt/data/gateway.lock`, obwohl der Code lokal/frisch
korrekt ist. Im Deploy-Log fehlt dabei **jede** `[stage2] ...`-Zeile komplett — das war
der entscheidende Hinweis auf die echte Ursache.

**Tatsaechliche Root Cause (verifiziert, Belege):**

- Dieser Railway-Service nutzt seit Part D.1 dieses Dokuments einen **Custom Start
  Command**: `/opt/hermes/docker/railway_gateway_with_dashboard.sh`.
- Railways eigene Doku stellt unmissverstaendlich klar: *"Dockerfile / Image: the start
  command overrides the image's `ENTRYPOINT` in exec form."*
  (<https://docs.railway.com/deployments/start-command>, bestaetigt durch einen
  unabhaengigen Community-Debugging-Bericht mit identischem Symptom: "The `startCommand`
  ... completely overrides the Dockerfile's `ENTRYPOINT` and `CMD`.").
- Unser Image setzt `ENTRYPOINT [ "/init", "/opt/hermes/docker/main-wrapper.sh" ]` (s6-overlay
  als PID 1). Ein Custom Start Command ersetzt dieses **komplette** Array — `/init` startet
  nie, `/etc/cont-init.d/01-hermes-setup` (→ `docker/stage2-hook.sh`) laeuft nie, der
  UID-Remap + `chown` von `config.yaml`/`gateway.lock`/etc. auf den `hermes`-User (UID 10000)
  passiert nie, und die Powerunits-`first_safe_v1`-Runtime-Policy-Anwendung
  (`docker/apply_powerunits_runtime_policy.py`) laeuft ebenfalls nie.
- `docker/hermes-exec-shim.sh` (`/opt/hermes/bin/hermes`, vorn auf `$PATH`) droppt jeden
  `hermes`-Aufruf automatisch von root auf den `hermes`-User (UID 10000) — das war **nie**
  das fehlende Teil. Der Gateway-Prozess lief also schon vorher korrekt als `hermes`
  (UID 10000); er traf nur auf `config.yaml`/`gateway.lock`, die nie auf diese UID
  umgechownt wurden, weil `stage2-hook.sh` nie ausgefuehrt wurde. Das erklaert auch, warum
  `RAILWAY_RUN_UID=0` wirkungslos war: die Prozess-UID war nie das Problem, die
  **Datei-Ownership auf dem Volume** war es.
- Nebenbefund (bestaetigt fuer Vollstaendigkeit, keine Korrektur noetig): das Dashboard
  startet trotzdem sauber (`HERMES_DASHBOARD_READY`), weil `railway_gateway_with_dashboard.sh`
  es als eigenen, direkt exec'ten Prozess startet, der nicht von `/init`/s6-Supervision
  abhaengt und keine der betroffenen Dateien beim Start oeffnet.

**Code-Fix (committed, kein weiterer Railway-Handgriff noetig):**

`docker/railway_gateway_with_dashboard.sh` fuehrt jetzt selbst den fehlenden
`docker/stage2-hook.sh`-Bootstrap aus (UID-Remap, `$HERMES_HOME`-Chown, Erst-Boot-Seeding,
`first_safe_v1`-Policy), bevor Gateway + Dashboard starten — inkl. `PATH`-Fix, damit
`stage2-hook.sh`s interne `s6-setuidgid`-Aufrufe (normalerweise nur unter `/init`
aufloesbar) auch in diesem direkt-exec'ten Kontext funktionieren. Idempotent, laeuft bei
jedem Boot/Restart erneut, kein Risiko fuer bestehende Daten (`stage2-hook.sh` seedet nur
fehlende Dateien, `chown` aendert nur Ownership).

**RAILWAY_RUN_UID=0 kann gesetzt bleiben** (schadet nicht, war aber fuer dieses konkrete
Symptom nicht die Ursache) — relevant bliebe sie nur, falls der Custom Start Command
jemals entfernt und wieder auf den reinen Default-`ENTRYPOINT`/`CMD`-Pfad (`/init` +
`main-wrapper.sh`, ohne Dashboard) umgestellt wird.

**Lessons fuer zukuenftige Architektur-Sync-Schritte:**

- Ein Upstream-Wechsel des Container-Privilege-/Boot-Modells (hier: tini -> s6-overlay
  mit `/init` als PID 1) macht **jeden vorhandenen Custom Start Command** auf gehosteten
  Deployments zu einem potenziellen stillen Bootstrap-Bypass — das muss beim naechsten
  "Upstream-Sync abgeschlossen"-Review explizit gegen jede bekannte Hosting-Plattform-
  Konfiguration (Railway Start Command, Compose-Overrides, k8s command/args) geprueft
  werden, nicht nur gegen den Code selbst.
- Fehlende erwartete Log-Zeilen (hier: kein einziges `[stage2] ...`) sind ein staerkerer
  Hinweis auf "Bootstrap-Schritt laeuft gar nicht" als auf "Bootstrap-Schritt laeuft, aber
  schlaegt fehl" — bei der naechsten aehnlichen Diagnose zuerst pruefen, ob die
  Boot-Stage ueberhaupt erreicht wird, bevor an der Chown-/UID-Logik selbst gezweifelt wird.

## Folge-Vorfall: `ModuleNotFoundError: powerunits_telegram_overlays` (v3.8, incident 2026-07-02, Teil 2)

**Symptom:** Direkt nach obigem Fix (Commit `e9bd89274`, `stage2-hook.sh` wird jetzt
explizit aus `railway_gateway_with_dashboard.sh` aufgerufen) crashte der Service in einer
Crash-Loop (Neustart alle ~1-2s) mit:

```
File "/opt/hermes/docker/apply_powerunits_runtime_policy.py", line 18, in <module>
    from powerunits_telegram_overlays import (...)
ModuleNotFoundError: No module named 'powerunits_telegram_overlays'
```

**Root Cause (verifiziert, KEIN Kontext-/Environment-Problem):** Der Traceback bricht in
Zeile 18 ab, **nachdem** Zeile 17 (`from powerunits_capability_tier import ...`) bereits
erfolgreich durchgelaufen ist. Das schliesst jede Hypothese rund um fehlende
venv-Aktivierung, `PYTHONPATH`, oder falsches Arbeitsverzeichnis sofort aus — beide Module
liegen im selben Repo-Root-Verzeichnis, ein Kontextproblem haette beide Imports gleich
betroffen. `docker/stage2-hook.sh` ruft das Skript ohnehin unveraendert per absolutem
Pfad zum venv-Python auf (`s6-setuidgid hermes "$INSTALL_DIR/.venv/bin/python"
"$INSTALL_DIR/docker/apply_powerunits_runtime_policy.py"`) — identisch im alten
(`/init`-basierten) und neuen (manuellen) Aufrufkontext.

Die tatsaechliche Ursache: `powerunits_telegram_overlays.py` (erstellt in Commit
`9df8d2c45`, "stabilize Tier 4B exposure, review_status validation, telegram overlays")
wurde **nie** zu `[tool.setuptools] py-modules` in `pyproject.toml` hinzugefuegt — im
Gegensatz zu `powerunits_capability_tier`, das dort explizit gelistet ist. Top-Level
`.py`-Module ausserhalb eines Packages (wie alle `powerunits_*.py`-Dateien im Repo-Root)
werden bei `uv pip install -e .` **nur** dann Teil der installierten/editable Distribution,
wenn sie in dieser Liste stehen. Ohne Eintrag ist ein solches Modul ausserhalb eines rohen
Source-Checkouts schlicht nicht importierbar — unabhaengig von CWD/PYTHONPATH/venv.

Das war rein zufaellig bisher unentdeckt, weil `docker/apply_powerunits_runtime_policy.py`
(und damit dieser Import) auf diesem Railway-Service **noch nie tatsaechlich gelaufen war**
— das ist exakt der im ersten Teil dieses Vorfalls beschriebene Bootstrap-Bypass durch den
Custom Start Command. Der erste Fix hat diesen Bypass behoben und dadurch zum ersten Mal
ueberhaupt einen echten Lauf dieses Skripts auf dem gebauten Image ausgeloest, was den
seit Commit `9df8d2c45` bereits latenten Packaging-Bug erstmals sichtbar gemacht hat.

Bei der Gelegenheit zusaetzlich gefunden (gleiche Bug-Klasse, noch nicht in Produktion
manifestiert, weil bislang durch die Capability-Tier-Gates nicht erreicht): auch
`powerunits_skill_draft_review_contract.py` (verwendet von
`tools/powerunits_tier4a_skill_draft_proposals_tool.py` und
`tools/powerunits_tier4b_review_governance_tool.py`) fehlte in `py-modules`.

**Fix (Commit `478b693e9`):**

1. `pyproject.toml`: `powerunits_telegram_overlays` und
   `powerunits_skill_draft_review_contract` zu `[tool.setuptools] py-modules` hinzugefuegt
   — der eigentliche, generische Packaging-Fix.
2. `docker/apply_powerunits_runtime_policy.py`: defensiver `sys.path.insert()` (Repo-Root
   relativ zum eigenen Dateipfad aufgeloest) als zusaetzliche Absicherung, damit dieses
   Skript auch bei einem zukuenftig erneut vergessenen `py-modules`-Eintrag nicht mehr
   bricht.
3. Neuer Invarianten-Test (`tests/test_packaging_metadata.py`,
   `test_every_top_level_powerunits_module_is_covered_by_py_modules`): prueft, dass jedes
   `powerunits_*.py`-Modul im Repo-Root in `py-modules` gelistet ist — verhindert, dass
   dieser Bug bei einem zukuenftigen neuen Fork-Modul erneut unentdeckt bleibt.

**Naechster Schritt fuer den User:** Redeploy anstossen (Push auf `powerunits-internal-setup`
loest bei Railway automatisch einen Rebuild aus, sofern Auto-Deploy aktiv ist; sonst manuell
"Redeploy" in der Railway-UI). Kein manueller Eingriff auf Railway selbst noetig — reiner
Code-/Packaging-Fix, kein Volume-/Berechtigungsproblem.

**Lesson:** Jedes neue top-level `powerunits_*.py`-Modul im Repo-Root MUSS zu `py-modules`
in `pyproject.toml` hinzugefuegt werden, sonst ist es ausserhalb eines rohen
Source-Checkouts (jedes gebaute Image, jeder Wheel-Install) nicht importierbar — der neue
Invarianten-Test faengt das jetzt automatisch ab.

## Folge-Vorfall: PermissionError auf `sessions/sessions.json` + `pairing/telegram-approved.json` (v3.8, incident 2026-07-02, Teil 3)

**Symptom:** Nach den beiden vorherigen Fixes (Bootstrap-Bypass-Fix + Packaging-Fix) startete
der Gateway sauber durch (`[stage2] Setup complete; starting user services`,
`HERMES_DASHBOARD_READY`), aber es traten **weitere, neue** `PermissionError`s bei zwei
anderen Dateien unter `/opt/data` auf:

- Beim Boot: `[gateway] Warning: Failed to load pairing sessions: [Errno 13] Permission
  denied: '/opt/data/sessions/sessions.json'` (nicht fatal, nur Warning).
- Beim Verarbeiten einer eingehenden Telegram-Nachricht: `PermissionError: [Errno 13]
  Permission denied: '/opt/data/pairing/telegram-approved.json'` — dieser Fehler war fatal
  fuer die Nachrichtenverarbeitung und wurde dem User direkt in Telegram angezeigt.

**Root Cause (verifiziert im Code):** `docker/stage2-hook.sh`s Chown-Logik war seit PR
#19795 (Mai 2026, Issue #19788) bewusst auf eine **hand-gepflegte Allowlist** bekannter
Hermes-Unterordner beschraenkt (`cron sessions logs hooks memories skills skins plans
workspace home profiles hermes_workspace pairing platforms/pairing`), plus eine separate
Allowlist bekannter Top-Level-Dateien (`auth.json`, `state.db`, `gateway.lock`, ...). Das war
urspruenglich eine bewusste Design-Entscheidung, um bei einem host-bind-gemounteten
`$HERMES_HOME` fremde, nicht-Hermes-Dateien nicht versehentlich umzuchownen.

Zwei unabhaengige Probleme in dieser Allowlist-Architektur haben zusammen die aktuellen
Fehler verursacht:

1. **Die Allowlist war bereits unvollstaendig** (obwohl `sessions` und `pairing` tatsaechlich
   BEIDE bereits in der Liste standen!) — das zeigt, dass selbst eine sorgfaeltig gepflegte
   Liste das Problem nicht strukturell loest: eine Code-Audit von `get_hermes_home() / "..."`
   im gesamten Python-Codebase (`gateway/`, `hermes_cli/`, `tools/`, `plugins/`, `agent/`, ...)
   ergab **weit ueber 30 verschiedene** Unterordner/Dateien unter `$HERMES_HOME`, mehrere
   davon dynamisch benannt (z.B. pro Provider, pro Messaging-Plattform) und damit prinzipiell
   nicht statisch auflistbar.
2. **Der eigentliche Trigger:** Die rekursive Chown-Behandlung der Unterordner-Allowlist war
   hinter einer Bedingung versteckt, die NUR prueft, ob das TOP-LEVEL-Verzeichnis
   `$HERMES_HOME` selbst falsch owned ist (`needs_chown`). Sobald das top-level Verzeichnis
   EINMAL korrekt auf `hermes` gechownt wurde (was durch einen frueheren — teilweise
   gecrashten — Boot-Versuch in diesem Vorfall bereits geschehen war, siehe Teil 1+2), blieb
   diese Bedingung fuer ALLE folgenden Boots dauerhaft `false` — und die komplette
   Unterordner-/Datei-Reparatur lief nie wieder, selbst wenn `sessions/sessions.json` oder
   `pairing/telegram-approved.json` (aus einer alten Volume-Version von vor der s6-Migration,
   oder durch einen root-kontextigen `docker exec ... hermes ...`-Schreibvorgang) weiterhin
   falsch owned waren.

**Fix (Commit-Hash siehe unten):** `docker/stage2-hook.sh` grundlegend ueberarbeitet:

1. Die beiden hand-gepflegten Allowlists (Unterordner + Top-Level-Dateien) sowie die separaten
   Ad-hoc-"immer-auf-jedem-Boot-zuruecksetzen"-Bloecke fuer `profiles/` und `cron/` wurden
   **entfernt** und durch EINE einzige, generische Reconciliation-Loop ersetzt, die JEDEN
   Top-Level-Eintrag unter `$HERMES_HOME` (Dateien, Ordner, inkl. Dotfiles) erfasst.
2. Diese Loop laeuft **unbedingt bei jedem Boot** (kein `needs_chown`-Gate mehr) — behebt damit
   strukturell auch das zweite Problem oben.
3. Statt einer Allowlist wird jetzt eine **Denylist** verwendet
   (`HERMES_DATA_DIR_CHOWN_EXCLUDE`, space-separated Top-Level-Namen), Default leer. Das
   bewahrt die urspruengliche #19788-Absicht (Schutz vor Zerstoerung fremder Host-Dateien in
   einem bind-gemounteten `$HERMES_HOME`) fuer den seltenen Fall, dass ein Operator das
   explizit braucht — deckt aber im Normalfall (dediziertes Volume/Mount) automatisch JEDEN
   aktuellen UND jeden zukuenftigen Hermes-State-Pfad ab, ohne dass er irgendwo eingetragen
   werden muss.
4. Bereits vor dem Chown geprueft (`stat -c %u`), ob ein Eintrag schon korrekt owned ist —
   vermeidet unnoetige rekursive Traversierung bereits korrekter, potenziell grosser
   Unterbaeume (`skills/`, `node_modules/`, `cache/`, ...) bei jedem Boot.
5. Tests aktualisiert/erweitert (`tests/tools/test_stage2_hook_toplevel_chown.py`,
   `tests/tools/test_stage2_hook_log_dir_seed.py`, `tests/tools/test_stage2_hook_unraid_uid.py`,
   `tests/test_docker_home_override_scripts.py`): funktionale Tests simulieren jetzt u.a.
   explizit einen frei erfundenen, auf keiner Liste stehenden Unterordner
   (`some_brand_new_feature_nobody_has_added_to_any_list/`) und pruefen, dass er trotzdem
   automatisch mitgechownt wird — das ist der direkte Regressionsschutz gegen genau diese
   Bug-Klasse.

**Abdeckung bestaetigt:** Der neue Mechanismus deckt den **gesamten** `$HERMES_HOME`-Baum ab,
nicht nur die zwei aktuell gemeldeten Pfade (`sessions/sessions.json`,
`pairing/telegram-approved.json`) — inklusive aller im Code-Audit gefundenen Pfade (`cache/`,
`plugins/`, `checkpoints/`, `whatsapp/`, `mcp-installs/`, dynamisch benannte
Provider-/Plattform-Dateien, u.v.m.) sowie jedem zukuenftigen, noch nicht existierenden
State-Pfad, den ein spaeteres Feature hinzufuegt.

**Naechster Schritt fuer den User:** Redeploy anstossen (Push loest bei aktivem Auto-Deploy
automatisch einen Rebuild aus; sonst manuell "Redeploy" in der Railway-UI). Kein weiterer
manueller Eingriff auf Railway noetig.

**Preflight-Checkliste (neuer, genereller Punkt fuer zukuenftige Docker-/Entrypoint-Aenderungen):**

> Bei Docker-/Entrypoint-Aenderungen, die Datei-Ownership betreffen: IMMER rekursiv auf das
> gesamte Datenverzeichnis anwenden (ggf. mit einer kurzen, expliziten Denylist fuer bekannte
> Ausnahmen), NIE nur auf einzelne zum Zeitpunkt der Aenderung bekannte Dateien/Ordner —
> sonst tauchen bei jedem neuen Feature/Unterordner erneut einzelne PermissionErrors auf
> einem bestehenden Volume auf. Eine Allowlist-basierte Ownership-Reparatur ist ein
> Wartungs-Zeitbombe: sie ist per Definition nur so vollstaendig wie der Stand des Codes zum
> Zeitpunkt ihrer letzten Aktualisierung, waehrend `get_hermes_home()`-Aufrufstellen
> kontinuierlich wachsen. Zusaetzlich: jede Ownership-Reparatur-Bedingung, die nur den
> TOP-LEVEL-Zustand prueft (statt jeden Eintrag einzeln), kann nach einem einzigen
> erfolgreichen Teil-Lauf dauerhaft "scharf gestellt" bleiben und nie wieder greifen —
> Reparaturen muessen pro Eintrag, nicht pro Verzeichnis-Wurzel, geprueft werden.
