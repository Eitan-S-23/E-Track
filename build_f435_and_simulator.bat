@echo off
setlocal EnableExtensions

rem One-click production build for AT32F435 firmware and LVGL simulator.
rem Default: GCC OTA App + GCC Boot + simulator.
rem Optional: --with-ac5 adds the AC5 App build; --ac5-only builds only AC5.
rem --legacy selects the old-layout AC5 target and requires an AC5 mode.

set "ROOT=%~dp0"
set "F435_BUILD=%ROOT%MDK-ARM_F435\build_f435.ps1"
set "CMAKE_SOURCE=%ROOT%MDK-ARM_F435\cmake-generated"
set "GCC_BUILD=%CMAKE_SOURCE%\build-gcc-release"
set "SIM_SLN=%ROOT%Simulator\LVGL.Simulator.sln"
set "MSBUILD=D:\vs2019\MSBuild\Current\Bin\MSBuild.exe"
set "AC5_TARGET=X-Track-App-AC5"
set "BUILD_AC5=0"
set "AC5_ONLY=0"
set "NO_PAUSE=0"

rem Keep compiler, CMake, cache, and MSBuild temporary writes inside the repo.
set "TEMP=%ROOT%.cache\build-temp"
set "TMP=%TEMP%"
set "TMPDIR=%TEMP%"
set "XDG_CACHE_HOME=%ROOT%.cache"
set "SCCACHE_DIR=%ROOT%.cache\sccache"
set "CCACHE_DIR=%ROOT%.cache\ccache"
set "SOURCE_DATE_EPOCH=1786320000"

:parse_args
if "%~1"=="" goto :args_done
if /I "%~1"=="--no-pause" (
    set "NO_PAUSE=1"
    shift
    goto :parse_args
)
if /I "%~1"=="--with-ac5" (
    set "BUILD_AC5=1"
    shift
    goto :parse_args
)
if /I "%~1"=="--ac5-only" (
    set "BUILD_AC5=1"
    set "AC5_ONLY=1"
    shift
    goto :parse_args
)
if /I "%~1"=="--legacy" (
    set "AC5_TARGET=X-Track"
    shift
    goto :parse_args
)
echo [FAIL] Unknown argument: %~1
goto :fail

:args_done
if /I not "%AC5_TARGET%"=="X-Track" goto :mode_valid
if "%BUILD_AC5%"=="1" goto :mode_valid
echo [FAIL] --legacy requires --with-ac5 or --ac5-only.
goto :fail

:mode_valid

for %%D in ("%TEMP%" "%SCCACHE_DIR%" "%CCACHE_DIR%") do (
    if not exist "%%~D" (
        mkdir "%%~D"
        if errorlevel 1 (
            echo [FAIL] Could not create project-local build directory: "%%~D"
            goto :fail
        )
    )
)

if "%AC5_ONLY%"=="1" (
    call :build_ac5
    if errorlevel 1 goto :fail
    goto :success
)

call :build_gcc
if errorlevel 1 goto :fail

if "%BUILD_AC5%"=="1" (
    call :build_ac5
    if errorlevel 1 goto :fail
)

call :build_simulator
if errorlevel 1 goto :fail

:success
echo.
echo [OK] Build finished.
echo.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:build_gcc
where cmake.exe >nul 2>nul
if errorlevel 1 (
    echo [FAIL] cmake.exe was not found on PATH.
    exit /b 1
)

echo [GCC] Configuring Release build...
cmake.exe -S "%CMAKE_SOURCE%" -B "%GCC_BUILD%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024
if errorlevel 1 (
    echo [FAIL] GCC CMake configure failed.
    exit /b 1
)

echo.
echo [GCC] Building OTA App and Boot targets...
cmake.exe --build "%GCC_BUILD%" --target X_Track_App_GCC X_Track_Boot --parallel
if errorlevel 1 (
    echo [FAIL] GCC firmware build failed.
    exit /b 1
)

set "GCC_APP_ELF=%GCC_BUILD%\app-gcc\X-Track-App-GCC.elf"
set "GCC_APP_HEX=%GCC_BUILD%\app-gcc\X-Track-App-GCC.hex"
set "GCC_APP_BIN=%GCC_BUILD%\app-gcc\X-Track-App-GCC.bin"
set "GCC_APP_MAP=%GCC_BUILD%\app-gcc\X-Track-App-GCC.map"
set "GCC_BOOT_ELF=%GCC_BUILD%\boot\X-Track-Boot.elf"
set "GCC_BOOT_HEX=%GCC_BUILD%\boot\X-Track-Boot.hex"
set "GCC_BOOT_BIN=%GCC_BUILD%\boot\X-Track-Boot.bin"
set "GCC_BOOT_MAP=%GCC_BUILD%\boot\X-Track-Boot.map"
for %%F in ("%GCC_APP_ELF%" "%GCC_APP_HEX%" "%GCC_APP_BIN%" "%GCC_APP_MAP%" "%GCC_BOOT_ELF%" "%GCC_BOOT_HEX%" "%GCC_BOOT_BIN%" "%GCC_BOOT_MAP%") do (
    if not exist "%%~F" (
        echo [FAIL] GCC build did not produce: "%%~F"
        exit /b 1
    )
)

echo [OK] GCC OTA App: "%GCC_APP_BIN%"
echo [OK] GCC Boot: "%GCC_BOOT_BIN%"
exit /b 0

:build_ac5
echo.
echo [AC5] Building auxiliary target %AC5_TARGET%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%F435_BUILD%" -Target "%AC5_TARGET%" -BootstrapIfNeeded -AutoStale -AutoFonts
if errorlevel 1 (
    echo [FAIL] AC5 firmware build failed.
    exit /b 1
)

if /I "%AC5_TARGET%"=="X-Track" (
    set "AC5_BIN=%ROOT%MDK-ARM_F435\Track.bin"
    set "AC5_HEX=%ROOT%MDK-ARM_F435\Objects\X-Track.hex"
    set "AC5_AXF=%ROOT%MDK-ARM_F435\Objects\X-Track.axf"
) else (
    set "AC5_BIN=%ROOT%MDK-ARM_F435\Track-App-AC5.bin"
    set "AC5_HEX=%ROOT%MDK-ARM_F435\Objects-App-AC5\X-Track-App-AC5.hex"
    set "AC5_AXF=%ROOT%MDK-ARM_F435\Objects-App-AC5\X-Track-App-AC5.axf"
)
for %%F in ("%AC5_BIN%" "%AC5_HEX%" "%AC5_AXF%") do (
    if not exist "%%~F" (
        echo [FAIL] AC5 build did not produce: "%%~F"
        exit /b 1
    )
)
echo [OK] AC5 target %AC5_TARGET%: "%AC5_BIN%"
exit /b 0

:build_simulator
echo.
echo [SIM] Building LVGL simulator...
"%MSBUILD%" "%SIM_SLN%" -p:Configuration=Debug -p:Platform=x64 -m -v:minimal -nologo
if errorlevel 1 (
    echo [FAIL] LVGL simulator build failed.
    exit /b 1
)
if not exist "%ROOT%Simulator\Output\Debug\x64\LVGL.Simulator.exe" (
    echo [FAIL] Simulator build did not produce LVGL.Simulator.exe.
    exit /b 1
)
echo [OK] Simulator: "%ROOT%Simulator\Output\Debug\x64\LVGL.Simulator.exe"
exit /b 0

:fail
echo.
echo See the error output above.
if "%NO_PAUSE%"=="0" pause
exit /b 1
