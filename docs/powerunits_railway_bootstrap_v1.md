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
