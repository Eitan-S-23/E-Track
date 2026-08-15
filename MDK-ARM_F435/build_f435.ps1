<#
  build_f435.ps1 - AT32F435 firmware manual incremental build (AC5)

  Why: when uVision (UV4.exe) runs as a GUI single instance, "UV4 -b" is
  unreliable (may use the stale in-memory project and skip changed files).
  This script does not guess compiler flags. It reuses Keil-generated
  the target-specific Objects* dep file (per-file compile command) and lnp file
  (link inputs + options): recompile each source -> armlink -> fromelf hex/bin.
  See repo AGENTS.md for the rationale and the rules agents must follow.

  NOTE: keep this script ASCII-only. Windows PowerShell 5.1 reads .ps1 as the
  system ANSI codepage (GBK on zh-CN) unless a BOM is present, so non-ASCII
  comments/strings corrupt the tokenizer. Chinese how-to lives in the doc
  (see docs/BUILD_F435_FIRMWARE.md).

  Usage (from anywhere):
    powershell -NoProfile -ExecutionPolicy Bypass -File MDK-ARM_F435\build_f435.ps1 `
      -Sources '..\USER\App\Pages\Dialplate\DialplateView.cpp','..\USER\App\Pages\Dialplate\Dialplate.cpp'

  Params:
    -Target        Keil target name. Defaults to X-Track-App-AC5.
    -Sources       Sources to recompile that already exist in the dep file
                   (use the EXACT path string from the dep; note its casing).
    -NewSources    Files not yet in the dep: each item is 'src|template'.
                   Borrow template's dep command and replace template's base
                   name with src's base name (for files newly added to the
                   project that the GUI has not regenerated a dep entry for).
    -ExtraLinkObjs Extra .o objects NOT listed in X-Track.lnp (new files),
                   appended to the armlink command line.
    -AutoStale     If -Sources is empty, scan every source in the dep and pick
                   the ones whose file is newer than their own .o.
    -AutoFonts     Scan ResourcePool.cpp IMPORT_FONT(name) entries, then append
                   missing font_name.o link inputs and compile font_name.c when
                   the source is not yet in the Keil dep file.
    -BootstrapIfNeeded
                   Run one blocking UV4 build when dep/lnp metadata is missing,
                   empty, or the normalized proj.uvprojx content changed.
                   Legacy metadata uses mtime once. Fails if UV4 is running.
    -UV4Path       uVision executable used only for metadata bootstrap.
    -BootstrapTimeoutSeconds
                   Maximum time to wait for the bootstrap UV4 process.
    The script also scans proj.uvprojx for newly added project sources that are
    not yet present in the Keil-generated dep/lnp files, compiles them from a
    same-extension template, and appends their object files for this link.

  Rules:
    - Never edit .sct / .lnp / project CPU/macros/include paths (reuse Keil
      config, including RAMCODE-into-RAM scatter setup).
    - Decide staleness by comparing a source/header against its OWN .o, never
      against X-Track.axf (relink refreshes axf and hides stale objects).
    - Abort on any non-zero exit code; print Program Size and output timestamps.
#>
param(
  [string]   $Target = 'X-Track-App-AC5',
  [string[]] $Sources = @(),
  [string[]] $NewSources = @(),
  [string[]] $ExtraLinkObjs = @(),
  [switch]   $AutoStale,
  [switch]   $AutoFonts,
  [switch]   $BootstrapIfNeeded,
  [string]   $UV4Path = 'D:\install\keil5 mdk\UV4\UV4.exe',
  [ValidateRange(30, 3600)]
  [int]      $BootstrapTimeoutSeconds = 900
)

$ErrorActionPreference = 'Stop'
# Self-locate the MDK-ARM_F435 dir this script lives in, so each repo clone
# builds its OWN tree. The old hard-coded D:\github\my\AT32F435RGT7_SDIO path
# forced a cross-repo file sync that silently clobbered divergent work.
# $PSScriptRoot is empty under -Command "& 'script'"; fall back to the
# invocation path, then to the current dir, before giving up.
$scriptDir =
  if ($PSScriptRoot) { $PSScriptRoot }
  elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path }
  else { (Get-Location).Path }
$projectDir = $scriptDir
$binDir     = 'D:\install\keil5 mdk\ARM\ARMCC\bin'
$armcc      = Join-Path $binDir 'armcc.exe'
$armasm     = Join-Path $binDir 'armasm.exe'
$armlink    = Join-Path $binDir 'armlink.exe'
$fromelf    = Join-Path $binDir 'fromelf.exe'
$uv4        = $UV4Path
$uvprojx    = Join-Path $projectDir 'proj.uvprojx'
$repoRoot   = Split-Path -Parent $projectDir

function Convert-ProjectPath([string]$path) {
  $result = $path.Trim().Replace('/', '\')
  while ($result.StartsWith('.\')) { $result = $result.Substring(2) }
  return $result.TrimEnd('\')
}

if (-not (Test-Path -LiteralPath $uvprojx)) { throw ("project not found: {0}" -f $uvprojx) }
$projectXml = [xml](Get-Content -LiteralPath $uvprojx -Raw)
$targetNodes = @($projectXml.Project.Targets.Target | Where-Object { $_.TargetName -eq $Target })
if ($targetNodes.Count -ne 1) { throw ("Keil target not found or duplicated: {0}" -f $Target) }
$targetNode = $targetNodes[0]
$targetCommon = $targetNode.TargetOption.TargetCommonOption
$objectDirRel = Convert-ProjectPath $targetCommon.OutputDirectory
$listingDirRel = Convert-ProjectPath $targetCommon.ListingPath
$outputName = [string]$targetCommon.OutputName
if (-not $objectDirRel -or -not $listingDirRel -or -not $outputName) {
  throw ("target paths/output name incomplete: {0}" -f $Target)
}

$depRel = Join-Path $objectDirRel ("proj_{0}.dep" -f $Target)
$lnpRel = Join-Path $objectDirRel ("{0}.lnp" -f $outputName)
$axfRel = Join-Path $objectDirRel ("{0}.axf" -f $outputName)
$hexRel = Join-Path $objectDirRel ("{0}.hex" -f $outputName)
$mapRel = Join-Path $listingDirRel ("{0}.map" -f $outputName)
$afterMake = [string]$targetCommon.AfterMake.UserProg1Name
$binMatch = [regex]::Match($afterMake, '--bin\s+-o\s+"(?<path>[^"]+)"')
if (-not $binMatch.Success) { throw ("target bin output not found in AfterMake: {0}" -f $Target) }
$binRel = Convert-ProjectPath $binMatch.Groups['path'].Value

$dep = Join-Path $projectDir $depRel
$lnp = Join-Path $projectDir $lnpRel
$axf = Join-Path $projectDir $axfRel
$hex = Join-Path $projectDir $hexRel
$map = Join-Path $projectDir $mapRel
$bin = Join-Path $projectDir $binRel
$metadataProjectHash = Join-Path $projectDir (Join-Path $objectDirRel ("proj_{0}.uvprojx.sha256" -f $Target))
$lnpArg = '.\' + $lnpRel
$axfArg = '.\' + $axfRel
$hexArg = '.\' + $hexRel

function Get-ProjectFileHash {
  $text = [IO.File]::ReadAllText($uvprojx)
  $normalized = $text.Replace("`r`n", "`n").Replace("`r", "`n")
  $bytes = [Text.Encoding]::UTF8.GetBytes($normalized)
  $sha256 = [Security.Cryptography.SHA256]::Create()
  try {
    $digest = $sha256.ComputeHash($bytes)
    return ([BitConverter]::ToString($digest)).Replace('-', '')
  } finally {
    $sha256.Dispose()
  }
}

function Update-KeilMetadataProjectHash {
  $currentHash = Get-ProjectFileHash
  $recordedHash = ''
  if (Test-Path -LiteralPath $metadataProjectHash -PathType Leaf) {
    $recordedHash = (Get-Content -LiteralPath $metadataProjectHash -Raw).Trim().ToUpperInvariant()
  }
  if ($recordedHash -ne $currentHash) {
    Set-Content -LiteralPath $metadataProjectHash -Value $currentHash -Encoding Ascii -NoNewline
  }
}

function Normalize-UVisionGeneratedWhitespace {
  $rteComponents = Join-Path $projectDir ("RTE\_{0}\RTE_Components.h" -f $Target)
  if (-not (Test-Path -LiteralPath $rteComponents -PathType Leaf)) { return }
  $text = [IO.File]::ReadAllText($rteComponents)
  $normalized = [regex]::Replace(
    $text,
    '[ \t]+(?=\r?$)',
    '',
    [Text.RegularExpressions.RegexOptions]::Multiline
  )
  if ($normalized -ne $text) {
    [IO.File]::WriteAllText($rteComponents, $normalized, [Text.Encoding]::ASCII)
  }
}

function Get-KeilMetadataProblems([switch]$IgnoreProjectHash) {
  $problems = New-Object System.Collections.Generic.List[string]
  $projectTime = (Get-Item -LiteralPath $uvprojx).LastWriteTimeUtc
  $metadataReady = $true
  foreach ($required in @($dep, $lnp)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
      $problems.Add(("missing: {0}" -f $required))
      $metadataReady = $false
      continue
    }
    $item = Get-Item -LiteralPath $required
    if ($item.Length -le 0) {
      $problems.Add(("empty: {0}" -f $required))
      $metadataReady = $false
    }
  }

  if ($metadataReady) {
    if (-not $IgnoreProjectHash -and (Test-Path -LiteralPath $metadataProjectHash -PathType Leaf)) {
      $recordedHash = (Get-Content -LiteralPath $metadataProjectHash -Raw).Trim().ToUpperInvariant()
      if ($recordedHash -notmatch '^[0-9A-F]{64}$') {
        $problems.Add(("invalid project hash stamp: {0}" -f $metadataProjectHash))
      } elseif ($recordedHash -ne (Get-ProjectFileHash)) {
        $problems.Add(("proj.uvprojx content hash changed: {0}" -f $uvprojx))
      }
    } else {
      foreach ($required in @($dep, $lnp)) {
        if ((Get-Item -LiteralPath $required).LastWriteTimeUtc -lt $projectTime) {
          $problems.Add(("older than proj.uvprojx: {0}" -f $required))
        }
      }
    }
  }
  return @($problems.ToArray())
}

function Invoke-KeilMetadataBootstrap {
  if (-not (Test-Path -LiteralPath $uv4 -PathType Leaf)) {
    throw ("UV4 executable not found: {0}" -f $uv4)
  }

  $uv4ProcessName = [IO.Path]::GetFileNameWithoutExtension($uv4)
  $running = @(Get-Process -Name $uv4ProcessName -ErrorAction SilentlyContinue)
  if ($running.Count -gt 0) {
    throw ("UV4 is already running ({0} process(es)). Close uVision and rerun to avoid single-instance asynchronous builds." -f $running.Count)
  }

  $objectDir = Join-Path $projectDir $objectDirRel
  $listingDir = Join-Path $projectDir $listingDirRel
  [IO.Directory]::CreateDirectory($objectDir) | Out-Null
  [IO.Directory]::CreateDirectory($listingDir) | Out-Null
  $bootstrapLog = Join-Path $objectDir 'uv4-bootstrap.log'
  if (Test-Path -LiteralPath $bootstrapLog) {
    Remove-Item -LiteralPath $bootstrapLog -Force
  }

  Write-Host ("[BOOTSTRAP] UV4 -b {0} -t {1}" -f $uvprojx, $Target) -ForegroundColor Yellow
  $argumentLine = '-b "{0}" -t "{1}" -o "{2}"' -f $uvprojx, $Target, $bootstrapLog
  $process = Start-Process -FilePath $uv4 -ArgumentList $argumentLine `
    -WorkingDirectory $projectDir -WindowStyle Hidden -PassThru
  Write-Host ("[BOOTSTRAP] waiting for UV4 pid {0} (timeout {1}s)" -f $process.Id, $BootstrapTimeoutSeconds) -ForegroundColor Yellow
  try {
    $timeoutMs = [int]($BootstrapTimeoutSeconds * 1000)
    if (-not $process.WaitForExit($timeoutMs)) {
      $taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
      & $taskkill /PID $process.Id /T /F | Out-Host
      throw ("UV4 bootstrap timed out after {0}s; terminated process tree {1}. See partial log: {2}" -f $BootstrapTimeoutSeconds, $process.Id, $bootstrapLog)
    }
    $process.WaitForExit()
    $uv4Exit = $process.ExitCode
  } finally {
    $process.Dispose()
  }
  Normalize-UVisionGeneratedWhitespace

  if (-not (Test-Path -LiteralPath $bootstrapLog -PathType Leaf)) {
    throw ("UV4 bootstrap did not create its log (exit {0}): {1}" -f $uv4Exit, $bootstrapLog)
  }
  $bootstrapText = Get-Content -LiteralPath $bootstrapLog -Raw
  $summaries = [regex]::Matches(
    $bootstrapText,
    '(?im)(?<errors>\d+)\s+Error\(s\),\s+(?<warnings>\d+)\s+Warning\(s\)'
  )
  if ($summaries.Count -eq 0) {
    throw ("UV4 bootstrap log has no build summary (exit {0}): {1}" -f $uv4Exit, $bootstrapLog)
  }
  $summary = $summaries[$summaries.Count - 1]
  $errorCount = [int]$summary.Groups['errors'].Value
  $warningCount = [int]$summary.Groups['warnings'].Value
  if ($errorCount -ne 0) {
    throw ("UV4 bootstrap failed: {0} error(s), {1} warning(s), exit {2}. See {3}" -f $errorCount, $warningCount, $uv4Exit, $bootstrapLog)
  }
  if ($uv4Exit -ne 0 -and -not ($uv4Exit -eq 1 -and $warningCount -gt 0)) {
    throw ("UV4 bootstrap returned unexpected exit {0} with zero reported errors. See {1}" -f $uv4Exit, $bootstrapLog)
  }

  $remaining = @(Get-KeilMetadataProblems -IgnoreProjectHash)
  if ($remaining.Count -gt 0) {
    throw ("UV4 bootstrap left invalid metadata: {0}" -f ($remaining -join '; '))
  }
  Update-KeilMetadataProjectHash
  Write-Host ("[BOOTSTRAP] metadata ready: 0 error(s), {0} warning(s)" -f $warningCount) -ForegroundColor Green
}

$metadataProblems = @(Get-KeilMetadataProblems)
if ($metadataProblems.Count -gt 0) {
  if (-not $BootstrapIfNeeded) {
    throw ("Keil generated metadata is unavailable or stale for target {0}: {1}. Rerun with -BootstrapIfNeeded." -f $Target, ($metadataProblems -join '; '))
  }
  Invoke-KeilMetadataBootstrap
}

foreach ($required in @($dep, $lnp)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf) -or (Get-Item -LiteralPath $required).Length -le 0) {
    throw ("Keil generated metadata is invalid after bootstrap check: {0}" -f $required)
  }
}
Update-KeilMetadataProjectHash

function Split-KeilArgs([string]$s) {
  $tokens = New-Object System.Collections.Generic.List[string]
  $sb = [System.Text.StringBuilder]::new()
  $inQuote = $false
  for ($i = 0; $i -lt $s.Length; $i++) {
    $ch = $s[$i]
    if ($ch -eq '"') { $inQuote = -not $inQuote; continue }
    if ([char]::IsWhiteSpace($ch) -and -not $inQuote) {
      if ($sb.Length -gt 0) { $tokens.Add($sb.ToString()); [void]$sb.Clear() }
      continue
    }
    [void]$sb.Append($ch)
  }
  if ($sb.Length -gt 0) { $tokens.Add($sb.ToString()) }
  $tokens.ToArray()
}

$depText = Get-Content -LiteralPath $dep -Raw
$lnpText = Get-Content -LiteralPath $lnp -Raw

function Get-DepCmd([string]$src) {
  $m = [regex]::Matches($depText, '(?ms)^F \((?<src>[^)]*)\)\([^)]*\)\((?<cmd>.*?)\)\r?$', 'Multiline') |
    Where-Object { $_.Groups['src'].Value -eq $src } | Select-Object -First 1
  if (-not $m) { return $null }
  return ($m.Groups['cmd'].Value -replace '\r?\n', ' ').Trim()
}

function Get-ObjPath([string]$src) {
  $base = [IO.Path]::GetFileNameWithoutExtension($src).ToLowerInvariant()
  return (Join-Path (Join-Path $projectDir $objectDirRel) ("{0}.o" -f $base))
}

function Compile-One([string]$src, [string]$cmd) {
  $argList = @(@(Split-KeilArgs $cmd) + @($src))
  $tool = if ([IO.Path]::GetExtension($src).ToLowerInvariant() -eq '.s') { $armasm } else { $armcc }
  Write-Host ("[CC] {0}" -f $src) -ForegroundColor Cyan
  Push-Location $projectDir
  try {
    & $tool @argList
    if ($LASTEXITCODE -ne 0) { throw ("compile failed ({0}): {1}" -f $LASTEXITCODE, $src) }
  } finally { Pop-Location }
}

function Add-Unique([string[]]$items, [string]$item) {
  if ($items -notcontains $item) { return @($items + $item) }
  return $items
}

function Get-NewSourceObject([string]$src) {
  $base = [IO.Path]::GetFileNameWithoutExtension($src)
  return ('.\' + (Join-Path $objectDirRel ("{0}.o" -f $base)))
}

function Get-ProjectSourceTemplate([string]$src) {
  $ext = [IO.Path]::GetExtension($src).ToLowerInvariant()
  $preferred = @()
  if ($ext -eq '.cpp') {
    $preferred = @(
      '..\USER\App\Utils\lv_poly_line\lv_poly_line.cpp',
      '..\USER\App\Pages\Menu\MainMenu.cpp',
      '..\USER\App\Pages\LiveMap\LiveMap.cpp'
    )
  } elseif ($ext -eq '.c') {
    $preferred = @(
      '..\USER\App\Resource\Font\font_cn_16.c',
      '..\USER\App\Common\DataProc\DP_Clock.cpp'
    )
  } elseif ($ext -eq '.s') {
    $preferred = @()
  }

  foreach ($candidate in $preferred) {
    if (Get-DepCmd $candidate) { return $candidate }
  }

  $matchExt = [regex]::Escape($ext)
  foreach ($m in [regex]::Matches($depText, '(?ms)^F \((?<src>[^)]*\.' + $matchExt.TrimStart('\') + ')\)\([^)]*\)\((?<cmd>.*?)\)\r?$', 'Multiline')) {
    $candidate = $m.Groups['src'].Value
    if ($candidate -ne $src -and (Get-DepCmd $candidate)) { return $candidate }
  }
  return $null
}

function Find-FontTemplate([string]$src) {
  $fontDir = Split-Path -Parent $src
  $absFontDir = [IO.Path]::GetFullPath((Join-Path $projectDir $fontDir))
  $base = [IO.Path]::GetFileNameWithoutExtension($src)
  $family = $base -replace '_\d+$', ''
  $candidates = New-Object System.Collections.ArrayList

  Get-ChildItem -LiteralPath $absFontDir -Filter '*.c' -File |
    Sort-Object Name |
    ForEach-Object {
      $rel = ('..\USER\App\Resource\Font\' + $_.Name)
      $relBase = [IO.Path]::GetFileNameWithoutExtension($rel)
      if ($rel -ne $src -and $relBase.StartsWith($family)) { [void]$candidates.Add($rel) }
    }

  Get-ChildItem -LiteralPath $absFontDir -Filter '*.c' -File |
    Sort-Object Name |
    ForEach-Object {
      $rel = ('..\USER\App\Resource\Font\' + $_.Name)
      if ($rel -ne $src) { [void]$candidates.Add($rel) }
    }

  foreach ($candidate in $candidates) {
    if (Get-DepCmd $candidate) { return $candidate }
  }
  return $null
}

if ($targetNode) {
  $projectSources = @(
    $targetNode.SelectNodes('./Groups/Group/Files/File/FilePath') |
      ForEach-Object { $_.InnerText } |
      Where-Object { $_ -match '\.(?:c|cpp|s)$' } |
      Where-Object { $_ -notmatch '\\lvgl\\(demos|examples|tests)\\' } |
      Sort-Object -Unique
  )

  $addedProjectCompile = 0
  $addedProjectLink = 0
  foreach ($src in $projectSources) {
    if (Get-DepCmd $src) { continue }

    $template = Get-ProjectSourceTemplate $src
    if (-not $template) { throw ("no dep template found for project source: {0}" -f $src) }
    $NewSources = Add-Unique $NewSources ("{0}|{1}" -f $src, $template)
    $addedProjectCompile++

    $obj = Get-NewSourceObject $src
    $objName = [IO.Path]::GetFileName($obj)
    if ($lnpText -inotmatch [regex]::Escape($objName)) {
      $ExtraLinkObjs = Add-Unique $ExtraLinkObjs $obj
      $addedProjectLink++
    }
  }

  if ($addedProjectCompile -gt 0 -or $addedProjectLink -gt 0) {
    Write-Host ("[AutoProject] compile additions: {0}, link additions: {1}" -f $addedProjectCompile, $addedProjectLink) -ForegroundColor Yellow
  }
}

if ($AutoStale -and $Sources.Count -eq 0) {
  # Parse dep: a compiled source (F line with a real cmd) is followed by I (header) lines
  # listing the headers it includes. Track source -> headers so that editing a header
  # (e.g. a macro in a .h) also marks the dependent .o stale (not only when the .cpp changes).
  $srcHdrs = @{}
  $order   = New-Object System.Collections.ArrayList
  $curSrc  = $null
  foreach ($rawLine in ($depText -split "`n")) {
    $line = $rawLine.TrimEnd("`r")
    if ($line -match '^F \((?<p>[^)]*)\)\([^)]*\)\((?<c>.*)\)$') {
      $p = $matches['p']; $c = $matches['c']
      if ($c.Trim().Length -gt 0 -and $p -match '\.(c|cpp|s)$' -and $p -notmatch '\\lvgl\\(demos|examples|tests)\\') {
        $curSrc = $p
        if (-not $srcHdrs.ContainsKey($p)) { $srcHdrs[$p] = (New-Object System.Collections.ArrayList); [void]$order.Add($p) }
      } else {
        $curSrc = $null
      }
    } elseif ($curSrc -ne $null -and $line -match '^I \((?<p>[^)]*)\)') {
      [void]$srcHdrs[$curSrc].Add($matches['p'])
    }
  }

  $mtime = @{}   # full path -> LastWriteTime cache (a header is shared by many sources)
  foreach ($s in $order) {
    if (-not (Get-DepCmd $s)) { continue }
    $obj = Get-ObjPath $s
    if (-not (Test-Path $obj)) { $Sources += $s; continue }
    $objT  = (Get-Item $obj).LastWriteTime
    $stale = $false
    foreach ($f in (@($s) + @($srcHdrs[$s]))) {
      if ([IO.Path]::IsPathRooted($f)) { $abs = [IO.Path]::GetFullPath($f) }
      else { $abs = [IO.Path]::GetFullPath((Join-Path $projectDir $f)) }
      if (-not $mtime.ContainsKey($abs)) {
        if (Test-Path -LiteralPath $abs) { $mtime[$abs] = (Get-Item -LiteralPath $abs).LastWriteTime } else { $mtime[$abs] = [datetime]::MinValue }
      }
      if ($mtime[$abs] -gt $objT) { $stale = $true; break }
    }
    if ($stale) { $Sources += $s }
  }
  Write-Host ("[AutoStale] stale sources (incl header deps): {0}" -f $Sources.Count) -ForegroundColor Yellow
}

if ($AutoFonts) {
  $resourcePool = Join-Path $repoRoot 'USER\App\Resource\ResourcePool.cpp'
  if (-not (Test-Path -LiteralPath $resourcePool)) { throw ("ResourcePool.cpp not found: {0}" -f $resourcePool) }

  $fontNames = @(
    [regex]::Matches((Get-Content -LiteralPath $resourcePool -Raw), 'IMPORT_FONT\(\s*(?<name>[A-Za-z0-9_]+)\s*\)') |
      ForEach-Object { $_.Groups['name'].Value } |
      Where-Object { $_ -ne 'name' } |
      Sort-Object -Unique
  )

  $addedLink = 0
  $addedCompile = 0
  foreach ($name in $fontNames) {
    $src = ("..\USER\App\Resource\Font\font_{0}.c" -f $name)
    $obj = Get-NewSourceObject $src
    $absSrc = [IO.Path]::GetFullPath((Join-Path $projectDir $src))
    if (-not (Test-Path -LiteralPath $absSrc)) { throw ("imported font source not found: {0}" -f $src) }

    if ($lnpText -inotmatch [regex]::Escape(("font_{0}.o" -f $name))) {
      $ExtraLinkObjs = Add-Unique $ExtraLinkObjs $obj
      $addedLink++
      Write-Host ("[AutoFonts] add link object: {0}" -f $obj) -ForegroundColor Yellow
    }

    if (-not (Get-DepCmd $src)) {
      $template = Find-FontTemplate $src
      if (-not $template) { throw ("no dep template found for font source: {0}" -f $src) }
      $NewSources = Add-Unique $NewSources ("{0}|{1}" -f $src, $template)
      $addedCompile++
      Write-Host ("[AutoFonts] add compile source: {0} (template {1})" -f $src, $template) -ForegroundColor Yellow
    }
  }

  Write-Host ("[AutoFonts] imported fonts: {0}, link additions: {1}, compile additions: {2}" -f $fontNames.Count, $addedLink, $addedCompile) -ForegroundColor Yellow
}

# 1) Recompile sources already present in the dep
foreach ($s in $Sources) {
  $cmd = Get-DepCmd $s
  if (-not $cmd) { throw ("source not in dep: {0} (use -NewSources for new files)" -f $s) }
  Compile-One $s $cmd
}

# 2) New files: borrow template command, replace base name
foreach ($pair in $NewSources) {
  $parts = $pair -split '\|', 2
  if ($parts.Count -ne 2) { throw ("NewSources must be 'src|template': {0}" -f $pair) }
  $src = $parts[0]; $tpl = $parts[1]
  $cmd = Get-DepCmd $tpl
  if (-not $cmd) { throw ("template not in dep: {0}" -f $tpl) }
  $tplBase = [IO.Path]::GetFileNameWithoutExtension($tpl)
  $srcBase = [IO.Path]::GetFileNameWithoutExtension($src)
  $cmd = $cmd.Replace($tplBase, $srcBase)
  Compile-One $src $cmd
}

# 3) Link (reuse all inputs/options from the selected target lnp)
Write-Host ("[LINK] armlink --via {0}" -f $lnpRel) -ForegroundColor Cyan
Push-Location $projectDir
try {
  $linkArgs = @('--via', $lnpArg) + $ExtraLinkObjs
  & $armlink @linkArgs
  if ($LASTEXITCODE -ne 0) { throw ("armlink failed: {0}" -f $LASTEXITCODE) }

  & $fromelf --i32combined --output $hexArg $axfArg
  if ($LASTEXITCODE -ne 0) { throw ("fromelf hex failed: {0}" -f $LASTEXITCODE) }

  & $fromelf --bin -o $binRel $axfArg
  if ($LASTEXITCODE -ne 0) { throw ("fromelf bin failed: {0}" -f $LASTEXITCODE) }
} finally { Pop-Location }

# 4) Report output timestamps
Write-Host "`n[OUTPUTS]" -ForegroundColor Green
Get-Item $axf, $hex, $bin, $map |
  Select-Object Name, Length, @{N='LastWriteTime';E={$_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')}} |
  Format-Table -AutoSize
Write-Host ("[OK] target {0} build complete (armlink/fromelf exit code 0)" -f $Target) -ForegroundColor Green
