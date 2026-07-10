<#
  build_f435.ps1 - AT32F435 (X-Track) firmware manual incremental build (AC5)

  Why: when uVision (UV4.exe) runs as a GUI single instance, "UV4 -b" is
  unreliable (may use the stale in-memory project and skip changed files).
  This script does not guess compiler flags. It reuses Keil-generated
  Objects\proj_X-Track.dep (per-file compile command) and Objects\X-Track.lnp
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
  [string[]] $Sources = @(),
  [string[]] $NewSources = @(),
  [string[]] $ExtraLinkObjs = @(),
  [switch]   $AutoStale,
  [switch]   $AutoFonts
)

$ErrorActionPreference = 'Stop'
$projectDir = 'D:\github\my\AT32F435RGT7_SDIO\MDK-ARM_F435'
$binDir     = 'D:\install\keil5 mdk\ARM\ARMCC\bin'
$armcc      = Join-Path $binDir 'armcc.exe'
$armasm     = Join-Path $binDir 'armasm.exe'
$armlink    = Join-Path $binDir 'armlink.exe'
$fromelf    = Join-Path $binDir 'fromelf.exe'
$dep        = Join-Path $projectDir 'Objects\proj_X-Track.dep'
$lnp        = Join-Path $projectDir 'Objects\X-Track.lnp'
$uvprojx    = Join-Path $projectDir 'proj.uvprojx'
$repoRoot   = Split-Path -Parent $projectDir

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
  return (Join-Path $projectDir ("Objects\{0}.o" -f $base))
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
  return (".\Objects\{0}.o" -f $base)
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

if (Test-Path -LiteralPath $uvprojx) {
  $projectText = Get-Content -LiteralPath $uvprojx -Raw
  $projectSources = @(
    [regex]::Matches($projectText, '<FilePath>(?<path>[^<]+\.(?:c|cpp|s))</FilePath>', 'IgnoreCase') |
      ForEach-Object { $_.Groups['path'].Value } |
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
    $obj = (".\Objects\font_{0}.o" -f $name)
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

# 3) Link (reuse all inputs/options from X-Track.lnp; append objs not in lnp)
Write-Host "[LINK] armlink --via X-Track.lnp" -ForegroundColor Cyan
Push-Location $projectDir
try {
  $linkArgs = @('--via', '.\Objects\X-Track.lnp') + $ExtraLinkObjs
  & $armlink @linkArgs
  if ($LASTEXITCODE -ne 0) { throw ("armlink failed: {0}" -f $LASTEXITCODE) }

  & $fromelf --i32combined --output '.\Objects\X-Track.hex' '.\Objects\X-Track.axf'
  if ($LASTEXITCODE -ne 0) { throw ("fromelf hex failed: {0}" -f $LASTEXITCODE) }

  & $fromelf --bin -o 'Track.bin' '.\Objects\X-Track.axf'
  if ($LASTEXITCODE -ne 0) { throw ("fromelf bin failed: {0}" -f $LASTEXITCODE) }
} finally { Pop-Location }

# 4) Report output timestamps
Write-Host "`n[OUTPUTS]" -ForegroundColor Green
Get-Item (Join-Path $projectDir 'Objects\X-Track.axf'),
         (Join-Path $projectDir 'Objects\X-Track.hex'),
         (Join-Path $projectDir 'Track.bin') |
  Select-Object Name, Length, @{N='LastWriteTime';E={$_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')}} |
  Format-Table -AutoSize
Write-Host "[OK] build complete (armlink/fromelf exit code 0)" -ForegroundColor Green
