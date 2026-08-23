<#
.SYNOPSIS
    Launches Developer Hermes under the dedicated Windows principal.

.DESCRIPTION
    Run from the ordinary host account. Elevation is NOT required and NOT used:
    the target account is a standard user, so this is a sideways switch, not a
    privilege escalation.

    Credentials are supplied interactively by runas. The credential-caching
    switch is deliberately not used, no password is ever written, and no
    credential store is copied into the dedicated principal's profile.

    Because runas starts a detached session whose stdout cannot be piped back,
    every non-interactive mode writes its result to a JSON artifact under
    .r5-dev\artifacts and this script waits for that artifact to appear.

.EXAMPLE
    .\launch-developer-hermes.ps1 -Mode shell
    .\launch-developer-hermes.ps1 -Mode verify
    .\launch-developer-hermes.ps1 -Mode probes
#>
[CmdletBinding()]
param(
    [string] $AccountName = 'hermes-dev',
    [ValidateSet('shell', 'verify', 'probes')]
    [string] $Mode        = 'shell',
    [string] $RepoBRoot   = 'W:\Workbench\EU-PP-Database',
    [int]    $TimeoutSeconds = 900
)

$ErrorActionPreference = 'Stop'

$RepoRoot     = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ProofRoot    = Join-Path $RepoRoot '.r5-dev'
$ArtifactDir  = Join-Path $ProofRoot 'artifacts'
$PrincipalDir = Join-Path $ProofRoot 'principal'
$Bootstrap    = Join-Path $PrincipalDir 'bootstrap.ps1'

foreach ($dir in @($ArtifactDir, $PrincipalDir)) {
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
}

if (-not (Get-LocalUser -Name $AccountName -ErrorAction SilentlyContinue)) {
    Write-Error "Local account '$AccountName' does not exist. Run provision-principal.ps1 from an elevated session first."
    exit 2
}

$venvPython = Join-Path $RepoRoot '.r1-proof\upstream-src\.venv\Scripts\python.exe'
$upstreamSrc = Join-Path $RepoRoot '.r1-proof\upstream-src'

# ------------------------------------------------------------------ bootstrap
#
# Runs inside the dedicated principal's own logon session. HOME, USERPROFILE,
# APPDATA and TEMP come from that session, so no synthetic HOME is needed or
# wanted: the isolation is the logon token, not an environment variable.

$bootstrapBody = @'
param(
    [string]$RepoRoot,
    [string]$RepoBRoot,
    [string]$Mode,
    [string]$PrincipalScriptDir
)

$ErrorActionPreference = 'Continue'

$env:HERMES_R5_PROOF_ROOT  = Join-Path $RepoRoot '.r5-dev'
$env:HERMES_HOME           = Join-Path $RepoRoot '.r5-dev\home'
$env:HERMES_R5_REPO_B_ROOT = $RepoBRoot
$env:HERMES_R5_UPSTREAM_SRC = Join-Path $RepoRoot '.r1-proof\upstream-src'
$env:HERMES_R5_CONTEXT     = 'developer'
$env:HERMES_DISABLE_LAZY_INSTALLS = '1'
$env:PYTHONNOUSERSITE      = '1'
$env:PYTHONUTF8            = '1'

# Git refuses repositories owned by another account. The dedicated principal
# records the exemption in ITS OWN profile gitconfig; the host gitconfig is
# never touched. Idempotent.
foreach ($repo in @($RepoRoot, $RepoBRoot)) {
    if (-not $repo) { continue }
    $normalised = $repo -replace '\\', '/'
    $existing = @(& git config --global --get-all safe.directory 2>$null)
    if ($existing -notcontains $normalised) {
        & git config --global --add safe.directory $normalised | Out-Null
    }
}

Write-Host ''
Write-Host 'R5 Developer Hermes -- dedicated principal session'
Write-Host ("  whoami      : {0}" -f (whoami))
Write-Host ("  sid         : {0}" -f ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value))
Write-Host ("  HERMES_HOME : {0}" -f $env:HERMES_HOME)
Write-Host ("  workspace A : {0}" -f $RepoRoot)
Write-Host ("  workspace B : {0}" -f $RepoBRoot)
Write-Host ''

Set-Location $RepoRoot

switch ($Mode) {
    'verify' {
        & powershell -ExecutionPolicy Bypass -File (Join-Path $PrincipalScriptDir 'verify-principal-isolation.ps1')
        Write-Host ''
        Write-Host 'Verification finished. This window closes in 20 seconds.'
        Start-Sleep -Seconds 20
    }
    'probes' {
        $python = Join-Path $RepoRoot '.r1-proof\upstream-src\.venv\Scripts\python.exe'
        & $python (Join-Path $RepoRoot 'scripts\r5_developer_hermes\harness.py') developer-probes
        & $python (Join-Path $RepoRoot 'scripts\r5_developer_hermes\harness.py') capability-inventory
        Write-Host ''
        Write-Host 'Probes finished. This window closes in 20 seconds.'
        Start-Sleep -Seconds 20
    }
    default {
        Write-Host 'Interactive developer shell. Type exit to leave.'
    }
}
'@

Set-Content -LiteralPath $Bootstrap -Value $bootstrapBody -Encoding UTF8

# ------------------------------------------------------------------- sentinels

$expectedArtifact = switch ($Mode) {
    'verify' { Join-Path $ArtifactDir 'principal_isolation.json' }
    'probes' { Join-Path $ArtifactDir 'developer_probes.json' }
    default  { $null }
}
if ($expectedArtifact -and (Test-Path -LiteralPath $expectedArtifact)) {
    Remove-Item -LiteralPath $expectedArtifact -Force
}

$noExit = if ($Mode -eq 'shell') { '-NoExit ' } else { '' }
$inner  = "powershell -ExecutionPolicy Bypass $noExit-File `"$Bootstrap`" " +
          "-RepoRoot `"$RepoRoot`" -RepoBRoot `"$RepoBRoot`" -Mode $Mode " +
          "-PrincipalScriptDir `"$PSScriptRoot`""

Write-Host ''
Write-Host "Launching Developer Hermes as $env:COMPUTERNAME\$AccountName (mode: $Mode)."
Write-Host 'runas will prompt for the account password. It is not stored.'
Write-Host ''

& runas.exe /user:"$env:COMPUTERNAME\$AccountName" $inner

if (-not $expectedArtifact) { exit 0 }

Write-Host ''
Write-Host "Waiting for $expectedArtifact ..."
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $expectedArtifact) {
        Write-Host ''
        Write-Host "Artifact ready: $expectedArtifact"
        exit 0
    }
    Start-Sleep -Seconds 3
}

Write-Warning "Timed out after $TimeoutSeconds s without $expectedArtifact. Check the runas window for errors."
exit 1
