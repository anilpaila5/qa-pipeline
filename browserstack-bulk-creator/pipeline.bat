@echo off
:: ============================================================
:: QA Pipeline — Jira → AI → BrowserStack → Traceability
:: Windows launcher
:: ============================================================
:: Usage:
::   Full pipeline:
::     pipeline.bat QA-1831 <project_id> <folder_id>
::
::   Generate only (CSV for review, no BrowserStack publish):
::     pipeline.bat QA-1831 <project_id> <folder_id> --generate-only
::
::   Publish a reviewed CSV:
::     pipeline.bat --publish-only input\QA-1831_cases.csv <project_id> <folder_id>
::
::   Traceability report:
::     pipeline.bat --report
::
::   With Slack notification:
::     pipeline.bat QA-1831 <project_id> <folder_id> --webhook https://hooks.slack.com/...
::
::   With Teams notification:
::     pipeline.bat QA-1831 <project_id> <folder_id> --webhook https://... --webhook-type teams
::
::   With Windows toast:
::     pipeline.bat QA-1831 <project_id> <folder_id> --toast
::
:: ============================================================

setlocal enabledelayedexpansion

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    pause
    exit /b 1
)

cd /d "%~dp0"

:: ── Special case: traceability report ────────────────────────────────────────
if "%~1"=="--report" (
    echo.
    echo ============================================================
    echo  Traceability and Coverage Report
    echo ============================================================
    python pipeline.py --traceability-report %2 %3 %4 %5
    pause
    exit /b 0
)

:: ── Special case: publish-only ────────────────────────────────────────────────
if "%~1"=="--publish-only" (
    if "%~2"=="" (
        echo [ERROR] --publish-only requires a CSV path as second argument.
        echo Usage: pipeline.bat --publish-only ^<csv^> ^<project_id^> ^<folder_id^>
        pause
        exit /b 1
    )
    echo.
    echo ============================================================
    echo  Publish-only: %~2
    echo  Project ID  : %~3
    echo  Folder ID   : %~4
    echo ============================================================
    python pipeline.py --publish-only --csv %~2 --project-id %~3 --folder-id %~4 %5 %6 %7
    pause
    exit /b 0
)

:: ── Full pipeline ─────────────────────────────────────────────────────────────
if "%~1"=="" (
    echo.
    echo Usage:
    echo   pipeline.bat ^<jira-issue^> ^<project_id^> ^<folder_id^> [options]
    echo   pipeline.bat --publish-only ^<csv^> ^<project_id^> ^<folder_id^>
    echo   pipeline.bat --report
    echo.
    echo Examples:
    echo   pipeline.bat QA-1831 12345 49769713
    echo   pipeline.bat QA-1831 12345 49769713 --generate-only
    echo   pipeline.bat QA-1831 12345 49769713 --concurrency 5 --toast
    echo   pipeline.bat QA-1831 12345 49769713 --webhook https://hooks.slack.com/...
    echo.
    pause
    exit /b 1
)

set JIRA_ISSUE=%~1
set PROJECT_ID=%~2
set FOLDER_ID=%~3
shift
shift
shift

set EXTRA=
:collect
if "%~1"=="" goto go
set EXTRA=%EXTRA% %~1
shift
goto collect

:go
echo.
echo ============================================================
echo  QA Pipeline: Jira to BrowserStack
echo  Jira Issue  : %JIRA_ISSUE%
echo  Project ID  : %PROJECT_ID%
echo  Folder ID   : %FOLDER_ID%
echo ============================================================
echo.

python pipeline.py ^
    --jira-issue %JIRA_ISSUE% ^
    --project-id %PROJECT_ID% ^
    --folder-id %FOLDER_ID% ^
    %EXTRA%

if errorlevel 1 (
    echo.
    echo [ERROR] Pipeline exited with an error.
    pause
    exit /b 1
)

echo.
pause
