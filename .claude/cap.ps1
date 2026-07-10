Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int left,top,right,bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x,y; }
}
"@
$exe = "D:\github\my\AT32F435RGT7_SDIO\Simulator\Output\Debug\x64\LVGL.Simulator.exe"
$out = "D:\github\my\AT32F435RGT7_SDIO\.claude\sim_new.png"
# 启动前清理任何残留实例（防止 exe 被锁导致后续构建 LNK1104）
cmd /c "taskkill /F /IM LVGL.Simulator.exe /T" 2>$null | Out-Null
Start-Sleep -Milliseconds 300
$p = Start-Process -FilePath $exe -PassThru
Start-Sleep -Seconds 7
$p.Refresh()
$h = $p.MainWindowHandle
if ($h -eq 0) { Start-Sleep -Seconds 2; $p.Refresh(); $h = $p.MainWindowHandle }
[Win]::ShowWindow($h, 5) | Out-Null
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
$g.Dispose(); $bmp.Dispose()
# 可靠结束进程树（taskkill /T /F），避免 exe 残留锁定
cmd /c ("taskkill /F /T /PID {0}" -f $p.Id) 2>$null | Out-Null
Start-Sleep -Milliseconds 300
cmd /c "taskkill /F /IM LVGL.Simulator.exe /T" 2>$null | Out-Null
Write-Output ("client {0} x {1} hwnd {2}" -f $w, $hh, $h)
