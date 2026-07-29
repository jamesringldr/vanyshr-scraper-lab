@echo off
REM Runs the WebGL probe in the interactive desktop session (real iGPU).
cd /d C:\Users\scraper\fps-scraper
call venv\Scripts\activate.bat
echo === probe start %DATE% %TIME% === > out\webgl_probe.log
python webgl_probe.py >> out\webgl_probe.log 2>&1
echo === probe end %DATE% %TIME% === >> out\webgl_probe.log
