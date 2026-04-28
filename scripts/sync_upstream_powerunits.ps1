param(
    [string]$ConfigPath = "config/powerunits_fork_sync_config.json",
    [string]$DateStamp = "",
    [string]$UpstreamRef = "",
    [switch]$SkipPush,
    [switch]$DryRun,
    [switch]$ConservativeMode
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

function Resolve-MergeTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Remote,
        [Parameter(Mandatory = $true)]
        [string]$Ref,
        [Parameter(Mandatory = $true)]
        [string]$FallbackBranch
    )

    $candidate = [string]$Ref
    $candidate = $candidate.Trim()
    if (-not $candidate) {
        return "${Remote}/${FallbackBranch}"
    }

    $remoteRef = "${Remote}/${candidate}"
    & git rev-parse --verify $remoteRef *> $null
    if ($LASTEXITCODE -eq 0) {
        return $remoteRef
    }

    & git rev-parse --verify $candidate *> $null
    if ($LASTEXITCODE -eq 0) {
        return $candidate
    }

    $tagRef = "refs/tags/$candidate"
    & git rev-parse --verify $tagRef *> $null
    if ($LASTEXITCODE -eq 0) {
        return $tagRef
    }

    throw "Unable to resolve upstream ref '$candidate'. Try a branch name, tag, or full ref."
}

function Get-SensitiveMatches {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ChangedFiles,
        [Parameter(Mandatory = $true)]
        [string[]]$Patterns
    )

    $matches = @()
    foreach ($file in $ChangedFiles) {
        foreach ($pattern in $Patterns) {
            if ($file -like $pattern) {
                $matches += [PSCustomObject]@{
                    file = $file
                    pattern = $pattern
                }
            }
        }
    }
    return $matches
}

function Write-SensitiveReport {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseRef,
        [Parameter(Mandatory = $true)]
        [string]$TargetRef,
        [Parameter(Mandatory = $true)]
        [string[]]$SensitivePatterns,
        [string[]]$ConservativeDeferPatterns = @(),
        [switch]$ConservativeMode
    )

    $files = git diff --name-only "$BaseRef...$TargetRef"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Sensitive diff review: unable to compute changed files for $BaseRef...$TargetRef" -ForegroundColor Yellow
        return
    }

    $changedFiles = @($files | Where-Object { $_ -and $_.Trim() })
    if (-not $changedFiles) {
        return
    }

    $sensitiveHits = Get-SensitiveMatches -ChangedFiles $changedFiles -Patterns $SensitivePatterns
    if (-not $sensitiveHits) {
        return
    }

    Write-Host ""
    Write-Host "Sensitive path review (manual check recommended):" -ForegroundColor Yellow
    foreach ($hit in ($sensitiveHits | Sort-Object file -Unique)) {
        Write-Host "  - $($hit.file)"
    }

    if ($ConservativeMode -and $ConservativeDeferPatterns.Count -gt 0) {
        $deferHits = Get-SensitiveMatches -ChangedFiles $changedFiles -Patterns $ConservativeDeferPatterns
        if ($deferHits) {
            Write-Host ""
            Write-Host "Conservative mode recommendation: defer for later review" -ForegroundColor Yellow
            foreach ($hit in ($deferHits | Sort-Object file -Unique)) {
                Write-Host "  - $($hit.file)"
            }
            Write-Host "Reason: keep sync minimal; isolate workflow/supply-chain-sensitive files."
        }
    }
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config not found: $ConfigPath"
}

$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

$upstreamRemote = [string]$cfg.upstream_remote
$originRemote = [string]$cfg.origin_remote
$upstreamBranch = [string]$cfg.upstream_branch
$defaultUpstreamRef = [string]$cfg.default_upstream_ref
$stableBranch = [string]$cfg.stable_branch
$activeBranch = [string]$cfg.active_branch
$integrationPrefix = [string]$cfg.integration_branch_prefix
$sensitivePatterns = @($cfg.sensitive_path_patterns)
$conservativeDeferPatterns = @($cfg.conservative_defer_patterns)
$protectedPaths = @($cfg.protected_paths)
$validationReminders = @($cfg.validation_reminders)

if (-not $DateStamp) {
    $DateStamp = Get-Date -Format "yyyyMMdd"
}

if (-not $integrationPrefix) {
    throw "integration_branch_prefix is required in config"
}

$refFromConfig = [string]$defaultUpstreamRef
$refFromConfig = $refFromConfig.Trim()
if (-not $UpstreamRef -and $refFromConfig) {
    $UpstreamRef = $refFromConfig
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
Invoke-Git -Args @("fetch", $upstreamRemote, "--tags")
Invoke-Git -Args @("fetch", $originRemote)
$mergeTarget = Resolve-MergeTarget -Remote $upstreamRemote -Ref $UpstreamRef -FallbackBranch $upstreamBranch
Write-Host "Upstream source ref: $mergeTarget"

if ($DryRun) {
    Write-Host ""
    Write-Host "== DryRun report ==" -ForegroundColor Green
    Write-Host "Current stable branch: $stableBranch"
    Write-Host "Configured active branch: $activeBranch"
    Write-Host "Computed integration branch: $integrationBranch"

    $stableVsOrigin = Get-AheadBehindLabel -LeftRef $stableBranch -RightRef "${originRemote}/${stableBranch}"
    $stableVsUpstream = Get-AheadBehindLabel -LeftRef $stableBranch -RightRef $mergeTarget
    Write-Host "Stable vs ${originRemote}/${stableBranch}: $stableVsOrigin"
    Write-Host "Stable vs $mergeTarget: $stableVsUpstream"

    Write-SensitiveReport `
        -BaseRef "${originRemote}/${stableBranch}" `
        -TargetRef $mergeTarget `
        -SensitivePatterns $sensitivePatterns `
        -ConservativeDeferPatterns $conservativeDeferPatterns `
        -ConservativeMode:$ConservativeMode

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
Write-Host "Merging $mergeTarget into $integrationBranch..." -ForegroundColor Cyan
$mergeCode = Invoke-Git -Args @("merge", $mergeTarget) -AllowFailure
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

Write-SensitiveReport `
    -BaseRef "${originRemote}/${stableBranch}" `
    -TargetRef "HEAD" `
    -SensitivePatterns $sensitivePatterns `
    -ConservativeDeferPatterns $conservativeDeferPatterns `
    -ConservativeMode:$ConservativeMode

Write-Host ""
Write-Host "Powerunits-protected paths to review in PR:" -ForegroundColor Yellow
foreach ($path in $protectedPaths) {
    Write-Host "  - $path"
}

Write-Checklist -Items $validationReminders

Write-Host ""
Write-Host "Safety note: this script does NOT auto-merge into '$stableBranch' or deploy." -ForegroundColor DarkYellow
