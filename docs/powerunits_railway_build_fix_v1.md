# Powerunits Railway Build Fix v1 (Docker `VOLUME` Compatibility)

## Before editing context

Ein v2.4-Runtime-Review ist verfrueht, solange der Build auf Railway nicht durchlaeuft.  
Der aktuelle Task ist deshalb bewusst ein minimaler Railway-Kompatibilitaets-Patch.

---

## Part A - Exact blocker diagnosis

Der Build-Blocker war eindeutig:

- Datei: `Dockerfile`
- Zeile/Instruktion: `VOLUME [ "/opt/data" ]`
- Railway-Fehler: `The 'VOLUME' keyword is banned in Dockerfiles. Use Railway volumes instead.`

Gleichzeitig bleibt Repo-seitig klar:

- `HERMES_HOME=/opt/data` ist gesetzt (Dockerfile).
- Entrypoint nutzt `HERMES_HOME="${HERMES_HOME:-/opt/data}"` und bootstrapt State dort.
- `/opt/data` ist weiterhin der intendierte persistente Hermes-State-Pfad.

Es wurde kein weiterer Railway-spezifischer harter Dockerfile-Blocker identifiziert.

---

## Part B - Minimal safe fix

Angewandter Fix (minimal):

- `VOLUME [ "/opt/data" ]` aus `Dockerfile` entfernt.

Nicht veraendert:

- `ENV HERMES_HOME=/opt/data`
- `ENTRYPOINT [ "/opt/hermes/docker/entrypoint.sh" ]`
- Entrypoint-Logik fuer State-Bootstrap unter `HERMES_HOME`

Damit wird nur der Railway-Build-Blocker entfernt, ohne Runtime-/Scope-Ausbau.

---

## Part C - Post-fix deploy assumptions

Nach dem Fix gilt:

- Mount-Pfad bleibt `/opt/data`.
- Persistenz erfolgt ueber Railway-Volume-Mount (platformseitig), nicht ueber Dockerfile-`VOLUME`.
- Railway muss sicherstellen, dass ein persistentes Volume auf `/opt/data` gemountet ist.

Keine weiteren manuellen Repo-Aenderungen sind dafuer noetig.

---

## Part D - Validation scope

Leichte Validierung:

- Dockerfile-Blocker-Instruktion entfernt.
- `HERMES_HOME`-/Entrypoint-State-Pfad unveraendert auf `/opt/data`.
- Keine Runtime-Logik, keine Tools, keine Integrationen erweitert.

---

## Part E - One exact next recommendation

`Redeploy the Railway Hermes service from the Powerunits-controlled fork next`
