@echo off
REM Runs the FPS smoke test in the interactive desktop session (real iGPU),
REM through a fresh FlameProxies residential IP. .env (FlameProxies key) is
REM loaded by smoke.py itself. LOCAL_HEADED=1 skips the Linux-only Xvfb/ffmpeg.
cd /d C:\Users\scraper\fps-scraper
call venv\Scripts\activate.bat

set USE_FLAME=1
set LOCAL_HEADED=1
set SKIP_GOOGLE=1
set GEOIP=1

REM timestamped output dir (wmic is removed on Win11 26200; use PowerShell)
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT_DIR=C:\Users\scraper\fps-scraper\out\smoke-%STAMP%
mkdir "%OUT_DIR%" 2>nul

REM Test subject (same as RUN_LOCAL baseline). Args: first last city state.
python smoke.py James Oehring Cameron MO > "%OUT_DIR%\run.log" 2>&1
echo STAMP=%STAMP% > "%OUT_DIR%\..\last-smoke.txt"
