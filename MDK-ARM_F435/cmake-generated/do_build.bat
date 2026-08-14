@echo off
setlocal

set "BUILD_TYPE=Debug"
set "ACTIVE_BUILD_DIR=build-gcc"
set "BUILD_SWITCH="
if /I "%~1"=="release" (
    set "BUILD_TYPE=Release"
    set "ACTIVE_BUILD_DIR=build-gcc-release"
    if "%SOURCE_DATE_EPOCH%"=="" (
        echo [FAIL] Release firmware build requires SOURCE_DATE_EPOCH.
        exit /b 2
    )
    if /I "%~2"=="rebuild" set "BUILD_SWITCH=--clean-first"
) else if /I "%~1"=="rebuild" (
    set "BUILD_SWITCH=--clean-first"
)

cmake -S . -B "%ACTIVE_BUILD_DIR%" -G "Ninja" -DCMAKE_BUILD_TYPE=%BUILD_TYPE%
if errorlevel 1 exit /b %errorlevel%
cmake --build "%ACTIVE_BUILD_DIR%" %BUILD_SWITCH% --parallel
endlocal
