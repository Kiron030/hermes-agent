param(
    [string]$ConfigPath = "config/powerunits_fork_sync_config.json",
    [string]$DateStamp = "",
    [switch]$SkipPush,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,
        [switch]$AllowFailure
    )

    & git @Args
    $code = $LASTEXITCODE
    if (-not $AllowFailure -and $code -ne 0) {
        throw "git $($Args -join ' ') failed with exit code $code"
    }
    return $code
}

function Write-Checklist {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Items
    )

    Write-Host ""
    Write-Host "Validation checklist (before merging into stable branch):" -ForegroundColor Yellow
    $i = 1
    foreach ($item in $Items) {
        Write-Host ("  {0}. {1}" -f $i, $item)
        $i++
    }
}

function Get-AheadBehindLabel {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LeftRef,
        [Parameter(Mandatory = $true)]
        [string]$RightRef
    )

    $line = git rev-list --left-right --count "$LeftRef...$RightRef" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $line) {
        return "n/a"
    }

    $parts = ($line.Trim() -split "\s+")
    if ($parts.Count -lt 2) {
        return "n/a"
    }

    return "ahead=$($parts[0]), behind=$($parts[1])"
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

$upstreamRemote = [string]$cfg.upstream_remote
$originRemote = [string]$cfg.origin_remote
$upstreamBranch = [string]$cfg.upstream_branch
$stableBranch = [string]$cfg.stable_branch
$activeBranch = [string]$cfg.active_branch
$integrationPrefix = [string]$cfg.integration_branch_prefix
$protectedPaths = @($cfg.protected_paths)
$validationReminders = @($cfg.validation_reminders)

if (-not $DateStamp) {
    $DateStamp = Get-Date -Format "yyyyMMdd"
}

if (-not $integrationPrefix) {
    throw "integration_branch_prefix is required in config"
}

$integrationBranch = "$integrationPrefix$DateStamp"

Write-Host "== Powerunits upstream sync helper ==" -ForegroundColor Cyan
Write-Host "Config: $ConfigPath"
Write-Host "Stable branch: $stableBranch"
Write-Host "Active customization branch: $activeBranch"
Write-Host "Integration branch: $integrationBranch"

if ($activeBranch -and $activeBranch -ne $stableBranch) {
    Write-Host "Note: active branch differs from stable branch in config." -ForegroundColor Yellow
}

# Require clean working tree.
$statusLines = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read git status"
}
if ($statusLines) {
    Write-Host ""
    Write-Host "Working tree is not clean. Commit/stash changes first:" -ForegroundColor Red
    $statusLines | ForEach-Object { Write-Host "  $_" }
    exit 1
}

# Validate required remotes.
$remotes = git remote
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read remotes"
}
if ($remotes -notcontains $upstreamRemote) {
    throw "Missing required remote '$upstreamRemote'"
}
if ($remotes -notcontains $originRemote) {
    throw "Missing required remote '$originRemote'"
}

Write-Host ""
Write-Host "Fetching remotes..." -ForegroundColor Cyan
Invoke-Git -Args @("fetch", $upstreamRemote)
Invoke-Git -Args @("fetch", $originRemote)

if ($DryRun) {
    Write-Host ""
    Write-Host "== DryRun report ==" -ForegroundColor Green
    Write-Host "Current stable branch: $stableBranch"
    Write-Host "Configured active branch: $activeBranch"
    Write-Host "Computed integration branch: $integrationBranch"

    $stableVsOrigin = Get-AheadBehindLabel -LeftRef $stableBranch -RightRef "${originRemote}/${stableBranch}"
    $stableVsUpstream = Get-AheadBehindLabel -LeftRef $stableBranch -RightRef "${upstreamRemote}/${upstreamBranch}"
    Write-Host "Stable vs ${originRemote}/${stableBranch}: $stableVsOrigin"
    Write-Host "Stable vs ${upstreamRemote}/${upstreamBranch}: $stableVsUpstream"

    Write-Host ""
    Write-Host "Powerunits-protected paths reminder:" -ForegroundColor Yellow
    foreach ($path in $protectedPaths) {
        Write-Host "  - $path"
    }

    Write-Checklist -Items $validationReminders

    Write-Host ""
    Write-Host "DryRun complete. No branch created, no merge, no push." -ForegroundColor DarkYellow
    exit 0
}

Write-Host ""
Write-Host "Preparing integration branch from stable branch..." -ForegroundColor Cyan
Invoke-Git -Args @("checkout", $stableBranch)
Invoke-Git -Args @("pull", $originRemote, $stableBranch)

# Create fresh integration branch. If it exists, stop safely.
$existsCode = Invoke-Git -Args @("rev-parse", "--verify", $integrationBranch) -AllowFailure
if ($existsCode -eq 0) {
    throw "Branch '$integrationBranch' already exists. Use a different DateStamp."
}
Invoke-Git -Args @("checkout", "-b", $integrationBranch)

Write-Host ""
Write-Host "Merging ${upstreamRemote}/${upstreamBranch} into $integrationBranch..." -ForegroundColor Cyan
$mergeCode = Invoke-Git -Args @("merge", "${upstreamRemote}/${upstreamBranch}") -AllowFailure
if ($mergeCode -ne 0) {
    $conflicts = git diff --name-only --diff-filter=U
    Write-Host ""
    Write-Host "Merge stopped due to conflicts. Resolve manually before push." -ForegroundColor Red
    if ($conflicts) {
        Write-Host "Conflicting files:"
        $conflicts | ForEach-Object { Write-Host "  - $_" }
    }
    Write-Host ""
    Write-Host "Important Powerunits-protected paths to verify during conflict resolution:" -ForegroundColor Yellow
    foreach ($path in $protectedPaths) {
        Write-Host "  - $path"
    }
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1) Resolve conflicts"
    Write-Host "  2) git add <resolved-files>"
    Write-Host "  3) git commit"
    Write-Host "  4) git push -u $originRemote $integrationBranch"
    exit 2
}

if (-not $SkipPush) {
    Write-Host ""
    Write-Host "Pushing integration branch to origin..." -ForegroundColor Cyan
    Invoke-Git -Args @("push", "-u", $originRemote, $integrationBranch)
}

Write-Host ""
Write-Host "Sync integration branch ready: $integrationBranch" -ForegroundColor Green
Write-Host "Create a PR: $integrationBranch -> $stableBranch"
Write-Host ""
Write-Host "Powerunits-protected paths to review in PR:" -ForegroundColor Yellow
foreach ($path in $protectedPaths) {
    Write-Host "  - $path"
}

Write-Checklist -Items $validationReminders

Write-Host ""
Write-Host "Safety note: this script does NOT auto-merge into '$stableBranch' or deploy." -ForegroundColor DarkYellow
