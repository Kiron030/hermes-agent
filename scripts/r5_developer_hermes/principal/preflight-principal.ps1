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
    [string]   $HostSecretRoot = (Join-Path $env:USERPROFILE '.powerunits\secrets'),

    # The scoped root whose DACL is protected, so a volume-root deny cannot
    # reach the workspace grants inside it. See hermes_r5_workspace_authority_v1.md.
    [string]   $ScopedWorkspaceRoot = 'W:\hermes-dev',

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

# ------------------------------------ 2b. volume-wide write authority inventory
#
# The decisive question is not "does the workspace root grant Modify" but "can
# the principal write anything OUTSIDE the two approved roots". On this host
# every local volume root carries an inheritable Allow for Authenticated Users,
# so a fresh standard account inherits write across whole volumes. Explicit
# workspace grants do nothing about that.
#
# Fail-closed: while the account does not exist its effective denies cannot be
# read, so broad write authority is reported as NOT_PROVEN, never as absent.

$SID_EVERYONE = 'S-1-1-0'

function Test-BroadWriteAllow {
    <# Allow ACE for Users / Authenticated Users / Everyone carrying write. #>
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { $acl = Get-Acl -LiteralPath $Path } catch { return $null }
    foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne 'Allow') { continue }
        $sid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { continue }
        if ($sid -notin @($SID_USERS, $SID_AUTH_USERS, $SID_EVERYONE)) { continue }
        # Generic-rights ACEs surface as negative numbers; the generic-write bit
        # (0x40000000) is what actually propagates Modify into children.
        $rights = [int]$ace.FileSystemRights
        if ($ace.FileSystemRights.ToString() -match 'Modify|FullControl|Write') { return $true }
        if (($rights -band 0x40000000) -ne 0 -or ($rights -band 0x10000000) -ne 0) { return $true }
    }
    return $false
}

function Get-PrincipalWriteDeny {
    <#
      Effective (explicit or inherited) write-deny for one SID.
      Returns $null when the answer is unknown (no SID yet, or ACL unreadable),
      otherwise a record saying whether a deny exists and whether it propagates
      to children. Inheritance is what lets a single root ACE cover a volume.
    #>
    param([string]$Path, [string]$Sid)
    if (-not $Sid) { return $null }
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { $acl = Get-Acl -LiteralPath $Path } catch { return $null }
    $found = $false
    $inheritable = $false
    foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne 'Deny') { continue }
        $aceSid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { continue }
        if ($aceSid -ne $Sid) { continue }
        $rights = [int]$ace.FileSystemRights
        $carriesWrite = ($ace.FileSystemRights.ToString() -match 'Modify|FullControl|Write|Delete|TakeOwnership|ChangePermissions') `
            -or (($rights -band 0x40000000) -ne 0) -or (($rights -band 0x10000000) -ne 0)
        if (-not $carriesWrite) { continue }
        $found = $true
        if ($ace.InheritanceFlags -band [System.Security.AccessControl.InheritanceFlags]::ContainerInherit) {
            $inheritable = $true
        }
    }
    return [ordered]@{ denied = $found; inheritable = $inheritable; dacl_protected = $acl.AreAccessRulesProtected }
}

function Test-PrincipalWriteDenied {
    param([string]$Path, [string]$Sid)
    $deny = Get-PrincipalWriteDeny -Path $Path -Sid $Sid
    if ($null -eq $deny) { return $null }
    return $deny.denied
}

$principalSidForAcl = $null
$principalAccountForAcl = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
if ($principalAccountForAcl) { $principalSidForAcl = $principalAccountForAcl.SID.Value }

$scopedRootNormalised = if ($ScopedWorkspaceRoot) { $ScopedWorkspaceRoot.TrimEnd('\').ToLower() } else { $null }

$volumeAuthority = @{}
$otherWriteOffenders = New-Object System.Collections.ArrayList
$unreadableChildren = New-Object System.Collections.ArrayList

foreach ($disk in (Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction SilentlyContinue)) {
    $volume = "$($disk.DeviceID)\"
    $rootDeny = Get-PrincipalWriteDeny -Path $volume -Sid $principalSidForAcl
    $entry = [ordered]@{
        volume                 = $volume
        file_system            = $disk.FileSystem
        hosts_workspace_root   = [bool](@($WorkspaceRoots | Where-Object { $_ -like "$($disk.DeviceID)*" }).Count)
        hosts_scoped_root      = ($scopedRootNormalised -and $scopedRootNormalised.StartsWith($disk.DeviceID.ToLower()))
        grants_broad_write     = (Test-BroadWriteAllow $volume)
        root_write_denied      = if ($null -eq $rootDeny) { $null } else { $rootDeny.denied }
        root_deny_inheritable  = if ($null -eq $rootDeny) { $null } else { $rootDeny.inheritable }
        escaping_children      = @()
        acl_unreadable_children = @()
    }

    if ($entry.grants_broad_write) {
        # An inheritable root deny covers the volume. The only way a child can
        # escape it is a protected DACL, so those are the ones worth listing.
        $escaping = New-Object System.Collections.ArrayList
        $unreadable = New-Object System.Collections.ArrayList
        foreach ($dir in (Get-ChildItem -LiteralPath $volume -Directory -Force -ErrorAction SilentlyContinue)) {
            $isScoped = ($scopedRootNormalised -and $dir.FullName.TrimEnd('\').ToLower() -eq $scopedRootNormalised)
            if ($isScoped) { continue }
            $childDeny = Get-PrincipalWriteDeny -Path $dir.FullName -Sid $principalSidForAcl
            if ($null -eq $childDeny) {
                [void]$unreadable.Add($dir.Name)
                [void]$unreadableChildren.Add($dir.FullName)
                continue
            }
            if ($childDeny.denied) { continue }
            if ($childDeny.dacl_protected -or $entry.root_deny_inheritable -ne $true) {
                [void]$escaping.Add($dir.Name)
                [void]$otherWriteOffenders.Add($dir.FullName)
            }
        }
        $entry.escaping_children = @($escaping)
        $entry.acl_unreadable_children = @($unreadable)
        if ($entry.root_write_denied -ne $true) { [void]$otherWriteOffenders.Add($volume) }
    }

    $volumeAuthority[$volume] = $entry
}

$broadWriteVolumes = @($volumeAuthority.Values | Where-Object { $_.grants_broad_write })
$otherWriteAuthority = 'NO'
if ($otherWriteOffenders.Count -gt 0) {
    $otherWriteAuthority = if ($principalSidForAcl) { 'YES' } else { 'NOT_PROVEN' }
}

if ($otherWriteAuthority -eq 'NOT_PROVEN') {
    Add-Blocker 'OTHER_WRITE_AUTHORITY_NOT_PROVEN' "$($broadWriteVolumes.Count) local volume(s) grant inheritable write to Authenticated Users ($((($broadWriteVolumes | ForEach-Object { $_.volume }) -join ', '))), and '$AccountName' does not exist yet, so its effective write-denies cannot be read. Explicit workspace grants alone do not produce workspace-only write authority."
} elseif ($otherWriteAuthority -eq 'YES') {
    Add-Blocker 'OTHER_WRITE_AUTHORITY_PRESENT' "'$AccountName' can write outside the approved workspace roots. No write-deny covers: $(($otherWriteOffenders | Select-Object -Unique -First 8) -join ', ')."
}
if ($unreadableChildren.Count -gt 0) {
    Add-Warning 'CHILD_ACL_UNREADABLE_NON_ELEVATED' "$($unreadableChildren.Count) top-level container(s) could not be read from a non-elevated session (OS-managed containers such as `$Recycle.Bin and System Volume Information grant no write to Users in the first place). Re-run preflight elevated to record their effective deny state."
}

# A workspace root inside a denied volume only keeps its grant if its own DACL
# is protected; otherwise the inherited deny wins and the grant is dead letter.
foreach ($root in $WorkspaceRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $volume = ($root -split ':')[0] + ':\'
    if (-not $volumeAuthority.ContainsKey($volume)) { continue }
    if ($volumeAuthority[$volume].principal_write_denied -ne $true) { continue }
    $protectedDacl = $false
    try { $protectedDacl = (Get-Acl -LiteralPath $root).AreAccessRulesProtected } catch { }
    if (-not $protectedDacl) {
        Add-Blocker 'WORKSPACE_GRANT_DEFEATED_BY_INHERITED_DENY' "$root inherits a write-deny for $AccountName from $volume and its own DACL is not protected, so the workspace grant cannot take effect. Disable inheritance on the scoped root instead of removing the deny."
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
# uv is not a nice-to-have: harness.py prepare-runtime runs `uv sync --frozen`
# to build the pinned modern-Hermes venv, so without it the R5 minimum
# capability set cannot be reconstructed for the dedicated principal.
if ($toolFacts['uv'].scope -ne 'SYSTEM_WIDE') {
    Add-Blocker 'R5_MINIMUM_TOOLCHAIN_NOT_SYSTEM_WIDE' "uv resolves to $($toolFacts['uv'].resolved_path) ($($toolFacts['uv'].scope)). harness.py prepare-runtime runs 'uv sync --frozen', so $AccountName cannot rebuild the pinned venv. Install uv machine-wide; do NOT open the host profile to reach this copy."
}
foreach ($optional in @('node', 'npm')) {
    if ($toolFacts[$optional].on_host_path -and $toolFacts[$optional].scope -eq 'USER_PROFILE_ONLY') {
        Add-Warning 'POST_R5_DX_TOOL_NOT_SYSTEM_WIDE' "$optional resolves into a user profile and will be unavailable to $AccountName. This is POST_R5_DEVELOPER_DX, not R5 acceptance; it is also what keeps the host Railway CLI shim out of reach, so do not fix it by exposing the profile."
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

# ------------------------- 4b. live vs proven-retired secret authority
#
# Not every historical blob still commands something. The classifier in
# scripts/r5_developer_hermes/retired_authority.py holds the evidence contract:
# one exact path at a time, every element verified against git metadata, and
# anything unverifiable stays LIVE_OR_UNKNOWN. If it cannot run, every finding
# is treated as live.

function Invoke-SecretAuthorityClassifier {
    param([array]$Findings)

    $fallback = [ordered]@{
        schema                                  = 'r5.secret_authority_classification.v1'
        entries                                 = @()
        ACTIVE_WORKSPACE_SECRET_FILES           = @($Findings | Where-Object { $_.size -gt 0 }).Count
        UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY = @($Findings | Where-Object { $_.size -le 0 -and ($_.git_tracked -or $_.in_git_history) }).Count
        HISTORICAL_DEAD_AUTHORITY               = 0
        SECRET_AUTHORITY_BLOCKED                = ($Findings.Count -gt 0)
        classifier                              = 'UNAVAILABLE_FAILED_CLOSED'
    }

    $python = (Get-Command 'python' -ErrorAction SilentlyContinue)
    $module = Join-Path $RepoRoot 'scripts\r5_developer_hermes\retired_authority.py'
    if (-not $python -or -not (Test-Path -LiteralPath $module)) {
        Add-Blocker 'SECRET_CLASSIFIER_UNAVAILABLE' 'Cannot run retired_authority.py (python or module missing), so every secret-class finding stays classified as live authority.'
        return $fallback
    }

    $dir = Join-Path $RepoRoot '.r5-dev\artifacts'
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $inPath  = Join-Path $dir 'secret_findings.json'
    $outPath = Join-Path $dir 'secret_authority_classification.json'

    # Windows PowerShell collapses a single-element array and serialises a
    # comma-wrapped one as {"value":[...],"Count":n}. Both shapes would reach
    # the classifier as "no findings", so build the array text explicitly.
    $items = @($Findings | ForEach-Object { $_ | ConvertTo-Json -Depth 6 -Compress })
    Set-Content -LiteralPath $inPath -Value ('[' + ($items -join ',') + ']') -Encoding UTF8
    & $python.Source $module --findings $inPath --out $outPath *> $null

    if (-not (Test-Path -LiteralPath $outPath)) {
        Add-Blocker 'SECRET_CLASSIFIER_FAILED' 'retired_authority.py produced no classification, so every secret-class finding stays classified as live authority.'
        return $fallback
    }
    try {
        return (Get-Content -LiteralPath $outPath -Raw | ConvertFrom-Json)
    } catch {
        Add-Blocker 'SECRET_CLASSIFIER_UNREADABLE' "Cannot parse the classification ($($_.Exception.GetType().Name)); findings stay classified as live authority."
        return $fallback
    }
}

$classification = Invoke-SecretAuthorityClassifier -Findings @($secretFindings)

# A classification that silently covers fewer findings than were scanned would
# read as "clean". Treat any shortfall as unresolved authority.
$classifiedCount = @($classification.entries).Count
if ($classifiedCount -ne @($secretFindings).Count) {
    Add-Blocker 'SECRET_CLASSIFICATION_INCOMPLETE' "The scan found $(@($secretFindings).Count) secret-class file(s) but the classifier returned $classifiedCount verdict(s). Unclassified findings are treated as live authority."
}

$activeSecretFiles   = [int]$classification.ACTIVE_WORKSPACE_SECRET_FILES
$unresolvedAuthority = [int]$classification.UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY
$deadAuthority       = [int]$classification.HISTORICAL_DEAD_AUTHORITY

if ($activeSecretFiles -gt 0) {
    Add-Blocker 'ACTIVE_WORKSPACE_SECRET_FILES' "$activeSecretFiles secret-class file(s) still hold content inside the workspace roots that $AccountName must be able to write. Relocate them to the host-only secret root; no OS boundary can hide a file in a tree the principal writes."
}
if ($unresolvedAuthority -gt 0) {
    Add-Blocker 'UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY' "$unresolvedAuthority secret-class file(s) are reachable through git object storage with live or unknown authority. Denying read on the working-tree file does not close this, and denying read on .git would destroy the required GIT capability. Rotate the credential, or record verifiable retirement evidence."
}
foreach ($entry in @($classification.entries)) {
    if ($entry.verdict -eq 'PROVEN_RETIRED_SECRET_AUTHORITY') {
        Add-Warning 'HISTORICAL_DEAD_AUTHORITY' "$($entry.relative_path) remains in git history but its authority is proven retired ($($entry.authority_target)). Informational: it is not a security blocker while the evidence contract holds."
    }
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

# ------------------------------------------------- 8. host-only secret layout
#
# Phase C must be able to assert that the relocated secrets are unreachable, so
# the exact external paths are recorded here. Paths are not secrets; the ACL on
# the host profile is what protects the contents.

$hostSecretFacts = [ordered]@{
    root        = $HostSecretRoot
    root_exists = (Test-Path -LiteralPath $HostSecretRoot)
    inside_profile = ($HostSecretRoot.TrimEnd('\') -like "$((Resolve-Path -LiteralPath $env:USERPROFILE).Path.TrimEnd('\'))\*")
    files       = @()
}
$hostSecretFiles = New-Object System.Collections.ArrayList
foreach ($name in @('repo-b.env', 'app.env', 'mapbox.env')) {
    $path = Join-Path $HostSecretRoot $name
    [void]$hostSecretFiles.Add([ordered]@{
        path   = $path
        exists = (Test-Path -LiteralPath $path)
    })
}
$hostSecretFacts.files = @($hostSecretFiles)
if (-not $hostSecretFacts.inside_profile) {
    Add-Blocker 'HOST_SECRET_ROOT_OUTSIDE_PROFILE' "$HostSecretRoot is not inside the host profile, so nothing guarantees $AccountName cannot read it."
}
if (-not $hostSecretFacts.root_exists) {
    Add-Warning 'HOST_SECRET_ROOT_ABSENT' "$HostSecretRoot does not exist yet. Run bootstrap-host-secrets.ps1 before relying on relocation."
}

# Reachability is decided by the ACL, so it can be answered before the account
# exists: a root with no broad allow and no principal allow is out of reach.
function Test-AnyAllowFor {
    param([string]$Path, [string[]]$Sids)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try { $acl = Get-Acl -LiteralPath $Path } catch { return $null }
    foreach ($ace in $acl.Access) {
        if ($ace.AccessControlType -ne 'Allow') { continue }
        $sid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { continue }
        if ($sid -in $Sids) { return $true }
    }
    return $false
}

$broadSids = @($SID_USERS, $SID_AUTH_USERS, $SID_EVERYONE)
$secretRootSids = if ($principalSidForAcl) { $broadSids + @($principalSidForAcl) } else { $broadSids }
$secretRootAllow = Test-AnyAllowFor -Path $HostSecretRoot -Sids $secretRootSids
$hostSecretFacts.principal_or_broad_allow = $secretRootAllow
$hostSecretRootReachable = switch ($secretRootAllow) {
    $true   { 'YES' }
    $false  { 'NO' }
    default { 'NOT_PROVEN' }
}
$hostSecretFacts.reachable_by_principal = $hostSecretRootReachable
if ($hostSecretRootReachable -eq 'YES') {
    Add-Blocker 'HOST_ONLY_SECRET_ROOT_REACHABLE' "$HostSecretRoot carries an allow ACE for a group $AccountName belongs to (or for the account itself). The relocation gains nothing while that stands."
} elseif ($hostSecretRootReachable -eq 'NOT_PROVEN') {
    Add-Blocker 'HOST_ONLY_SECRET_ROOT_NOT_PROVEN' "Cannot read the ACL of $HostSecretRoot, so its unreachability is unproven."
}

$hostProfileRoot = (Resolve-Path -LiteralPath $env:USERPROFILE).Path
$hostProfileAllow = Test-AnyAllowFor -Path $hostProfileRoot -Sids $secretRootSids
$hostProfileReadDesign = switch ($hostProfileAllow) {
    $true   { 'YES' }
    $false  { 'NO' }
    default { 'NOT_PROVEN' }
}
if ($hostProfileReadDesign -ne 'NO') {
    Add-Blocker 'HOST_PROFILE_READABLE_BY_DESIGN' "$hostProfileRoot does not provably exclude $AccountName (allow-for-broad-group = $hostProfileAllow). Do not widen this; the default profile ACL is what carries the boundary."
}

# A relocation that leaves a link behind restores exactly the reachability it
# was meant to remove, so the origins are checked for reparse points.
$relocationOrigins = @(
    (Join-Path $WorkspaceRoots[-1] '.env'),
    (Join-Path $WorkspaceRoots[-1] 'app\.env.local'),
    (Join-Path $WorkspaceRoots[-1] 'scripts\mapbox\.env.local')
)
$linkFindings = New-Object System.Collections.ArrayList
foreach ($origin in $relocationOrigins) {
    if (-not (Test-Path -LiteralPath $origin)) { continue }
    $item = Get-Item -LiteralPath $origin -Force
    if ($item.LinkType) {
        [void]$linkFindings.Add([ordered]@{ path = $origin; link_type = $item.LinkType; target = @($item.Target) })
        Add-Blocker 'WORKSPACE_LINK_INTO_SECRET_ROOT' "$origin is a $($item.LinkType). A link makes the external secret readable through the workspace again; delete it and inject through the environment instead."
    }
}

# ------------------------------------------------------- 9. authority gates
#
# A READY result must mean the intended authority boundary, not merely that
# explicit workspace ACEs could be added. Each gate is derived from evidence
# collected above and fails closed.

$workspaceDesign = @{}
foreach ($root in $WorkspaceRoots) {
    $verdict = 'YES'
    $detail  = 'grantable: local fixed NTFS, no inherited deny in the way'
    if (-not (Test-Path -LiteralPath $root)) {
        $verdict = 'NO'; $detail = 'workspace root does not exist'
    } elseif ($driveFacts[$root].drive_type -ne 'LOCAL_FIXED' -or $driveFacts[$root].is_subst -or $driveFacts[$root].file_system -ne 'NTFS') {
        $verdict = 'NO'; $detail = "unsuitable volume ($($driveFacts[$root].drive_type)/$($driveFacts[$root].file_system), subst=$($driveFacts[$root].is_subst))"
    } else {
        $volume = ($root -split ':')[0] + ':\'
        $inheritedDeny = ($volumeAuthority.ContainsKey($volume) -and $volumeAuthority[$volume].principal_write_denied -eq $true)
        $protectedDacl = $false
        try { $protectedDacl = (Get-Acl -LiteralPath $root).AreAccessRulesProtected } catch { }
        if ($inheritedDeny -and -not $protectedDacl) {
            $verdict = 'NO'; $detail = "inherited write-deny from $volume would defeat the grant; protect this DACL instead"
        }
    }
    $workspaceDesign[$root] = [ordered]@{ root = $root; rw_design = $verdict; detail = $detail }
}

$orderedRoots = @($WorkspaceRoots)
$repoARwDesign = if ($orderedRoots.Count -ge 1) { $workspaceDesign[$orderedRoots[0]].rw_design } else { 'NO' }
$repoBRwDesign = if ($orderedRoots.Count -ge 2) { $workspaceDesign[$orderedRoots[1]].rw_design } else { 'NO' }

$gates = [ordered]@{
    ACTIVE_WORKSPACE_SECRET_FILES                 = $activeSecretFiles
    UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY       = $unresolvedAuthority
    HISTORICAL_DEAD_AUTHORITY                     = $deadAuthority
    HOST_ONLY_SECRET_ROOT_REACHABLE_BY_HERMES_DEV = $hostSecretRootReachable
    OTHER_WRITE_AUTHORITY                         = $otherWriteAuthority
    REPO_A_RW_DESIGN                              = $repoARwDesign
    REPO_B_RW_DESIGN                              = $repoBRwDesign
    HOST_PROFILE_READ_DESIGN                      = $hostProfileReadDesign
    R5_MINIMUM_TOOLCHAIN                          = if ($toolFacts['uv'].scope -eq 'SYSTEM_WIDE' -and $toolFacts['python'].scope -eq 'SYSTEM_WIDE' -and $toolFacts['git'].scope -eq 'SYSTEM_WIDE') { 'AVAILABLE' } else { 'INCOMPLETE' }
}

$gatesPassed = (
    $gates.ACTIVE_WORKSPACE_SECRET_FILES -eq 0 -and
    $gates.UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY -eq 0 -and
    $gates.HOST_ONLY_SECRET_ROOT_REACHABLE_BY_HERMES_DEV -eq 'NO' -and
    $gates.OTHER_WRITE_AUTHORITY -eq 'NO' -and
    $gates.REPO_A_RW_DESIGN -eq 'YES' -and
    $gates.REPO_B_RW_DESIGN -eq 'YES' -and
    $gates.HOST_PROFILE_READ_DESIGN -eq 'NO' -and
    $gates.R5_MINIMUM_TOOLCHAIN -eq 'AVAILABLE'
)

# ------------------------------------------------------------------ report

$report = [ordered]@{
    schema                   = 'r5.principal_preflight.v2'
    generated_utc            = (Get-Date).ToUniversalTime().ToString('o')
    repo_root                = $RepoRoot
    account                  = $accountFacts
    workspace_roots          = $WorkspaceRoots
    drives                   = $driveFacts
    workspace_acls           = $aclFacts
    scoped_workspace_root    = $ScopedWorkspaceRoot
    volume_authority         = $volumeAuthority
    other_write_offenders    = @($otherWriteOffenders | Select-Object -Unique)
    workspace_rw_design      = $workspaceDesign
    toolchain                = $toolFacts
    pinned_runtime           = $runtimeFacts
    in_workspace_secret_files = @($secretFindings)
    secret_authority         = $classification
    host_secret_layout       = $hostSecretFacts
    workspace_links_into_secret_root = @($linkFindings)
    host_credential_stores   = $storeFacts
    deploy_cli_absolute_candidates = @($deployCandidates)
    host_profile_sentinel    = $sentinelFacts
    warnings                 = @($warnings)
    blockers                 = @($blockers)
    gates                    = $gates
    PREFLIGHT_RESULT         = if ($blockers.Count -eq 0 -and $gatesPassed) { 'READY_FOR_PROVISIONING' } else { 'BLOCKED' }
}

$artifactDir = Split-Path $ArtifactPath -Parent
if (-not (Test-Path -LiteralPath $artifactDir)) { New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ArtifactPath -Encoding UTF8

Write-Host ''
Write-Host '--- authority gates ---'
foreach ($key in $gates.Keys) { Write-Host ("{0,-46} = {1}" -f $key, $gates[$key]) }
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
