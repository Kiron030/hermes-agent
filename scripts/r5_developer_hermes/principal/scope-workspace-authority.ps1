<#
.SYNOPSIS
    Scopes the dedicated principal's write authority to one workspace root, by
    creating that root with a protected DACL and denying write everywhere else
    on the local fixed volumes.

.DESCRIPTION
    provision-principal.ps1 is strictly additive: it grants, never removes. That
    is the right contract for granting, but it cannot produce the property R5
    actually needs. Every local volume root on this class of host carries an
    inheritable Allow for Authenticated Users, so a fresh standard account
    inherits write across whole volumes before any grant is made. Removing that
    Allow is not an option: on this host it is the only ACE that gives the
    non-elevated host user write access to its own data, because its
    Administrators membership is deny-only in an unelevated token.

    So the authority is scoped from the other side, with two mutations that add
    nothing to any existing principal:

      1. A scoped workspace root is CREATED with inheritance disabled, holding
         an explicit ACL: Administrators, SYSTEM, the host user, and the
         dedicated principal. Nothing else.
      2. An inheritable WRITE-deny for the dedicated principal is added at each
         volume root. Read and execute are left alone, so no tool, service or
         OS path breaks, and traversal never depends on a privilege.

    Because the scoped root's DACL is protected, the volume-root deny cannot
    reach into it: the workspace grant survives. That is the whole design.

    Every DACL this script touches is exported to a backup file BEFORE any
    mutation. rollback-workspace-authority.ps1 restores from that file.

    Run from an ELEVATED PowerShell session. Run preflight-principal.ps1 first.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\scope-workspace-authority.ps1 -WhatIf
    powershell -ExecutionPolicy Bypass -File .\scope-workspace-authority.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]   $AccountName          = 'hermes-dev',

    # Created by this script. Must not already exist as an unprotected host
    # directory: protecting someone else's directory is not this script's job.
    [string]   $ScopedWorkspaceRoot  = 'W:\hermes-dev',

    # Volume roots that receive the inheritable write-deny. Default is every
    # local fixed volume, because host data lives on more than one of them.
    [string[]] $DenyWriteVolumes     = @(),

    # The human account that must keep full access to the scoped root.
    [string]   $HostUserSid          = ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value),

    [string]   $BackupPath,
    [string]   $ArtifactPath
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
if (-not $BackupPath)   { $BackupPath   = Join-Path $RepoRoot ".r5-dev\acl-backups\acl_backup_$stamp.json" }
if (-not $ArtifactPath) { $ArtifactPath = Join-Path $RepoRoot '.r5-dev\artifacts\workspace_authority.json' }

$SID_ADMINISTRATORS = 'S-1-5-32-544'
$SID_SYSTEM         = 'S-1-5-18'

$actions = New-Object System.Collections.ArrayList
function Add-Action([string]$Kind, [string]$Target, [string]$Detail, [string]$State) {
    [void]$actions.Add([ordered]@{ kind = $Kind; target = $Target; detail = $Detail; state = $State })
    Write-Host ("  {0,-9} {1,-10} {2}" -f $State, $Kind, $Detail)
}

# ------------------------------------------------------------ guard: elevation

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must run ELEVATED. It creates a directory and edits volume-root ACLs.`n`n  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit 2
}

# ------------------------------------------------------- guard: the principal

$account = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
if (-not $account) {
    Write-Error "'$AccountName' does not exist. Run provision-principal.ps1 first; this script scopes an existing principal's authority."
    exit 2
}
$accountSid = $account.SID.Value

$isAdmin = $false
try {
    $isAdmin = [bool](@(Get-LocalGroupMember -SID $SID_ADMINISTRATORS -ErrorAction Stop |
                        Where-Object { $_.Name -match "\\$AccountName$" }).Count)
} catch { }
if ($isAdmin) {
    Write-Error "'$AccountName' is an administrator. Scoping its file authority would be theatre. Remove it from Administrators first."
    exit 2
}

# -------------------------------------------- guard: never scope a profile path

$profileRoot = (Join-Path $env:SystemDrive 'Users')
if ($ScopedWorkspaceRoot.TrimEnd('\') -like "$profileRoot*") {
    Write-Error "Refusing to operate on '$ScopedWorkspaceRoot': it is inside the user profile tree."
    exit 2
}

if (-not $DenyWriteVolumes -or $DenyWriteVolumes.Count -eq 0) {
    $DenyWriteVolumes = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
                          ForEach-Object { "$($_.DeviceID)\" })
}

Write-Host ''
Write-Host 'R5 workspace authority scoping'
Write-Host "  principal   : $AccountName ($accountSid)"
Write-Host "  scoped root : $ScopedWorkspaceRoot"
Write-Host "  deny write  : $($DenyWriteVolumes -join ', ')"
Write-Host "  acl backup  : $BackupPath"
Write-Host ''

# ------------------------------------------------- 1. back up every DACL first

$backupTargets = @(@($ScopedWorkspaceRoot) + $DenyWriteVolumes | Select-Object -Unique)
$backupEntries = New-Object System.Collections.ArrayList
foreach ($path in $backupTargets) {
    if (-not (Test-Path -LiteralPath $path)) {
        [void]$backupEntries.Add([ordered]@{ path = $path; existed = $false; sddl = $null })
        continue
    }
    [void]$backupEntries.Add([ordered]@{
        path    = $path
        existed = $true
        sddl    = (Get-Acl -LiteralPath $path).Sddl
    })
}
$backup = [ordered]@{
    schema        = 'r5.acl_backup.v1'
    captured_utc  = (Get-Date).ToUniversalTime().ToString('o')
    account_name  = $AccountName
    account_sid   = $accountSid
    scoped_root   = $ScopedWorkspaceRoot
    entries       = @($backupEntries)
}
$backupDir = Split-Path $BackupPath -Parent
if (-not (Test-Path -LiteralPath $backupDir)) { New-Item -ItemType Directory -Force -Path $backupDir | Out-Null }
$backup | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $BackupPath -Encoding UTF8
Add-Action 'backup' $BackupPath "captured $($backupEntries.Count) DACL(s) before any mutation" 'WRITTEN'

# --------------------------------------------- 2. scoped root with protected DACL

$scopedExisted = Test-Path -LiteralPath $ScopedWorkspaceRoot
if ($scopedExisted) {
    $existingAcl = Get-Acl -LiteralPath $ScopedWorkspaceRoot
    if (-not $existingAcl.AreAccessRulesProtected) {
        Write-Error "Refusing to operate on '$ScopedWorkspaceRoot': it already exists with an inheriting DACL, so it may be a pre-existing host directory. Choose a path this script can create, or protect it deliberately by hand."
        exit 2
    }
    Add-Action 'scoped-root' $ScopedWorkspaceRoot 'already exists with a protected DACL' 'PRESENT'
} else {
    if ($PSCmdlet.ShouldProcess($ScopedWorkspaceRoot, 'Create scoped workspace root')) {
        New-Item -ItemType Directory -Force -Path $ScopedWorkspaceRoot | Out-Null
        Add-Action 'scoped-root' $ScopedWorkspaceRoot 'created' 'CREATED'
    } else {
        Add-Action 'scoped-root' $ScopedWorkspaceRoot 'would create' 'WHATIF'
    }
}

function New-FullControlRule([string]$Sid) {
    New-Object System.Security.AccessControl.FileSystemAccessRule(
        (New-Object System.Security.Principal.SecurityIdentifier($Sid)),
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
         [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow)
}
function New-ModifyRule([string]$Sid) {
    New-Object System.Security.AccessControl.FileSystemAccessRule(
        (New-Object System.Security.Principal.SecurityIdentifier($Sid)),
        [System.Security.AccessControl.FileSystemRights]::Modify,
        ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
         [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow)
}

if ((Test-Path -LiteralPath $ScopedWorkspaceRoot) -and
    $PSCmdlet.ShouldProcess($ScopedWorkspaceRoot, 'Protect DACL and set the scoped ACL')) {
    $acl = Get-Acl -LiteralPath $ScopedWorkspaceRoot
    # $true, $false: stop inheriting AND drop the inherited entries, so the
    # volume-root deny added below cannot reach the grants inside this root.
    # A freshly created directory carries no explicit entries, so nothing that
    # a human authored is discarded here.
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FullControlRule $SID_ADMINISTRATORS))
    $acl.AddAccessRule((New-FullControlRule $SID_SYSTEM))
    $acl.AddAccessRule((New-ModifyRule $HostUserSid))
    $acl.AddAccessRule((New-ModifyRule $accountSid))
    Set-Acl -LiteralPath $ScopedWorkspaceRoot -AclObject $acl
    Add-Action 'scoped-acl' $ScopedWorkspaceRoot "inheritance disabled; Modify for $AccountName and the host user, FullControl for Administrators and SYSTEM" 'CHANGED'
} else {
    Add-Action 'scoped-acl' $ScopedWorkspaceRoot 'would disable inheritance and set the scoped ACL' 'WHATIF'
}

# ------------------------------------------ 3. inheritable write-deny per volume

$WRITE_DENY_RIGHTS =
    [System.Security.AccessControl.FileSystemRights]::Write -bor
    [System.Security.AccessControl.FileSystemRights]::Delete -bor
    [System.Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
    [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
    [System.Security.AccessControl.FileSystemRights]::TakeOwnership

function Test-HasWriteDeny {
    param($Acl, [string]$Sid)
    foreach ($ace in $Acl.Access) {
        if ($ace.AccessControlType -ne 'Deny') { continue }
        $aceSid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { continue }
        if ($aceSid -ne $Sid) { continue }
        if (([int]$ace.FileSystemRights -band [int]$WRITE_DENY_RIGHTS) -ne 0) { return $true }
    }
    return $false
}

foreach ($volume in $DenyWriteVolumes) {
    if (-not (Test-Path -LiteralPath $volume)) {
        Add-Action 'deny' $volume 'volume not present' 'ABSENT'
        continue
    }
    $acl = Get-Acl -LiteralPath $volume
    if (Test-HasWriteDeny -Acl $acl -Sid $accountSid) {
        Add-Action 'deny' $volume "write-deny for $AccountName already present" 'PRESENT'
        continue
    }
    if (-not $PSCmdlet.ShouldProcess($volume, "Deny write to $AccountName (inheritable)")) {
        Add-Action 'deny' $volume "would deny write to $AccountName" 'WHATIF'
        continue
    }
    # Read and execute are deliberately NOT denied. Denying them would break
    # tools that read machine-wide state and would make traversal depend on the
    # bypass-traverse-checking privilege.
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        (New-Object System.Security.Principal.SecurityIdentifier($accountSid)),
        $WRITE_DENY_RIGHTS,
        ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
         [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Deny)
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $volume -AclObject $acl
    Add-Action 'deny' $volume "denied write to $AccountName (ContainerInherit, ObjectInherit)" 'CHANGED'
}

# ------------------------------------------------------------------- 4. report

$report = [ordered]@{
    schema                = 'r5.workspace_authority.v1'
    generated_utc         = (Get-Date).ToUniversalTime().ToString('o')
    account_name          = $AccountName
    account_sid           = $accountSid
    scoped_workspace_root = $ScopedWorkspaceRoot
    scoped_root_pre_existed = $scopedExisted
    host_user_sid         = $HostUserSid
    deny_write_volumes    = @($DenyWriteVolumes)
    acl_backup_path       = $BackupPath
    actions               = @($actions)
    existing_ace_removed  = $false
    broad_ace_modified    = $false
    read_access_denied    = $false
    whatif                = [bool]$WhatIfPreference
}
$artifactDir = Split-Path $ArtifactPath -Parent
if (-not (Test-Path -LiteralPath $artifactDir)) { New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ArtifactPath -Encoding UTF8

Write-Host ''
Write-Host "artifact   = $ArtifactPath"
Write-Host "acl backup = $BackupPath"
Write-Host ''
Write-Host 'Rollback:'
Write-Host "  powershell -ExecutionPolicy Bypass -File .\rollback-workspace-authority.ps1 -BackupPath `"$BackupPath`""
Write-Host ''
Write-Host 'Next: clone the working copies into the scoped root, then re-run preflight-principal.ps1'
Write-Host '      with -WorkspaceRoots pointing at them.'
