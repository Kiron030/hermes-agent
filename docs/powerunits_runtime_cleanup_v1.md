# Powerunits Runtime Cleanup v1 (Final First-Safe Surface Consistency)

## Before editing restatement

Die Runtime ist verbessert, aber weiterhin nur teilweise effektiv.

Der verbleibende Blocker ist die Konsistenz zwischen effektiver und sichtbarer Surface.

---

## Part A - Remaining leakage layer

Die verbleibende sichtbare Ueberexposition stammt primaer aus dem spae ten Surface-Builder:

- `hermes_cli/banner.py` (`build_welcome_banner`)

Konkret:

1. Der Banner zeigte nicht nur finale callable Tools, sondern mischte zusaetzlich
   `unavailable_toolsets` in die Anzeige.
2. Der Banner renderte weiterhin den breiten Skill-Katalog aus dem Dateisystem.
3. Dadurch entstand sichtbare Ueberexposition (browser/discord/homeassistant/etc.)
   trotz gehaerteter Tool-Registry.
4. Daraus ergab sich auch die Inkonsistenz "4 tools" vs. mehrere gelistete
   unerwuenschte Toolsets.

---

## Part B - Final first-safe cleanup (implementiert)

In `hermes_cli/banner.py` wurde ein first-safe Anzeige-Lockdown eingefuehrt:

1. Policy-Guard:
   - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` wird erkannt.
2. Toolset-Darstellung:
   - in first-safe werden keine `unavailable/default` Toolsets mehr in den Banner
     gemischt.
   - angezeigt wird nur die finale callable Tool-Surface.
3. Skills-Darstellung:
   - in first-safe wird kein breiter Skill-Katalog mehr ausgegeben
     (`Available Skills: hidden in first-safe mode`).
4. MCP-Darstellung:
   - MCP-Server-Block wird in first-safe nicht mehr angezeigt.

Fail-closed: Bei Unsicherheit wird Surface im first-safe Modus verborgen statt
ambig sichtbar gelassen.

---

## Part C - Erwartetes sichtbares Ergebnis nach Redeploy

Im Startup-Banner sollten folgende Flaechen verschwinden:

- `browser`
- `discord`
- `homeassistant`
- `image_gen`
- `messaging/send_message`
- `moa/mixture_of_agents`
- breite Skill-Kataloganzeige (z. B. `67 skills` + MCP/GitHub/Codex/Claude-Code/Subagent-Beispiele)

Die sichtbare Banner-Surface sollte mit der reduzierten first-safe Runtime
konsistent sein.

---

## Part D - Railway implications

Minimal:

1. Nur Redeploy.
2. `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` beibehalten.

Keine weiteren Railway- oder Secret-Aenderungen.

---

## Part E - One exact next recommendation

`Redeploy Hermes after final first-safe surface cleanup next`

