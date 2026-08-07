@echo off
REM Runs the Zaba HTTP service on serv-01 (Windows).
REM Canonical path: C:\Users\scraper\zaba-scraper
REM
REM Config via .env in this folder:
REM   ZABA_SERVICE_TOKEN, FLAMEPROXIES_API_KEY, FLAMEPROXIES_PACKAGE_ID
REM   Fetch: FlameProxies via curl --proxy first (minimize host residential IP)
REM   ZABA_DIRECT_FALLBACK=1  = last-resort host IP only after all Flame attempts fail
REM   ZABA_PORT (default 8788)

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
  echo   python -m venv venv
  echo   venv\Scripts\activate.bat
  echo   pip install -r requirements.txt
  exit /b 1
)

if "%ZABA_PORT%"=="" set ZABA_PORT=8788
echo Starting zaba-scraper-service on :%ZABA_PORT% from %CD%
python -m uvicorn service:app --host 0.0.0.0 --port %ZABA_PORT%
