Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-GuardFullPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [IO.Path]::GetFullPath($Path)
}

function Test-GuardInside {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate
    )

    $rootFull = (Get-GuardFullPath $Root).TrimEnd('\')
    $candidateFull = Get-GuardFullPath $Candidate
    return $candidateFull.Equals($rootFull, [StringComparison]::OrdinalIgnoreCase) -or
        $candidateFull.StartsWith($rootFull + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Resolve-GuardPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = Get-GuardFullPath $Path
    $tail = New-Object 'System.Collections.Generic.List[string]'
    $probe = $full
    while (-not (Test-Path -LiteralPath $probe)) {
        $parent = Split-Path -Parent $probe
        if ([string]::IsNullOrEmpty($parent) -or $parent.Equals($probe, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Cannot resolve output parent: $Path"
        }
        $tail.Insert(0, (Split-Path -Leaf $probe))
        $probe = $parent
    }

    $resolved = (Resolve-Path -LiteralPath $probe).Path
    foreach ($part in $tail) {
        $resolved = Join-Path $resolved $part
    }
    return Get-GuardFullPath $resolved
}

function Assert-GuardNoReparseParents {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = Get-GuardFullPath $Root
    $candidateFull = Get-GuardFullPath $Path
    if (-not (Test-GuardInside $rootFull $candidateFull)) {
        throw "Path is outside active worktree: $candidateFull"
    }

    $relative = $candidateFull.Substring($rootFull.TrimEnd('\').Length).TrimStart('\')
    $current = $rootFull
    if ($relative.Length -eq 0) {
        $parts = @()
    } else {
        $parts = $relative -split '\\'
    }
    foreach ($part in $parts) {
        $current = Join-Path $current $part
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse point in output path: $current"
            }
        }
    }
}

function Assert-ActiveWorktree {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $requested = Get-GuardFullPath $RepoRoot
    if (-not (Test-Path -LiteralPath $requested -PathType Container)) {
        throw "Repository root is not a directory: $requested"
    }

    $gitRoot = (& git -C $requested rev-parse --show-toplevel 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitRoot)) {
        throw "Unable to resolve git worktree root from: $requested"
    }
    $gitRoot = Resolve-GuardPath $gitRoot
    $requestedResolved = Resolve-GuardPath $requested
    if (-not $gitRoot.Equals($requestedResolved, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Requested root does not match git worktree root: requested=$requestedResolved git=$gitRoot"
    }

    $rootItem = Get-Item -LiteralPath $gitRoot -Force
    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Git worktree root is a reparse point: $gitRoot"
    }
    return $gitRoot
}

function Assert-WorktreeOutput {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    $root = Assert-ActiveWorktree $RepoRoot
    $resolved = Resolve-GuardPath $OutputPath
    Assert-GuardNoReparseParents -Root $root -Path $resolved
    return $resolved
}

function New-WorktreeDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$DirectoryPath
    )

    $root = Assert-ActiveWorktree $RepoRoot
    $resolved = Get-GuardFullPath $DirectoryPath
    if (-not (Test-GuardInside $root $resolved)) {
        throw "Output directory is outside active worktree: $resolved"
    }
    $parent = Split-Path -Parent $resolved
    if ($parent) {
        $parentResolved = Resolve-GuardPath $parent
        Assert-GuardNoReparseParents -Root $root -Path $parentResolved
    }
    [IO.Directory]::CreateDirectory($resolved) | Out-Null
    Assert-GuardNoReparseParents -Root $root -Path $resolved
    return $resolved
}

function Assert-WorktreeFileOutput {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$FilePath
    )

    $root = Assert-ActiveWorktree $RepoRoot
    $resolved = Get-GuardFullPath $FilePath
    if (-not (Test-GuardInside $root $resolved)) {
        throw "Output file is outside active worktree: $resolved"
    }
    $parent = Split-Path -Parent $resolved
    if ([string]::IsNullOrWhiteSpace($parent)) {
        throw "Output file has no parent directory: $resolved"
    }
    New-WorktreeDirectory -RepoRoot $root -DirectoryPath $parent | Out-Null
    return $resolved
}
