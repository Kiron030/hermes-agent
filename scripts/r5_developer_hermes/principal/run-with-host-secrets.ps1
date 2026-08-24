<#
.SYNOPSIS
    Host-user launcher. Loads host-only env files into THIS process environment
    and runs a normal development command with them.

.DESCRIPTION
    Run as the ORDINARY human account. This is what keeps local development
    working after the secret files have been moved out of the repository: the
    values arrive through the process environment, which is exactly what every
    Repo-B consumer already prefers over an on-disk file.

    Injection only. This script never:
      * copies a secret file into a repository,
      * writes a secret value into any file, artifact or log,
      * prints a value (key NAMES are printed, values never are),
      * creates a symlink or junction from a workspace into the secret root.

    Reading this source grants nothing. The authority is the file ACL on the
    secret root, which belongs to the host account's profile. A different local
    principal running this exact script gets an access-denied on the env file,
    and the explicit principal guard below refuses to start at all.

.EXAMPLE
    # Repo-B backend
    .\run-with-host-secrets.ps1 -Load repo-b -WorkingDirectory W:\Workbench\EU-PP-Database `
        uv run uvicorn main:app --reload

.EXAMPLE
    # Analytics app dev server
    .\run-with-host-secrets.ps1 -Load app,repo-b -WorkingDirectory W:\Workbench\EU-PP-Database\app `
        npm run dev

.EXAMPLE
    # Mapbox style script
    .\run-with-host-secrets.ps1 -Load mapbox -WorkingDirectory W:\Workbench\EU-PP-Database `
        powershell -File scripts\mapbox\apply_units_basemap_muse.ps1

.EXAMPLE
    # Which keys would be injected, without running anything
    .\run-with-host-secrets.ps1 -Load repo-b -ListKeys
#>
[CmdletBinding()]
param(
    [ValidateSet('repo-b', 'app', 'mapbox')]
    [string[]] $Load = @('repo-b'),

    [string]   $SecretRoot,
    [string]   $WorkingDirectory,

    [string[]] $WorkspaceRoots = @('W:\Workbench\hermes-agent', 'W:\Workbench\EU-PP-Database'),
    [string]   $PrincipalName  = 'hermes-dev',

    # Print the key names that would be injected and exit.
    [switch]   $ListKeys,

    # Existing process variables win by default, mirroring load_dotenv(override=False).
    [switch]   $Override,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Command
)

$ErrorActionPreference = 'Stop'

if (-not $SecretRoot) { $SecretRoot = Join-Path $env:USERPROFILE '.powerunits\secrets' }

$LogicalFiles = @{
    'repo-b' = 'repo-b.env'
    'app'    = 'app.env'
    'mapbox' = 'mapbox.env'
}

# ------------------------------------------------- guard: not the dedicated principal

$currentAccount = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($currentAccount -match "\\$([regex]::Escape($PrincipalName))$") {
    Write-Error @"
Refusing to run as '$currentAccount'.

This launcher exists for the human host account. The dedicated principal is not
supposed to hold production secrets, and handing them to it through a launcher
would defeat the entire boundary. Its access denial is the point, not a defect.
"@
    exit 2
}

# --------------------------------------------------- guard: root must be host-only

$profileRoot = (Resolve-Path -LiteralPath $env:USERPROFILE).Path.TrimEnd('\')
$normalisedSecretRoot = $SecretRoot.TrimEnd('\')
if ($normalisedSecretRoot -notlike "$profileRoot\*") {
    Write-Error "Refusing secret root '$SecretRoot': it must live inside the running account's profile ('$profileRoot')."
    exit 2
}
foreach ($root in $WorkspaceRoots) {
    $normalisedWorkspace = $root.TrimEnd('\')
    if ($normalisedSecretRoot -eq $normalisedWorkspace -or $normalisedSecretRoot -like "$normalisedWorkspace\*") {
        Write-Error "Refusing secret root '$SecretRoot': it is inside workspace root '$root', which the dedicated principal can read."
        exit 2
    }
}

# ------------------------------------------------------------------- injection

function Import-HostSecretFile {
    <#
      Sets process environment variables from KEY=value lines. Returns the key
      NAMES it set. Values are never returned, printed or persisted.
    #>
    param([string]$Path, [bool]$AllowOverride)

    $item = Get-Item -LiteralPath $Path -Force
    if ($item.LinkType) {
        throw "Refusing '$Path': it is a $($item.LinkType). A link is how filesystem reachability comes back."
    }

    $names = New-Object System.Collections.ArrayList
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        $trimmed = $line.Trim()
        if ($trimmed -eq '' -or $trimmed.StartsWith('#')) { continue }
        $split = $trimmed.IndexOf('=')
        if ($split -le 0) { continue }
        $key   = $trimmed.Substring(0, $split).Trim()
        $value = $trimmed.Substring($split + 1).Trim()
        if ($value.Length -ge 2 -and (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $already = [Environment]::GetEnvironmentVariable($key)
        if ($already -and -not $AllowOverride) {
            [void]$names.Add("$key (kept existing)")
            continue
        }
        Set-Item -LiteralPath "Env:$key" -Value $value
        [void]$names.Add($key)
    }
    return $names
}

$loadedKeys = New-Object System.Collections.ArrayList
$loadedFiles = New-Object System.Collections.ArrayList

foreach ($logical in $Load) {
    $path = Join-Path $SecretRoot $LogicalFiles[$logical]
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Error @"
Missing host-only env file for '$logical': $path

Create the layout first:
  powershell -ExecutionPolicy Bypass -File .\bootstrap-host-secrets.ps1
"@
        exit 2
    }
    $names = Import-HostSecretFile -Path $path -AllowOverride:$Override
    [void]$loadedFiles.Add($path)
    foreach ($name in $names) { [void]$loadedKeys.Add("$logical/$name") }
}

Write-Host ''
Write-Host "Host-only secrets loaded from $SecretRoot"
foreach ($file in $loadedFiles) { Write-Host "  file : $file" }
Write-Host "  keys : $($loadedKeys.Count)"
foreach ($key in $loadedKeys) { Write-Host "         $key" }
Write-Host ''

if ($ListKeys) {
    Write-Host 'ListKeys: nothing was executed. Values were never printed.'
    exit 0
}

# --------------------------------------------------------------------- execute

$argv = @($Command | Where-Object { $_ -ne $null })
if ($argv.Count -gt 0 -and $argv[0] -eq '--') { $argv = @($argv[1..($argv.Count - 1)]) }
if ($argv.Count -eq 0) {
    Write-Host 'No command given. The secrets are in THIS process environment only;'
    Write-Host 'they disappear when this window closes. Re-run with a command, e.g.:'
    Write-Host '  .\run-with-host-secrets.ps1 -Load repo-b -WorkingDirectory W:\Workbench\EU-PP-Database uv run pytest'
    exit 0
}

if ($WorkingDirectory) {
    if (-not (Test-Path -LiteralPath $WorkingDirectory)) {
        Write-Error "Working directory '$WorkingDirectory' does not exist."
        exit 2
    }
    Set-Location -LiteralPath $WorkingDirectory
}

$exe = $argv[0]
$rest = if ($argv.Count -gt 1) { $argv[1..($argv.Count - 1)] } else { @() }

Write-Host "Running: $exe $($rest -join ' ')"
Write-Host "  cwd  : $(Get-Location)"
Write-Host ''

& $exe @rest
exit $LASTEXITCODE
