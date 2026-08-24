# R5 Developer Hermes — workspace authority boundary (v1)

**Disposition (2026-08-24):** the Linux container is the canonical R5
primary isolation boundary. This document and
`scope-workspace-authority.ps1` are `FALLBACK_ONLY`. Do not execute the
ACL script against `C:\`, `D:\`, or `W:\`.

Phase B2 of the R5 isolation remediation. Two preflight blockers stood between
the prepared artifacts and a provisionable boundary: a historical secret that no
longer commands anything, and a volume ACL that would hand the future principal
write access to the whole workbench drive.

Everything below is read-only evidence and prepared human runbooks. No account
was created, no ACL was changed, no secret was moved, no history was rewritten,
and nothing remote was touched.

---

## 1. Repo-B `.env.pgurl` reconciliation

```
REPO_B_LOCAL_BRANCH       = feature/env-externalization-compat-xs
REPO_B_LOCAL_HEAD         = d267b815999e727f17ac9419a9d26820277eee8d
REPO_B_ORIGIN_MAIN        = 7bd3f9a09d94cfa1c26ccc9486920ec23f84699c
LOCAL_PGURL_EXISTS        = YES
LOCAL_PGURL_SIZE          = 0
LOCAL_PGURL_TRACKED       = YES   (on the local feature branch)
REMOTE_MAIN_PGURL_TRACKED = NO
```

Nothing is wrong. `git rev-list --left-right --count origin/main...HEAD` reports
`2 1`: the local branch carries one commit of its own and is two commits behind
canonical main, and the retirement commit is one of those two. The retirement
landed on `main`; the feature branch simply predates it and still carries the
file in its index. The retirement commit is present locally — it was fetched —
so canonical main can be read without any network access.

`feature/env-externalization-compat-xs` is active, unrelated work (the Repo-B
env-externalization compatibility change). It must not be switched, reset or
merged to make R5's preflight look better.

**Minimum safe reconciliation.** Do not reconcile the human's checkout at all.
Give the dedicated principal its **own working copy pinned to canonical main**,
inside the scoped workspace root described below. That copy does not track
`.env.pgurl`, so the R5 workspace reflects the retired state by construction,
while the feature branch keeps its own index untouched. This falls out of the
authority design anyway — two principals sharing one working tree is a hazard
regardless of ACLs — so it costs nothing extra.

A git *worktree* would be the cheaper move, but it keeps its object store in the
human's `.git`, which would drag the original path back into the principal's
required grants. A clone is the right call here.

---

## 2. Live versus proven-retired secret authority

The old preflight treated every historical secret-class blob as requiring
rotation. That is correct as a default and wrong for this one case, so the fix
is a narrow, verified exception rather than a switch that turns detection off.

`scripts/r5_developer_hermes/retired_authority.py` holds the contract. A finding
may be classified `PROVEN_RETIRED_SECRET_AUTHORITY` only when all five elements
verify:

| # | Element | How it is verified |
|---|---------|--------------------|
| 1 | exact path | equality against a checked-in evidence entry; no pattern, prefix or wildcard form exists |
| 2 | canonical main no longer tracks it | `git ls-tree -r --name-only origin/main -- <path>` is empty |
| 3 | live copy holds no secret | the working-tree file is absent or 0 bytes (`stat`, never `open`) |
| 4 | retirement is canonical | the recorded commit is an ancestor of `origin/main` **and** that commit deletes this exact path |
| 5 | human attestation | `service_deleted = true` plus a non-empty statement, attester and date |

Anything unverifiable — missing evidence file, unparsable evidence, git failure,
short SHA, a commit that exists but deletes something else — yields
`LIVE_OR_UNKNOWN_SECRET_AUTHORITY`. Content in the working tree outranks every
retirement claim and yields `LIVE_SECRET_PRESENT`.

Evidence lives in `scripts/r5_developer_hermes/principal/retired_secret_authority.json`
and currently holds exactly one entry. There is deliberately no
`ignore_git_history_secrets` flag; a test asserts that no script in the
principal directory offers one.

Verified against the real repository, all five checks pass:

```
CURRENT_PGURL_CLASSIFICATION    = NO_ACTIVE_SECRET (0 bytes, no content)
HISTORICAL_PGURL_CLASSIFICATION = PROVEN_RETIRED_SECRET_AUTHORITY
                                  -> HISTORICAL_DEAD_AUTHORITY = WARN/INFO
LIVE_SECRET_BLOCKERS            = none
```

The legacy target is the Railway PostgreSQL sandbox service Repo B documents as
"Legacy enrichment sandbox — archive after Phase A", human-deleted and attested.
It is **not** the production source of truth; `DATABASE_URL_TIMESCALE` and
`DATABASE_URL` are, they live only in the host-only secret root, and this entry
says nothing about them.

---

## 3. The `W:\` authority problem

### 3.1 Evidence

```
W_VOLUME_ROOT_BROAD_MODIFY = YES
```

`W:\` carries two Allow entries for `Authenticated Users`:

| Entry | Inheritance | Effect |
|-------|-------------|--------|
| `Modify, Synchronize` | none | write access to the volume root itself |
| generic `0xE0010000` | ContainerInherit, ObjectInherit, **InheritOnly** | write access to every child that inherits |

`W:\Workbench`, `W:\Workbench\hermes-agent` and `W:\Workbench\EU-PP-Database` all
have inheritance enabled and show that entry as inherited. So does every other
top-level directory: `AI_Workspace`, `cache`, `dataset`, `models`, `opt`.

`C:\` and `D:\` carry the same structure. `D:\` also holds host data (`Archiv`,
a second `Workbench`). On `C:\` the OS is safe because `C:\Users`, `C:\Windows`
and `C:\Program Files` have **protected** DACLs and therefore never inherit it —
but user-created top-level directories do.

Two findings decide the design:

**The broad ACE is load-bearing for the human.** `whoami /groups` shows
`BUILTIN\Administrators` as *deny-only* in the host user's normal token, so the
`Administrators: FullControl` entry cannot grant access in an unelevated
session. Every top-level directory on `W:\` is owned by `PIXEL\User`, and
ownership alone confers no data access. `Authenticated Users: Modify` is
therefore the **only** entry that gives the interactive host user write access
to its own 1.8 TB of data. Removing or narrowing it without first adding an
explicit grant for that user would break every host workflow on the volume.

**Nothing else depends on it.** No Windows service and no scheduled task
references a `W:\` path, so the blast radius of the broad ACE is the interactive
host user alone.

### 3.2 Options considered

| Option | Verdict |
|--------|---------|
| **A. Tighten the `W:\` root ACL** and grant required principals explicitly | **Rejected.** Rewrites the one entry the host user depends on, propagates a DACL change across 1.8 TB, and a mistake locks the human out of their own data. High risk, no benefit over C. |
| **B. Disable inheritance / scoped ACLs alone** | **Insufficient on its own.** Protecting the two repo roots stops an inherited deny from reaching them, but nothing stops the principal writing `W:\dataset`, `W:\models` or `D:\Archiv`. Necessary as a component, not as the answer. |
| **C. Dedicated scoped workspace + principal-specific write-deny** | **Recommended.** See below. |
| **D. Separate VHDX volume for the principal** | Rejected as larger, not safer: it needs boot-time mounting, adds a failure mode, and still requires the same deny to keep the principal off `W:\` and `D:\`. |

Two constraints from the mission brief also rule out the obvious shortcuts. An
inherited DENY that defeats the explicit Repo-A/Repo-B allow is not acceptable —
so the scoped root's DACL must be protected. And a design where the principal can
still modify arbitrary `W:\` content is not acceptable — so a scoped root alone
is not enough.

### 3.3 Recommended design

```
RECOMMENDED_WORKSPACE_AUTHORITY_DESIGN = DEDICATED_SCOPED_WORKSPACE
OTHER_W_WRITE_AFTER_DESIGN             = NO
```

Two mutations, neither of which modifies or removes any existing entry:

1. **Scoped workspace root**, created by `scope-workspace-authority.ps1` at
   `W:\hermes-dev`, with inheritance **disabled** and an explicit DACL:
   Administrators and SYSTEM FullControl, the host user Modify, `hermes-dev`
   Modify. Nothing else. Working clones of Repo A and Repo B live inside it.
2. **Inheritable write-deny for the `hermes-dev` SID at each local fixed volume
   root** (`C:\`, `D:\`, `W:\`). Write, Delete, DeleteSubdirectoriesAndFiles,
   ChangePermissions and TakeOwnership only — **read and execute are left
   alone**.

Why this holds:

- The deny targets one SID that does not exist yet, so its blast radius on
  existing workflows is provably zero. The broad `Authenticated Users` entry is
  never touched, so the host user's access is unchanged.
- The scoped root's protected DACL means the volume-root deny cannot reach the
  grants inside it. `REPO_A_RW` and `REPO_B_RW` survive.
- Denying write but not read means no machine-wide tool, service or OS path
  breaks, and directory traversal never depends on the bypass-traverse-checking
  privilege.
- `C:\Users`, `C:\Windows` and `C:\Program Files` have protected DACLs, so the
  `C:\` deny cannot reach the principal's own profile or the OS. Its own profile
  stays writable, which it must be.
- Read access to other volume content remains. That is honest and within the
  stated acceptance list (`OTHER_W_WRITE = NO`, `HOST_PROFILE_READ = NO`); the
  host profile stays unreadable by its own default ACL, and after relocation
  nothing outside the profile holds a secret.

Every DACL is exported to `.r5-dev/acl-backups/acl_backup_<stamp>.json` **before**
the first mutation, and `rollback-workspace-authority.ps1` restores from it.

---

## 4. Developer capability

```
TOOLCHAIN_STRATEGY   = machine-wide install of the required tools; no profile exposure
R5_MINIMUM_CAPABILITY = Python, Git, GitHub CLI (unauthenticated), uv, pytest,
                        terminal, filesystem, skills
POST_R5_DEVELOPER_DX  = Node/npm, TypeScript LSP, browser, delegation
```

`uv` is not optional. `harness.py prepare_runtime()` runs `uv sync --frozen` to
build the pinned modern-Hermes venv, so without `uv` the dedicated principal
cannot reconstruct its runtime at all. It currently resolves to
`C:\Users\User\.local\bin\uv.exe`, which is correctly out of reach. The fix is a
**machine-wide install** (`C:\Program Files\uv`), not a grant into the profile.
Preflight now treats this as a blocker rather than a warning.

Python, Git and GitHub CLI are already machine-wide with `BUILTIN\Users`
read/execute and need no ACL change.

Node and npm resolve through `C:\nvm4w\nodejs`, which is a **symbolic link to
`C:\Users\User\AppData\Local\nvm\v20.20.0`**. That is exactly why the host
Railway CLI shim is unreachable, and it must stay that way. Node is not needed
for R5 acceptance — the proven capabilities are filesystem, terminal, git, test
loop and skills — so it is `POST_R5_DEVELOPER_DX`, not a silent downgrade. When
it is wanted, install Node LTS machine-wide (`C:\Program Files\nodejs`); a fresh
machine-wide npm prefix carries no `railway` shim, so deploy authority is not
smuggled in with it. Do not add `C:\nvm4w` to the principal's PATH.

The Railway CLI must never become authenticated for this principal. Nothing in
this design copies credentials or widens a credential store.

---

## 5. Preflight after these changes

`preflight-principal.ps1` now reports and *asserts* the real boundary. `READY`
requires all of:

```
ACTIVE_WORKSPACE_SECRET_FILES                 = 0
UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY       = 0
HOST_ONLY_SECRET_ROOT_REACHABLE_BY_HERMES_DEV = NO
OTHER_WRITE_AUTHORITY                         = NO
REPO_A_RW_DESIGN                              = YES
REPO_B_RW_DESIGN                              = YES
HOST_PROFILE_READ_DESIGN                      = NO
R5_MINIMUM_TOOLCHAIN                          = AVAILABLE
```

Current run (read-only, non-elevated, account absent):

```
ACTIVE_WORKSPACE_SECRET_FILES                 = 0
UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY       = 0
HISTORICAL_DEAD_AUTHORITY                     = 1   (informational)
HOST_ONLY_SECRET_ROOT_REACHABLE_BY_HERMES_DEV = NO
OTHER_WRITE_AUTHORITY                         = NOT_PROVEN   <- blocker
REPO_A_RW_DESIGN                              = YES
REPO_B_RW_DESIGN                              = YES
HOST_PROFILE_READ_DESIGN                      = NO
R5_MINIMUM_TOOLCHAIN                          = INCOMPLETE   <- blocker (uv)
PREFLIGHT_RESULT                              = BLOCKED
```

`OTHER_WRITE_AUTHORITY` is `NOT_PROVEN` rather than `YES` because the account
does not exist, so its effective denies cannot be read. Both states block; only
a proven `NO` passes. The gate is not satisfied by the presence of explicit
workspace ACEs — that was precisely the old mistake.

---

## HUMAN_RUNBOOK

Ordered. Stop at any step whose output does not match. Steps 1 and 2 are the
only ones that change the operating system.

**Step 0 — install uv machine-wide** (elevated).

```powershell
winget install --id astral-sh.uv --scope machine --accept-package-agreements --accept-source-agreements
```

If winget declines a machine scope, extract the official `uv` zip to
`C:\Program Files\uv` and append that directory to the **machine** `Path`.
Verify from a *new* shell:

```powershell
(Get-Command uv).Source     # expect C:\Program Files\uv\uv.exe, NOT C:\Users\...
```

**Step 1 — create the principal** (elevated). Dry run first.

```powershell
cd W:\Workbench\hermes-agent\scripts\r5_developer_hermes\principal
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1
```

Expected: a standard local account `hermes-dev`, member of `Users`, not of
`Administrators`; `host_secret_root_granted = false`; `toolchain_acls_changed = false`.

**Step 2 — scope its write authority** (elevated). Dry run first.

```powershell
powershell -ExecutionPolicy Bypass -File .\scope-workspace-authority.ps1 -WhatIf
powershell -ExecutionPolicy Bypass -File .\scope-workspace-authority.ps1
```

Expected: an ACL backup path is printed **before** any change; `W:\hermes-dev` is
created with inheritance disabled; one write-deny per volume root. The script
refuses if `hermes-dev` is an administrator, if the scoped root already exists
with an inheriting DACL, or if the session is not elevated.

Record the printed backup path. It is the only supported rollback input.

**Step 3 — place the working copies** (as the host user, not elevated).

```powershell
New-Item -ItemType Directory -Force -Path W:\hermes-dev\workspace | Out-Null
git clone https://github.com/<org>/hermes-agent.git      W:\hermes-dev\workspace\hermes-agent
git clone https://github.com/<org>/EU-PP-Database.git    W:\hermes-dev\workspace\EU-PP-Database
git -C W:\hermes-dev\workspace\hermes-agent   checkout r5-developer-hermes
git -C W:\hermes-dev\workspace\EU-PP-Database checkout main
```

The Repo-B clone must sit on `main`, which does not track `.env.pgurl`. The
human's `W:\Workbench\EU-PP-Database` feature branch is not touched.

**Step 4 — re-run preflight against the scoped roots** (elevated, so the
OS-managed containers can be read).

```powershell
powershell -ExecutionPolicy Bypass -File .\preflight-principal.ps1 `
  -WorkspaceRoots 'W:\hermes-dev\workspace\hermes-agent','W:\hermes-dev\workspace\EU-PP-Database' `
  -ScopedWorkspaceRoot 'W:\hermes-dev' `
  -CreateSentinel
```

```
PREFLIGHT_EXPECTED_AFTER_HUMAN_ACTION = READY
```

**Step 5 — Phase C property proof.** Launch as the dedicated principal and run
the verifier; do not skip it, it is the only empirical proof.

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-developer-hermes.ps1 -Verify
```

### Phase-C acceptance criteria

```
CHILD_OS_PRINCIPAL                     = DEDICATED (separate SID, not administrator)
HOST_PROFILE_FILESYSTEM_REACHABLE      = NO
HOST_ONLY_SECRET_ROOT_REACHABLE        = NO
RAILWAY_AUTH_REACHABLE                 = NO
GH_AUTH_REACHABLE                      = NO
WINDOWS_CREDENTIAL_AUTHORITY_REACHABLE = NO
PRODUCTION_SECRET_FILES_REACHABLE      = NO
PRODUCTION_DEPLOY_REACHABLE            = NO
OTHER_WRITE_AUTHORITY                  = NO   (attempted writes outside the scope all fail)
R5_MINIMUM_TOOLCHAIN                   = AVAILABLE
workspace roots                        = readable AND writable
git status                             = works
ISOLATION_ACCEPTANCE                   = PASS
```

## ROLLBACK_RUNBOOK

Reverses step 2 completely. Elevated.

```powershell
cd W:\Workbench\hermes-agent\scripts\r5_developer_hermes\principal
powershell -ExecutionPolicy Bypass -File .\rollback-workspace-authority.ps1 `
  -BackupPath '<the path printed in step 2>' -WhatIf
powershell -ExecutionPolicy Bypass -File .\rollback-workspace-authority.ps1 `
  -BackupPath '<the path printed in step 2>'
```

Only the DACL is restored — never the owner, never the SACL — so a rollback
cannot change who owns host data. The scoped root is deliberately left in place;
the removal command is printed rather than executed, because it may hold clones.

Reversing step 1:

```powershell
Remove-LocalUser -Name hermes-dev          # after the ACL rollback, not before
```

Reversing step 0: `winget uninstall astral-sh.uv`, then remove the machine PATH
entry. Nothing else depends on it.

---

## What was deliberately not done

- No account created, no ACL mutated, no secret relocated.
- No Git history rewritten. The retirement is a normal commit on canonical main;
  the historical blob stays, classified as dead authority.
- Nothing remote touched: no Railway, Vercel, GitHub or CI configuration change.
- The human's `feature/env-externalization-compat-xs` branch was read and left
  exactly as it was.
