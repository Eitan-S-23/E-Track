@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================
rem  One-click iconfont -> LVGL font converter
rem
rem  Default:
rem    - Pick the newest subfolder under this directory that contains
rem      iconfont.json and iconfont.ttf.
rem    - Generate ../../USER/App/Resource/Font/font_iconfont_20.c
rem    - Use size=20, bpp=4.
rem
rem  Usage:
rem    convert_iconfont.bat
rem    convert_iconfont.bat --no-pause
rem    convert_iconfont.bat "font_xxxxx"
rem    convert_iconfont.bat "font_xxxxx" "..\..\USER\App\Resource\Font\font_iconfont_24.c" 24 4
rem ============================================================

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "REPO_ROOT=%%~fI"

set "NO_PAUSE="
if /i "%~1"=="--no-pause" (
  set "NO_PAUSE=1"
  shift /1
)

set "ICON_DIR=%~1"
set "OUT_C=%~2"
set "SIZE=%~3"
set "BPP=%~4"

if not defined SIZE set "SIZE=20"
if not defined BPP set "BPP=4"
if not defined OUT_C set "OUT_C=%REPO_ROOT%\USER\App\Resource\Font\font_iconfont_%SIZE%.c"

if not defined ICON_DIR (
  for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$root = '%SCRIPT_DIR%';" ^
    "$dir = Get-ChildItem -LiteralPath $root -Directory | Where-Object { (Test-Path -LiteralPath (Join-Path $_.FullName 'iconfont.json')) -and (Test-Path -LiteralPath (Join-Path $_.FullName 'iconfont.ttf')) } | Sort-Object LastWriteTime -Descending | Select-Object -First 1;" ^
    "if ($dir) { $dir.FullName }"`) do set "ICON_DIR=%%I"
) else (
  if exist "%SCRIPT_DIR%%ICON_DIR%\" set "ICON_DIR=%SCRIPT_DIR%%ICON_DIR%"
)

if not defined ICON_DIR (
  echo [FAIL] No iconfont package found.
  echo        Put iconfont.json and iconfont.ttf under a subfolder of:
  echo        %SCRIPT_DIR%
  goto :fail
)

for %%I in ("%ICON_DIR%") do set "ICON_DIR=%%~fI"
set "ICON_JSON=%ICON_DIR%\iconfont.json"
set "ICON_TTF=%ICON_DIR%\iconfont.ttf"

if not exist "%ICON_JSON%" (
  echo [FAIL] Missing: %ICON_JSON%
  goto :fail
)
if not exist "%ICON_TTF%" (
  echo [FAIL] Missing: %ICON_TTF%
  goto :fail
)

for /f "usebackq delims=" %%R in (`powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$jsonPath = '%ICON_JSON%';" ^
  "$json = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json;" ^
  "$codes = @($json.glyphs | ForEach-Object { '0x' + ([string]$_.unicode).ToLowerInvariant() } | Sort-Object -Unique);" ^
  "if ($codes.Count -eq 0) { exit 2 }" ^
  "$codes -join ','"`) do set "RANGE=%%R"

if not defined RANGE (
  echo [FAIL] No glyph unicode range found in: %ICON_JSON%
  goto :fail
)

for %%I in ("%OUT_C%") do set "OUT_C=%%~fI"
for %%I in ("%OUT_C%") do if not exist "%%~dpI" mkdir "%%~dpI"

echo [iconfont] package : %ICON_DIR%
echo [iconfont] output  : %OUT_C%
echo [iconfont] size    : %SIZE%
echo [iconfont] bpp     : %BPP%
echo [iconfont] range   : %RANGE%
echo.

npx --yes lv_font_conv@1.5.3 --font "%ICON_TTF%" --size %SIZE% --bpp %BPP% --format lvgl --no-compress --no-kerning --range "%RANGE%" -o "%OUT_C%"
if errorlevel 1 goto :fail

echo.
echo [DONE] LVGL icon font generated.
echo        Symbol name is the output file name without extension.
echo        Example: font_iconfont_20.c defines font_iconfont_20.
echo.
if not defined NO_PAUSE pause
exit /b 0

:fail
echo.
echo [FAIL] Conversion failed.
echo.
if not defined NO_PAUSE pause
exit /b 1
