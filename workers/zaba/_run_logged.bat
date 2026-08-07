@echo off
REM Detached launcher — called by Task Scheduler or SSH. Logging to service.log.
cd /d C:\Users\scraper\zaba-scraper
call C:\Users\scraper\fps-scraper\venv\Scripts\activate.bat
>> service.log echo [%date% %time%] starting uvicorn on 8788
python -m uvicorn service:app --host 0.0.0.0 --port 8788 >> service.log 2>&1
>> service.log echo [%date% %time%] uvicorn exited code %ERRORLEVEL%
