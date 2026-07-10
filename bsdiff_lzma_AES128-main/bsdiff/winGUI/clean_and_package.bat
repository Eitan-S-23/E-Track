@echo off
echo Checking for running instances of BSDiff_GUI.exe...
taskkill /f /im BSDiff_GUI.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    echo BSDiff_GUI.exe was terminated.
    timeout /t 2 /nobreak >nul
) else (
    echo No running instances found.
)

echo Deleting existing executable if it exists...
if exist "dist\BSDiff_GUI.exe" (
    del /f "dist\BSDiff_GUI.exe" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo Deleted existing executable.
    ) else (
        echo Failed to delete executable. It may be in use by another process.
        echo Try closing all Explorer windows that might be accessing the file.
        echo Press any key to try again or Ctrl+C to exit...
        pause > nul
        del /f "dist\BSDiff_GUI.exe" 2>nul
    )
)

echo Running packaging script...
python package_app.py
echo.
echo If packaging was successful, the executable is available in the dist folder.
echo Press any key to continue...
pause > nul 