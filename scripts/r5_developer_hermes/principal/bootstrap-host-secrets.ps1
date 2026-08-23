<#
.SYNOPSIS
    Creates the host-only secret root and (opt-in) relocates untracked workspace
    secret files into it.

.DESCRIPTION
    Run as the ORDINARY human account. No elevation, because the target lives
    inside that account's own profile and therefore already excludes every other
    local principal.

    The point of this script is to move secret-class files OUT of the two
    workspace roots that the dedicated `hermes-dev` principal must have Modify
    on. As long as a secret sits inside those roots, no OS boundary can hide it:
    the workspace is deliberately read/write.

    Deliberately absent:
      * no symlink, junction or hardlink from the workspace into the secret root
        (that would restore exactly the filesystem reachability being removed),
      * no copy left behind in the repository,
      * no secret value is read, printed, logged or written to any artifact.
        Files are handled as opaque bytes by Move-Item and reported by size only.

.EXAMPLE
    # 1. layout only, nothing moved
    powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1

    # 2. dry run of the relocation
    powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1 -Relocate -WhatIf

    # 3. relocate for real
    powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1 -Relocate
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    # Never hardcode a username: the root is derived from the running account.
    [string]   $SecretRoot,

    [string]   $RepoBRoot      = 'W:\Workbench\EU-PP-Database',
    [string[]] $WorkspaceRoots = @('W:\Workbench\hermes-agent', 'W:\Workbench\EU-PP-Database'),

    [string]   $PrincipalName  = 'hermes-dev',

    # Move the untracked workspace secret files into the host-only root.
    [switch]   $Relocate,

    # Defence in depth only. Not granting access is the actual boundary.
    [switch]   $DenyPrincipal,

    [string]   $ArtifactPath
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $SecretRoot)   { $SecretRoot   = Join-Path $env:USERPROFILE '.powerunits\secrets' }
if (-not $ArtifactPath) { $ArtifactPath = Join-Path $RepoRoot '.r5-dev\artifacts\host_secret_layout.json' }

# Logical name -> (external file, workspace origin). The logical name is what
# run-with-host-secrets.ps1 loads; the origin is what -Relocate consumes.
$LogicalFiles = @(
    [ordered]@{ logical = 'repo-b'; external = 'repo-b.env'; origin = (Join-Path $RepoBRoot '.env') }
    [ordered]@{ logical = 'app';    external = 'app.env';    origin = (Join-Path $RepoBRoot 'app\.env.local') }
    [ordered]@{ logical = 'mapbox'; external = 'mapbox.env'; origin = (Join-Path $RepoBRoot 'scripts\mapbox\.env.local') }
)

$actions = New-Object System.Collections.ArrayList
function Add-Action([string]$Kind, [string]$Target, [string]$Detail, [string]$State) {
    [void]$actions.Add([ordered]@{ kind = $Kind; target = $Target; detail = $Detail; state = $State })
    Write-Host ("  {0,-9} {1,-9} {2}" -f $State, $Kind, $Detail)
}

# --------------------------------------------------- guard: root must be host-only

$profileRoot = (Resolve-Path -LiteralPath $env:USERPROFILE).Path.TrimEnd('\')
$normalisedSecretRoot = $SecretRoot.TrimEnd('\')

if ($normalisedSecretRoot -notlike "$profileRoot\*") {
    Write-Error @"
Refusing to use '$SecretRoot' as the secret root.

The root must live inside the running account's profile ('$profileRoot'), which
is what makes it unreachable for every other local principal. A path outside the
profile has no such guarantee.
"@
    exit 2
}
foreach ($root in $WorkspaceRoots) {
    $normalisedWorkspace = $root.TrimEnd('\')
    if ($normalisedSecretRoot -eq $normalisedWorkspace -or $normalisedSecretRoot -like "$normalisedWorkspace\*") {
        Write-Error "Refusing to place the secret root inside workspace root '$root'. That is the reachability this script exists to remove."
        exit 2
    }
}

Write-Host ''
Write-Host 'R5 host-only secret layout'
Write-Host "  secret root : $SecretRoot"
Write-Host "  relocate    : $([bool]$Relocate)"
Write-Host ''

# ------------------------------------------------------------- 1. directory

if (Test-Path -LiteralPath $SecretRoot) {
    Add-Action 'dir' $SecretRoot 'secret root already exists' 'PRESENT'
} elseif ($PSCmdlet.ShouldProcess($SecretRoot, 'Create host-only secret root')) {
    New-Item -ItemType Directory -Force -Path $SecretRoot | Out-Null
    Add-Action 'dir' $SecretRoot 'created secret root (inherits profile ACL)' 'CREATED'
} else {
    Add-Action 'dir' $SecretRoot 'would create secret root' 'WHATIF'
}

# ------------------------------------------------- 2. logical files (empty stubs)

foreach ($entry in $LogicalFiles) {
    $external = Join-Path $SecretRoot $entry.external
    if (Test-Path -LiteralPath $external) {
        $size = (Get-Item -LiteralPath $external -Force).Length
        Add-Action 'file' $external "$($entry.logical): already present ($size bytes)" 'PRESENT'
        continue
    }
    if (-not (Test-Path -LiteralPath $SecretRoot)) {
        Add-Action 'file' $external "$($entry.logical): would be created once the root exists" 'WHATIF'
        continue
    }
    if ($PSCmdlet.ShouldProcess($external, "Create empty $($entry.logical) env file")) {
        # A header comment only. This script never writes a value.
        Set-Content -LiteralPath $external -Encoding UTF8 -Value @(
            "# Powerunits host-only secrets: $($entry.logical)",
            '# KEY=value, one per line. Loaded into the process environment by',
            '# run-with-host-secrets.ps1. Never copy this file into a repository.'
        )
        Add-Action 'file' $external "$($entry.logical): created empty env file" 'CREATED'
    } else {
        Add-Action 'file' $external "$($entry.logical): would create empty env file" 'WHATIF'
    }
}

# ---------------------------------------------- 3. principal must have no access

$principalSid = $null
$principalAccount = Get-LocalUser -Name $PrincipalName -ErrorAction SilentlyContinue
if ($principalAccount) { $principalSid = $principalAccount.SID.Value }

$principalGranted = $null
if ($principalSid -and (Test-Path -LiteralPath $SecretRoot)) {
    $acl = Get-Acl -LiteralPath $SecretRoot
    $granting = @($acl.Access | Where-Object {
        $_.AccessControlType -eq 'Allow' -and
        (try { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { '' }) -eq $principalSid
    })
    $principalGranted = ($granting.Count -gt 0)
    if ($principalGranted) {
        Add-Action 'acl' $SecretRoot "'$PrincipalName' HAS an allow ACE here; remove it before relying on this layout" 'FAILED'
    } else {
        Add-Action 'acl' $SecretRoot "'$PrincipalName' has no allow ACE (profile ACL excludes it)" 'VERIFIED'
    }

    if ($DenyPrincipal -and -not $principalGranted) {
        $hasDeny = @($acl.Access | Where-Object {
            $_.AccessControlType -eq 'Deny' -and
            (try { $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { '' }) -eq $principalSid
        }).Count -gt 0
        if ($hasDeny) {
            Add-Action 'acl' $SecretRoot 'explicit deny already present' 'PRESENT'
        } elseif ($PSCmdlet.ShouldProcess($SecretRoot, "Add explicit deny for $PrincipalName")) {
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                (New-Object System.Security.Principal.SecurityIdentifier($principalSid)),
                [System.Security.AccessControl.FileSystemRights]::FullControl,
                ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
                 [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
                [System.Security.AccessControl.PropagationFlags]::None,
                [System.Security.AccessControl.AccessControlType]::Deny)
            $acl.AddAccessRule($rule)
            Set-Acl -LiteralPath $SecretRoot -AclObject $acl
            Add-Action 'acl' $SecretRoot "added explicit deny for '$PrincipalName' (defence in depth)" 'CHANGED'
        }
    }
} elseif (-not $principalAccount) {
    Add-Action 'acl' $SecretRoot "'$PrincipalName' does not exist yet; nothing can be granted to it" 'VERIFIED'
}

# ----------------------------------------------------------- 4. relocation

$relocations = New-Object System.Collections.ArrayList
if ($Relocate) {
    foreach ($entry in $LogicalFiles) {
        $origin   = $entry.origin
        $external = Join-Path $SecretRoot $entry.external
        $record   = [ordered]@{
            logical      = $entry.logical
            origin       = $origin
            external     = $external
            state        = $null
            bytes_moved  = $null
        }

        if (-not (Test-Path -LiteralPath $origin)) {
            $record.state = 'ORIGIN_ABSENT'
            Add-Action 'move' $origin "$($entry.logical): nothing to relocate" 'SKIPPED'
            [void]$relocations.Add($record); continue
        }

        $originItem = Get-Item -LiteralPath $origin -Force
        if ($originItem.LinkType) {
            $record.state = 'ORIGIN_IS_REPARSE_POINT'
            Add-Action 'move' $origin "$($entry.logical): origin is a $($originItem.LinkType); refusing to touch it" 'FAILED'
            [void]$relocations.Add($record); continue
        }

        # git-tracked files are a different problem: untracking is a repository
        # change and the blob stays in history. Those go through the runbook.
        $tracked = $false
        Push-Location (Split-Path $origin -Parent)
        try {
            & git ls-files --error-unmatch -- $originItem.Name *> $null
            $tracked = ($LASTEXITCODE -eq 0)
        } catch {
        } finally {
            Pop-Location
        }
        if ($tracked) {
            $record.state = 'ORIGIN_IS_GIT_TRACKED'
            Add-Action 'move' $origin "$($entry.logical): git-tracked; relocation alone would not remove it from history" 'FAILED'
            [void]$relocations.Add($record); continue
        }

        if ((Test-Path -LiteralPath $external) -and ((Get-Item -LiteralPath $external -Force).Length -gt 200)) {
            $record.state = 'TARGET_NOT_EMPTY'
            Add-Action 'move' $external "$($entry.logical): target already holds content; refusing to overwrite" 'FAILED'
            [void]$relocations.Add($record); continue
        }

        if (-not $PSCmdlet.ShouldProcess($origin, "Move to $external")) {
            $record.state = 'WHATIF'
            Add-Action 'move' $origin "$($entry.logical): would move $($originItem.Length) bytes to $external" 'WHATIF'
            [void]$relocations.Add($record); continue
        }

        $bytes = $originItem.Length
        # Move-Item, not Copy-Item: no residue may stay inside the workspace.
        Move-Item -LiteralPath $origin -Destination $external -Force
        $record.state       = 'MOVED'
        $record.bytes_moved = $bytes
        Add-Action 'move' $origin "$($entry.logical): moved $bytes bytes out of the workspace" 'CHANGED'
        [void]$relocations.Add($record)
    }

    # A relocation that leaves a link behind has achieved nothing.
    foreach ($entry in $LogicalFiles) {
        if (Test-Path -LiteralPath $entry.origin) {
            $left = Get-Item -LiteralPath $entry.origin -Force
            if ($left.LinkType) {
                Add-Action 'guard' $entry.origin "a $($left.LinkType) now stands where the secret was; delete it" 'FAILED'
            }
        }
    }
}

# ------------------------------------------------------------------ 5. report

$report = [ordered]@{
    schema             = 'r5.host_secret_layout.v1'
    generated_utc      = (Get-Date).ToUniversalTime().ToString('o')
    secret_root        = $SecretRoot
    secret_root_inside_profile = $true
    secret_root_inside_workspace = $false
    principal_name     = $PrincipalName
    principal_has_allow_ace = $principalGranted
    logical_files      = @($LogicalFiles | ForEach-Object {
        $external = Join-Path $SecretRoot $_.external
        [ordered]@{
            logical  = $_.logical
            external = $external
            exists   = (Test-Path -LiteralPath $external)
            origin   = $_.origin
            origin_still_in_workspace = (Test-Path -LiteralPath $_.origin)
        }
    })
    relocations        = @($relocations)
    actions            = @($actions)
    symlinks_created   = $false
    secret_values_read = $false
    whatif             = [bool]$WhatIfPreference
}

$artifactDir = Split-Path $ArtifactPath -Parent
if (-not (Test-Path -LiteralPath $artifactDir)) { New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ArtifactPath -Encoding UTF8

Write-Host ''
Write-Host "artifact = $ArtifactPath"
Write-Host ''
Write-Host 'Next: verify the normal human workflow with run-with-host-secrets.ps1 BEFORE'
Write-Host 'creating the dedicated principal. If local development is broken, fix that first.'
