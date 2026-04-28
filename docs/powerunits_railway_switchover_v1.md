# Powerunits Railway Switchover v1 (Third-Party Template -> Official Fork)

## Before editing context

Das Repo ist bereits deploybar genug (Dockerfile, Entrypoint, `HERMES_HOME=/opt/data`, Gateway-Startpfad vorhanden).  
Der richtige naechste Schritt ist daher **Switchover-Readiness**, nicht weitere Architektur- oder Capability-Arbeit.

---

## Part A - First switchover checklist

Exakte Reihenfolge fuer den ersten Source-Switch in Railway:

1. **Service auswaehlen**
   - Bestehenden Hermes-Service im separaten Hermes-Railway-Projekt verwenden.
   - Third-Party-Service nur als Vergleichsartefakt belassen.

2. **Source Repo umstellen**
   - Railway Source auf den Powerunits-kontrollierten `hermes-agent` Fork setzen.
   - Branch fuer den ersten Switch: `powerunits-internal-setup`.

3. **Volume beibehalten**
   - Vorhandenes persistentes Volume nicht entfernen.
   - Mount-Ziel fuer den offiziellen Containerpfad bestaetigen: `/opt/data`.
   - Hinweis: Railway ignoriert Dockerfile-`VOLUME`; der Mount muss platformseitig gesetzt sein.

4. **Env-Variablen kontrollieren**
   - Nur Minimalvertrag setzen (siehe Part C).
   - Unsichere/unnuetze Variablen aus Third-Party-Template nicht uebernehmen.

5. **Deploy triggern**
   - Nach Source-Umstellung manuellen Deploy ausloesen (oder Auto-Deploy auf Branch-Update).
   - Build-/Start-Logs auf Entrypoint und Gateway-Start pruefen.

6. **Erste Health-Verifikation**
   - Service startet ohne Crashloop.
   - Gateway laeuft im Foreground-Modus.
   - Telegram-Interaktion mit erlaubtem User funktioniert.
   - Runtime-Policy aktiv: `powerunits.runtime_policy.id = first_safe_v1` in `config.yaml`.

---

## Part B - Runtime command verification

### Verifikation im aktuellen Fork

- Dockerfile setzt `ENTRYPOINT ["/opt/hermes/docker/entrypoint.sh"]`.
- `entrypoint.sh` aktiviert venv, bootstrapt State unter `HERMES_HOME` (default `/opt/data`) und endet mit:
  - `exec hermes "$@"`
- Damit kann Railway den Runtime-Command direkt als:
  - `gateway run`
  verwenden (effektiver Prozess: `hermes gateway run`).

### Repo-side Anpassung noetig?

- **Nein, keine Code-/Config-Aenderung noetig** fuer den ersten Switchover.
- Der bestehende Docker/Entrypoint-Pfad ist fuer den initialen Railway-Switch ausreichend.

---

## Part C - Minimal env contract for first live run

Fuer den ersten produktionsnahen internen Lauf nur:

- `TELEGRAM_BOT_TOKEN` (required)
- `TELEGRAM_ALLOWED_USERS` (required)
- genau **ein** Provider-Key (required), z. B.:
  - `OPENROUTER_API_KEY` **oder**
  - `OPENAI_API_KEY` **oder**
  - `ANTHROPIC_API_KEY`

Optional nur falls Webhook-Modus explizit genutzt wird:

- `TELEGRAM_WEBHOOK_URL`
- `TELEGRAM_WEBHOOK_SECRET`

### Muss weiterhin unset bleiben

- write-faehige DB-Credentials (z. B. `DATABASE_URL`)
- Bucket/Object-Storage Credentials
- Railway/Admin Control-Plane Tokens
- GitHub write/admin Tokens
- beliebige Powerunits-Produktionssecrets ausserhalb des Minimalvertrags

---

## Part D - First post-deploy validation

Nach dem ersten Fork-Deploy:

1. **Service boot**
   - Container startet stabil, kein Restart-Loop.
2. **Volume persistence**
   - `/opt/data` bleibt ueber Redeploy hinweg erhalten.
3. **Telegram pairing / interaction**
   - Erlaubter interner User kann interagieren.
4. **Access restriction**
   - Nicht erlaubte User sind blockiert (Allowlist greift).
5. **Optional tools**
   - Keine optionalen Plattform-/Tool-Erweiterungen aktiv.
6. **Dangerous capability check**
   - Keine Broad-Tool/Infra-Control Erweiterungen ausgerollt.

---

## Part E - Template retirement rule

Der Third-Party-Template-Pfad gilt als retire-faehing, wenn alle Kriterien erfuellt sind:

- offizieller Fork-Deploy erfolgreich
- Telegram-Interaktion erfolgreich
- Persistenz unter `/opt/data` bestaetigt
- kein fehlender Bootstrap-Baustein fuer den offiziellen Pfad

Danach:

- Third-Party-Template nicht mehr als kanonische Betriebsbasis verwenden.

---

## Part F - One exact next recommendation

`Switch the Railway Hermes service to the Powerunits-controlled fork next`

---

## Post-policy verification linkage (v2.5)

Die Runtime-Verifikation nach Policy-Redeploy (Wirksamkeit + Rest-Blocker) ist dokumentiert in:

- `docs/powerunits_runtime_verification_v1.md`
