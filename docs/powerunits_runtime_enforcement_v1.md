# Powerunits Runtime Enforcement v1 (First-Safe Lockdown)

## Before editing restatement

Der Policy-Hook wird ausgefuehrt (`[powerunits-policy] applied first_safe_v1 ...`), aber die Live-Runtime-Surface bleibt zu breit.

Der Blocker ist jetzt **Enforcement**, nicht Policy-Intent.

---

## Part A - Root-cause diagnosis

### Was die finale Surface wirklich steuert

1. **Plattform-Exposure (connect/disconnect):**
   - wird in `gateway/config.py` durch `load_gateway_config()` + `_apply_env_overrides()` bestimmt.
   - `_apply_env_overrides()` aktiviert Plattformen erneut aus Env-Variablen (z. B. `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`, `HASS_TOKEN`), auch wenn `config.yaml` sie deaktiviert.

2. **Callable Toolsets pro Plattform:**
   - werden in `gateway/run.py` ueber `_load_gateway_config()` + `_get_platform_tools(...)` aufgeloest und an `AIAgent(enabled_toolsets=...)` uebergeben.

3. **Bundled Skills Surface:**
   - wird bei Start ueber `tools/skills_sync.py` in `~/.hermes/skills` synchronisiert (Entrypoint + Gateway-Start).
   - Skill-Slash-Commands werden in `gateway/run.py` zusaetzlich ueber `get_skill_commands()` exponiert.

### Warum die bisherige Policy nicht ausreichte

- Die bisherige Policy schrieb `config.yaml` korrekt um, war aber nicht der letzte autoritative Layer:
  - Env-Overrides in `gateway/config.py` konnten Plattform-Aktivierung wieder oeffnen.
  - Bundled-Skill-Sync und Skill-Slash-Command-Pfade konnten weiterhin breite Skill-Surface sichtbar machen.
- Ergebnis: Policy vorhanden, aber nicht hart genug gegen spaetere Runtime-Resolver.

---

## Part B - Enforced first-safe surface (implementiert)

### 1) Harte Plattform-Lockdown-Enforcement

In `gateway/config.py`:

- Neue Powerunits-Lockdown-Erkennung fuer `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`.
- Nach Env-Overrides wird eine fail-closed Korrektur angewendet:
  - alle Plattformen ausser Telegram werden explizit `enabled = false`,
  - Telegram bleibt als einzige aktivierbare Plattform.

Damit kann ein gesetztes Token fuer andere Plattformen die Surface nicht mehr wieder oeffnen.

### 2) Harte Toolset-Enforcement am Runtime-Resolver

In `gateway/run.py`:

- `_load_gateway_config()` wird unter Policy auf fail-closed Toolset-Werte normalisiert.
- Die effektiv aufgeloesten Toolsets werden zusaetzlich zur Laufzeit gefiltert.
- Telegram-Only allowlist fuer first-safe:
  - `memory`
  - `session_search`
  - `todo`
  - `clarify`
- Kein Browser, kein Code-Execution, kein File-Mutation-Toolset, keine Delegation, kein Cron, kein MCP.

### 3) Skill-Surface-Lockdown

In `docker/entrypoint.sh` und `gateway/run.py`:

- Bundled-Skill-Sync wird in first-safe deaktiviert.
- Skill-Slash-Commands werden in first-safe nicht exponiert.
- `/help` und `/commands` zeigen in first-safe keine Skill-Command-Liste.

Damit wird breite Skill-Exposure (inkl. GitHub-/MCP-/Subagent-bezogener Skillnamen) fail-closed reduziert.

### 4) Policy-Allowlist angepasst

In `docker/apply_powerunits_runtime_policy.py`:

- Telegram-Allowlist auf first-safe Kernflaeche reduziert:
  - entfernt: `skills`, `no_mcp`
  - gesetzt: `memory`, `session_search`, `todo`, `clarify`

---

## Part C - Fail-closed posture

Bei Ambiguitaet wurde „nicht exponieren“ umgesetzt:

- Skill-Sync off in first-safe
- Skill-Slash-Commands off in first-safe
- Plattformen ausser Telegram hard-disabled nach Env-Overrides
- Runtime-Toolsets final gefiltert (nicht nur advisory in YAML)

---

## Part D - Railway implications (minimal)

Nach diesem Repo-Change ist fuer Railway nur noetig:

1. Redeploy des Services aus dem aktualisierten Fork/Branch.
2. Sicherstellen, dass `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1` gesetzt bleibt.

Keine neuen Secrets, keine neuen Volumes, keine DB-Aenderung, keine neuen externen Integrationen.

---

## Part E - One exact next recommendation

`Redeploy Hermes with enforced first-safe runtime lockdown next`

