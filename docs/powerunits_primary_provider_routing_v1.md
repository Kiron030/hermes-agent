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
  - `model.default = "gpt-4.1"`
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

---

## OpenAI request compatibility linkage (v3.4)

Nach erfolgreichem OpenAI-first Routing kann ein weiterer Fehler auftreten:

- HTTP 400, Parameter `include`, Meldung zu **encrypted content** / nicht unterstuetzt fuer das Modell.

Fix und Diagnose: `docs/powerunits_openai_request_compatibility_v1.md`

---

## Part G — `max_tokens`-Limit-Mismatch bei "custom" auf echtem OpenAI (v3.5, 2026-07-02, Vorfall Teil 5)

### Symptom

Nach erfolgreichem Boot (kein `PermissionError`, kein `ModuleNotFoundError`) meldete Telegram bei der allerersten, winzigen Nachricht ("hey bist du da?"):

```
🗜️ Context too large (~5,419 tokens) — compressing (1/3)...
⚠️ Context length exceeded (5,419 tokens). Cannot compress further.
⚠️ Session auto-reset ...
```

`/opt/data/logs/agent.log` zeigte den echten Fehler:

```
WARNING agent.conversation_loop: API call failed (attempt 1/3) error_type=BadRequestError
provider=custom base_url=https://api.openai.com/v1 model=gpt-4.1
summary=HTTP 400: max_tokens is too large: 65536. This model supports at most
32768 completion tokens, whereas you provided 65536.
```

### Root Cause

`plugins/model-providers/custom/__init__.py` — `CustomProfile` setzt
`default_max_tokens=65536` als **generischer** Floor fuer lokale/Ollama-artige
Backends (verhindert `num_predict=128`-Truncation, #39281). Dieser Default
wird unbedingt gesendet, sobald der User (bzw. hier: die Powerunits-Policy
`first_safe_v1`) kein explizites `model.max_tokens` gesetzt hat
(`agent/transports/chat_completions.py::_build_kwargs_from_profile`,
Prioritaet `ephemeral > user_max > profile_max`).

Das Problem: "custom" ist ein **generischer Alias**, der sowohl lokale
Ollama/vLLM/llama.cpp-Server ALS AUCH echte gehostete OpenAI-kompatible
Endpoints abdeckt (siehe Part C dieses Dokuments — Powerunits zeigt
`provider="custom"` bewusst auf `https://api.openai.com/v1`). Der generische
65536-Default beruecksichtigte nicht, dass echtes OpenAI fuer `gpt-4.1-mini`
ein hartes Limit von **32768** Completion-Tokens durchsetzt und alles
darueber mit HTTP 400 ablehnt.

Der 400er enthaelt den String `"max_tokens"`, der in
`agent/error_classifier.py::_CONTEXT_OVERFLOW_PATTERNS` gelistet ist —
dadurch wurde der Fehler als `context_overflow` klassifiziert. Da die Session
zu diesem Zeitpunkt winzig war (System-Prompt + eine kurze Nachricht), konnte
`_compress_context()` beim ersten Versuch nichts kuerzen, wodurch Hermes
sofort mit "Cannot compress further" aufgab und die Session zurueckgesetzt
hat — obwohl die wahre Ursache nichts mit der Kontextgroesse zu tun hatte.

(Randnotiz: die zuvor untersuchte Hypothese eines veralteten
`context_length_cache.yaml`-Eintrags hat sich als falsch herausgestellt —
die Datei existierte auf dem Volume gar nicht. Der echte Fehler war rein
ein `max_tokens`-Limit-Mismatch, siehe oben.)

### Fix (implementiert)

1. **`agent/model_metadata.py`** — neue Tabelle
   `OPENAI_DIRECT_MAX_COMPLETION_TOKENS` (`gpt-4.1-mini`, `gpt-4.1`,
   `gpt-4.1-nano` → 32768) + Helper `get_openai_direct_max_completion_tokens()`
   (Longest-Prefix-Match, analog zu `DEFAULT_CONTEXT_LENGTHS`).
2. **`providers/base.py`** — `ProviderProfile.get_max_tokens()` erhaelt ein
   optionales `base_url`-Keyword (Default `None`, abwaertskompatibel), damit
   Profile, die als Alias fuer mehrere echte Backends dienen, diese anhand
   der URL unterscheiden koennen.
3. **`plugins/model-providers/custom/__init__.py`** — `CustomProfile`
   ueberschreibt `get_max_tokens()`: zeigt `base_url` auf `api.openai.com`,
   wird der reale Cap aus der neuen Tabelle verwendet statt des generischen
   65536-Defaults; bei unbekannten Modellen (z.B. `gpt-5.4`, die bereits
   `max_completion_tokens` korrekt erzwingen) bleibt der generische Default
   als Fallback erhalten. Lokale/Ollama-Backends sind unveraendert.
4. **`plugins/model-providers/opencode-zen/__init__.py`** —
   `OpenCodeGoProfile.get_max_tokens()`-Signatur um das neue `base_url`-Keyword
   ergaenzt (sonst `TypeError` durch den neuen Call-Site-Parameter).
5. **`agent/transports/chat_completions.py`** — Call-Site leitet
   `base_url=params.get("base_url")` an `profile.get_max_tokens()` weiter.
6. **`agent/model_metadata.py::parse_available_output_tokens_from_error()`** —
   zusaetzliches Pattern fuer OpenAI's exakte Fehler-Formulierung
   (`"supports at most (\d+) completion tokens"`). Dadurch wird dieser
   Fehlertyp — auch fuer Modelle, die (noch) nicht in der obigen Tabelle
   stehen — nicht mehr blind als "Prompt zu lang" (Kompressions-Loop, endet
   in "Cannot compress further") behandelt, sondern korrekt als
   "Output-Cap zu hoch" erkannt und automatisch mit reduziertem `max_tokens`
   wiederholt (bestehende Logik in `agent/conversation_loop.py`, Zeilen
   ~2971-3002 — kein Retry-Code noetig, nur die Erkennung wurde ergaenzt).
   Die grobe `context_overflow`-Klassifizierung in `error_classifier.py`
   wurde bewusst NICHT angefasst (Scope-Begrenzung; siehe Empfehlung unten).

### Tests

`tests/providers/test_provider_profiles.py::TestCustomProfile`,
`tests/agent/transports/test_chat_completions.py`
(`test_custom_provider_on_real_openai_caps_to_model_limit` u.a.),
`tests/agent/test_model_metadata.py::TestOpenAIDirectMaxCompletionTokens`,
`tests/test_output_cap_parsing.py::TestParseOpenAIDirectOutputCap`.

### Offener Punkt (bewusst NICHT umgesetzt, um den Scope zu begrenzen)

`error_classifier.py` klassifiziert 400er mit `"max_tokens"` im Fehlertext
weiterhin pauschal als `context_overflow` (nicht als eigene Kategorie). Das
ist unkritisch, weil `parse_available_output_tokens_from_error()` das
OpenAI-Format jetzt VOR jeder Kompression abfaengt und stattdessen einen
gezielten Retry mit reduziertem `max_tokens` ausloest — der eigentliche Bug
(Session-Reset auf kurzen Sessions) ist damit behoben. Eine sauberere
Langfrist-Loesung waere ein eigener `FailoverReason.output_cap_too_large`
in `error_classifier.py`, um die Doppel-Klassifizierung + nachgelagerte
Diskriminierung in `conversation_loop.py` in einen einzigen Schritt zu
konsolidieren — als Refactoring fuer einen separaten, kleineren PR
vorgeschlagen, nicht Teil dieses Incident-Fixes.

### Redeploy

Kein manueller Schritt auf Railway noetig ausser dem Redeploy selbst — keine
neue Env-Var, keine Volume-Aenderung.

