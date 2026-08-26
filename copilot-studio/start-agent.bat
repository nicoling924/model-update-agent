@echo off
rem ============================================================
rem  Model Update Agent - PC edition launcher (Windows)
rem  Starts the SharePoint watcher: drop "RUN <COMPANY> <PERIOD>.txt"
rem  into <WATCH_DIR>\inbox and the updated model lands in outbox\.
rem  Configure WATCH_DIR and LLM_MODE in ..\.env first (see PC_SETUP.md).
rem ============================================================
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 copilot-studio\sharepoint_watcher.py
) else (
    python copilot-studio\sharepoint_watcher.py
)
pause
