@echo off
:: ============================================================
:: BrowserStack Bulk Test Case Creator — Windows launcher
:: ============================================================
:: Usage:
::   run.bat <project_id>                          live run (all CSV files)
::   run.bat <project_id> --dry-run                dry-run (no API calls)
::   run.bat <project_id> --resume                 skip already-created cases
::   run.bat <project_id> --reset                  delete checkpoint, start fresh
::   run.bat <project_id> --concurrency 5          5 parallel workers
::   run.bat <project_id> --file <name.csv>        one CSV file only
::   run.bat <project_id> --report out.csv         write results CSV report
::
:: Prerequisites:
::   Python 3.10+ installed and on PATH
::   pip install -r requirements.txt  (run once)
::
:: Probe script (run this FIRST if the API format is unknown):
::   probe.bat <project_id> <folder_id>
:: ============================================================

setlocal enabledelayedexpansion

:: ── Validate Python ──────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Install Python 3.10+ and retry.
    pause
    exit /b 1
)

:: ── Validate project ID arg ──────────────────────────────────
if "%~1"=="" (
    echo.
    echo Usage: run.bat ^<project_id^> [options]
    echo.
    echo Options:
    echo   --dry-run                  Print payloads, make no API calls
    echo   --resume                   Skip already-created cases ^(use after interruption^)
    echo   --reset                    Delete checkpoint file, start completely fresh
    echo   --concurrency ^<N^>          Run N parallel workers ^(default: 1, recommended: 3-5^)
    echo   --file ^<FILENAME^>          Process only one CSV file
    echo   --report ^<OUTPUT.csv^>      Write a CSV report after completion
    echo   --username ^<username^>      Pre-supply username ^(key still prompted^)
    echo.
    echo First time? Confirm the API format works:
    echo   probe.bat ^<project_id^> ^<folder_id^>
    echo.
    pause
    exit /b 1
)

set PROJECT_ID=%~1
shift

:: ── Collect remaining args ───────────────────────────────────
set EXTRA_ARGS=
:arg_loop
if "%~1"=="" goto run
set EXTRA_ARGS=%EXTRA_ARGS% %~1
shift
goto arg_loop

:run
echo.
echo ============================================================
echo  BrowserStack Bulk Test Case Creator
echo  Project ID : %PROJECT_ID%
echo ============================================================
echo.

:: Change to the script's own directory so relative paths work.
cd /d "%~dp0"

python create_test_cases.py --project-id %PROJECT_ID% %EXTRA_ARGS%

if errorlevel 1 (
    echo.
    echo [ERROR] Script exited with an error. See output above.
    echo.
    echo If this was interrupted mid-run, restart with:
    echo   run.bat %PROJECT_ID% --resume
    pause
    exit /b 1
)

echo.
echo Done. To skip already-created cases on re-run: run.bat %PROJECT_ID% --resume
pause
