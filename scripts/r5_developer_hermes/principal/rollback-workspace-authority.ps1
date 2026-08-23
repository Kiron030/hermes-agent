<#
.SYNOPSIS
    Restores the DACLs captured by scope-workspace-authority.ps1.

.DESCRIPTION
    Reverses the authority scoping exactly: each backed-up DACL is written back
    from its recorded SDDL, so the volume-root write-denies disappear and the
    volumes return to the state they had before the mutation.

    Only the DACL is restored, never the owner or the SACL, so a rollback cannot
    change who owns host data.

    The scoped workspace root is NOT deleted. Removing a directory that may hold
    working clones is a human decision, and the command is printed instead.

    Run from an ELEVATED PowerShell session.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\rollback-workspace-authority.ps1 -BackupPath ..\..\..\.r5-dev\acl-backups\acl_backup_<stamp>.json -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [string] $BackupPath
)

$ErrorActionPreference = 'Stop'

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must run ELEVATED. It restores volume-root ACLs.`n`n  powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -BackupPath `"$BackupPath`""
    exit 2
}

if (-not (Test-Path -LiteralPath $BackupPath)) {
    Write-Error "Backup '$BackupPath' does not exist. Without it there is nothing to restore to; refusing to guess a prior ACL."
    exit 2
}

$backup = Get-Content -LiteralPath $BackupPath -Raw | ConvertFrom-Json
if ($backup.schema -ne 'r5.acl_backup.v1') {
    Write-Error "Backup '$BackupPath' is not an r5.acl_backup.v1 document."
    exit 2
}

Write-Host ''
Write-Host 'R5 workspace authority rollback'
Write-Host "  backup    : $BackupPath"
Write-Host "  captured  : $($backup.captured_utc)"
Write-Host "  principal : $($backup.account_name) ($($backup.account_sid))"
Write-Host ''

$restored = 0
foreach ($entry in @($backup.entries)) {
    if (-not $entry.existed) {
        Write-Host ("  SKIPPED   {0} (did not exist when the backup was taken)" -f $entry.path)
        continue
    }
    if (-not (Test-Path -LiteralPath $entry.path)) {
        Write-Host ("  MISSING   {0} (no longer present)" -f $entry.path)
        continue
    }
    if (-not $PSCmdlet.ShouldProcess($entry.path, 'Restore the captured DACL')) {
        Write-Host ("  WHATIF    {0}" -f $entry.path)
        continue
    }
    $acl = Get-Acl -LiteralPath $entry.path
    # 'Access' restores the DACL only: owner and SACL are left as they are.
    $acl.SetSecurityDescriptorSddlForm($entry.sddl, 'Access')
    Set-Acl -LiteralPath $entry.path -AclObject $acl
    Write-Host ("  RESTORED  {0}" -f $entry.path)
    $restored++
}

Write-Host ''
Write-Host "restored $restored DACL(s)."
if ($backup.scoped_root) {
    Write-Host ''
    Write-Host 'The scoped workspace root was left in place on purpose. To remove it:'
    Write-Host "  Remove-Item -LiteralPath `"$($backup.scoped_root)`" -Recurse -Force"
}
Write-Host ''
Write-Host 'Re-run preflight-principal.ps1 to confirm the host is back to its previous authority state.'
