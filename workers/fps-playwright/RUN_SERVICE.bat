@echo off
REM Runs the FPS HTTP service (service.py) on serv-01.
REM Must run in an interactive desktop session (same as run_direct.bat) —
REM smoke.py's Camoufox harvest renders into the real desktop on Windows
REM (no Xvfb), so this can't run as a headless/Session-0 Windows Service.
REM
REM Config via env or fps-playwright\.env:
REM   FPS_SERVICE_TOKEN     bearer token required on POST /v1/fps/search
REM   FPS_SMOKE_TIMEOUT_S   max seconds for the Camoufox harvest step (default 120)
REM   FPS_KEEP_ARTIFACTS=1  keep per-request out dirs instead of deleting them
REM   PORT                  listen port (default 8787)
cd /d C:\Users\scraper\fps-scraper
call venv\Scripts\activate.bat

if "%PORT%"=="" set PORT=8787
echo Starting fps-scraper-service on :%PORT%
python -m uvicorn service:app --host 0.0.0.0 --port %PORT%
