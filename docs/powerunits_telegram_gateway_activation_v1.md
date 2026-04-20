# Powerunits Telegram Gateway Activation v1

## Before editing restatement

Runtime-Hardening ist nicht mehr der Blocker.

Die Allowlist-User-ID ist verifiziert.

Das fehlende Stueck ist Telegram Gateway Activation / Startup Path.

---

## Part A - Actual startup path determination

### Beobachteter Container-Startpfad

- `Dockerfile` nutzt:
  - `ENTRYPOINT ["/opt/hermes/docker/entrypoint.sh"]`
- `docker/entrypoint.sh` beendet mit:
  - `exec hermes "$@"`

### Root cause

Wenn beim Containerstart kein expliziter Command uebergeben wird, war `$@` leer.

Dann startete effektiv nur `hermes` (Default-CLI/Chat-Route mit Banner), nicht zwingend `hermes gateway run`.

Dadurch fehlen die erwarteten Telegram-Gateway-Logs wie:

- `Connected to Telegram (polling mode)`
- `Connected to Telegram (webhook mode)`

### Schlussfolgerung

Der Prozess war lauffaehig, aber der Telegram-Gateway-Laufpfad wurde nicht robust und explizit aktiviert.

---

## Part B - Telegram activation contract

### Telegram-Aktivierungsvariablen (minimal)

- `TELEGRAM_BOT_TOKEN` (required)
- `TELEGRAM_ALLOWED_USERS` (required fuer internal-only)

### Polling vs webhook

- Polling ist Default, wenn `TELEGRAM_WEBHOOK_URL` **nicht** gesetzt ist.
- Webhook-Mode wird nur aktiv bei gesetztem `TELEGRAM_WEBHOOK_URL` (plus optional Secret/Port).

### Healthy log signal

Bei erfolgreichem Gateway-Start mit Telegram muessen explizite Connection-Lines erscheinen:

- `Connected to Telegram (polling mode)` oder
- `Connected to Telegram (webhook mode)`

---

## Part C - Smallest fix implemented

Repo-seitig wurde der Startpfad fail-safe auf Gateway aktiviert:

1. `Dockerfile`
   - `CMD [ "gateway", "run" ]` hinzugefuegt.
2. `docker/entrypoint.sh`
   - Wenn keine Args uebergeben werden, wird automatisch auf `gateway run` gesetzt:
     - `No command provided; defaulting to: hermes gateway run`
     - `set -- gateway run`

Damit startet der Container auch ohne externe Start-Command-Konfiguration deterministisch im Telegram-faehigen Gateway-Modus.

---

## Part D - Operator verification after redeploy

Nach Redeploy in Railway sollten in den Logs erscheinen:

1. `No command provided; defaulting to: hermes gateway run` (nur wenn kein Command uebergeben wurde)
2. Gateway-Startup-Header (`Hermes Gateway Starting...`)
3. Eine Telegram-Connection-Line:
   - `Connected to Telegram (polling mode)` oder
   - `Connected to Telegram (webhook mode)`

Dann Live-Test:

- allowlisted User sendet `/start`, `/help`, und normalen Text
- Erwartung: erste sichtbare Bot-Antwort im DM + keine `Unauthorized user`-Meldung fuer diesen User

---

## Railway setting note

Mit diesem Fix ist kein zwingender Railway-Start-Command mehr noetig.

Wichtig:

- Falls Railway bereits einen expliziten Start-Command setzt, muss dieser mit Gateway kompatibel sein (empfohlen: `gateway run` oder leer, damit Docker-CMD greift).

---

## Part E - One exact next recommendation

`Redeploy Hermes with explicit Telegram gateway activation next`

