param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
. (Join-Path $root 'Tools\provenance\worktree_guard.ps1')
$root = Assert-ActiveWorktree $root
$exe = Assert-WorktreeOutput -RepoRoot $root -OutputPath (Join-Path $root 'Simulator\Output\Debug\x64\LVGL.Simulator.exe')
$out = Assert-WorktreeOutput -RepoRoot $root -OutputPath (Join-Path $root '.claude\sim_new.png')
$tempPath = Assert-WorktreeOutput -RepoRoot $root -OutputPath (Join-Path $root '.cache\simulator-capture')
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Build the simulator first: $exe" }
$exeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if ($CheckOnly) {
  Write-Output "EXE=$exe SHA256=$exeHash OUTPUT=$out"
  exit 0
}
$savedTemp = @($env:TEMP, $env:TMP, $env:TMPDIR)
$tempPath = New-WorktreeDirectory -RepoRoot $root -DirectoryPath $tempPath
$env:TEMP = $tempPath
$env:TMP = $tempPath
$env:TMPDIR = $tempPath
$p = $null
$bmp = $null
$g = $null
try {
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left,top,right,bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x,y; }
}
"@
# Stop only instances from this worktree, never another project's simulator.
Get-Process -Name LVGL.Simulator -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -eq $exe } | Stop-Process -Force
Start-Sleep -Milliseconds 300
$p = Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 7
$p.Refresh()
$h = $p.MainWindowHandle
if ($h -eq 0) { Start-Sleep -Seconds 2; $p.Refresh(); $h = $p.MainWindowHandle }
if ($p.HasExited -or $h -eq 0 -or -not $p.Responding -or [Win]::IsHungAppWindow($h)) {
  throw 'Simulator did not become responsive within the capture timeout.'
}
[Win]::ShowWindowAsync($h, 5) | Out-Null
[Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 600
$r = New-Object Win+RECT
[Win]::GetClientRect($h, [ref]$r) | Out-Null
$tl = New-Object Win+POINT; $tl.x = 0; $tl.y = 0
[Win]::ClientToScreen($h, [ref]$tl) | Out-Null
$w = $r.right - $r.left; $hh = $r.bottom - $r.top
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($tl.x, $tl.y, 0, 0, (New-Object System.Drawing.Size($w, $hh)))
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output ("client {0} x {1} hwnd {2} EXE_SHA256={3} OUTPUT={4}" -f $w, $hh, $h, $exeHash, $out)
} finally {
  if ($g) { $g.Dispose() }
  if ($bmp) { $bmp.Dispose() }
  if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  $env:TEMP = $savedTemp[0]
  $env:TMP = $savedTemp[1]
  $env:TMPDIR = $savedTemp[2]
}
