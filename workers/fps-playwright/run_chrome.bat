@echo off
REM FPS smoke via patchright + system Edge (channel=msedge), headed, in the
REM interactive desktop session (real iGPU). Google-referer path by default
REM (the lost build's "aha"). No proxy = box's home residential IP.
cd /d C:\Users\scraper\fps-scraper
call venv\Scripts\activate.bat

set CHANNEL=chromium
set PROFILE_DIR=C:\Users\scraper\fps-scraper\cft-profile
set DIRECT_NAME=1
REM DIRECT_NAME=1 → go straight to the /name/ results URL (replicates the manual
REM Edge test), skipping the homepage + form interaction that tripped DataDome.

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT_DIR=C:\Users\scraper\fps-scraper\out\chrome-%STAMP%
mkdir "%OUT_DIR%" 2>nul

python smoke_chrome.py James Oehring Cameron MO > "%OUT_DIR%\run.log" 2>&1
