# Developer Hermes recovery — manifest, audit, readiness

**Slice:** `RECOVERY_1_MANIFEST_AND_AUDIT`  
**Architecture:** `PINNED_GIT_REBUILD_PLUS_ENCRYPTED_HOME`  
**Status:** contract + audit only. Encrypted backup is **not** implemented.

```text
OFF_DEVICE_ENCRYPTED_BACKUP = NOT_YET
```

This document is the human runbook for Slice 1. It does not claim that an
off-device encrypted backup exists. Recovery 2 introduces restic and the
encrypted `HERMES_HOME` + Developer-secret backup. Do not treat GitHub
reachability as backup readiness.

## What Git reconstructs

Pinned Git plus the checked-in bootstrap reconstruct:

- Repo A at `origin/powerunits-internal-setup`
- Repo B at `origin/main` (`Kiron030/Powerunits.io`, local name `EU-PP-Database`)
- R5 Developer image, egress broker, Desktop sidecar
- launch / prove tooling and Desktop remote integration
- Telegram lifecycle and profile templates
- non-root runtime contract (`hermes` / `10000:10000`, `HERMES_HOME=/opt/data`)

Current canonical SHAs are recorded at audit time. Do not reuse a stale
Recovery 0A SHA.

Local-only source that is not on a remote must already be in the Recovery 0B
staging pack (`W:\Workbench\backups\recovery-0b-local-git-safety-20260826T1445Z`)
or the audit reports `BACKUP_READINESS = BLOCKED_LOCAL_WORK`. The audit never
pushes, stashes, or mutates worktrees.

## What the encrypted backup must contain

When Recovery 2 exists, the encrypted backup must contain:

| Item | Class | Mechanism |
|---|---|---|
| Named volume `r5-developer-hermes-home` | `MUST_BACKUP_ENCRYPTED_FULL_LOGICAL` | Logical volume export, then encrypt |
| `W:\hermes-dev\credentials\developer-hermes-model.env` | Developer secret slot | Encrypted file backup |
| `W:\hermes-dev\credentials\developer-hermes-desktop.env` | Developer secret slot | Encrypted file backup |
| `W:\hermes-dev\credentials\developer-hermes-egress.token` | Developer secret slot | Encrypted file backup |

The Developer Telegram token lives at `/opt/data/profiles/telegram-ops/.env`
inside `r5-developer-hermes-home`. A full logical volume backup covers it.
Do not copy raw Docker Desktop volume filesystem paths.

Broker volumes `r5-egress-broker-state`, `r5-egress-ca-pub`, and
`r5-egress-broker-home` are `REGENERATABLE_FROM_GIT_AND_HOST_SLOTS` unless a
later source audit contradicts Recovery 0A.

## What is intentionally excluded

- `%USERPROFILE%\.powerunits\secrets` (production / Repo B host secrets)
- Railway / Operator Hermes credentials
- production database credentials
- host GitHub credential store
- Docker socket
- the whole Windows profile
- Operator Hermes and Railway runtime state

A recovery manifest must never contain secret material. The audit reports
slot `PRESENT` / `MISSING` / `UNEXPECTED` only.

## Where the recovery key must live

The Recovery 2 encryption key must live **off the machine that holds the
backup**, not in Git, not in `HERMES_HOME`, and not next to
`W:\hermes-dev\credentials`. Until Recovery 2 succeeds, no recovery key
exists.

```text
RECOVERY_KEY = NOT_YET
OFF_DEVICE_ENCRYPTED_BACKUP = NOT_YET
```

## How to check backup readiness

From the Workbench checkout (never from `W:\hermes-dev`):

```powershell
.\scripts\r5_developer_hermes\audit-developer-hermes-recovery.ps1
.\scripts\r5_developer_hermes\audit-developer-hermes-recovery.ps1 -WriteManifest
```

Ready means `BACKUP_READINESS = READY_FOR_RECOVERY_2`. That is not an
off-device backup. Blockers include uncovered local Git work, a failed
Recovery 0B hash check, a missing `r5-developer-hermes-home` volume, a wrong
runtime uid/gid, a stale upstream pin, unexpected secret slots, or missing
Developer host secret slots.

The generated live manifest is machine-specific and gitignored:

`.r5-dev/recovery/developer-hermes-recovery-manifest.json`

Committed contract:

- schema: `scripts/r5_developer_hermes/recovery/developer-hermes-recovery-manifest.schema.json`
- template: `scripts/r5_developer_hermes/recovery/developer-hermes-recovery-manifest.template.json`

## Host path constraint

The current runtime contract uses literal `W:` paths. This slice does **not**
redesign that. Restore on a replacement machine must preserve the `W:` root
until a later slice parameterizes host roots.

## Before a machine migration or risky Docker operation

1. Run the audit. Require `READY_FOR_RECOVERY_2` or resolve blockers.
2. Confirm Recovery 0B staging hashes still `PASS`.
3. Do **not** proceed on GitHub reachability alone.
4. Do **not** reset `r5-developer-hermes-home` until Recovery 2 has a verified
   off-device encrypted snapshot.
5. Do not stop Developer Hermes or Developer Telegram for this audit.
6. Do not touch Operator Hermes or Railway.

## Next slice

`RECOVERY_2_ENCRYPTED_BACKUP` — install/use restic, encrypt
`r5-developer-hermes-home` plus Developer secret slots, verify restore.
Do not start that work from this document alone; wait for the Recovery 2
brief.
