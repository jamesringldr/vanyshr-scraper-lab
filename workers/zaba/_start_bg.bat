@echo off
cd /d C:\Users\scraper\zaba-scraper
start "zaba" /MIN C:\Users\scraper\fps-scraper\venv\Scripts\python.exe -m uvicorn service:app --host 0.0.0.0 --port 8788
