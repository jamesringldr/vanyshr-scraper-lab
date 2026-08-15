@echo off
REM Quickscan HTTP service on serv-01 (Windows).
REM Canonical path: C:\Users\scraper\quickscan-service
REM Port: 8790 (FPS 8787, Zaba 8788, NPD 8789)

setlocal
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
  call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
) else (
  echo ERROR: no venv found.
  exit /b 1
)

if "%QUICKSCAN_PORT%"=="" set QUICKSCAN_PORT=8790
echo Starting quickscan-service on :%QUICKSCAN_PORT% from %CD%
python -m uvicorn quickscan_service:app --host 0.0.0.0 --port %QUICKSCAN_PORT%
