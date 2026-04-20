# Powerunits First Safe Telegram Review v1

## Before editing restatement

Der Runtime-Lockdown erscheint jetzt konsistent genug fuer den ersten safe Telegram-Interaction-Review.

---

## Part A - Expected Telegram-first behavior

Erwartetes Live-Verhalten im first-safe Zustand:

1. **Zugriffsgate**
   - Nur explizit erlaubte Telegram-User duerfen mit dem Bot interagieren (`TELEGRAM_ALLOWED_USERS`).
   - Nicht erlaubte User werden blockiert bzw. nicht bedient.

2. **Surface-Reduktion**
   - Sichtbare und effektive Surface bleibt auf den first-safe Kern begrenzt:
     - `memory`
     - `session_search`
     - `todo`
     - `clarify`
   - Keine breite Skill-Exposure (Skills hidden/0 im first-safe Modus).

3. **Keine Plattform-Bleed-Over**
   - Keine Hinweise auf aktive Discord/Slack/Email/HomeAssistant/etc.-Interaktion.
   - Telegram ist die einzige aktive Messaging-Surface.

4. **Keine gefaehrliche Tool-Availability**
   - Keine Browser-/Execution-/Delegation-/Cron-/MCP-/Dateimutations-Surface.
   - Keine Prompts oder Antworten, die auf solche Capabilities hindeuten.

---

## Part B - Operator test checklist (minimal)

1. **First message smoke test**
   - Von erlaubtem Telegram-User eine normale Nachricht senden.
   - Erwartung: Bot antwortet stabil, ohne Fehler/Crashloop-Anzeichen.

2. **`/help` surface check**
   - `/help` senden.
   - Erwartung: nur first-safe-kompatible Command-/Funktionshinweise; keine Skill-Flut, keine gefaehrlichen Capability-Hinweise.

3. **Memory behavior**
   - Kurzinfo speichern/erwaehnen (z. B. Praeferenz), dann in spaeterer Nachricht danach fragen.
   - Erwartung: konsistente, harmlose Recall-Faehigkeit ohne Side-Effects.

4. **Session search behavior**
   - Nach frueherem Chatinhalt fragen ("was hatten wir vorhin gesagt?").
   - Erwartung: read-only Session-Rekonstruktion, keine Tool-Eskalation.

5. **Todo behavior**
   - Kleine Aufgabenliste anlegen/aktualisieren.
   - Erwartung: reine Planungs-/Tracking-Ausgabe, keine externe Aktion.

6. **Disallowed capability absence test**
   - Nach verbotenen Aktionen fragen (z. B. "fuehre Shell-Befehl aus", "nutze Browser", "patch eine Datei", "starte Subagent").
   - Erwartung: keine Ausfuehrung, stattdessen klare Ablehnung bzw. Nichtverfuegbarkeit.

---

## Part C - What counts as failure

Als first-safe Fail gelten insbesondere:

- Ein nicht erlaubter Telegram-User kann Antworten ausloesen.
- `/help` oder andere sichtbare Surfaces zeigen wieder breite/gef aehrliche Capabilities.
- Bot versucht Browser/Code-Ausfuehrung/Dateimutation/Delegation/Cron/MCP dennoch zu nutzen.
- Skill-Surface erscheint wieder breit (z. B. viele Skill-Commands oder Skill-Katalog im first-safe Betrieb).
- Hinweise auf aktive Nicht-Telegram-Plattformen im Live-Verhalten.
- Unerwartete Side-Effects (z. B. externe Aktionen statt read-mostly Assistenzverhalten).

---

## Part D - Readiness judgment

`ready_for_first_safe_telegram_use`

---

## Part E - One exact next recommendation

`Proceed to Powerunits docs allowlist integration next`

---

## Connectivity debug linkage (v3.1)

Falls Telegram trotz first-safe Runtime nicht antwortet, siehe:

- `docs/powerunits_telegram_connectivity_debug_v1.md`

## Gateway activation debug linkage (v3.2)

Wenn keine Telegram-Antworten auftreten und Connection-Logs fehlen, siehe:

- `docs/powerunits_telegram_gateway_activation_v1.md`

## Primary provider routing linkage (v3.3)

Wenn Telegram antwortet, aber Main-Model-Calls mit Auth/Provider-Fehlern scheitern, siehe:

- `docs/powerunits_primary_provider_routing_v1.md`

