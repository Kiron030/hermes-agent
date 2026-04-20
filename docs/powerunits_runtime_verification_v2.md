# Powerunits Runtime Verification v2 (Post-Enforcement Mismatch Analysis)

## Before editing restatement

Dies ist **Post-Enforcement-Verifikation**.

Die Runtime ist verbessert, aber weiterhin nicht first-safe.

---

## Part A - Expected vs observed

### Intended first-safe posture (Soll)

- Telegram only
- Minimaler first-safe Tool-Scope
- Keine breiten Messaging-/Automation-/Execution-Surfaces
- Keine breite Skill-Exposure im Startup-/Command-Surface

### Observed live runtime evidence after redeploy (Ist)

- Policy-Hook laeuft:  
  - `[powerunits-policy] applied first_safe_v1 to /opt/data/config.yaml`
- Positiv: mehrere vormals gefaehrliche Flaechen sind in der sichtbaren Startup-Liste nicht mehr vorhanden.
- Negativ: Startup-Banner zeigt weiterhin unerwuenschte Surface:
  - `browser`
  - `discord`
  - `homeassistant`
  - `image_gen`
  - `messaging: send_message`
  - `moa: mixture_of_agents`
- Skills weiterhin breit sichtbar:
  - `67 skills`
  - inkl. Beispiele wie `mcp: native-mcp`, GitHub-nahe Skills, `codex`, `claude-code`, `subagent-driven-development`
- Banner-Inkonsistenz:
  - zeigt gleichzeitig `4 tools`, aber listet weiterhin mehrere unerwuenschte Toolsets.

---

## Part B - What is fixed

Im Vergleich zu frueheren Stufen wirkt die Enforcement-Richtung:

- `code_execution` / `execute_code` erscheint nicht mehr in der sichtbaren Startup-Liste
- `cronjob` erscheint nicht mehr sichtbar
- `delegation` erscheint nicht mehr sichtbar
- breite File-Write/Patch-Surface erscheint sichtbar reduziert

Damit ist ein relevanter Teil der high-risk Surface bereits gedrueckt.

---

## Part C - What still violates first-safe

Weiterhin zu breit im sichtbaren Runtime-Surface:

- Toolset-/Plattformnahe Exposition:
  - `browser`
  - `discord`
  - `homeassistant`
  - `image_gen`
  - `messaging/send_message`
  - `moa/mixture_of_agents`
- Skill-Exposure:
  - breite Skill-Zahl (`67 skills`)
  - sichtbare Skills ausserhalb first-safe (MCP-/GitHub-/Subagent-/Codex-/Claude-Code-Bezug)
- Sichtbarkeitskonsistenz:
  - Startup-Banner widerspricht eigener Summenzeile (`4 tools` vs. gezeigte breite Toolsets)

---

## Part D - Root-cause hypothesis

Wahrscheinlichkeitsbild nach aktuellem Stand:

1. **Primär:** verbleibende **Presentation-/Assembly-Inkonsistenz** im Startup-/Banner-/Help-Surface.  
   Der Banner baut seine Darstellung aus Toolset-Mapping + Availability-/Skill-Scans zusammen und ist damit nicht zwingend identisch zur finalen callable Toolmenge.

2. **Sekundär:** moegliche **Rest-Exposure in spaeten Command-/Registry-Assemblies** (Skill- und Command-Surfaces), obwohl die harte Tool-Registry bereits reduziert ist.

3. **Nicht ausreichend belegt:** dass die weiterhin sichtbaren Toolsets voll callable sind.  
   Die Evidenz zeigt sicher: sichtbare Surface ist noch zu breit; ob jeder sichtbare Eintrag auch tatsaechlich ausfuehrbar ist, muss separat per gezieltem Runtime-Calltest validiert werden.

Kurz: Das verbleibende Problem ist sehr wahrscheinlich **nicht nur Policy-Datei**, sondern vor allem die letzte sichtbare Surface-Zusammenstellung (Banner/Help/Skill-Assembly) plus moegliche Rest-Leaks in spaeten Registrierungs-/Menuelayern.

---

## Part E - Readiness judgment

`partially_effective`

Begruendung:

- Sicherheitsreduktion ist erkennbar (mehrere High-Risk-Flaechen verschwunden),
- aber Runtime-Sichtflaeche ist weiterhin nicht konsistent mit first-safe und bleibt ueberexponiert.

---

## Part F - One exact next recommendation

`Implement one final first-safe surface cleanup next`

---

## Cleanup linkage (v2.8)

Die umgesetzte finale Surface-Bereinigung ist dokumentiert in:

- `docs/powerunits_runtime_cleanup_v1.md`

