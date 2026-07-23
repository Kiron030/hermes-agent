# Example tree for `$HERMES_HOME/powerunits_local_reference` (Tier 2 / Phase 2B)

**Hermes does not create this directory.** Operators may copy this example onto the
Railway volume when they want curated local reference drops for
`summarize_powerunits_allowlisted_locals` / `read_powerunits_local_reference_file`.

## Safety

- **No secrets** (tokens, DB URLs, Telegram keys, Railway credentials).
- Prefer summaries, ISO2 lists, operator checklists, non-sensitive JSON/YAML.
- Keep the tree small (dozens of files, not multi‑GB dumps).

## Install (optional, after `CAPABILITY_TIER=2`)

On the Hermes host / volume (`HERMES_HOME=/opt/data`):

```bash
mkdir -p /opt/data/powerunits_local_reference
# copy files from this example directory into that path
```

Without this directory, Tier‑2 tools still work on **`hermes_workspace`**
(including `.json`/`.yaml` via extended read).

## Files in this example

| File | Purpose |
|------|---------|
| `README.md` | This file |
| `operator_scope_snapshot_v1.json` | Non-secret country-scope reminder for operators |
