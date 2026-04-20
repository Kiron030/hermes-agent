# Powerunits Runtime Policy v1 (Tiered First-Deployment Safety)

## Before editing context

Der aktuelle Blocker ist Runtime-Over-Permissioning, nicht Build/Start.  
Das Ziel ist daher kontrollierte Capability-Shaping fuer den ersten Live-Betrieb, nicht komplettes De-Powering von Hermes.

---

## Part A - Runtime surface diagnosis

### Warum die breite Standardoberflaeche sichtbar ist

- Standard-Toolsets fuer Messaging (z. B. `hermes-telegram`) sind sehr breit und enthalten u. a.:
  - `terminal`/`process`
  - Browser-Tools
  - `execute_code`
  - `delegate_task`
  - Web-/Image-/MCP-nahe Funktionalitaet
- Diese Defaults werden ueber `platform_toolsets` aufgeloest.
- Gebuendelte Skills werden beim Start nach `HERMES_HOME/skills` synchronisiert.

### Was sauber restriktierbar ist

- Plattform-Toolsets pro Plattform (`platform_toolsets`) -> gut fuer fail-closed.
- Plattform-Exposure (`platforms.<name>.enabled`) -> klar steuerbar.
- Approval-Verhalten (`approvals`) und `command_allowlist`.

### Was bewusst nicht tief umgebaut wurde

- Keine Entfernung von Tool-Implementierungen.
- Keine dauerhafte Entfernung von Skills.
- Keine invasive Aenderung der Agent-Kernlogik.

---

## Part B - Tiered policy

### 1) Allowed now

- Telegram als einzige aktive Messaging-Plattform
- Core Conversation + Memory
- Session Search (read-only conversation recall)
- Skills read/list/view
- Todo/Plan-Orchestrierung ohne Mutations-Tools

### 2) Installed but disabled / not exposed now

- Browser-Tooling
- Delegation/Subagents
- Cron-Operations
- GitHub-nahe Faehigkeiten
- File write/patch pathways
- Discord/Slack/Email/weitere Messaging-Plattformen
- MCP-/weitere externe Integrationen
- Web-Scraping/Search-Toolsets

### 3) Forbidden now

- Code execution
- Shell/SSH/Docker exec
- Write-faehige DB-Zugaenge
- Infra/Deploy/Worker/Bucket control
- Unrestricted filesystem mutation
- Autonomous multi-step operational mutation paths

---

## Part C - Implemented smallest restriction mechanism

Implementiert wurde eine kleine policy-basierte Laufzeit-Restriktion:

1. Neues Policy-Skript:
   - `docker/apply_powerunits_runtime_policy.py`
2. Entrypoint-Hook:
   - `docker/entrypoint.sh` ruft Policy an, wenn
     - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
3. Docker Runtime default:
   - `Dockerfile` setzt
     - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`

### Effekt der Policy

- `platform_toolsets.telegram` wird auf eine enge Allowlist gesetzt:
  - `memory`, `session_search`, `skills`, `todo`, `no_mcp`
- Alle anderen relevanten Plattformen werden toolset-seitig auf `[]` gesetzt.
- Plattform-Exposure:
  - `platforms.telegram.enabled = true`
  - andere Plattformen `enabled = false`
- `approvals.mode = manual`, `approvals.cron_mode = deny`
- `command_allowlist = []`

Fail-closed:

- Policy wird bei Containerstart wieder angewendet (keine einmalige Best-Effort-Konfiguration).

---

## Part D - Railway/runtime implications

Nach diesem Repo-Change in Railway:

1. Keine neuen Secrets erforderlich.
2. Sicherstellen, dass der Service weiterhin:
   - getrenntes Projekt/Service nutzt
   - Volume auf `/opt/data` gemountet hat
3. Env fuer Policy ist bereits im Dockerfile gesetzt:
   - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
   - optional in Railway explizit sichtbar setzen/ueberschreiben, falls gewuenscht
4. Telegram/Provider-Minimalvertrag unveraendert lassen.

---

## Part E - One exact next recommendation

`Redeploy Hermes with the tiered first-safe runtime policy next`

---

## Post-policy verification linkage (v2.5)

Die nachgelagerte Runtime-Verifikation (inkl. Effektivitaetseinstufung und Rest-Blocker) ist dokumentiert in:

- `docs/powerunits_runtime_verification_v1.md`
