# Powerunits Hermes Workspace v1

## Purpose

Bounded persistent internal workspace for Hermes outputs on Railway volume:

- Root: `/opt/data/hermes_workspace/`
- Allowed subdirs:
  - `analysis`
  - `notes`
  - `drafts`
  - `exports`

No repo writes, no GitHub writes, no DB writes.

## Tool contract

Toolset: `powerunits_workspace`

- `list_hermes_workspace(subdir?)`
  - Optional `subdir`: one of `analysis|notes|drafts|exports`
- `read_hermes_workspace_file(path)`
  - Path must be relative and start with allowed subdir (e.g. `notes/today.md`)
- `save_hermes_workspace_note(kind, name, content, overwrite_mode?)`
  - `kind`: one of allowed subdirs
  - `name`: file name only, `.md`/`.txt`
  - `overwrite_mode`: `forbid` (default) or `overwrite`

## Safety boundary

- Fixed root under persistent volume (`HERMES_HOME` default `/opt/data`)
- No absolute paths
- No `..`
- No root escape
- Only allowlisted subdirs
- Only text extensions (`.md`, `.txt`)
- No delete, no rename, no generic file-tool exposure

## Runtime behavior

- Directories are auto-created if missing (startup + tool access path).
- Content persists via Railway volume.

## Practical usage by subdir

- `analysis`: strukturierte Auswertungen, Zwischenanalysen, Vergleichsnotizen
- `notes`: kurze operative Mitschriften, Fakten, Session-Notizen
- `drafts`: entstehende Entwuerfe (Prompts, Texte, Runbook-Entwuerfe)
- `exports`: explizite Endresultate zum Weitergeben (readable output snapshots)

## Recommended markdown templates

### Analysis note template

```md
# <Title>

## Source
- alias: <allowlist_alias>
- file: <source_file_path>
- read_at: <utc_timestamp>

## Key findings
- ...
- ...

## Risks/uncertainties
- ...

## Next actions
- ...
```

### Notes template

```md
# <Short note title>
- source: <alias>/<file>
- context: <why this matters>
- bullets:
  - ...
```

### Drafts template

```md
# DRAFT: <Title>
Status: draft

## Core points
- ...
```

### Exports template

```md
# <Export title>

## Summary
- ...

## Source reference
- alias: <allowlist_alias>
- file: <source_file_path>
```

## GitHub read token naming

Read-only GitHub docs path uses:

- Preferred: `POWERUNITS_GITHUB_TOKEN_READ`
- Legacy fallback (compat): `POWERUNITS_GITHUB_DOCS_TOKEN`

Write token is intentionally out of scope.

## Telegram validation prompts

1. `Nutze list_hermes_workspace ohne Argumente und zeige nur die Ordner.`
2. `Nutze save_hermes_workspace_note mit kind=notes, name=today.md, content='...'.`
3. `Nutze read_hermes_workspace_file mit path=notes/today.md und fasse in 4 Bulletpoints zusammen.`
4. `Versuche read_hermes_workspace_file mit path=../secret.md (soll fail-closed).`
5. `Versuche save_hermes_workspace_note mit kind=notes, name=data.json (soll fail-closed).`
