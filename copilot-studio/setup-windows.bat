@echo off
rem ============================================================
rem  Model Update Agent - one-time Windows setup
rem  Installs the Python dependencies. Needs Python 3.10+ on the
rem  machine (Microsoft Store "Python 3.12" is fine and usually
rem  allowed on corporate PCs). Run this once, then start-agent.bat.
rem ============================================================
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m pip install --user -r requirements.txt
) else (
    python -m pip install --user -r requirements.txt
)
if not exist .env copy copilot-studio\env.windows.example .env
echo.
echo Setup done. Edit .env (WATCH_DIR + LLM_MODE), then run start-agent.bat
pause
