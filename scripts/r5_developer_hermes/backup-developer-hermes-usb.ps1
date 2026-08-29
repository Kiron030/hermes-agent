<#
.SYNOPSIS
    Encrypted Developer Hermes USB backup (Recovery 2).

.DESCRIPTION
    Audits readiness, builds self-contained Repo A/B Git capsules, exports
    Developer HERMES_HOME logically, includes only the approved Developer
    secret slots, and writes an incremental restic snapshot to an explicitly
    confirmed removable USB destination.

    Never formats or repartitions a disk.
    Never writes the Windows system drive.
    Never stores the restic password on the USB or on the command line.

    DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST

.EXAMPLE
    .\scripts\r5_developer_hermes\backup-developer-hermes-usb.ps1 -UsbRoot E:\ -WhatIf
    .\scripts\r5_developer_hermes\backup-developer-hermes-usb.ps1 -UsbRoot E:\ -AllowResticDownload
    .\scripts\r5_developer_hermes\backup-developer-hermes-usb.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string] $UsbRoot = '',
    [switch] $AllowResticDownload,
    [switch] $SkipRuntime,
    [switch] $Json,
    [string] $RepoB = '',
    [string] $CredentialsDir = ''
)

$ErrorActionPreference = 'Stop'

function Get-R5CanonicalPath {
    param([Parameter(Mandatory = $true)][string] $Path)
    return [System.IO.Path]::GetFullPath($Path)
}

function Test-R5PathIsDedicatedClone {
    param([Parameter(Mandatory = $true)][string] $Path)
    $canon = (Get-R5CanonicalPath -Path $Path).TrimEnd('\').ToLowerInvariant()
    $root = (Get-R5CanonicalPath -Path 'W:\hermes-dev').TrimEnd('\').ToLowerInvariant()
    return ($canon -eq $root) -or $canon.StartsWith($root + '\')
}

function Get-R5SystemDrive {
    $raw = $env:SystemDrive
    if (-not $raw) { $raw = 'C:' }
    return $raw.TrimEnd('\').ToUpperInvariant()
}

function Get-R5RemovableDrives {
    $rows = @()
    $disks = Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction SilentlyContinue
    foreach ($disk in $disks) {
        $letter = ([string]$disk.DeviceID).TrimEnd('\').ToUpperInvariant()
        $removable = [int]$disk.DriveType -eq 2
        $rows += [pscustomobject]@{
            Root       = "$letter\"
            Letter     = $letter
            Label      = [string]$disk.VolumeName
            DriveType  = [int]$disk.DriveType
            Removable  = $removable
            UsbBus     = $false
            FreeBytes  = [int64]$disk.FreeSpace
            TotalBytes = [int64]$disk.Size
        }
    }
    return $rows
}

function ConvertFrom-R5SecureString {
    param([Parameter(Mandatory = $true)][SecureString] $Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$ResolvedScriptRoot = Get-R5CanonicalPath -Path $PSScriptRoot
$RepoRoot = Get-R5CanonicalPath -Path (Join-Path $ResolvedScriptRoot '..\..')
if ((Test-R5PathIsDedicatedClone -Path $ResolvedScriptRoot) -or (Test-R5PathIsDedicatedClone -Path $RepoRoot)) {
    Write-Error 'HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED. Run this backup from W:\Workbench\hermes-agent.'
    exit 2
}

$SystemDrive = Get-R5SystemDrive
$Candidates = @(Get-R5RemovableDrives | Where-Object { $_.Letter -ne $SystemDrive -and $_.Removable })

if (-not $UsbRoot) {
    if ($Candidates.Count -eq 0) {
        Write-Error 'No removable USB drive found. Insert the recovery USB and pass -UsbRoot.'
        exit 2
    }
    if ($Candidates.Count -gt 1) {
        Write-Host 'Multiple removable drives found. Pass -UsbRoot explicitly:'
        $Candidates | ForEach-Object { Write-Host ("  {0}  label={1}" -f $_.Root, $_.Label) }
        Write-Error 'USB_AMBIGUOUS: refusing to auto-select a destination.'
        exit 2
    }
    $UsbRoot = $Candidates[0].Root
    Write-Host "One removable drive found: $UsbRoot"
}

$ResolvedUsb = Get-R5CanonicalPath -Path $UsbRoot
$UsbLetter = ([IO.Path]::GetPathRoot($ResolvedUsb)).TrimEnd('\').ToUpperInvariant()
if ($UsbLetter -eq $SystemDrive) {
    Write-Error 'USB_SYSTEM_DRIVE: refusing to write the Windows system drive.'
    exit 2
}
$Match = $Candidates | Where-Object { $_.Letter -eq $UsbLetter }
if (-not $Match) {
    Write-Error 'USB_NOT_REMOVABLE: destination is not an explicitly removable/USB recovery volume.'
    exit 2
}

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = 'python'
}
$BackupPy = Join-Path $ResolvedScriptRoot 'recovery\backup.py'

if ($WhatIfPreference) {
    Write-Host "DRY_RUN = YES"
    Write-Host "USB_WRITES = NO"
    Write-Host "NETWORK_DOWNLOADS = NO"
    Write-Host "SECRET_INPUT_REQUIRED = NO"
    Write-Host "RUNTIME_MUTATIONS = NO"
    Write-Host "Inspecting removable destination: $ResolvedUsb"
    $ArgList = @($BackupPy, '--usb-root', $ResolvedUsb, '--dry-run')
    if ($AllowResticDownload) { $ArgList += '--allow-restic-download' }
    if ($Json) { $ArgList += '--json' }
    if ($RepoB) { $ArgList += @('--repo-b', $RepoB) }
    if ($CredentialsDir) { $ArgList += @('--credentials-dir', $CredentialsDir) }
    if ($env:RESTIC_PASSWORD) {
        Remove-Item Env:RESTIC_PASSWORD -ErrorAction SilentlyContinue
    }
    & $Python @ArgList
    exit $LASTEXITCODE
}

Write-Host ''
Write-Host 'This will write an encrypted restic repository to:'
Write-Host "  $ResolvedUsb"
Write-Host 'The recovery password is NOT stored on the USB, in Git, or on this PC.'
Write-Host 'Store it independently (password manager + optional physical copy).'
Write-Host 'Type YES to confirm this exact removable destination.'
$Answer = Read-Host 'Confirm'
if ($Answer -ne 'YES') {
    Write-Error 'USB_NOT_CONFIRMED: Human did not confirm the destination.'
    exit 2
}

$Password = Read-Host 'Restic recovery password (not echoed)' -AsSecureString
$PasswordConfirm = Read-Host 'Confirm restic recovery password' -AsSecureString
$Plain = ConvertFrom-R5SecureString -Secure $Password
$PlainConfirm = ConvertFrom-R5SecureString -Secure $PasswordConfirm
if ($Plain -ne $PlainConfirm -or [string]::IsNullOrEmpty($Plain)) {
    $Plain = $null
    $PlainConfirm = $null
    Write-Error 'restic passwords did not match or were empty.'
    exit 2
}

$ArgList = @($BackupPy, '--usb-root', $ResolvedUsb, '--confirm-usb')
if ($AllowResticDownload) { $ArgList += '--allow-restic-download' }
if ($SkipRuntime) { $ArgList += '--skip-runtime' }
if ($Json) { $ArgList += '--json' }
if ($RepoB) { $ArgList += @('--repo-b', $RepoB) }
if ($CredentialsDir) { $ArgList += @('--credentials-dir', $CredentialsDir) }

$previous = $env:RESTIC_PASSWORD
try {
    $env:RESTIC_PASSWORD = $Plain
    $Plain = $null
    $PlainConfirm = $null
    & $Python @ArgList
    $code = $LASTEXITCODE
}
finally {
    if ($null -eq $previous) {
        Remove-Item Env:RESTIC_PASSWORD -ErrorAction SilentlyContinue
    }
    else {
        $env:RESTIC_PASSWORD = $previous
    }
}
exit $code
