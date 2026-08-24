<#
.SYNOPSIS
    One-command Developer Hermes launcher.

.DESCRIPTION
    Starts or reuses the isolated Linux-container Developer Hermes runtime.
    Workspace roots are fixed. Host profile, secrets, Docker socket, and
    production credentials are never mounted or inherited.

.EXAMPLE
    .\launch-developer-hermes.ps1
    .\launch-developer-hermes.ps1 -Mode prove
    .\launch-developer-hermes.ps1 -Mode down
#>
[CmdletBinding()]
param(
    [ValidateSet('shell', 'up', 'down', 'prove', 'build')]
    [string] $Mode = 'shell'
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$LaunchPy = Join-Path $PSScriptRoot 'launch.py'
$ApprovedRepoA = 'W:\hermes-dev\workspace\hermes-agent'
$ApprovedRepoB = 'W:\hermes-dev\workspace\EU-PP-Database'
$DockerExe = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'

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
    'down'  { Invoke-Launch 'down'; break }
    'prove' { Invoke-Launch 'prove-dx'; break }
    default {
        Invoke-Launch 'preflight'
        Invoke-Launch 'up'
        & $DockerExe exec -it -w /workspace `
            -e HERMES_HOME=/opt/data -e HOME=/opt/data `
            r5-developer-hermes /bin/bash
    }
}
