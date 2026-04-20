# Powerunits Telegram Connectivity Debug v1

## Before editing restatement

Die Runtime-Surface ist ausreichend reduziert, aber Telegram antwortet weiterhin nicht.

Der aktuelle Blocker ist Connectivity / Allowlist / Update-Handling.

---

## Part A - Likely failure points

### 1) Polling vs webhook mode mismatch

Im Adapter gilt:

- Standard: **Polling**
- Webhook nur wenn `TELEGRAM_WEBHOOK_URL` gesetzt ist

Codepfad:

- `gateway/platforms/telegram.py` in `connect()`
  - mit `TELEGRAM_WEBHOOK_URL` -> `start_webhook(...)`
  - ohne `TELEGRAM_WEBHOOK_URL` -> `start_polling(...)`

Moegliche Ausfallbilder:

- Webhook-URL gesetzt, aber extern falsch geroutet
- Polling-Konflikt mit zweitem aktiven Poller fuer denselben Bot-Token

### 2) Allowlist-ID passt nicht zum realen Telegram `user_id`

Autorisierung laeuft in `gateway/run.py` ueber:

- `TELEGRAM_ALLOWED_USERS` (CSV, exakte IDs als String-Set)
- optional globale Allowlists/Flags

Wichtig:

- bei gesetzter Allowlist werden unautorisierte DMs standardmaessig auf `ignore` gestellt (kein Pairing-Prompt),
- dadurch wirkt das System im Chat oft "stumm", obwohl es korrekt blockiert.

### 3) Telegram Gateway-Init nicht erfolgreich

Auch bei laufendem Service kann Telegram selbst nicht connected sein, z. B.:

- fehlender/ungueltiger Token
- Konflikt in Polling-Mode
- Library/Adapter-Init-Problem

### 4) Startverhalten

Falls der Container nur `hermes` (Default-CLI) statt `hermes gateway run` startet, bleibt Telegram trotz laufendem Prozess inaktiv.

Siehe Aktivierungsanalyse + Fix:

- `docs/powerunits_telegram_gateway_activation_v1.md`

---

## Part B - Railway/log debugging guidance

Diese Logstrings sind die wichtigsten Marker:

### Positiv (Telegram aktiv)

- `Connected to Telegram (polling mode)`
- `Connected to Telegram (webhook mode)`

### Token/Startup/Adapter-Probleme

- `No bot token configured`
- `Failed to connect to Telegram: ...`
- `Telegram startup failed: ...`
- `Telegram: python-telegram-bot not installed`

### Polling-Konflikt / Polling-Fehler

- `Telegram polling conflict`
- `Another process is already polling this Telegram bot token`
- `Telegram polling error: ...`
- `Telegram network error, scheduling reconnect: ...`

### Unauthorized / Allowlist-Probleme

- `Unauthorized user: <id> (<name>) on telegram`
- `Ignoring message with no user_id from telegram`

Hinweis:

- Wenn `TELEGRAM_ALLOWED_USERS` gesetzt ist, kann bei unautorisierter DM bewusst kein sichtbarer Pairing-Reply erfolgen (Default `ignore`), daher unbedingt Logs gegenpruefen.

---

## Part C - Exact operator checks (minimal)

1. **Bot token shape und Aktivitaet**
   - Sicherstellen, dass `TELEGRAM_BOT_TOKEN` gesetzt ist und nicht leer/placeholder.
   - In Logs auf `Connected to Telegram (...)` pruefen.
   - Falls nicht vorhanden: auf `No bot token configured` / `Telegram startup failed: ...` / `Failed to connect to Telegram: ...` pruefen.

2. **Telegram user ID Format pruefen**
   - `TELEGRAM_ALLOWED_USERS` muss echte numerische Telegram User IDs enthalten (CSV, ohne @username).
   - Keine Namen/Usernames eintragen.
   - Testweise exakt die eigene numerische ID eintragen.

3. **Polling vs webhook aktiv bestaetigen**
   - `Connected to Telegram (polling mode)` => Polling aktiv
   - `Connected to Telegram (webhook mode)` => Webhook aktiv
   - Bei Webhook-Modus URL/Route/Secret auf Railway gegentesten.

4. **Unauthorized-Fall explizit pruefen**
   - Bei fehlender Antwort im Chat Railway-Logs parallel pruefen:
     - wenn `Unauthorized user: ... on telegram` erscheint, ist Allowlist der wahrscheinliche Hauptgrund.

5. **One successful first reply (Erfolgskriterium)**
   - Von allowlisted User eine normale Textnachricht senden.
   - Erfolg: eine erste Bot-Antwort im DM + keine Unauthorized-/Polling-Konflikt-Fehler im gleichen Zeitfenster.

---

## Part D - One exact next recommendation

`Verify TELEGRAM_ALLOWED_USERS and Telegram gateway activation next`

