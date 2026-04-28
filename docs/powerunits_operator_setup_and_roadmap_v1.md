# Powerunits Hermes Setup & Roadmap v1

## A) Current state (first-safe internal)

### Was aktuell funktioniert

- Railway-Deployment ist stabil.
- Telegram-Zugriff funktioniert.
- first-safe Runtime-Posture ist aktiv.
- Allowlisted private GitHub read surfaces funktionieren (alias-gesteuert).
- Bounded persistent Workspace auf Railway-Volume funktioniert.
- Docs-to-workspace Roundtrip funktioniert:
  1. Quelle lesen
  2. Zusammenfassen
  3. in Workspace speichern
  4. wieder aus Workspace lesen

### Was bewusst deaktiviert bleibt

- kein GitHub-Write (`POWERUNITS_GITHUB_TOKEN_WRITE` ungenutzt)
- kein DB-Zugriff
- kein breites privates Repo-Browsing
- keine generischen File-Write-Pfade ausserhalb des bounded Workspace

### Bedeutung von first-safe

- nur explizit allowgelistete Toolsets
- fail-closed bei fehlender Voraussetzung (Token, Bundle, Alias, Pfad)
- klare Grenzen statt impliziter „Best effort“-Escapes

---

## B) Current operator workflow

### 1) Read surfaces verwalten

Datei: `config/powerunits_github_knowledge.json`

Pro Surface:

- `alias`
- `repo`
- `branch`
- `root_prefix`
- `allowed_extensions`
- `enabled`

Hinzufuegen/entfernen:

1. Surface in `surfaces` ergaenzen oder `enabled=false` setzen.
2. Deployen.
3. In Telegram mit Alias testen (`list_powerunits_roadmap_dir(alias=...)`, `read_powerunits_roadmap_file(alias=..., name=...)`).

### 2) Telegram-Nutzung (read -> summarize -> save)

Empfohlener Operatorfluss:

1. Datei in allowlist-Surface lesen (`alias` + `name`).
2. knappe, operator-taugliche Zusammenfassung erzeugen.
3. Ergebnis in Workspace speichern (`save_hermes_workspace_note`).
4. Speicherpfad bestaetigen.

### 3) Workspace-Nutzung

Root: `/opt/data/hermes_workspace`

Allowlisted Subdirs:

- `analysis`
- `notes`
- `drafts`
- `exports`

Railway-Volume liefert Persistenz ueber Deploys hinweg.

---

## C) Risks and boundaries

### Read token vs write token

- Read-Pfad nutzt `POWERUNITS_GITHUB_TOKEN_READ` (legacy fallback kompatibel).
- Write-Token bleibt ungenutzt.

### Warum GitHub write vorerst nicht

- Write-Flows erhoehen Risiko (Repo-Mutation, Review-Bypass, Incident-Blast-Radius).
- Aktueller Fokus: sichere interne Assistenz mit dokumentierter Nachvollziehbarkeit.

### Warum zuerst Railway-Workspace statt Repo-Write

- klare Blast-Radius-Grenze auf `/opt/data/hermes_workspace`
- keine Auswirkungen auf Produktrepo-Branches
- einfache Operabilitaet/Debugbarkeit bei minimalem Risiko

### Warum broad repo access vermieden wird

- minimiert Secret-/Scope-Risiken
- verhindert Tool-Surface-Drift
- erhaelt deterministische, reviewbare Operator-Pfade

---

## D) Future roadmap (staged, realistic)

1. **Mehr allowlisted read surfaces**  
   Additiv ueber Alias-Config, ohne freie Repo-Wahl.

2. **Bessere docs-to-workspace Workflows**  
   bessere Vorlagen, konsistente kurze Operator-Ausgaben, weniger Prompt-Reibung.

3. **Suche ueber allowlisted sources**  
   nur innerhalb erlaubter Aliase/Roots, weiterhin read-only.

4. **Exportpfad aus Workspace in dediziertes privates Output-Repo**  
   spaeter, streng kontrolliert, explizit reviewed.

5. **Bounded read-only DB facades**  
   nur selektive, stabile Read-Views; keine Writes.

6. **Cross-source Synthesis**  
   erlaubte Docs + Workspace kombiniert, mit klarer Quellenangabe.

7. **Controlled code-adjacent analysis**  
   spaeter nur ueber eng allowgelistete, read-only Sichten.

8. **Operator-reviewed automation**  
   Automationsschritte nur mit klarer Freigabelogik.

9. **Selektive Delegation/Subagents spaeter**  
   begrenzt, beobachtbar, nur bei klaren Use-Cases.

10. **Browser/Web research spaeter nur isoliert**  
    strikt getrennte Umgebung, keine Scope-Vermischung mit internen Repos.

---

## E) Practical next steps

### Als naechstes bauen

1. 1–2 zusaetzliche hochwertige Read-Surfaces ueber Alias-Allowlist.
2. Vergleichs- und Zusammenfassungs-Pattern fuer docs-to-workspace standardisieren.
3. kurze Operator-Checklisten fuer Telegram-Validierung pro Surface.

### Explizit vermeiden (vorerst)

- GitHub write aktivieren
- broad private repo browsing
- DB write oder ungegrenzte DB reads
- generische File-Tools ausserhalb Workspace
- automatische infra-/deploy-mutations ohne Review
