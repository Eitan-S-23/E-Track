@echo off
setlocal

rem One-click build for AT32F435 firmware and LVGL simulator.
rem Outputs stay in the existing project locations:
rem   Firmware BIN: MDK-ARM_F435\Track.bin
rem   Firmware AXF: MDK-ARM_F435\Objects\X-Track.axf
rem   Firmware HEX: MDK-ARM_F435\Objects\X-Track.hex
rem   Simulator EXE: Simulator\Output\Debug\x64\LVGL.Simulator.exe

set "ROOT=%~dp0"
set "F435_BUILD=%ROOT%MDK-ARM_F435\build_f435.ps1"
set "F435_LNP=%ROOT%MDK-ARM_F435\Objects\X-Track.lnp"
set "SIM_SLN=%ROOT%Simulator\LVGL.Simulator.sln"
set "MSBUILD=D:\vs2019\MSBuild\Current\Bin\MSBuild.exe"
set "NO_PAUSE=0"

if /I "%~1"=="--no-pause" set "NO_PAUSE=1"

echo [1/2] Building F435 firmware...
powershell -NoProfile -ExecutionPolicy Bypass -File "%F435_BUILD%" -AutoStale -AutoFonts
if errorlevel 1 (
    echo.
    echo [FAIL] F435 firmware build failed.
    goto :fail
)

echo.
echo [2/2] Building LVGL simulator...
"%MSBUILD%" "%SIM_SLN%" -p:Configuration=Debug -p:Platform=x64 -m -v:minimal -nologo
if errorlevel 1 (
    echo.
    echo [FAIL] LVGL simulator build failed.
    goto :fail
)

echo.
echo [OK] Build finished.
echo Firmware BIN: "%ROOT%MDK-ARM_F435\Track.bin"
echo Firmware HEX: "%ROOT%MDK-ARM_F435\Objects\X-Track.hex"
echo Firmware AXF: "%ROOT%MDK-ARM_F435\Objects\X-Track.axf"
echo Simulator EXE: "%ROOT%Simulator\Output\Debug\x64\LVGL.Simulator.exe"
echo.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:fail
echo.
echo See the error output above.
if "%NO_PAUSE%"=="0" pause
exit /b 1
