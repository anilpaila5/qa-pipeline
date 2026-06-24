@echo off
:: ============================================================
:: BrowserStack API Format Probe — Windows launcher
:: ============================================================
:: Run this FIRST to confirm the API endpoint and payload
:: format before running the main script.
::
:: Usage:
::   probe.bat <project_id> <folder_id>
::
:: Example (using your real IDs):
::   probe.bat 12345 49769713
::
:: After running, look for the line:
::   ✓ SUCCESS — This is the correct format!
:: Then delete the "API_PROBE_DELETE_ME" test case from BrowserStack UI.
:: ============================================================

setlocal

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo.
    echo Usage: probe.bat ^<project_id^> ^<folder_id^>
    echo.
    echo Example:
    echo   probe.bat 12345 49769713
    echo.
    pause
    exit /b 1
)

if "%~2"=="" (
    echo.
    echo [ERROR] Folder ID is required as the second argument.
    echo Usage: probe.bat ^<project_id^> ^<folder_id^>
    pause
    exit /b 1
)

cd /d "%~dp0"

echo.
echo ============================================================
echo  BrowserStack API Format Probe
echo  Project ID : %~1
echo  Folder ID  : %~2
echo ============================================================
echo.
echo Trying all known endpoint + payload combinations...
echo You will be prompted for your credentials.
echo.

python probe_api.py --project-id %~1 --folder-id %~2

echo.
pause
