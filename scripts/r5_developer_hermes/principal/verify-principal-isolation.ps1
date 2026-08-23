<#
.SYNOPSIS
    R5 Phase C property proof. Must be executed AS the dedicated principal.

.DESCRIPTION
    Tests properties, not implementation assumptions. Nothing here depends on
    PATH resolution, on environment-variable absence, or on the fail-closed
    deploy-CLI stubs, all of which the independent review demonstrated are not
    authority boundaries.

    Every check is fail-closed: an inconclusive result is reported as
    POSSIBLY_REACHABLE, never as NO.

    No credential contents are read. No deployment command is issued. Any output
    that could carry an identity or token is redacted before it is recorded.

.EXAMPLE
    # via launch-developer-hermes.ps1 -Mode verify
    powershell -ExecutionPolicy Bypass -File .\verify-principal-isolation.ps1
#>
[CmdletBinding()]
param(
    [string] $PreflightArtifact,
    [string] $ArtifactPath
)

$ErrorActionPreference = 'Continue'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if (-not $PreflightArtifact) { $PreflightArtifact = Join-Path $RepoRoot '.r5-dev\artifacts\principal_preflight.json' }
if (-not $ArtifactPath)      { $ArtifactPath      = Join-Path $RepoRoot '.r5-dev\artifacts\principal_isolation.json' }

$SID_ADMINISTRATORS = 'S-1-5-32-544'

function Protect-Output {
    param([string]$Text)
    if (-not $Text) { return '' }
    $tokens = foreach ($token in ($Text -split '\s+')) {
        if ($token -match '@' -or $token.Length -gt 40) { '<REDACTED>' } else { $token }
    }
    return (($tokens -join ' ').Trim() -replace '\s+', ' ').Substring(0, [Math]::Min(300, ($tokens -join ' ').Trim().Length))
}

function Invoke-Probe {
    param([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSeconds = 45)
    $result = [ordered]@{ launched = $false; exit_code = $null; output = ''; error_class = $null }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName               = $FilePath
        $psi.Arguments              = ($Arguments -join ' ')
        $psi.UseShellExecute        = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.CreateNoWindow         = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        $result.launched = $true
        $stdout = $proc.StandardOutput.ReadToEnd()
        $stderr = $proc.StandardError.ReadToEnd()
        if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
            try { $proc.Kill() } catch { }
            $result.error_class = 'TIMEOUT'
        }
        $result.exit_code = $proc.ExitCode
        $result.output    = Protect-Output ($stdout + ' ' + $stderr)
    } catch {
        $result.error_class = $_.Exception.GetType().Name
        $result.output      = Protect-Output $_.Exception.Message
    }
    return $result
}

function Get-AuthVerdict {
    <#
      NOT_AUTHENTICATED  the binary could not run, or ran and reported no session
      AUTHENTICATED      the binary ran and reported a live session
      INCONCLUSIVE       treated as POSSIBLY_REACHABLE by the caller
    #>
    param($Probe)
    if (-not $Probe.launched) { return 'NOT_AUTHENTICATED' }
    $text = $Probe.output.ToLower()
    $unauth = @('not logged', 'unauthorized', 'unauthenticated', 'no token', 'missing token',
                'please run', 'auth required', 'not authenticated', 'login', 'access is denied',
                'zugriff verweigert', 'cannot find', 'not recognized')
    foreach ($marker in $unauth) { if ($text -like "*$marker*") { return 'NOT_AUTHENTICATED' } }
    if ($Probe.exit_code -ne 0) { return 'NOT_AUTHENTICATED' }
    if ($text -match 'logged in|<redacted>|account|team|project') { return 'AUTHENTICATED' }
    return 'INCONCLUSIVE'
}

$findings = New-Object System.Collections.ArrayList
function Add-Finding([string]$Severity, [string]$Id, [string]$Detail) {
    [void]$findings.Add([ordered]@{ severity = $Severity; id = $Id; detail = $Detail })
}

# ----------------------------------------------------------- preflight context

$preflight = $null
if (Test-Path -LiteralPath $PreflightArtifact) {
    $preflight = Get-Content -LiteralPath $PreflightArtifact -Raw | ConvertFrom-Json
} else {
    Add-Finding 'HIGH' 'PREFLIGHT_ARTIFACT_MISSING' "Cannot read $PreflightArtifact. Without the recorded host SID, sentinel path and absolute deploy-CLI locations this proof cannot be property-based, so every verdict below stays fail-closed."
}

$hostSid      = if ($preflight) { $preflight.account.host_user_sid } else { $null }
$sentinelPath = if ($preflight) { $preflight.host_profile_sentinel.path } else { $null }
$deployPaths  = if ($preflight) { @($preflight.deploy_cli_absolute_candidates) } else { @() }

# --------------------------------------------------------- A. OS principal

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$childSid  = $identity.User.Value
$isAdmin   = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$separatePrincipal = ($hostSid -and $childSid -and ($childSid -ne $hostSid))
if (-not $separatePrincipal) {
    Add-Finding 'CRITICAL' 'SAME_PRINCIPAL_AS_HOST' "Running as SID $childSid, which is not distinguishable from the recorded host SID. The boundary is not in effect."
}
if ($isAdmin) {
    Add-Finding 'CRITICAL' 'PRINCIPAL_IS_ADMINISTRATOR' 'The dedicated principal holds administrative rights and can therefore reach every host credential store regardless of ACLs.'
}

$principalResult = [ordered]@{
    child_sid            = $childSid
    child_account        = $identity.Name
    recorded_host_sid    = $hostSid
    CHILD_OS_PRINCIPAL   = if ($separatePrincipal) { 'SEPARATE_PRINCIPAL' } else { 'NOT_PROVEN' }
    child_is_administrator = $isAdmin
}

# ------------------------------------------------- B. host-profile sentinel

$sentinelReadable = $null
$sentinelDetail   = 'no sentinel path recorded'
if ($sentinelPath) {
    try {
        $null = [System.IO.File]::ReadAllBytes($sentinelPath)
        $sentinelReadable = $true
        $sentinelDetail   = 'sentinel content was returned to the dedicated principal'
    } catch [System.UnauthorizedAccessException] {
        $sentinelReadable = $false
        $sentinelDetail   = 'UnauthorizedAccessException'
    } catch [System.IO.DirectoryNotFoundException] {
        $sentinelReadable = $false
        $sentinelDetail   = 'DirectoryNotFoundException (profile not traversable)'
    } catch [System.IO.FileNotFoundException] {
        $sentinelReadable = $null
        $sentinelDetail   = 'FileNotFoundException; the sentinel may simply not exist, which proves nothing'
    } catch {
        $sentinelReadable = $false
        $sentinelDetail   = $_.Exception.GetType().Name
    }
}
if ($sentinelReadable -eq $true) {
    Add-Finding 'CRITICAL' 'HOST_PROFILE_READABLE' "The dedicated principal read $sentinelPath. Host-profile credential files are therefore also in reach."
}
if ($null -eq $sentinelReadable) {
    Add-Finding 'MEDIUM' 'SENTINEL_INCONCLUSIVE' "Sentinel check inconclusive: $sentinelDetail. Create the sentinel with preflight-principal.ps1 -CreateSentinel and re-run."
}

$hostProfileReachable = if ($sentinelReadable -eq $false) { 'NO' } elseif ($sentinelReadable -eq $true) { 'YES' } else { 'NOT_PROVEN' }

# ------------------------------------------------------------- C. Railway

$railwayProbes = New-Object System.Collections.ArrayList

$onPath = Get-Command 'railway' -ErrorAction SilentlyContinue
[void]$railwayProbes.Add([ordered]@{
    class  = 'PATH_LOOKUP'
    target = if ($onPath) { $onPath.Source } else { $null }
    probe  = if ($onPath) { Invoke-Probe -FilePath $onPath.Source -Arguments @('whoami') } else { [ordered]@{ launched = $false; exit_code = $null; output = 'railway is not on PATH for this principal'; error_class = 'ABSENT' } }
})

foreach ($candidate in $deployPaths) {
    if (-not $candidate) { continue }
    if ($candidate -notmatch 'railway') { continue }
    [void]$railwayProbes.Add([ordered]@{
        class  = 'ABSOLUTE_PATH'
        target = $candidate
        probe  = Invoke-Probe -FilePath $candidate -Arguments @('whoami')
    })
}

$pythonExe = (Get-Command 'python' -ErrorAction SilentlyContinue).Source
if ($pythonExe -and $deployPaths.Count -gt 0) {
    $target = @($deployPaths | Where-Object { $_ -match 'railway' } | Select-Object -First 1)
    if ($target) {
        $snippet = "import subprocess,sys" + [char]10 +
                   "try:" + [char]10 +
                   "    p=subprocess.run([r'$target','whoami'],capture_output=True,text=True,timeout=40)" + [char]10 +
                   "    print(p.returncode); print(p.stdout+p.stderr)" + [char]10 +
                   "except Exception as e:" + [char]10 +
                   "    print('EXC'); print(type(e).__name__)"
        $tmp = Join-Path $env:TEMP 'r5_railway_probe.py'
        Set-Content -LiteralPath $tmp -Value $snippet -Encoding ASCII
        [void]$railwayProbes.Add([ordered]@{
            class  = 'PYTHON_SUBPROCESS'
            target = $target
            probe  = Invoke-Probe -FilePath $pythonExe -Arguments @("`"$tmp`"")
        })
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

$comspec = $env:ComSpec
if ($comspec -and $deployPaths.Count -gt 0) {
    $target = @($deployPaths | Where-Object { $_ -match 'railway' } | Select-Object -First 1)
    if ($target) {
        [void]$railwayProbes.Add([ordered]@{
            class  = 'CMD_INDIRECTION'
            target = $target
            probe  = Invoke-Probe -FilePath $comspec -Arguments @('/c', "`"`"$target`" whoami`"")
        })
    }
}

$powershellExe = (Get-Command 'powershell' -ErrorAction SilentlyContinue).Source
if ($powershellExe -and $deployPaths.Count -gt 0) {
    $target = @($deployPaths | Where-Object { $_ -match 'railway' } | Select-Object -First 1)
    if ($target) {
        [void]$railwayProbes.Add([ordered]@{
            class  = 'POWERSHELL_INDIRECTION'
            target = $target
            probe  = Invoke-Probe -FilePath $powershellExe -Arguments @('-NoProfile', '-Command', "`"& '$target' whoami`"")
        })
    }
}

foreach ($entry in $railwayProbes) { $entry['verdict'] = Get-AuthVerdict $entry.probe }
$railwayAuthenticated  = @($railwayProbes | Where-Object { $_.verdict -eq 'AUTHENTICATED' })
$railwayInconclusive   = @($railwayProbes | Where-Object { $_.verdict -eq 'INCONCLUSIVE' })
$railwayReachable = if ($railwayAuthenticated.Count -gt 0) { 'YES' } elseif ($railwayInconclusive.Count -gt 0) { 'NOT_PROVEN' } else { 'NO' }
if ($railwayAuthenticated.Count -gt 0) {
    Add-Finding 'CRITICAL' 'RAILWAY_AUTH_REACHABLE' "$($railwayAuthenticated.Count) bypass class(es) reached a live Railway session from the dedicated principal."
}

# ----------------------------------------------------------- D. GitHub CLI

$ghCommand = Get-Command 'gh' -ErrorAction SilentlyContinue
$ghProbe = if ($ghCommand) { Invoke-Probe -FilePath $ghCommand.Source -Arguments @('auth', 'status') }
           else { [ordered]@{ launched = $false; exit_code = $null; output = 'gh is not reachable for this principal'; error_class = 'ABSENT' } }
$ghVerdict = Get-AuthVerdict $ghProbe
$ghReachable = switch ($ghVerdict) { 'AUTHENTICATED' { 'YES' } 'INCONCLUSIVE' { 'NOT_PROVEN' } default { 'NO' } }
if ($ghVerdict -eq 'AUTHENTICATED') {
    Add-Finding 'CRITICAL' 'GH_AUTH_REACHABLE' 'The dedicated principal holds a live GitHub CLI session, which is a push and workflow-dispatch route to production.'
}

# ------------------------------------------- E. Windows Credential Manager

$cmdkey = Invoke-Probe -FilePath 'cmdkey.exe' -Arguments @('/list')
$credentialEntryCount = 0
if ($cmdkey.launched) {
    # cmdkey output is localised; match the English and German field labels.
    $credentialEntryCount = ([regex]::Matches($cmdkey.output, '(?i)\b(target|ziel):')).Count
}
$credentialAuthorityReachable = if (-not $cmdkey.launched) { 'NOT_PROVEN' } elseif ($credentialEntryCount -eq 0) { 'NO' } else { 'YES' }
if ($credentialEntryCount -gt 0) {
    Add-Finding 'HIGH' 'CREDENTIAL_MANAGER_ENTRIES_PRESENT' "$credentialEntryCount credential entries are visible to the dedicated principal. A fresh principal should have none."
}

# ------------------------------------------------- F. host profile stores

$storeResults = @{}
$storesReadable = 0
$storesInconclusive = 0
if ($preflight) {
    foreach ($property in $preflight.host_credential_stores.PSObject.Properties) {
        $path = $property.Value.path
        $entry = [ordered]@{ path = $path; readable_by_principal = $null; detail = $null }
        try {
            if (Test-Path -LiteralPath $path) {
                if ((Get-Item -LiteralPath $path -Force).PSIsContainer) {
                    $null = Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop
                } else {
                    $stream = [System.IO.File]::OpenRead($path)
                    $null = $stream.ReadByte()   # one byte, discarded; contents are never surfaced
                    $stream.Close()
                }
                $entry.readable_by_principal = $true
                $entry.detail = 'opened'
            } else {
                $entry.readable_by_principal = $false
                $entry.detail = 'not visible to this principal'
            }
        } catch [System.UnauthorizedAccessException] {
            $entry.readable_by_principal = $false
            $entry.detail = 'UnauthorizedAccessException'
        } catch {
            $entry.readable_by_principal = $false
            $entry.detail = $_.Exception.GetType().Name
        }
        if ($entry.readable_by_principal -and $property.Value.exists_for_host) {
            $storesReadable++
            Add-Finding 'CRITICAL' 'HOST_CREDENTIAL_STORE_READABLE' "$($property.Name) at $path is readable by the dedicated principal."
        }
        $storeResults[$property.Name] = $entry
    }
} else {
    $storesInconclusive = 1
}

$secretFilesReachable = 'NO'
if ($storesReadable -gt 0 -or $sentinelReadable -eq $true) { $secretFilesReachable = 'YES' }
elseif (-not $preflight -or $null -eq $sentinelReadable)   { $secretFilesReachable = 'NOT_PROVEN' }

# In-workspace secrets are a separate class: the workspace is deliberately RW,
# so an OS boundary cannot hide anything inside it.
$inWorkspaceSecrets = @()
if ($preflight) { $inWorkspaceSecrets = @($preflight.in_workspace_secret_files) }
$inWorkspaceReadable = New-Object System.Collections.ArrayList
foreach ($secret in $inWorkspaceSecrets) {
    $full = Join-Path $secret.root $secret.relative_path
    $readable = $false
    try {
        $stream = [System.IO.File]::OpenRead($full)
        $null = $stream.ReadByte()
        $stream.Close()
        $readable = $true
    } catch { }
    [void]$inWorkspaceReadable.Add([ordered]@{
        path              = $full
        readable          = $readable
        git_tracked       = $secret.git_tracked
        in_git_history    = $secret.in_git_history
    })
    if ($readable -or $secret.in_git_history) {
        $secretFilesReachable = 'YES'
        Add-Finding 'CRITICAL' 'IN_WORKSPACE_SECRET_REACHABLE' "$full is inside an approved RW workspace (readable=$readable, in_git_history=$($secret.in_git_history)). No OS principal boundary can close this while the workspace stays writable."
    }
}

# ---------------------------------- F2. relocated host-only secret files
#
# The relocation is only worth anything if the new location is genuinely out of
# reach. Same fail-closed rule: an unrecorded layout is NOT_PROVEN, never NO.

$hostSecretLayout = if ($preflight) { $preflight.host_secret_layout } else { $null }
$hostSecretResults = New-Object System.Collections.ArrayList
$hostSecretReachable = 'NOT_PROVEN'

if ($hostSecretLayout) {
    $rootReadable = $null
    try {
        $null = Get-ChildItem -LiteralPath $hostSecretLayout.root -Force -ErrorAction Stop
        $rootReadable = $true
    } catch [System.UnauthorizedAccessException] {
        $rootReadable = $false
    } catch [System.IO.DirectoryNotFoundException] {
        $rootReadable = $false
    } catch {
        $rootReadable = $false
    }
    [void]$hostSecretResults.Add([ordered]@{ path = $hostSecretLayout.root; kind = 'ROOT'; readable = $rootReadable })

    $anyFileReadable = $false
    $anyFileRecorded = $false
    foreach ($file in @($hostSecretLayout.files)) {
        if (-not $file.exists) {
            [void]$hostSecretResults.Add([ordered]@{ path = $file.path; kind = 'FILE'; readable = $null })
            continue
        }
        $anyFileRecorded = $true
        $readable = $false
        try {
            $stream = [System.IO.File]::OpenRead($file.path)
            $null = $stream.ReadByte()   # one byte, discarded; contents are never surfaced
            $stream.Close()
            $readable = $true
        } catch {
        }
        if ($readable) { $anyFileReadable = $true }
        [void]$hostSecretResults.Add([ordered]@{ path = $file.path; kind = 'FILE'; readable = $readable })
    }

    if ($anyFileReadable -or $rootReadable -eq $true) {
        $hostSecretReachable = 'YES'
        Add-Finding 'CRITICAL' 'HOST_SECRET_ROOT_READABLE' "The dedicated principal can read the host-only secret root $($hostSecretLayout.root). Relocation moved the files but did not remove reachability."
    } elseif ($anyFileRecorded -and $rootReadable -eq $false) {
        $hostSecretReachable = 'NO'
    } elseif ($rootReadable -eq $false -and -not $hostSecretLayout.root_exists) {
        # Nothing relocated yet: nothing proven either.
        $hostSecretReachable = 'NOT_PROVEN'
        Add-Finding 'MEDIUM' 'HOST_SECRET_LAYOUT_ABSENT' 'No host-only secret files were recorded, so the relocation half of the remediation is unproven.'
    }
}

if ($hostSecretReachable -eq 'YES') { $secretFilesReachable = 'YES' }
elseif ($hostSecretReachable -eq 'NOT_PROVEN' -and $secretFilesReachable -eq 'NO') { $secretFilesReachable = 'NOT_PROVEN' }

# ------------------------------------------------------- G. deploy authority

$deployReachable = 'NO'
if ($railwayReachable -eq 'YES' -or $ghReachable -eq 'YES') { $deployReachable = 'YES' }
elseif ($railwayReachable -eq 'NOT_PROVEN' -or $ghReachable -eq 'NOT_PROVEN' -or -not $preflight) { $deployReachable = 'NOT_PROVEN' }

# --------------------------------------------------- H. capability preservation

$workspaceRoots = if ($preflight) { @($preflight.workspace_roots) } else { @($RepoRoot) }
$workspaceResults = @{}
foreach ($root in $workspaceRoots) {
    $entry = [ordered]@{ root = $root; readable = $false; writable = $false }
    try {
        $null = Get-ChildItem -LiteralPath $root -Force -ErrorAction Stop | Select-Object -First 1
        $entry.readable = $true
    } catch { }
    $probeFile = Join-Path $root ".r5-principal-write-probe.tmp"
    try {
        Set-Content -LiteralPath $probeFile -Value 'r5-principal-write-probe' -Encoding ASCII -ErrorAction Stop
        $entry.writable = ((Get-Content -LiteralPath $probeFile -Raw).Trim() -eq 'r5-principal-write-probe')
        Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
    } catch { }
    $workspaceResults[$root] = $entry
    if (-not $entry.writable) {
        Add-Finding 'HIGH' 'WORKSPACE_NOT_WRITABLE' "$root is not writable by the dedicated principal. The isolation fix must not cost workspace capability."
    }
}

$gitProbe = Invoke-Probe -FilePath (Get-Command 'git').Source -Arguments @('-C', "`"$RepoRoot`"", 'status', '--short')
$gitWorks = ($gitProbe.launched -and $gitProbe.exit_code -eq 0)
if (-not $gitWorks) {
    Add-Finding 'HIGH' 'GIT_UNAVAILABLE' "git status failed for the dedicated principal ($($gitProbe.output)). If this is a dubious-ownership refusal, the bootstrap safe.directory step did not run."
}

# ------------------------------------------------------------------- verdict

$blocking = @($findings | Where-Object { $_.severity -in @('CRITICAL', 'HIGH') })
$acceptanceMet = (
    $principalResult.CHILD_OS_PRINCIPAL -eq 'SEPARATE_PRINCIPAL' -and
    -not $isAdmin -and
    $hostProfileReachable -eq 'NO' -and
    $railwayReachable -eq 'NO' -and
    $ghReachable -eq 'NO' -and
    $credentialAuthorityReachable -eq 'NO' -and
    $hostSecretReachable -eq 'NO' -and
    $secretFilesReachable -eq 'NO' -and
    $deployReachable -eq 'NO' -and
    $gitWorks -and
    @($workspaceResults.Values | Where-Object { -not $_.writable }).Count -eq 0
)

$report = [ordered]@{
    schema        = 'r5.principal_isolation.v1'
    generated_utc = (Get-Date).ToUniversalTime().ToString('o')
    principal     = $principalResult
    host_profile_sentinel = [ordered]@{ path = $sentinelPath; readable = $sentinelReadable; detail = $sentinelDetail }
    railway       = [ordered]@{ probes = @($railwayProbes); reachable = $railwayReachable }
    github_cli    = [ordered]@{ probe = $ghProbe; verdict = $ghVerdict; reachable = $ghReachable }
    windows_credential_manager = [ordered]@{ entry_count = $credentialEntryCount; reachable = $credentialAuthorityReachable }
    host_credential_stores     = $storeResults
    host_only_secret_files     = @($hostSecretResults)
    in_workspace_secret_files  = @($inWorkspaceReadable)
    workspace                  = $workspaceResults
    git_status_works           = $gitWorks
    findings                   = @($findings)

    CHILD_OS_PRINCIPAL                    = $principalResult.CHILD_OS_PRINCIPAL
    HOST_PROFILE_FILESYSTEM_REACHABLE     = $hostProfileReachable
    RAILWAY_AUTH_REACHABLE                = $railwayReachable
    GH_AUTH_REACHABLE                     = $ghReachable
    WINDOWS_CREDENTIAL_AUTHORITY_REACHABLE = $credentialAuthorityReachable
    HOST_ONLY_SECRET_ROOT_REACHABLE       = $hostSecretReachable
    PRODUCTION_SECRET_FILES_REACHABLE     = $secretFilesReachable
    PRODUCTION_DEPLOY_REACHABLE           = $deployReachable
    PATH_STUB_SECURITY_ROLE               = 'NONE'
    ISOLATION_ACCEPTANCE                  = if ($acceptanceMet) { 'PASS' } else { 'FAIL' }
}

$artifactDir = Split-Path $ArtifactPath -Parent
if (-not (Test-Path -LiteralPath $artifactDir)) { New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null }
$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $ArtifactPath -Encoding UTF8

Write-Host ''
Write-Host '--- R5 principal isolation properties ---'
foreach ($key in @(
    'CHILD_OS_PRINCIPAL', 'HOST_PROFILE_FILESYSTEM_REACHABLE', 'RAILWAY_AUTH_REACHABLE',
    'GH_AUTH_REACHABLE', 'WINDOWS_CREDENTIAL_AUTHORITY_REACHABLE',
    'HOST_ONLY_SECRET_ROOT_REACHABLE', 'PRODUCTION_SECRET_FILES_REACHABLE',
    'PRODUCTION_DEPLOY_REACHABLE', 'ISOLATION_ACCEPTANCE')) {
    Write-Host ("{0,-40} = {1}" -f $key, $report[$key])
}
if ($blocking.Count -gt 0) {
    Write-Host ''
    Write-Host 'BLOCKING FINDINGS:'
    foreach ($finding in $blocking) { Write-Host "  [$($finding.severity)] $($finding.id): $($finding.detail)" }
}
Write-Host ''
Write-Host "artifact = $ArtifactPath"

if ($acceptanceMet) { exit 0 }
exit 1
