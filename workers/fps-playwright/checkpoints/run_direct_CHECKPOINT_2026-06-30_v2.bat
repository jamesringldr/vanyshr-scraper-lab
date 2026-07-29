@echo off
REM ISOLATION TEST: run FPS smoke DIRECT from the box's own home residential IP,
REM NO proxy (USE_FLAME unset). Tests whether Camoufox/fingerprint alone passes
REM FPS Cloudflare from a known-trusted residential IP. If this 403s, the problem
REM is the fingerprint, not the proxy.
cd /d C:\Users\scraper\fps-scraper
call venv\Scripts\activate.bat

set LOCAL_HEADED=1
set SKIP_GOOGLE=1
REM NOTE: USE_FLAME intentionally NOT set -> smoke.py runs with no proxy.

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT_DIR=C:\Users\scraper\fps-scraper\out\direct-%STAMP%
mkdir "%OUT_DIR%" 2>nul

python smoke.py James Oehring Cameron MO > "%OUT_DIR%\run.log" 2>&1
