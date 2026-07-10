@echo off
REM ============================================================
REM  One-click LVGL CJK subset font generator (double-click to run)
REM  - Reads font_config.json in this folder
REM  - For an existing font, new chars are merged and de-duplicated
REM  CLI usage also works:  gen_font.bat --cstr "your text"
REM  (Chinese status text is printed by gen_font.py via UTF-8.)
REM ============================================================
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul || set "PY=py"

echo [gen_font] config = font_config.json
echo.
"%PY%" gen_font.py %*
set "ERR=%ERRORLEVEL%"

echo.
if "%ERR%"=="0" (
  echo [DONE] Success. Add the generated .c to the Keil project and rebuild.
) else (
  echo [FAIL] exit code %ERR% -- see messages above.
)
echo.
pause
