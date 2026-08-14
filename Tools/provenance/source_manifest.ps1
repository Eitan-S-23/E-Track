[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [switch]$CopySources
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'worktree_guard.ps1')

$root = Assert-ActiveWorktree $RepoRoot
$output = New-WorktreeDirectory -RepoRoot $root -DirectoryPath $OutputDirectory
$copyRoot = Join-Path $output 'p'
if ($CopySources) {
    New-WorktreeDirectory -RepoRoot $root -DirectoryPath $copyRoot | Out-Null
}

$rootPatterns = @(
    'ArduinoAPI/',
    'Libraries/',
    'USER/',
    'boot/',
    'bsdiff_lzma_AES128-main/',
    'cmake/',
    'MDK-ARM_F435/Platform/',
    'MDK-ARM_F435/cmake-generated/cmake/',
    'Simulator/LVGL.Simulator/',
    'Tools/',
    'tests/',
    'segger_rtt/',
    'vendor/'
)
$topFiles = @(
    'AGENTS.md',
    'CMakeLists.txt',
    'build_f435_and_simulator.bat',
    'MDK-ARM_F435/build_f435.ps1',
    'MDK-ARM_F435/proj.uvprojx'
)

$gitArgs = @('-C', $root, 'ls-files', '-co', '--exclude-standard', '--') +
    @($rootPatterns + $topFiles)
$candidatePaths = @(& git @gitArgs)
if ($LASTEXITCODE -ne 0) {
    throw "git ls-files failed: $LASTEXITCODE"
}

$paths = New-Object 'System.Collections.Generic.List[string]'
foreach ($raw in $candidatePaths) {
    $path = ([string]$raw).Replace('\', '/')
    if ($path -like '*.base@*') {
        continue
    }
    if ($path.StartsWith('Tools/provenance/', [StringComparison]::Ordinal)) {
        continue
    }
    if ($topFiles -contains $path) {
        $paths.Add($path)
        continue
    }
    foreach ($prefix in $rootPatterns) {
        if ($path.StartsWith($prefix, [StringComparison]::Ordinal)) {
            if ($path -match '(^|/)(build[^/]*|Output|Objects|Listings|\.vs|__pycache__)(/|$)') {
                break
            }
            $paths.Add($path)
            break
        }
    }
}

$uniqueSet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::Ordinal)
$uniqueList = New-Object 'System.Collections.Generic.List[string]'
foreach ($path in $paths) {
    if ($uniqueSet.Add($path)) {
        $uniqueList.Add($path)
    }
}
$ordered = [string[]]$uniqueList.ToArray()
[Array]::Sort($ordered, [System.StringComparer]::Ordinal)

$records = New-Object 'System.Collections.Generic.List[object]'
$lines = New-Object 'System.Collections.Generic.List[string]'
foreach ($relative in $ordered) {
    $source = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not (Test-GuardInside $root $source)) {
        throw "Manifest source escapes worktree: $relative"
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        continue
    }
    $item = Get-Item -LiteralPath $source -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Manifest source is a reparse point: $source"
    }
    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToUpperInvariant()
    $record = [pscustomobject]@{
        Path = $relative
        Length = [int64]$item.Length
        SHA256 = $hash
    }
    $records.Add($record)
    $lines.Add(('{0}  {1}  {2}' -f $hash, $item.Length, $relative))

    if ($CopySources) {
        $target = Join-Path $copyRoot $relative
        Assert-WorktreeOutput -RepoRoot $root -OutputPath $target | Out-Null
        New-WorktreeDirectory -RepoRoot $root -DirectoryPath (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant()
        if ($targetHash -ne $hash -or (Get-Item -LiteralPath $target).Length -ne $item.Length) {
            throw "Manifest source copy mismatch: $relative"
        }
    }
}

$encoding = [Text.UTF8Encoding]::new($false)
$manifestPath = Join-Path $output 'source-manifest.txt'
[IO.File]::WriteAllText($manifestPath, (($lines -join "`r`n") + "`r`n"), $encoding)
$manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToUpperInvariant()
$recordArray = @($records.ToArray())
$orderingName = 'UTF-8 normalized slash paths, bytewise Ordinal ascending'

$json = [ordered]@{
    Schema = 'p2-5-source-manifest-v1'
    Ordering = $orderingName
    Encoding = 'UTF-8 without BOM, CRLF, one trailing newline'
    RepoRoot = $root
    Head = (& git -C $root rev-parse HEAD).Trim()
    FileCount = $records.Count
    ManifestSHA256 = $manifestHash
    Files = $recordArray
}
[IO.File]::WriteAllText((Join-Path $output 'source-manifest.json'), (($json | ConvertTo-Json -Depth 6) + "`r`n"), $encoding)

$summary = [ordered]@{
    Result = 'PASS'
    FileCount = $records.Count
    ManifestSHA256 = $manifestHash
    ManifestPath = $manifestPath
    CopyRoot = if ($CopySources) { $copyRoot } else { $null }
}
[IO.File]::WriteAllText((Join-Path $output 'summary.json'), (($summary | ConvertTo-Json -Depth 5) + "`r`n"), $encoding)
Write-Output (($summary | ConvertTo-Json -Compress -Depth 5))
