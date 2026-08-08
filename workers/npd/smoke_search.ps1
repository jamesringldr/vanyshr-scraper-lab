@echo off
REM Quick smoke against local/serv01 NPD service
setlocal
set BASE=%NPD_BASE_URL%
if "%BASE%"=="" set BASE=http://127.0.0.1:8789
curl.exe -sS "%BASE%/health"
echo.
curl.exe -sS -X POST "%BASE%/v1/npd/search" ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer %NPD_SERVICE_TOKEN%" ^
  -d "{\"first_name\":\"James\",\"last_name\":\"Oehring\",\"city\":\"Cameron\",\"state\":\"MO\"}"
echo.
