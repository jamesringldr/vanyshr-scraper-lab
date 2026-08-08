@echo off
REM NPD HTTP service on serv-01 (Windows).
REM Canonical path: C:\Users\scraper\npd-scraper
REM Port: 8789 (FPS 8787, Zaba 8788)

setlocal
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
  call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
) else if exist "C:\Users\scraper\fps-scraper\venv\Scripts\activate.bat" (
  echo Using shared FPS venv at C:\Users\scraper\fps-scraper\venv
  call C:\Users\scraper\fps-scraper\venv\Scripts\activate.bat
) else (
  echo ERROR: no venv found.
  exit /b 1
)

if "%NPD_PORT%"=="" set NPD_PORT=8789
echo Starting npd-scraper-service on :%NPD_PORT% from %CD%
python -m uvicorn service:app --host 0.0.0.0 --port %NPD_PORT%
