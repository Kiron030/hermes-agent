<#
.SYNOPSIS
    R5 Phase A preflight for the dedicated Windows security principal.

.DESCRIPTION
    Read-only inspection. Requires no elevation and mutates no OS state, with
    one deliberate exception: -CreateSentinel writes a harmless synthetic marker
    into the CURRENT user's profile so that Phase C can prove the marker is
    unreadable from the dedicated principal.

    Never reads or prints credential contents. Secret-class files are reported
    by path and size only.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\preflight-principal.ps1 -CreateSentinel
#>
[CmdletBinding()]
param(
    [string]   $AccountName    = 'hermes-dev',
    [string[]] $WorkspaceRoots = @('W:\Workbench\hermes-agent', 'W:\Workbench\EU-PP-Database'),
    [string]   $ArtifactPath,
    [switch]   $CreateSentinel
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $ArtifactPath) {
    $ArtifactPath = Join-Path $RepoRoot '.r5-dev\artifacts\principal_preflight.json'
}

# Well-known SIDs. Group names are localised; SIDs are not.
$SID_ADMINISTRATORS = 'S-1-5-32-544'
$SID_USERS          = 'S-1-5-32-545'
$SID_AUTH_USERS     = 'S-1-5-11'

$blockers = New-Object System.Collections.ArrayList
$warnings = New-Object System.Collections.ArrayList

function Add-Blocker([string]$Id, [string]$Detail) {
    [void]$blockers.Add([ordered]@{ id = $Id; detail = $Detail })
}
function Add-Warning([string]$Id, [string]$Detail) {
    [void]$warnings.Add([ordered]@{ id = $Id; detail = $Detail })
}

# --------------------------------------------------------------- path helpers

function Resolve-RealPath {
    <#
      Walks a path and substitutes any symlink/junction ancestor with its target.
      Windows PowerShell 5.1 has no ResolveLinkTarget, so this is done manually.
      A tool that lives behind a reparse point into another user's profile is
      NOT reachable by a different principal, however innocuous its nominal path.
    #>
    param([string]$Path)
    if (-not $Path) { return $null }
    $current = $Path
    for ($hop = 0; $hop -lt 8; $hop++) {
        $redirected = $false
        $probe = $current
        while ($probe) {
            $item = Get-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
            if ($item -and $item.LinkType -in @('SymbolicLink', 'Junction') -and $item.Target) {
                $target = @($item.Target)[0]
                $current = $current.Substring($probe.Length).TrimStart('\')
                $current = if ($current) { Join-Path $target $current } else { $target }
                $redirected = $true
                break
            }
            $parent = Split-Path $probe -Parent
            if ($parent -eq $probe) { break }
            $probe = $parent
        }
        if (-not $redirected) { break }
    }
    return $current
}

function Get-PathScope {
    <#
      SYSTEM_WIDE       reachable by any local principal with Users read/execute
      USER_PROFILE_ONLY lives under some user's profile; another principal cannot use it
    #>
    param([string]$Path)
    if (-not $Path) { return 'ABSENT' }
    $real = Resolve-RealPath $Path
    if ($real -match '^[A-Za-z]:\\Users\\(?!Public\\|Default\\)') { return 'USER_PROFILE_ONLY' }
    return 'SYSTEM_WIDE'
}

function Test-ReadableByStandardUsers {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $acl = Get-Acl -LiteralPath $Path
    } catch {
        return $null
    }
    foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne 'Allow') { continue }
        try {
            $sid = $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        } catch {
            continue
        }
        if ($sid -in @($SID_USERS, $SID_AUTH_USERS)) {
            if ($ace.FileSystemRights.ToString() -match 'ReadAndExecute|Modify|FullControl') { return $true }
        }
    }
    return $false
}

function Get-AclSummary {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 'ABSENT' }
    $acl = Get-Acl -LiteralPath $Path
    $entries = foreach ($ace in $acl.Access) {
        $sid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { 'UNRESOLVED' }
        [ordered]@{
            sid       = $sid
            type      = $ace.AccessControlType.ToString()
            rights    = $ace.FileSystemRights.ToString()
            inherited = [bool]$ace.IsInherited
        }
    }
    return [ordered]@{ owner = $acl.Owner; access = @($entries) }
}

# ------------------------------------------------------------- 1. drive class

$driveFacts = @{}
foreach ($root in $WorkspaceRoots) {
    $letter = ($root -split ':')[0]
    $disk   = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='${letter}:'" -ErrorAction SilentlyContinue
    $substd = (& cmd.exe /c subst) -join "`n"
    $driveFacts[$root] = [ordered]@{
        drive         = "${letter}:"
        exists        = (Test-Path -LiteralPath $root)
        drive_type_id = if ($disk) { [int]$disk.DriveType } else { $null }
        drive_type    = switch ($disk.DriveType) { 2 { 'REMOVABLE' } 3 { 'LOCAL_FIXED' } 4 { 'NETWORK_SHARE' } 5 { 'CDROM' } default { 'UNKNOWN' } }
        file_system   = $disk.FileSystem
        provider_name = $disk.ProviderName
        is_subst      = [bool]($substd -match [regex]::Escape("${letter}:\"))
    }
    if (-not (Test-Path -LiteralPath $root)) {
        Add-Blocker 'WORKSPACE_ROOT_MISSING' "$root does not exist"
    }
    if ($disk -and [int]$disk.DriveType -eq 4) {
        Add-Blocker 'WORKSPACE_ON_NETWORK_SHARE' "$root is on a network share; a second principal needs its own credentials to reach it"
    }
    if ($driveFacts[$root].is_subst) {
        Add-Blocker 'WORKSPACE_ON_SUBST_DRIVE' "${letter}: is a subst mapping. subst is per-logon-session and will not exist for $AccountName"
    }
    if ($disk -and $disk.FileSystem -ne 'NTFS') {
        Add-Blocker 'WORKSPACE_NOT_NTFS' "$root is on $($disk.FileSystem); per-principal ACLs require NTFS"
    }
}

# --------------------------------------------------------------- 2. root ACLs

$aclFacts = @{}
foreach ($root in $WorkspaceRoots) { $aclFacts[$root] = Get-AclSummary $root }

# Note whether the volume root already hands Modify to every authenticated user.
$volumeGrants = @{}
foreach ($root in $WorkspaceRoots) {
    $volume = ($root -split ':')[0] + ':\'
    if ($volumeGrants.ContainsKey($volume)) { continue }
    $summary = Get-AclSummary $volume
    $broad = @($summary.access | Where-Object {
        $_.type -eq 'Allow' -and $_.sid -in @($SID_USERS, $SID_AUTH_USERS) -and $_.rights -match 'Modify|FullControl'
    })
    $volumeGrants[$volume] = [ordered]@{
        volume                            = $volume
        grants_modify_to_all_authenticated = ($broad.Count -gt 0)
        entries                            = @($broad)
    }
    if ($broad.Count -gt 0) {
        Add-Warning 'VOLUME_ROOT_ALREADY_GRANTS_MODIFY' "$volume already grants Modify to Users/Authenticated Users. $AccountName inherits Modify across the whole volume, not just the approved workspace roots. Explicit grants remain worthwhile so the boundary survives a later tightening of the volume root."
    }
}

# --------------------------------------------------------------- 3. toolchain

$toolNames = @('python', 'py', 'uv', 'uvx', 'git', 'node', 'npm', 'gh', 'railway', 'vercel')
$toolFacts = @{}
foreach ($name in $toolNames) {
    $cmd  = Get-Command $name -ErrorAction SilentlyContinue
    $path = if ($cmd) { $cmd.Source } else { $null }
    $real = Resolve-RealPath $path
    $toolFacts[$name] = [ordered]@{
        on_host_path              = [bool]$cmd
        path                      = $path
        resolved_path             = $real
        scope                     = Get-PathScope $path
        readable_by_standard_user = if ($real) { Test-ReadableByStandardUsers (Split-Path $real -Parent) } else { $null }
    }
}

# The pinned modern-Hermes runtime the R5 probes actually execute.
$venvPython = Join-Path $RepoRoot '.r1-proof\upstream-src\.venv\Scripts\python.exe'
$venvCfg    = Join-Path $RepoRoot '.r1-proof\upstream-src\.venv\pyvenv.cfg'
$venvHome   = $null
if (Test-Path -LiteralPath $venvCfg) {
    $line = (Get-Content -LiteralPath $venvCfg | Where-Object { $_ -match '^\s*home\s*=' } | Select-Object -First 1)
    if ($line) { $venvHome = ($line -split '=', 2)[1].Trim() }
}
$runtimeFacts = [ordered]@{
    venv_python                   = $venvPython
    venv_python_exists            = (Test-Path -LiteralPath $venvPython)
    venv_base_python              = $venvHome
    venv_base_scope               = Get-PathScope $venvHome
    venv_base_readable_by_users   = Test-ReadableByStandardUsers $venvHome
    venv_is_repo_local            = ($venvPython -like "$RepoRoot*")
    separate_dev_environment_required = $false
}
if (-not $runtimeFacts.venv_python_exists) {
    Add-Blocker 'PINNED_RUNTIME_MISSING' "The pinned R1 venv is absent. Recreating it needs uv, which is $($toolFacts['uv'].scope)."
}
if ($venvHome -and (Get-PathScope $venvHome) -eq 'USER_PROFILE_ONLY') {
    $runtimeFacts.separate_dev_environment_required = $true
    Add-Blocker 'VENV_BASE_IN_USER_PROFILE' "The venv base interpreter $venvHome lives in a user profile; $AccountName cannot execute it."
}

foreach ($required in @('python', 'git')) {
    if ($toolFacts[$required].scope -ne 'SYSTEM_WIDE') {
        Add-Blocker 'REQUIRED_TOOL_NOT_SYSTEM_WIDE' "$required resolves to $($toolFacts[$required].resolved_path) ($($toolFacts[$required].scope)); $AccountName cannot execute it."
    }
}
foreach ($optional in @('uv', 'node', 'npm')) {
    if ($toolFacts[$optional].on_host_path -and $toolFacts[$optional].scope -eq 'USER_PROFILE_ONLY') {
        Add-Warning 'OPTIONAL_TOOL_NOT_SYSTEM_WIDE' "$optional resolves into a user profile and will be unavailable to $AccountName. This is a capability limitation, not a security defect; for node it is also what removes the host Railway CLI from reach."
    }
}

# --------------------------------------- 4. secret-class files in the workspace

$secretPatterns = @('.env', '.env.*', '*.pem', '*.key', 'id_rsa', 'id_ed25519', 'credentials', '*.pfx')
$prunedDirs     = @('node_modules', '.venv', 'venv', 'site-packages', '.git', '__pycache__',
                    '.r5-dev', '.r1-proof', 'dist', 'build', '.next', '.cache')
$secretFindings = New-Object System.Collections.ArrayList

function Find-SecretClassFiles {
    <#
      Prunes heavy directories during traversal. Get-ChildItem -Recurse -Include
      filters only after enumerating, which walks entire dependency trees and
      turns this check into a multi-minute stall.
    #>
    param([string]$Root, [int]$MaxDepth = 3)
    $results = New-Object System.Collections.ArrayList
    $queue = New-Object System.Collections.Queue
    $queue.Enqueue([pscustomobject]@{ Path = $Root; Depth = 0 })
    while ($queue.Count -gt 0) {
        $node = $queue.Dequeue()
        try {
            $entries = [System.IO.Directory]::EnumerateFileSystemEntries($node.Path)
        } catch {
            continue
        }
        foreach ($entry in $entries) {
            $name = [System.IO.Path]::GetFileName($entry)
            if ([System.IO.Directory]::Exists($entry)) {
                if ($prunedDirs -contains $name) { continue }
                if ($node.Depth -lt $MaxDepth) {
                    $queue.Enqueue([pscustomobject]@{ Path = $entry; Depth = $node.Depth + 1 })
                }
                continue
            }
            if ($name -like '*.example' -or $name -like '*.sample') { continue }
            foreach ($pattern in $secretPatterns) {
                if ($name -like $pattern) {
                    [void]$results.Add((Get-Item -LiteralPath $entry -Force))
                    break
                }
            }
        }
    }
    return $results
}

foreach ($root in $WorkspaceRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $found = Find-SecretClassFiles -Root $root
    foreach ($file in $found) {
        $relative = $file.FullName.Substring($root.Length).TrimStart('\')
        $tracked  = $false
        $inHistory = $false
        Push-Location $root
        try {
            & git ls-files --error-unmatch -- $relative *> $null
            $tracked = ($LASTEXITCODE -eq 0)
            $hits = & git log --all --oneline --diff-filter=A -- $relative 2>$null
            $inHistory = [bool]$hits
        } catch {
        } finally {
            Pop-Location
        }
        [void]$secretFindings.Add([ordered]@{
            root            = $root
            relative_path   = $relative
            size            = $file.Length
            git_tracked     = $tracked
            in_git_history  = $inHistory
        })
    }
}

$historySecrets = @($secretFindings | Where-Object { $_.in_git_history })
if ($secretFindings.Count -gt 0) {
    Add-Blocker 'SECRETS_INSIDE_APPROVED_WORKSPACE' "$($secretFindings.Count) secret-class file(s) live inside the workspace roots that $AccountName is required to have Modify on. An OS-principal boundary cannot make these unreadable while WORKSPACE_RW stays YES."
}
if ($historySecrets.Count -gt 0) {
    Add-Blocker 'SECRETS_IN_GIT_HISTORY' "$($historySecrets.Count) secret-class file(s) are reachable through git object storage. Denying read on the working-tree file does not close this, and denying read on .git would destroy the required GIT capability. Rotation is the only fix that holds."
}

# ------------------------------------------------- 5. account / elevation state

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$account   = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
$adminMembers = @()
try {
    $adminMembers = @(Get-LocalGroupMember -SID $SID_ADMINISTRATORS -ErrorAction Stop | ForEach-Object { $_.Name })
} catch {
}

$accountFacts = [ordered]@{
    account_name             = $AccountName
    account_exists           = [bool]$account
    account_enabled          = if ($account) { [bool]$account.Enabled } else { $null }
    account_is_administrator = [bool](@($adminMembers | Where-Object { $_ -match "\\$AccountName$" }).Count)
    host_user                = $identity.Name
    host_user_sid            = $identity.User.Value
    session_is_elevated      = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}
if (-not $account) {
    Add-Warning 'ACCOUNT_NOT_PROVISIONED' "$AccountName does not exist yet. provision-principal.ps1 must be run from an elevated session."
}
if (-not $accountFacts.session_is_elevated) {
    Add-Warning 'SESSION_NOT_ELEVATED' 'This session cannot create accounts or set ACLs. Provisioning is a human step.'
}

# ---------------------------------------------------- 6. host-profile sentinel

$sentinelPath = Join-Path $env:USERPROFILE '.r5-host-profile-sentinel.txt'
$sentinelFacts = [ordered]@{
    path            = $sentinelPath
    exists          = (Test-Path -LiteralPath $sentinelPath)
    created_by_this_run = $false
    purpose         = 'Phase C reads this exact absolute path as the dedicated principal and must be denied.'
}
if ($CreateSentinel -and -not $sentinelFacts.exists) {
    Set-Content -LiteralPath $sentinelPath -Encoding ASCII -Value @(
        'R5 host-profile sentinel.',
        'Synthetic marker with no secret value.',
        'If the dedicated principal can read this line, the OS boundary is not holding.'
    )
    $sentinelFacts.exists = $true
    $sentinelFacts.created_by_this_run = $true
}
if (-not $sentinelFacts.exists) {
    Add-Warning 'SENTINEL_ABSENT' 'Re-run with -CreateSentinel before Phase C.'
}

# ------------------------------------- 7. host credential stores to be excluded

$credentialStores = [ordered]@{
    railway_home    = Join-Path $env:USERPROFILE '.railway'
    railway_appdata = Join-Path $env:APPDATA 'railway'
    gh_hosts        = Join-Path $env:APPDATA 'GitHub CLI\hosts.yml'
    gcloud          = Join-Path $env:APPDATA 'gcloud'
    vercel          = Join-Path $env:APPDATA 'com.vercel.cli'
    ssh             = Join-Path $env:USERPROFILE '.ssh'
    aws             = Join-Path $env:USERPROFILE '.aws'
}
$storeFacts = @{}
foreach ($entry in $credentialStores.GetEnumerator()) {
    $storeFacts[$entry.Key] = [ordered]@{
        path             = $entry.Value
        exists_for_host  = (Test-Path -LiteralPath $entry.Value)
        must_be_denied_to_principal = $true
    }
}

# Absolute deploy-CLI locations, recorded so Phase C can attack them by absolute
# path. The proof must not depend on PATH resolution.
$deployCandidates = New-Object System.Collections.ArrayList
foreach ($name in @('railway', 'vercel')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) {
        $real = Resolve-RealPath $cmd.Source
        [void]$deployCandidates.Add($real)
        $dir = Split-Path $real -Parent
        foreach ($ext in @('.exe', '.cmd', '.bat', '.ps1', '')) {
            $candidate = Join-Path $dir "$name$ext"
            if ((Test-Path -LiteralPath $candidate) -and ($deployCandidates -notcontains $candidate)) {
                [void]$deployCandidates.Add($candidate)
            }
        }
    }
}
foreach ($extra in @(
    (Join-Path $env:LOCALAPPDATA 'nvm'),
    (Join-Path $env:APPDATA 'npm')
)) {
    if (Test-Path -LiteralPath $extra) {
        # -Filter is evaluated by the filesystem provider; -Include would walk
        # every nested package directory first.
        foreach ($binary in @('railway.exe', 'vercel.exe')) {
            Get-ChildItem -LiteralPath $extra -Recurse -Depth 5 -Filter $binary -File -ErrorAction SilentlyContinue |
                ForEach-Object { if ($deployCandidates -notcontains $_.FullName) { [void]$deployCandidates.Add($_.FullName) } }
        }
    }
}

# ------------------------------------------------------------------ report

$report = [ordered]@{
    schema                   = 'r5.principal_preflight.v1'
    generated_utc            = (Get-Date).ToUniversalTime().ToString('o')
    repo_root                = $RepoRoot
    account                  = $accountFacts
    workspace_roots          = $WorkspaceRoots
    drives                   = $driveFacts
    workspace_acls           = $aclFacts
    volume_root_grants       = $volumeGrants
    toolchain                = $toolFacts
    pinned_runtime           = $runtimeFacts
    in_workspace_secret_files = @($secretFindings)
    host_credential_stores   = $storeFacts
    deploy_cli_absolute_candidates = @($deployCandidates)
    host_profile_sentinel    = $sentinelFacts
    warnings                 = @($warnings)
    blockers                 = @($blockers)
    PREFLIGHT_RESULT         = if ($blockers.Count -eq 0) { 'READY_FOR_PROVISIONING' } else { 'BLOCKED' }
}

$artifactDir = Split-Path $ArtifactPath -Parent
if (-not (Test-Path -LiteralPath $artifactDir)) { New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ArtifactPath -Encoding UTF8

Write-Host ''
Write-Host "PREFLIGHT_RESULT = $($report.PREFLIGHT_RESULT)"
Write-Host "artifact         = $ArtifactPath"
if ($blockers.Count -gt 0) {
    Write-Host ''
    Write-Host 'BLOCKERS:'
    foreach ($blocker in $blockers) { Write-Host "  [$($blocker.id)] $($blocker.detail)" }
}
if ($warnings.Count -gt 0) {
    Write-Host ''
    Write-Host 'WARNINGS:'
    foreach ($warning in $warnings) { Write-Host "  [$($warning.id)] $($warning.detail)" }
}

if ($blockers.Count -gt 0) { exit 1 }
exit 0
