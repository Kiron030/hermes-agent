<#
.SYNOPSIS
    One-command Developer Hermes launcher.

.DESCRIPTION
    Starts or reuses the isolated Linux-container Developer Hermes runtime.
    Workspace roots are fixed. Host profile, secrets, Docker socket, and
    production credentials are never mounted or inherited.

    DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST

    The dedicated trees under W:\hermes-dev are container execution
    workspaces. Container-written files may be malicious or compromised
    even though they cannot autonomously escape the container. This
    launcher refuses to run if its resolved script or repository root is
    under W:\hermes-dev. Run it from W:\Workbench\hermes-agent.

    RESET_DEVELOPER_HERMES_HOME: -Mode reset stops the container and
    removes only the fixed named volume r5-developer-hermes-home. Use
    after suspected prompt injection, a bad Skill, bad config, or other
    poisoned persistent state. It never accepts an arbitrary volume name
    and never touches Repo A/B, host secrets, or production.

.EXAMPLE
    .\launch-developer-hermes.ps1
    .\launch-developer-hermes.ps1 -Mode prove
    .\launch-developer-hermes.ps1 -Mode down
    .\launch-developer-hermes.ps1 -Mode reset -WhatIf
    .\launch-developer-hermes.ps1 -Mode reset
    .\launch-developer-hermes.ps1 -Mode desktop
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [ValidateSet('shell', 'up', 'down', 'prove', 'build', 'reset', 'desktop', 'desktop-down')]
    [string] $Mode = 'shell'
)

$ErrorActionPreference = 'Stop'

function Get-R5CanonicalPath {
    param([Parameter(Mandatory = $true)][string] $Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $full)) {
        return $full
    }
    $item = Get-Item -LiteralPath $full -Force
    $guard = 0
    while ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        $guard++
        if ($guard -gt 8) { break }
        $target = $item.Target
        if (-not $target) { break }
        if ($target -is [array]) { $target = $target[0] }
        if (-not $target) { break }
        if (-not [System.IO.Path]::IsPathRooted([string]$target)) {
            $parent = if ($item.PSIsContainer) { $item.FullName } else { $item.DirectoryName }
            $target = [System.IO.Path]::GetFullPath((Join-Path $parent ([string]$target)))
        }
        else {
            $target = [System.IO.Path]::GetFullPath([string]$target)
        }
        if (-not (Test-Path -LiteralPath $target)) { break }
        $item = Get-Item -LiteralPath $target -Force
    }
    return $item.FullName
}

function Test-R5PathIsDedicatedClone {
    param([Parameter(Mandatory = $true)][string] $Path)
    $canon = (Get-R5CanonicalPath -Path $Path).TrimEnd('\').ToLowerInvariant()
    $root = (Get-R5CanonicalPath -Path 'W:\hermes-dev').TrimEnd('\').ToLowerInvariant()
    return ($canon -eq $root) -or $canon.StartsWith($root + '\')
}

$ResolvedScriptRoot = Get-R5CanonicalPath -Path $PSScriptRoot
$RepoRoot = Get-R5CanonicalPath -Path (Join-Path $ResolvedScriptRoot '..\..\..')
if ((Test-R5PathIsDedicatedClone -Path $ResolvedScriptRoot) -or (Test-R5PathIsDedicatedClone -Path $RepoRoot)) {
    Write-Error 'HOST_LAUNCHER_FROM_CONTAINER_CLONE = DENIED. DEDICATED_CONTAINER_CLONES = DO_NOT_EXECUTE_ON_HOST. Run this launcher from W:\Workbench\hermes-agent.'
    exit 2
}

$LaunchPy = Join-Path $ResolvedScriptRoot 'launch.py'
$ApprovedRepoA = 'W:\hermes-dev\workspace\hermes-agent'
$ApprovedRepoB = 'W:\hermes-dev\workspace\EU-PP-Database'
$DockerExe = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$FixedHomeVolume = 'r5-developer-hermes-home'

if (-not (Test-Path -LiteralPath $LaunchPy)) {
    Write-Error 'Developer Hermes launcher is missing.'
    exit 2
}
if (-not (Test-Path -LiteralPath $ApprovedRepoA) -or -not (Test-Path -LiteralPath $ApprovedRepoB)) {
    Write-Error 'Dedicated workspace clones are missing. Expected the two approved roots under W:\hermes-dev\workspace.'
    exit 2
}
if (-not (Test-Path -LiteralPath $DockerExe)) {
    Write-Error 'Docker Desktop Linux engine is required.'
    exit 2
}

$osType = & $DockerExe info --format '{{.OSType}}'
if ($osType -ne 'linux') {
    Write-Error "Linux containers required. OSType=$osType"
    exit 2
}

$python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { 'python' }

function Invoke-Launch {
    param([string] $Command)
    & $python $LaunchPy $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Developer Hermes $Command failed."
    }
}

switch ($Mode) {
    'build' { Invoke-Launch 'build'; break }
    'up'    { Invoke-Launch 'up'; break }
    'desktop' {
        Invoke-Launch 'desktop-up'
        Write-Host 'Official Desktop Remote Gateway: http://127.0.0.1:19119'
        Write-Host 'Credentials: W:\hermes-dev\credentials\developer-hermes-desktop.env'
        break
    }
    'desktop-down' { Invoke-Launch 'desktop-down'; break }
    'down'  { Invoke-Launch 'down'; break }
    'prove' { Invoke-Launch 'prove-dx'; break }
    'reset' {
        if ($PSCmdlet.ShouldProcess($FixedHomeVolume, 'RESET_DEVELOPER_HERMES_HOME (container + fixed named volume only)')) {
            Invoke-Launch 'reset'
        }
        break
    }
    default {
        Invoke-Launch 'preflight'
        Invoke-Launch 'up'
        & $DockerExe exec -it -w /workspace `
            -e HERMES_HOME=/opt/data -e HOME=/opt/data `
            r5-developer-hermes /bin/bash
    }
}
