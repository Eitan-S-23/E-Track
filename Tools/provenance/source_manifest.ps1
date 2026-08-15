[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [switch]$CopySources,
    [ValidateSet('Legacy', 'Production', 'Validation', 'Governance')]
    [string]$Profile = 'Legacy'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$utilityModule = Join-Path (Join-Path (Join-Path $PSHOME 'Modules') 'Microsoft.PowerShell.Utility') `
    'Microsoft.PowerShell.Utility.psd1'
Import-Module $utilityModule -ErrorAction Stop
. (Join-Path $PSScriptRoot 'worktree_guard.ps1')

function ConvertTo-NativeArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') {
        return $Value
    }

    $builder = New-Object Text.StringBuilder
    [void]$builder.Append('"')
    $slashCount = 0
    foreach ($character in $Value.ToCharArray()) {
        if ($character -eq '\') {
            $slashCount++
            continue
        }
        if ($character -eq '"') {
            if ($slashCount -gt 0) {
                [void]$builder.Append(('\' * (($slashCount * 2) + 1)))
            } else {
                [void]$builder.Append('\')
            }
            [void]$builder.Append('"')
            $slashCount = 0
            continue
        }
        if ($slashCount -gt 0) {
            [void]$builder.Append(('\' * $slashCount))
            $slashCount = 0
        }
        [void]$builder.Append($character)
    }
    if ($slashCount -gt 0) {
        [void]$builder.Append(('\' * ($slashCount * 2)))
    }
    [void]$builder.Append('"')
    return $builder.ToString()
}

function Invoke-GitNullPathList {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$Pathspecs
    )

    $arguments = @('-C', $Root, 'ls-files', '-co', '--exclude-standard', '-z', '--') +
        @($Pathspecs)
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = 'git'
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    if ($null -ne $startInfo.PSObject.Properties['ArgumentList']) {
        foreach ($argument in $arguments) {
            [void]$startInfo.ArgumentList.Add($argument)
        }
    } else {
        $startInfo.Arguments = (($arguments | ForEach-Object {
            ConvertTo-NativeArgument ([string]$_)
        }) -join ' ')
    }

    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    $buffer = New-Object IO.MemoryStream
    $rawBytes = $null
    $stderr = ''
    $exitCode = -1
    try {
        if (-not $process.Start()) {
            throw 'Unable to start git.'
        }
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.StandardOutput.BaseStream.CopyTo($buffer)
        $process.WaitForExit()
        $stderr = $stderrTask.Result
        $exitCode = $process.ExitCode
        $rawBytes = $buffer.ToArray()
    } finally {
        $buffer.Dispose()
        $process.Dispose()
    }
    if ($exitCode -ne 0) {
        throw "git ls-files failed: $exitCode $($stderr.Trim())"
    }

    $strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
    try {
        $decoded = $strictUtf8.GetString($rawBytes)
    } catch {
        throw "git ls-files returned a non-UTF-8 path: $($_.Exception.Message)"
    }
    return @($decoded.Split([char[]]@([char]0), [StringSplitOptions]::RemoveEmptyEntries))
}

$root = Assert-ActiveWorktree $RepoRoot
$output = New-WorktreeDirectory -RepoRoot $root -DirectoryPath $OutputDirectory
$copyRoot = Join-Path $output 'p'
if ($CopySources) {
    New-WorktreeDirectory -RepoRoot $root -DirectoryPath $copyRoot | Out-Null
}

$profileConfigPath = Join-Path $PSScriptRoot 'manifest_profiles.json'
$profileConfig = Get-Content -LiteralPath $profileConfigPath -Raw | ConvertFrom-Json
if ($profileConfig.schema -ne 'etrack-manifest-profiles-v1') {
    throw "Unsupported manifest profile schema: $($profileConfig.schema)"
}
$profileProperty = $profileConfig.profiles.PSObject.Properties[$Profile]
if ($null -eq $profileProperty) {
    throw "Manifest profile is not defined: $Profile"
}
$profileDefinition = $profileProperty.Value
$rootPatterns = @($profileDefinition.root_patterns | ForEach-Object { [string]$_ })
$topFiles = @($profileDefinition.top_files | ForEach-Object { [string]$_ })
$excludePrefixes = @($profileDefinition.exclude_prefixes | ForEach-Object { [string]$_ })
$excludePathRegex = [string]$profileConfig.exclude_path_regex

$candidatePaths = @(Invoke-GitNullPathList -Root $root -Pathspecs @($rootPatterns + $topFiles))

$paths = New-Object 'System.Collections.Generic.List[string]'
foreach ($raw in $candidatePaths) {
    $path = ([string]$raw).Replace('\', '/')
    if ($path -like '*.base@*') {
        continue
    }
    $excludedByPrefix = $false
    foreach ($prefix in $excludePrefixes) {
        if ($path.StartsWith($prefix, [StringComparison]::Ordinal)) {
            $excludedByPrefix = $true
            break
        }
    }
    if ($excludedByPrefix) {
        continue
    }
    if ($topFiles -contains $path) {
        $paths.Add($path)
        continue
    }
    foreach ($prefix in $rootPatterns) {
        if ($path.StartsWith($prefix, [StringComparison]::Ordinal)) {
            if (-not [string]::IsNullOrWhiteSpace($excludePathRegex) -and
                $path -match $excludePathRegex) {
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
$pathEncoding = [Text.UTF8Encoding]::new($false, $true)
$orderedMap = New-Object 'System.Collections.Generic.SortedDictionary[string,string]' `
    ([System.StringComparer]::Ordinal)
foreach ($path in $uniqueList) {
    $sortKey = ([BitConverter]::ToString($pathEncoding.GetBytes($path))).Replace('-', '')
    $orderedMap.Add($sortKey, $path)
}
$ordered = [string[]]@($orderedMap.Values)

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
        Assert-WorktreeFileOutput -RepoRoot $root -FilePath $target | Out-Null
        New-WorktreeDirectory -RepoRoot $root -DirectoryPath (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target
        $targetHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant()
        if ($targetHash -ne $hash -or (Get-Item -LiteralPath $target).Length -ne $item.Length) {
            throw "Manifest source copy mismatch: $relative"
        }
    }
}

$encoding = [Text.UTF8Encoding]::new($false)
$manifestPath = Assert-WorktreeFileOutput `
    -RepoRoot $root `
    -FilePath (Join-Path $output 'source-manifest.txt')
[IO.File]::WriteAllText($manifestPath, (($lines -join "`r`n") + "`r`n"), $encoding)
$manifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToUpperInvariant()
$recordArray = @($records.ToArray())
$orderingName = 'UTF-8 normalized slash paths, bytewise Ordinal ascending'

$schemaName = if ($Profile -eq 'Legacy') { 'p2-5-source-manifest-v1' } else { 'etrack-input-manifest-v2' }
$json = [ordered]@{
    Schema = $schemaName
}
if ($Profile -ne 'Legacy') {
    $json['Profile'] = $Profile
}
$json['Ordering'] = $orderingName
$json['Encoding'] = 'UTF-8 without BOM, CRLF, one trailing newline'
$json['FileCount'] = $records.Count
$json['ManifestSHA256'] = $manifestHash
$json['Files'] = $recordArray
$manifestJsonPath = Assert-WorktreeFileOutput `
    -RepoRoot $root `
    -FilePath (Join-Path $output 'source-manifest.json')
[IO.File]::WriteAllText($manifestJsonPath, (($json | ConvertTo-Json -Depth 6) + "`r`n"), $encoding)
$manifestJsonHash = (Get-FileHash -LiteralPath $manifestJsonPath -Algorithm SHA256).Hash.ToUpperInvariant()
$head = (& git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($head)) {
    throw "git rev-parse HEAD failed: $LASTEXITCODE"
}

$summary = [ordered]@{
    Result = 'PASS'
    Profile = $Profile
    RepoRoot = $root
    Head = $head
    FileCount = $records.Count
    ManifestSHA256 = $manifestHash
    ManifestPath = $manifestPath
    ManifestJsonSHA256 = $manifestJsonHash
    ManifestJsonPath = $manifestJsonPath
    CopyRoot = if ($CopySources) { $copyRoot } else { $null }
}
$summaryPath = Assert-WorktreeFileOutput `
    -RepoRoot $root `
    -FilePath (Join-Path $output 'summary.json')
[IO.File]::WriteAllText($summaryPath, (($summary | ConvertTo-Json -Depth 5) + "`r`n"), $encoding)
Write-Output (($summary | ConvertTo-Json -Compress -Depth 5))
