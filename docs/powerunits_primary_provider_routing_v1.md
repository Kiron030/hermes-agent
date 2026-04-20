# Powerunits Primary Provider Routing v1

## Before editing restatement

Telegram funktioniert.

Runtime-Safety funktioniert.

Der aktuelle Fehler ist Provider-Routing-Mismatch.

---

## Part A - Actual provider selection path

### Wo der Provider gewaehlt wird

Der Runtime-Pfad geht ueber:

- `gateway/run.py` -> Runtime-Resolution
- `hermes_cli/runtime_provider.py` -> `resolve_runtime_provider(...)`
- `hermes_cli/auth.py` -> `resolve_provider(...)`

### Warum aktuell OpenRouter gewaehlt wurde

`resolve_provider(...)` mappt im `auto`-Fall vorhandenes `OPENAI_API_KEY` oder `OPENROUTER_API_KEY` auf `"openrouter"`:

- `OPENAI_API_KEY` vorhanden -> Provider `"openrouter"`

Damit ist "openrouter" im Code ein generischer OpenAI-kompatibler Einstiegspunkt fuer den Auto-Pfad, nicht zwingend nur OpenRouter als Vendor.

### Woher `anthropic/claude-opus-4.6` kommt

Das Modell kommt aus `config.yaml` `model.default`, initial aus `cli-config.yaml.example`:

- `model.default: "anthropic/claude-opus-4.6"`

### Gesamtursache

Kombination aus:

1. Default-Model auf OpenRouter-Katalog-ID (`anthropic/claude-opus-4.6`)
2. Auto-Provider-Resolution auf `"openrouter"`
3. Fehlendem `OPENROUTER_API_KEY`

Ergebnis: 401/Auth-Fehler trotz funktionierendem Telegram/Gateway.

---

## Part B - Canonical Powerunits short-term path

Gewaehlter canonical path:

- `openai_direct_first`

Kurzbegruendung:

- Railway hat bereits `OPENAI_API_KEY`.
- Kein zusaetzlicher Provider-Key noetig.
- Kleinster stabiler Schritt fuer internen Operator-Spike.

---

## Part C - Smallest fix implemented

Im Powerunits Runtime-Policy-Applier wurde die Primary-Route explizit und deterministisch gesetzt:

- Datei: `docker/apply_powerunits_runtime_policy.py`
- Erzwingt in `config.yaml`:
  - `model.default = "gpt-4.1-mini"`
  - `model.provider = "custom"`
  - `model.base_url = "https://api.openai.com/v1"`

Damit wird der Primary-Pfad auf OpenAI-direct ausgerichtet und nicht mehr implizit ueber OpenRouter-Defaults gesteuert.

---

## Part D - Railway env contract (operator)

### Required

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS`
- `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`

### Optional

- `OPENAI_BASE_URL` (nur falls bewusst non-standard OpenAI-kompatibler Endpoint gewuenscht)

### Unset/Remove if conflicting

- `OPENROUTER_API_KEY` (fuer diesen canonical Path nicht noetig; entfernt Verwirrung)
- `OPENROUTER_BASE_URL` (nicht noetig fuer openai_direct_first)
- `HERMES_INFERENCE_PROVIDER` (entfernen, falls auf `openrouter` oder anderes gesetzt)

---

## Part E - Auxiliary provider warning

Die Auxiliary-Warnung muss fuer v3.3 nicht zwingend sofort behoben werden.

Sie kann **deferred** werden, solange:

- Primary-Turns stabil laufen
- Telegram-Operator-Flow fuer first-safe intakt ist

Auxiliary-Coverage kann in einem separaten Schritt konsistent nachgezogen werden.

---

## Part F - One exact next recommendation

`Set the canonical provider env and redeploy next`

