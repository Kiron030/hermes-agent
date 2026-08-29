<#
.SYNOPSIS
    Verify a Developer Hermes encrypted USB backup (Recovery 2).

.DESCRIPTION
    Checks manifest schema, restic repository health, self-contained Git
    capsules, HERMES_HOME artifact checksums, Developer secret-slot
    completeness, and production-secret exclusions. Does not perform a
    full Developer restore.

    DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST

.EXAMPLE
    .\scripts\r5_developer_hermes\verify-developer-hermes-usb-backup.ps1 -UsbRoot E:\
#>
[CmdletBinding()]
param(
    [string] $UsbRoot = '',
    [switch] $Json
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
        if ([int]$disk.DriveType -eq 2) {
            $rows += [pscustomobject]@{ Letter = $letter; Root = "$letter\" }
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
    Write-Error 'HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED. Run this verify from W:\Workbench\hermes-agent.'
    exit 2
}

$SystemDrive = Get-R5SystemDrive
$Candidates = @(Get-R5RemovableDrives | Where-Object { $_.Letter -ne $SystemDrive })
if (-not $UsbRoot) {
    if ($Candidates.Count -eq 0) {
        Write-Error 'No removable USB drive found. Pass -UsbRoot.'
        exit 2
    }
    if ($Candidates.Count -gt 1) {
        Write-Error 'USB_AMBIGUOUS: multiple removable drives; pass -UsbRoot explicitly.'
        exit 2
    }
    $UsbRoot = $Candidates[0].Root
}

$ResolvedUsb = Get-R5CanonicalPath -Path $UsbRoot
$UsbLetter = ([IO.Path]::GetPathRoot($ResolvedUsb)).TrimEnd('\').ToUpperInvariant()
if ($UsbLetter -eq $SystemDrive) {
    Write-Error 'USB_SYSTEM_DRIVE: refusing the Windows system drive.'
    exit 2
}

Write-Host "Type YES to verify the backup on $ResolvedUsb"
$Answer = Read-Host 'Confirm'
if ($Answer -ne 'YES') {
    Write-Error 'USB_NOT_CONFIRMED'
    exit 2
}

$Password = Read-Host 'Restic recovery password (not echoed)' -AsSecureString
$Plain = ConvertFrom-R5SecureString -Secure $Password
if ([string]::IsNullOrEmpty($Plain)) {
    Write-Error 'RESTIC_PASSWORD missing'
    exit 2
}

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = 'python'
}
$VerifyPy = Join-Path $ResolvedScriptRoot 'recovery\verify.py'
$ArgList = @($VerifyPy, '--usb-root', $ResolvedUsb, '--confirm-usb')
if ($Json) { $ArgList += '--json' }

$previous = $env:RESTIC_PASSWORD
try {
    $env:RESTIC_PASSWORD = $Plain
    $Plain = $null
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
