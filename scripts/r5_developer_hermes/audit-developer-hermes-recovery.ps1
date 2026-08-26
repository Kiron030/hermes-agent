<#
.SYNOPSIS
    Read-only Developer Hermes recovery audit (Slice 1).

.DESCRIPTION
    Inspects Git pins, Docker volume/container identity, Developer secret-slot
    metadata, and the Recovery 0B staging pack. Never prints secret values.
    Never stops Developer Hermes, Telegram, or Operator Hermes. Never installs
    restic or writes an encrypted backup.

    DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST

.EXAMPLE
    .\scripts\r5_developer_hermes\audit-developer-hermes-recovery.ps1
    .\scripts\r5_developer_hermes\audit-developer-hermes-recovery.ps1 -WriteManifest
    .\scripts\r5_developer_hermes\audit-developer-hermes-recovery.ps1 -Json
#>
[CmdletBinding()]
param(
    [switch] $WriteManifest,
    [switch] $Json,
    [string] $Staging = '',
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

$ResolvedScriptRoot = Get-R5CanonicalPath -Path $PSScriptRoot
$RepoRoot = Get-R5CanonicalPath -Path (Join-Path $ResolvedScriptRoot '..\..')
if ((Test-R5PathIsDedicatedClone -Path $ResolvedScriptRoot) -or (Test-R5PathIsDedicatedClone -Path $RepoRoot)) {
    Write-Error 'HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED. Run this audit from W:\Workbench\hermes-agent.'
    exit 2
}

$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = 'python'
}

$AuditPy = Join-Path $ResolvedScriptRoot 'recovery\audit.py'
$ArgList = @($AuditPy)
if ($WriteManifest) { $ArgList += '--write-manifest' }
if ($Json) { $ArgList += '--json' }
if ($Staging) { $ArgList += @('--staging', $Staging) }
if ($RepoB) { $ArgList += @('--repo-b', $RepoB) }
if ($CredentialsDir) { $ArgList += @('--credentials-dir', $CredentialsDir) }

& $Python @ArgList
exit $LASTEXITCODE
