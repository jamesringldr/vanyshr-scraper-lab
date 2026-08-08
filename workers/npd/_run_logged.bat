@echo off
REM Detached launcher for Task Scheduler / SSH.
cd /d C:\Users\scraper\npd-scraper
call C:\Users\scraper\fps-scraper\venv\Scripts\activate.bat
>> service.log echo [%date% %time%] starting uvicorn on 8789
python -m uvicorn service:app --host 0.0.0.0 --port 8789 >> service.log 2>&1
>> service.log echo [%date% %time%] uvicorn exited code %ERRORLEVEL%
