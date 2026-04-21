# Powerunits Runtime Enforcement v2 (Final Surface Lockdown)

## Before editing restatement

Der Policy-Hook laeuft, aber die Live-Surface ist weiterhin klar ueberexponiert.

Der Blocker ist die **finale Runtime-Registrierung/Exposure-Ebene**, nicht Policy-Intent.

---

## Part A - True final registration path

### 1) Finale Tool-Liste ("Available tools")

Die finale, fuer Agent-Calls relevante Tool-Liste wird in `model_tools.get_tool_definitions(...)` gebaut.

- Dort werden Toolsets auf konkrete Toolnamen aufgeloest.
- Danach filtert die Registry per `check_fn`.
- Dieses Ergebnis wird als finale callable Surface an `AIAgent` geliefert.

Wichtig: Fruehere YAML-/Platform-Filter sind nur vorgelagerte Inputs. Entscheidend ist die letzte Selektion in `get_tool_definitions(...)`.

### 2) Bundled Skills / Skill-Commands

- Bundled Skills werden ueber `tools/skills_sync.py` in den Runtime-Skill-Pfad synchronisiert.
- Skill-/Plugin-Command-Exposure fuer Messaging-Menues wird in `hermes_cli/commands.py` aufgebaut (`telegram_menu_commands`/Skill-Collector).
- In `gateway/run.py` werden Skill-Commands zusaetzlich im Slash-Dispatch verarbeitet.

### 3) Warum v1 noch Rest-Exposure erlaubte

- v1 hat Plattform- und Gateway-Toolset-Layer gehaertet, aber die letzte globale Tool-Registry-Selektion war noch nicht policy-hart gekappt.
- Zusaetzlich konnten Skill-/Plugin-Menuepfade weiterhin Runtime-Command-Surface sichtbar machen.

---

## Part B - Final first-safe enforcement (implementiert)

### 1) Harte finale Tool-Registry-Kappung

In `model_tools.py`:

- Bei `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` wird in `get_tool_definitions(...)` die Toolmenge final per Intersection auf die first-safe Allowlist begrenzt.
- Allowlist-basiert (ueber Toolsets): `memory`, `session_search`, `todo`, `clarify`, `powerunits_docs`.

Effekt: Auch wenn ein spaeter Layer breite Toolsets anfordert, bleibt die final callable Surface hard-capped.

### 2) Harte Skill-/Plugin-Menue-Kappung fuer Messaging

In `hermes_cli/commands.py`:

- `_collect_gateway_skill_entries(...)` liefert unter first-safe keine Skill-/Plugin-Entries mehr.

Effekt:

- keine breite Skill-Slash-Exposure in Telegram/Discord-Menues,
- keine GitHub-/Subagent-/Codex-/Claude-Code Skill-Command-Sichtbarkeit aus diesem Pfad.

### 3) Bereits bestehende v1-Layer bleiben aktiv

- Plattform-Lockdown in `gateway/config.py` (nur Telegram enabled).
- Gateway-seitige Toolset-Enforcement und Skill-Command-Dispatch-Gating in `gateway/run.py`.
- Skill-Sync-Deaktivierung fuer first-safe in `docker/entrypoint.sh`.

---

## Part C - Help/banner/command consistency

Konsistenz fuer first-safe wurde auf den relevanten Runtime-Surfaces gehaertet:

- finale callable Tool-Registry (via `model_tools.get_tool_definitions`) ist hard-capped,
- Gateway `/help` und `/commands` zeigen keine Skill-Command-Liste im first-safe Modus,
- Messaging-Menues bekommen keine Skill-/Plugin-Command-Eintraege aus dem zentralen Collector.

---

## Part D - Railway implications

Minimal:

1. Nur Redeploy nach diesen Repo-Aenderungen.
2. `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` gesetzt lassen.

Keine weiteren Railway- oder Secret-Aenderungen erforderlich.

---

## Part E - One exact next recommendation

`Redeploy Hermes after final runtime surface enforcement next`

---

## Post-enforcement verification linkage (v2.7)

Die Verifikation nach Redeploy inkl. Mismatch-Analyse ist dokumentiert in:

- `docs/powerunits_runtime_verification_v2.md`

## Final cleanup linkage (v2.8)

- `docs/powerunits_runtime_cleanup_v1.md`

