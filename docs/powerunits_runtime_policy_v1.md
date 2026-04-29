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

### 1) Allowed now (Telegram toolsets, first-safe Stand)

- Telegram als einzige aktive Messaging-Plattform
- Eng zugelassene Toolsets (siehe `apply_powerunits_runtime_policy.py` / `model_tools.py`): `memory`, `session_search`, `todo`, `powerunits_docs`, `powerunits_github_docs`, `powerunits_workspace` (ohne `clarify` im Telegram-first-safe Pfad)
- Session Search (read-only conversation recall)
- Manifest-keyed Powerunits-Doku (`read_powerunits_doc` auf gebündeltem `docker/powerunits_docs/`)
- Todo/Plan-Orchestrierung ohne breite Mutations-/File-/Repo-Tools

### 2) Installed but disabled / not exposed now

- Browser-Tooling
- Delegation/Subagents
- Cron-Operations
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
   - `docker/apply_powerunits_runtime_policy.py` (setzt u. a. `model.api_mode: chat_completions`, `agent.reasoning_effort: none` fuer OpenAI-first-safe)
2. Entrypoint-Hook:
   - `docker/entrypoint.sh` ruft Policy an, wenn
     - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
3. Docker Runtime default:
   - `Dockerfile` setzt
     - `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`

### Effekt der Policy

- `platform_toolsets.telegram` wird auf eine enge Allowlist gesetzt:
  - `memory`, `session_search`, `todo`, `powerunits_docs`, `powerunits_github_docs`, `powerunits_workspace`
  - (Historisch: `skills` / `no_mcp` / `clarify` — `clarify` entfernt wegen fehlendem Gateway-Callback und Modell-Loops.)
- Alle anderen relevanten Plattformen werden toolset-seitig auf `[]` gesetzt.
- Plattform-Exposure:
  - `platforms.telegram.enabled = true`
  - andere Plattformen `enabled = false`
- `approvals.mode = manual`, `approvals.cron_mode = deny`
- `command_allowlist = []`
- **OpenAI wire (Hermes v0.11+ / Railway):** `model.api_mode: chat_completions` und `agent.reasoning_effort: none` werden erzwungen (Policy-Skript + Gateway-Lockdown bei `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`). **Warum:** Auf direktem `https://api.openai.com/v1` lehnen GPT-4.x-Modelle Responses-Payloads mit ``include: ["reasoning.encrypted_content"]`` mit HTTP 400 ab; Telegram bricht dann **vor** Tool-Ausfuehrung ab. **Wann spaeter `codex_responses`:** sobald der Betrieb bewusst auf GPT-5+ (oder einen anderen Anbieter) wechselt, der die Responses-/Reasoning-Pipeline unterstuetzt — dann Policy anpassen oder Lockdown-Env deaktivieren und Modell/``api_mode`` explizit setzen.

Zusaetzlich (Gateway-Prozess): Bei aktivem `HERMES_POWERUNITS_RUNTIME_POLICY` wendet `gateway/run.py::_apply_powerunits_runtime_lockdown_to_user_config` dieselben `model`/`agent`-Werte auf die geladene User-Config an (sichtbare Konsistenz mit der Container-Policy).

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

## Final enforcement linkage (v2.6b)

- `docs/powerunits_runtime_enforcement_v2.md`

## Post-enforcement verification linkage (v2.7)

- `docs/powerunits_runtime_verification_v2.md`

## Final cleanup linkage (v2.8)

- `docs/powerunits_runtime_cleanup_v1.md`

## First safe Telegram review linkage (v3.0)

- `docs/powerunits_first_safe_telegram_review_v1.md`

## Docs allowlist integration linkage (v3.5)

- `docs/powerunits_docs_allowlist_integration_v1.md`

## Docs reader linkage (v3.7)

- `docs/powerunits_docs_reader_v1.md`

## Bundled docs freshness linkage

- `docs/powerunits_docs_freshness_v1.md`
