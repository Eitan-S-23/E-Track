Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:GuardSeparators = if (
    [IO.Path]::DirectorySeparatorChar -eq [IO.Path]::AltDirectorySeparatorChar
) {
    [char[]]@([IO.Path]::DirectorySeparatorChar)
} else {
    [char[]]@(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
}
$script:GuardPathComparison = if ([IO.Path]::DirectorySeparatorChar -eq '\') {
    [StringComparison]::OrdinalIgnoreCase
} else {
    [StringComparison]::Ordinal
}

function Get-GuardFullPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    return [IO.Path]::GetFullPath($Path)
}

function Get-GuardNormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = Get-GuardFullPath $Path
    $pathRoot = [IO.Path]::GetPathRoot($full)
    while ($full.Length -gt $pathRoot.Length -and
        $script:GuardSeparators -contains $full[$full.Length - 1]) {
        $full = $full.Substring(0, $full.Length - 1)
    }
    return $full
}

function Test-GuardPathEqual {
    param(
        [Parameter(Mandatory = $true)][string]$Left,
        [Parameter(Mandatory = $true)][string]$Right
    )

    return (Get-GuardNormalizedPath $Left).Equals(
        (Get-GuardNormalizedPath $Right),
        $script:GuardPathComparison
    )
}

function Test-GuardInside {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Candidate
    )

    $rootFull = Get-GuardNormalizedPath $Root
    $candidateFull = Get-GuardNormalizedPath $Candidate
    $separator = [string][IO.Path]::DirectorySeparatorChar
    $prefix = if ($rootFull.EndsWith($separator, $script:GuardPathComparison)) {
        $rootFull
    } else {
        $rootFull + $separator
    }
    return $candidateFull.Equals($rootFull, $script:GuardPathComparison) -or
        $candidateFull.StartsWith($prefix, $script:GuardPathComparison)
}

function Resolve-GuardPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = Get-GuardNormalizedPath $Path
    $tail = New-Object 'System.Collections.Generic.List[string]'
    $probe = $full
    while (-not (Test-Path -LiteralPath $probe)) {
        $parent = Split-Path -Parent $probe
        if ([string]::IsNullOrEmpty($parent) -or (Test-GuardPathEqual $parent $probe)) {
            throw "Cannot resolve output parent: $Path"
        }
        $tail.Insert(0, (Split-Path -Leaf $probe))
        $probe = $parent
    }

    $resolved = (Resolve-Path -LiteralPath $probe).Path
    foreach ($part in $tail) {
        $resolved = Join-Path $resolved $part
    }
    return Get-GuardNormalizedPath $resolved
}

function Assert-GuardNoReparseParents {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = Get-GuardNormalizedPath $Root
    $candidateFull = Get-GuardNormalizedPath $Path
    if (-not (Test-GuardInside $rootFull $candidateFull)) {
        throw "Path is outside active worktree: $candidateFull"
    }

    $relative = $candidateFull.Substring($rootFull.Length).TrimStart($script:GuardSeparators)
    $current = $rootFull
    if ($relative.Length -eq 0) {
        $parts = @()
    } else {
        $parts = $relative.Split(
            $script:GuardSeparators,
            [StringSplitOptions]::RemoveEmptyEntries
        )
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

    $requested = Get-GuardNormalizedPath $RepoRoot
    if (-not (Test-Path -LiteralPath $requested -PathType Container)) {
        throw "Repository root is not a directory: $requested"
    }

    $gitRoot = (& git -C $requested rev-parse --show-toplevel 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitRoot)) {
        throw "Unable to resolve git worktree root from: $requested"
    }
    $gitRoot = Resolve-GuardPath $gitRoot
    $requestedResolved = Resolve-GuardPath $requested
    if (-not (Test-GuardPathEqual $gitRoot $requestedResolved)) {
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
    $resolved = Get-GuardNormalizedPath $DirectoryPath
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
    $resolved = Get-GuardNormalizedPath $FilePath
    if (-not (Test-GuardInside $root $resolved)) {
        throw "Output file is outside active worktree: $resolved"
    }
    $parent = Split-Path -Parent $resolved
    if ([string]::IsNullOrWhiteSpace($parent)) {
        throw "Output file has no parent directory: $resolved"
    }
    New-WorktreeDirectory -RepoRoot $root -DirectoryPath $parent | Out-Null
    $item = Get-Item -LiteralPath $resolved -Force -ErrorAction SilentlyContinue
    if ($null -ne $item) {
        $hasLinkType = $null -ne $item.PSObject.Properties['LinkType'] -and
            -not [string]::IsNullOrWhiteSpace([string]$item.LinkType)
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or $hasLinkType) {
            throw "Output file is a link or reparse point: $resolved"
        }
        if ($item.PSIsContainer) {
            throw "Output file path is an existing directory: $resolved"
        }
    }
    return $resolved
}
