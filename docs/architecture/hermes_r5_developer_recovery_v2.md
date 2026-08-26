# Developer Hermes recovery — encrypted USB backup

**Slice:** `RECOVERY_2_USB_ENCRYPTED_BACKUP`  
**Architecture:** `PINNED_GIT_REBUILD_PLUS_ENCRYPTED_HOME`  
**Backup tool:** restic `0.18.1` (pinned Windows amd64, official SHA256SUMS)

```text
NEW_PC + USB + RECOVERY_KEY
  → Repo A recoverable (self-contained capsule)
  → Repo B recoverable (self-contained capsule)
  → Developer HERMES_HOME recoverable (logical volume export)
  → approved Developer credentials recoverable
```

Restore is **not** implemented in this slice. Recovery 3 is the restore bootstrap.

## Human command

From the Workbench checkout (never from `W:\hermes-dev`):

```powershell
.\scripts\r5_developer_hermes\backup-developer-hermes-usb.ps1 -UsbRoot E:\
.\scripts\r5_developer_hermes\verify-developer-hermes-usb-backup.ps1 -UsbRoot E:\
```

If `-UsbRoot` is omitted, the script lists removable drives. One drive still requires
an explicit path plus `YES`. Multiple drives never auto-select.

The script never formats, never repartitions, and never writes the Windows
system drive.

## Recovery key

The restic password is entered through a PowerShell `SecureString` and passed
to restic only as `RESTIC_PASSWORD`. It is not placed on a command line, not
logged, not stored in Git, not stored in the restic repository, and not stored
in plaintext on the USB.

Store the key independently: off-device password manager plus an optional
physical copy.

## USB layout

```text
HERMES-RECOVERY/
  README_FIRST.txt
  recovery-manifest.json
  checksums.sha256
  bootstrap/          # restic.exe + runbooks; no secrets
  restic/
  repository/         # encrypted restic repo
```

A volume label `HERMES_RECOVERY` is recommended. Reformatting is not required
and is never performed by these scripts.

## Git capsules

Backup time refreshes Repo A and Repo B Git discovery. Recovery-0B bundles are
evidence only. Each backup writes a **self-contained** `git bundle --all`
plus safe dirty/untracked/stash/worktree artifacts.

If safe local-only work cannot be placed in the new capsule, backup fails:

```text
BACKUP_BLOCKED_LOCAL_WORK
```

The known Repo B secret-bearing stash (`.env.pgurl`) is excluded:

```text
EXCLUDED_SECRET_BEARING_LOCAL_STATE = YES
```

Exact Workbench reconstruction is then not byte-for-byte. Security wins.
Production secrets stay outside this Developer pack.

## HERMES_HOME

Named volume `r5-developer-hermes-home` is exported as a logical tar through a
throwaway container bind. Raw Docker Desktop volume filesystem paths are
forbidden.

The smallest consistency window stops only local Developer writers (Telegram
gateway, Desktop sidecar, Developer container). Egress stays up. Operator
Railway is untouched. After the snapshot the previous local components are
restarted through the canonical launchers.

## Developer secret allowlist

Only these host slots are copied, by filename, never by directory walk:

- `W:\hermes-dev\credentials\developer-hermes-model.env`
- `W:\hermes-dev\credentials\developer-hermes-desktop.env`
- `W:\hermes-dev\credentials\developer-hermes-egress.token`

The Developer Telegram slot lives inside `HERMES_HOME` and is covered by the
logical volume export.

## Incremental

A second backup to the same USB repository creates a new restic snapshot.
The repository is not re-initialized. Old snapshots are not pruned in v1.

## Next slice

`RECOVERY_3_RESTORE_BOOTSTRAP` — restore from USB + recovery key onto a new PC.
Do not start that work from a live backup that has not been Human-authorized.
