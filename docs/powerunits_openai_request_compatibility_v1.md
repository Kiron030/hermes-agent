# Powerunits OpenAI Request Compatibility v1

## Before editing restatement

Telegram funktioniert.

Runtime-Safety funktioniert.

Provider-Routing funktioniert jetzt (OpenAI-first, `custom` + `https://api.openai.com/v1` + `gpt-4.1-mini`).

Der verbleibende Blocker war OpenAI-Request-Kompatibilitaet: HTTP 400 mit Parameter `include` / Meldung zu **encrypted content**, weil der Responses-Pfad Felder sendete, die das gewaehlte Modell nicht unterstuetzt.

---

## Part A — Payload root cause

### Wo `include` gesetzt wird

Im Codex-/Responses-Pfad baut `run_agent.AIAgent._build_api_kwargs()` fuer `api_mode == "codex_responses"` ein OpenAI-**Responses**-Payload.

Bei aktiviertem Reasoning (`reasoning_config` aus Gateway/Config) wurde fuer die Standard-Zweige gesetzt:

- `reasoning: { effort, summary: "auto" }`
- `include: ["reasoning.encrypted_content"]`

Siehe `run_agent.py` im Block fuer `self.api_mode == "codex_responses"` (unmittelbar vor dem Chat-Completions-Fallback).

### Warum „encrypted content“

`reasoning.encrypted_content` ist ein **Responses-API**-Feature fuer Modelle mit verschluesselter Reasoning-Pipeline (v. a. GPT-5-Familie auf OpenAI). GPT-4.x auf `api.openai.com` lehnt diese `include`-Werte mit 400 ab.

### Modell- vs. Endpoint- vs. Request-Shape

- **Nicht** primaer ein reines Auth-Problem (nach v3.3).
- **Request-shape-spezifisch**: derselbe Endpoint `https://api.openai.com/v1` akzeptiert je nach Modell unterschiedliche Responses-Felder.
- Zusaetzlich war **api_mode** fuer `api.openai.com` URL-basiert zu aggressiv auf `codex_responses` gesetzt (`hermes_cli/runtime_provider._detect_api_mode_for_url`), obwohl GPT-4.x stabil ueber **Chat Completions** (`/v1/chat/completions`) laeuft.

### First-safe

Das Weglassen inkompatibler `include`/`reasoning`-Felder fuer GPT-4.x auf direktem OpenAI ist **first-safe**: keine neue Capability, nur Korrektur der API-Konformitaet.

---

## Part B — Smallest compatible fix (implemented)

1. **`hermes_cli/runtime_provider.py` — `_detect_api_mode_for_url`**
   - Kein automatisches `codex_responses` mehr nur wegen `api.openai.com`.
   - GPT-5+ bleibt modellgetrieben: Upgrade passiert in `run_agent.AIAgent.__init__` ueber `_provider_model_requires_responses_api` (bestehende Logik).

2. **`run_agent.py` — `AIAgent.__init__`**
   - Auto-Upgrade Chat Completions → Responses **nur** noch wenn `_provider_model_requires_responses_api(...)` (z. B. `gpt-5*`), nicht mehr schlicht wegen direkter OpenAI-URL.

3. **`run_agent.py` — `_build_api_kwargs` (Codex-Zweig)**
   - Zusaetzlicher Schutz: bei **direktem** `api.openai.com` und Modellen **ohne** GPT-5-Prefix werden `reasoning` und `include: reasoning.encrypted_content` weggelassen (`include` leer).

4. **Tests**
   - `tests/hermes_cli/test_detect_api_mode_for_url.py` angepasst.
   - `tests/run_agent/test_run_agent_codex_responses.py` um Abdeckung fuer GPT-4.1-mini / GPT-5 auf OpenAI ergaenzt.

---

## Part C — Operator expectations

### Logs nach Erfolg

- Erwartete Modus-Zeilen haengen vom gewaehlten Modell ab:
  - **GPT-4.1-mini** auf direktem OpenAI: effektiv **chat completions** (kein `/v1/responses` fuer den Hauptturn, sofern nicht manuell `api_mode: codex_responses` gesetzt).
  - **GPT-5.x**: Weiterhin **Responses** (`codex_responses`) mit kompatiblen Reasoning-Feldern.

### Erste erfolgreiche Telegram-Antwort

- Normale Textantwort des Bots ohne HTTP-400 in Railway-Logs.
- Keine wiederholten Fehler zu `include` / `encrypted content`.

### Railway-Umgebung

- **Keine** zusaetzlichen Railway-Variablen fuer diesen Fix noetig.
- Bestehendes `OPENAI_API_KEY` + Powerunits-`config.yaml` (Policy) reichen.

---

## Part D — One exact next recommendation

`Redeploy Hermes after OpenAI request compatibility fix next`

---

## Verknuepfung

Siehe auch: `docs/powerunits_primary_provider_routing_v1.md` (OpenAI-first Routing v3.3).
