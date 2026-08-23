<#
.SYNOPSIS
    Provisions the dedicated, non-administrative Windows principal that carries
    the R5 isolation boundary.

.DESCRIPTION
    Idempotent. Every mutation is additive: existing ACL entries are preserved,
    inheritance is never broken, and no ACL is ever reset. The script refuses to
    touch the host user's profile.

    The account password is requested interactively and is never written to disk,
    to the repository, or to any artifact.

    Run from an ELEVATED PowerShell session.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1 -WhatIf
    powershell -ExecutionPolicy Bypass -File .\provision-principal.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]   $AccountName    = 'hermes-dev',
    [string]   $FullName       = 'Hermes Developer (R5 isolated principal)',
    [string[]] $WorkspaceRoots = @('W:\Workbench\hermes-agent', 'W:\Workbench\EU-PP-Database'),

    # Verified as readable, never modified. Declared so the report can state
    # which toolchain locations the boundary depends on.
    [string[]] $ToolchainPaths = @('C:\Python311', 'C:\Program Files\Git', 'C:\Program Files\GitHub CLI'),

    # Host-only secret root. Named solely so this script can refuse to grant it.
    [string]   $HostSecretRoot = (Join-Path $env:USERPROFILE '.powerunits\secrets'),

    # Opt-in, PARTIAL mitigation for secret-class files that live inside the
    # approved workspace. Read the caveat printed at the end before relying on it.
    [switch]   $DenyInWorkspaceSecrets,
    [string[]] $InWorkspaceSecretFiles = @(),

    [string]   $ArtifactPath
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $ArtifactPath) {
    $ArtifactPath = Join-Path $RepoRoot '.r5-dev\artifacts\principal_provision.json'
}

$SID_ADMINISTRATORS = 'S-1-5-32-544'
$SID_USERS          = 'S-1-5-32-545'

$actions = New-Object System.Collections.ArrayList
function Add-Action([string]$Kind, [string]$Target, [string]$Detail, [string]$State) {
    [void]$actions.Add([ordered]@{ kind = $Kind; target = $Target; detail = $Detail; state = $State })
    Write-Host ("  {0,-10} {1,-12} {2}" -f $State, $Kind, $Detail)
}

# ------------------------------------------------------------ guard: elevation

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error @"
This script must run ELEVATED. It creates a local account and edits ACLs.

Start an elevated PowerShell and run:

  powershell -ExecutionPolicy Bypass -File "$PSCommandPath"
"@
    exit 2
}

# --------------------------------------------------- guard: never touch a profile

$forbiddenPrefixes = @(
    (Join-Path $env:SystemDrive 'Users\'),
    $env:USERPROFILE
)
foreach ($root in $WorkspaceRoots) {
    foreach ($forbidden in $forbiddenPrefixes) {
        if ($root.TrimEnd('\') -like "$($forbidden.TrimEnd('\'))*") {
            Write-Error "Refusing to operate on '$root': it is inside a user profile. The whole point of this boundary is that user profiles stay out of reach."
            exit 2
        }
    }
    # Named separately from the generic profile guard so the reason is unambiguous
    # in the transcript: the host-only secret root is the relocation target and
    # granting it would undo the relocation.
    if ($root.TrimEnd('\') -like "$($HostSecretRoot.TrimEnd('\'))*") {
        Write-Error "Refusing to operate on '$root': it is the host-only secret root. Relocating secrets there and then granting access to it would cancel out."
        exit 2
    }
    if (-not (Test-Path -LiteralPath $root)) {
        Write-Error "Workspace root '$root' does not exist. Run preflight-principal.ps1 first."
        exit 2
    }
}

Write-Host ''
Write-Host "R5 dedicated principal provisioning"
Write-Host "  account   : $AccountName"
Write-Host "  workspaces: $($WorkspaceRoots -join ', ')"
Write-Host ''

# ----------------------------------------------------------- 1. local account

$account = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
if ($account) {
    Add-Action 'account' $AccountName "local account '$AccountName' already exists" 'PRESENT'
} else {
    if ($PSCmdlet.ShouldProcess($AccountName, 'Create standard local account')) {
        Write-Host ''
        Write-Host "Choose a password for '$AccountName'. It is never stored by this script."
        $secret = Read-Host -AsSecureString "Password for $AccountName"
        $confirm = Read-Host -AsSecureString "Confirm password"
        $a = [Runtime.InteropServices.Marshal]::PtrToStringUni([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret))
        $b = [Runtime.InteropServices.Marshal]::PtrToStringUni([Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirm))
        $matched = ($a -ceq $b)
        $a = $null; $b = $null
        [GC]::Collect()
        if (-not $matched) {
            Write-Error 'Passwords did not match. Nothing was created.'
            exit 2
        }
        $account = New-LocalUser -Name $AccountName `
                                 -FullName $FullName `
                                 -Description 'R5 Developer Hermes. Workspace-only. No production authority.' `
                                 -Password $secret `
                                 -PasswordNeverExpires `
                                 -AccountNeverExpires
        $secret = $null
        Add-Action 'account' $AccountName "created standard local account '$AccountName'" 'CREATED'
    } else {
        Add-Action 'account' $AccountName "would create standard local account '$AccountName'" 'WHATIF'
    }
}

# --------------------------------------------- 2. group membership: Users, not Admins

$inAdmins = $false
try {
    $inAdmins = [bool](@(Get-LocalGroupMember -SID $SID_ADMINISTRATORS -ErrorAction Stop |
                         Where-Object { $_.Name -match "\\$AccountName$" }).Count)
} catch {
}
if ($inAdmins) {
    Write-Error "'$AccountName' is a member of Administrators. That defeats the entire boundary. Remove it manually and re-run; this script will not silently change administrative group membership."
    exit 2
}
Add-Action 'group' 'Administrators' "'$AccountName' is not an administrator" 'VERIFIED'

$inUsers = $false
try {
    $inUsers = [bool](@(Get-LocalGroupMember -SID $SID_USERS -ErrorAction Stop |
                        Where-Object { $_.Name -match "\\$AccountName$" }).Count)
} catch {
}
if (-not $inUsers) {
    if ($PSCmdlet.ShouldProcess($AccountName, 'Add to the local Users group')) {
        try {
            Add-LocalGroupMember -SID $SID_USERS -Member $AccountName -ErrorAction Stop
            Add-Action 'group' 'Users' "'$AccountName' added to the local Users group" 'CHANGED'
        } catch {
            Add-Action 'group' 'Users' "could not add to Users: $($_.Exception.Message)" 'FAILED'
        }
    } else {
        Add-Action 'group' 'Users' "would add '$AccountName' to the local Users group" 'WHATIF'
    }
} else {
    Add-Action 'group' 'Users' "'$AccountName' already in the local Users group" 'PRESENT'
}

$accountSid = $null
$resolved = Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue
if ($resolved) { $accountSid = $resolved.SID.Value }

# ------------------------------------------------------------ 3. ACL helpers

function Test-HasExplicitRule {
    param($Acl, [string]$Sid, [string]$Rights, [string]$Type)
    foreach ($ace in $Acl.Access) {
        if ($ace.IsInherited) { continue }
        $aceSid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { continue }
        if ($aceSid -ne $Sid) { continue }
        if ($ace.AccessControlType.ToString() -ne $Type) { continue }
        if ($ace.FileSystemRights.ToString() -eq $Rights) { return $true }
    }
    return $false
}

# Statement-position `try` (not a parenthesized pipeline expression). Windows
# PowerShell 5.1 treats `(try { ... } catch { ... })` inside Where-Object as
# the command name "try" and throws CommandNotFoundException.
function Test-UsersGroupReadExecute {
    param($Acl, [string]$Sid)
    foreach ($ace in $Acl.Access) {
        if ($ace.AccessControlType -ne 'Allow') { continue }
        $aceSid = try { $ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { '' }
        if ($aceSid -ne $Sid) { continue }
        if ($ace.FileSystemRights.ToString() -match 'ReadAndExecute|Modify|FullControl') {
            return $true
        }
    }
    return $false
}

function Grant-InheritedModify {
    param([string]$Path, [string]$Sid)
    $acl = Get-Acl -LiteralPath $Path
    if (Test-HasExplicitRule -Acl $acl -Sid $Sid -Rights 'Modify, Synchronize' -Type 'Allow') {
        Add-Action 'acl' $Path 'Modify grant already present' 'PRESENT'
        return
    }
    if (-not $PSCmdlet.ShouldProcess($Path, "Grant Modify (inherited) to $AccountName")) {
        Add-Action 'acl' $Path "would grant Modify to $AccountName" 'WHATIF'
        return
    }
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        (New-Object System.Security.Principal.SecurityIdentifier($Sid)),
        [System.Security.AccessControl.FileSystemRights]::Modify,
        ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
         [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow)
    # AddAccessRule is additive. No SetAccessRuleProtection, no RemoveAccessRule,
    # no purge: every pre-existing entry and all inheritance survive untouched.
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
    Add-Action 'acl' $Path "granted Modify (ContainerInherit, ObjectInherit) to $AccountName" 'CHANGED'
}

function Grant-TraverseOnly {
    param([string]$Path, [string]$Sid)
    $acl = Get-Acl -LiteralPath $Path
    if (Test-HasExplicitRule -Acl $acl -Sid $Sid -Rights 'ReadAndExecute, Synchronize' -Type 'Allow') {
        Add-Action 'acl' $Path 'traverse grant already present' 'PRESENT'
        return
    }
    if (-not $PSCmdlet.ShouldProcess($Path, "Grant this-folder-only traverse to $AccountName")) {
        Add-Action 'acl' $Path "would grant traverse to $AccountName" 'WHATIF'
        return
    }
    # InheritanceFlags None: the grant applies to this container only and does not
    # cascade into sibling content on the volume.
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        (New-Object System.Security.Principal.SecurityIdentifier($Sid)),
        [System.Security.AccessControl.FileSystemRights]::ReadAndExecute,
        [System.Security.AccessControl.InheritanceFlags]::None,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
    Add-Action 'acl' $Path "granted this-folder-only traverse to $AccountName" 'CHANGED'
}

# ------------------------------------------- 4. workspace grants (least privilege)

if ($accountSid) {
    foreach ($root in $WorkspaceRoots) {
        # Ancestors get traverse only, so the principal can reach the workspace
        # without gaining rights over unrelated content on the volume.
        $ancestors = @()
        $cursor = Split-Path $root -Parent
        while ($cursor) {
            $ancestors = @($cursor) + $ancestors
            $parent = Split-Path $cursor -Parent
            if ($parent -eq $cursor -or -not $parent) {
                if ($cursor -notmatch '^[A-Za-z]:\\$') { $ancestors = @("$(($cursor -split ':')[0]):\") + $ancestors }
                break
            }
            $cursor = $parent
        }
        foreach ($ancestor in ($ancestors | Select-Object -Unique)) { Grant-TraverseOnly -Path $ancestor -Sid $accountSid }
        Grant-InheritedModify -Path $root -Sid $accountSid
    }
} else {
    Add-Action 'acl' '-' 'account SID unavailable (WhatIf run); no ACL changes attempted' 'WHATIF'
}

# ------------------------------------------- 4b. toolchain: verify, never grant
#
# The dedicated principal executes Python and git from machine-wide locations.
# On this host those already carry BUILTIN\Users ReadAndExecute, so provisioning
# needs no toolchain ACL change at all. Verify that rather than assume it, and
# never widen anything: a missing grant is reported for a human decision.

$SID_USERS_GROUP = 'S-1-5-32-545'
$toolchainFacts = New-Object System.Collections.ArrayList
foreach ($path in $ToolchainPaths) {
    $entry = [ordered]@{ path = $path; exists = (Test-Path -LiteralPath $path); users_read_execute = $null }
    if ($entry.exists) {
        $acl = Get-Acl -LiteralPath $path
        $entry.users_read_execute = Test-UsersGroupReadExecute -Acl $acl -Sid $SID_USERS_GROUP
    }
    [void]$toolchainFacts.Add($entry)
    if ($entry.exists -and -not $entry.users_read_execute) {
        Add-Action 'toolchain' $path "BUILTIN\Users has no read/execute here; $AccountName will not be able to run it. Decide this deliberately; this script does not widen toolchain ACLs." 'FAILED'
    } elseif ($entry.exists) {
        Add-Action 'toolchain' $path 'BUILTIN\Users already has read/execute; no ACL change needed' 'VERIFIED'
    } else {
        Add-Action 'toolchain' $path 'absent on this host' 'ABSENT'
    }
}

# --------------------- 5. optional partial mitigation for in-workspace secrets

$secretActions = New-Object System.Collections.ArrayList
if ($DenyInWorkspaceSecrets -and $accountSid) {
    foreach ($file in $InWorkspaceSecretFiles) {
        if (-not (Test-Path -LiteralPath $file)) {
            [void]$secretActions.Add([ordered]@{ path = $file; state = 'ABSENT' })
            continue
        }
        $acl = Get-Acl -LiteralPath $file
        if (Test-HasExplicitRule -Acl $acl -Sid $accountSid -Rights 'ReadData' -Type 'Deny') {
            [void]$secretActions.Add([ordered]@{ path = $file; state = 'PRESENT' })
            Add-Action 'deny' $file 'ReadData deny already present' 'PRESENT'
            continue
        }
        if (-not $PSCmdlet.ShouldProcess($file, "Deny ReadData to $AccountName")) {
            [void]$secretActions.Add([ordered]@{ path = $file; state = 'WHATIF' })
            continue
        }
        # ReadData only. Denying the full Read set would also deny ReadAttributes,
        # which breaks `git status` on tracked files and would cost the GIT capability.
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier($accountSid)),
            [System.Security.AccessControl.FileSystemRights]::ReadData,
            [System.Security.AccessControl.InheritanceFlags]::None,
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Deny)
        $acl.AddAccessRule($rule)
        Set-Acl -LiteralPath $file -AclObject $acl
        [void]$secretActions.Add([ordered]@{ path = $file; state = 'CHANGED' })
        Add-Action 'deny' $file "denied ReadData to $AccountName" 'CHANGED'
    }
}

# ------------------------------------------------------------------- 6. report

$report = [ordered]@{
    schema           = 'r5.principal_provision.v1'
    generated_utc    = (Get-Date).ToUniversalTime().ToString('o')
    account_name     = $AccountName
    account_sid      = $accountSid
    account_is_administrator = $inAdmins
    workspace_roots  = $WorkspaceRoots
    actions          = @($actions)
    toolchain        = @($toolchainFacts)
    toolchain_acls_changed = $false
    host_secret_root = $HostSecretRoot
    host_secret_root_granted = $false
    in_workspace_secret_denies = @($secretActions)
    password_persisted = $false
    host_profile_touched = $false
    credential_stores_copied = $false
    whatif           = [bool]$WhatIfPreference
}
$artifactDir = Split-Path $ArtifactPath -Parent
if (-not (Test-Path -LiteralPath $artifactDir)) { New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ArtifactPath -Encoding UTF8

Write-Host ''
Write-Host "artifact = $ArtifactPath"
Write-Host ''
Write-Host 'Next: launch-developer-hermes.ps1, then verify-principal-isolation.ps1.'

if ($DenyInWorkspaceSecrets) {
    Write-Host ''
    Write-Host 'CAVEAT on -DenyInWorkspaceSecrets:'
    Write-Host '  A deny ACE hides the working-tree file only. Any secret that was ever'
    Write-Host '  committed remains readable from .git object storage, and denying read on'
    Write-Host '  .git would destroy the GIT capability R5 must keep. For a committed'
    Write-Host '  credential, rotation is the only mitigation that actually holds.'
}
