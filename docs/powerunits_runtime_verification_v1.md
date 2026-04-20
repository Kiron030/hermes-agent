# Powerunits Runtime Verification v1 (Post-Policy Runtime)

## Before editing restatement

Der aktuelle Task ist **Runtime-Verifikation**, nicht Capability-Expansion.

Es werden keine neuen Tools, keine DB-Integration und keine Erweiterungen der erlaubten Surface eingefuehrt.

---

## Scope

Diese Verifikation bewertet den ersten Live-Stand **nach Redeploy** mit aktivierter Policy:

- `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`
- `docker/apply_powerunits_runtime_policy.py`
- `docker/entrypoint.sh`

---

## Part A - Runtime verification

### Verfuegbare Runtime-Evidenz

Im lokalen Arbeitskontext liegt derzeit **kein post-redeploy Railway-Startup-/Runtime-Logauszug** vor, der die zur Laufzeit aufgeloeste Tool-Surface direkt zeigt.

Vorliegende Evidenz:

1. Repo-seitige Aktivierung ist klar vorhanden:
   - `Dockerfile` setzt `HERMES_POWERUNITS_RUNTIME_POLICY=first_safe_v1`.
   - `entrypoint.sh` ruft die Policy-Anwendung beim Start auf.
   - `apply_powerunits_runtime_policy.py` schreibt fail-closed Werte in `config.yaml`.
2. Branch-/Deploy-Vorbereitung ist aktualisiert und gepusht (`powerunits-internal-setup`), aber ohne beigefuegten Live-Tool-Inventory-Snapshot.

### Erwartete Surface nach Policy (Soll-Zustand)

- Sichtbar bleiben (Telegram):
  - `memory`, `session_search`, `skills`, `todo`, `no_mcp`
- Nicht mehr exposed:
  - Browser-/Execution-/Delegation-/MCP-nahe Toolsets
  - weitere Messaging-Plattformen ausser Telegram
- Telegram-first / single-user-first:
  - Telegram bleibt einzige aktive Plattform
  - User-Zugriff bleibt ueber `TELEGRAM_ALLOWED_USERS` eng begrenzt

### Ist-Zustand (belegt vs. unbelegt)

- **Belegt:** Policy-Mechanik ist beim Startpfad wirksam verdrahtet (Repo-seitig).
- **Nicht belegt mit Live-Log:** finale Laufzeit-Toolliste direkt aus dem redeployten Railway-Prozess.

---

## Part B - Policy effectiveness

Einstufung: **partially effective**

Begruendung:

- Positiv: Die Policy ist technisch sauber und fail-closed in den Startup-Pfad integriert.
- Einschränkung: Ohne post-redeploy Runtime-Evidenz (Tool-Inventory/Startup-Snapshot) ist die tatsaechliche Live-Exposition nicht abschliessend verifiziert.

---

## Part C - Remaining blocker

Dominanter Blocker fuer vollstaendige Verifikation:

- Fehlender Live-Nachweis der **tatsaechlich aufgeloesten** Tool-Surface nach Redeploy (Startup-/Runtime-Log mit sichtbarer Tool-/Platform-Aufloesung).

---

## Part D - One exact next recommendation

`Proceed to first safe Telegram interaction next`

