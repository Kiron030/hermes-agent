# Powerunits GitHub Docs Reader v1

## Scope

Kleinstmoegliche read-only GitHub-Dokuoberflaeche fuer Hermes:

- Repo: `Kiron030/Powerunits.io`
- Branch: `starting_the_seven_phases`
- Allowlisted roots are alias-driven from `config/powerunits_repo_read_allowlist.json`
  (e.g. `powerunits_roadmap -> docs/roadmap`, `powerunits_architecture -> docs/architecture`).

Keine Writes, keine Codepfade, keine freie Repo-/Branch-/Path-Wahl durch das Modell.

Operator-verwaltete Konfiguration:

- `config/powerunits_repo_read_allowlist.json`
- Modell waehlt nur per `alias`; repo/branch/root kommen ausschliesslich aus der Allowlist.

## Tools

- `list_powerunits_roadmap_dir(subpath?)`
- `read_powerunits_roadmap_file(name, max_output_chars?)`

Beide Tools akzeptieren optional `alias` (Default: `powerunits_roadmap`) und sind hart auf den allowgelisteten Root beschraenkt.

## Runtime env contract

- Pflicht: `POWERUNITS_GITHUB_TOKEN_READ`
  - Fine-grained read-only Token, minimal auf dieses eine private Repo begrenzt.
- Legacy fallback (nur Kompatibilitaet): `POWERUNITS_GITHUB_DOCS_TOKEN`
- Optional (trusted operator config, nicht modellgesteuert):
  - `POWERUNITS_GITHUB_DOCS_REPO` (Default `Kiron030/Powerunits.io`)
  - `POWERUNITS_GITHUB_DOCS_BRANCH` (Default `starting_the_seven_phases`)
  - `POWERUNITS_GITHUB_DOCS_ROOT` (Default `docs/roadmap`)

Wenn Token fehlt, wird das Toolset via `check_fn` nicht exponiert (fail-closed).

## Safety controls

- Modell kann repo/branch/root nicht zur Laufzeit waehlen.
- Alias muss in `config/powerunits_repo_read_allowlist.json` existieren und `enabled=true` sein.
- `subpath`/`name` Validierung:
  - kein `..`
  - keine absoluten Pfade
  - kein Root-Escape
- Lesen nur fuer `.md`/`.txt`.
- Keine Datei- oder Repo-Writes.

## Telegram validation prompts

1. `Nutze list_powerunits_roadmap_dir mit alias="powerunits_roadmap" und gib die Eintraege aus.`
2. `Nutze list_powerunits_roadmap_dir mit alias="powerunits_architecture" und gib die Eintraege aus.`
3. `Lies je eine .md-Datei aus alias="powerunits_roadmap" und alias="powerunits_architecture"; speichere eine Vergleichsanalyse unter analysis als "roadmap_vs_architecture.md".`
4. `Versuche read_powerunits_roadmap_file mit alias="powerunits_architecture" und name="../secret.md" (soll fail-closed invalid_name).`
5. `Versuche read_powerunits_roadmap_file mit alias="powerunits_architecture" und name="some.json" (soll fail-closed invalid_name).`

## Docs-to-workspace usage pattern

Bei expliziter Operator-Anweisung soll Hermes ohne Meta-Schleifen:

1. aus allowgelistetem Alias/Datei lesen,
2. knapp zusammenfassen,
3. in `powerunits_workspace` speichern,
4. kurz bestaetigen mit Quelle (`alias` + Datei) und gespeichertem Workspace-Pfad.

Bei expliziter Vergleichsanfrage:

1. Datei aus Alias A lesen,
2. Datei aus Alias B lesen,
3. kurze Vergleichssynthese (Alignment/Gaps/Risks/Next actions),
4. in `analysis/` speichern und Pfad kurz bestaetigen.
