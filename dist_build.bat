@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  Build a CLEAN distribution package (no personal keys / proxies)
REM  Output: dist\  (safe to zip and share with others)
REM ============================================================

set DIST=dist
if exist "%DIST%" (
  echo Removing old %DIST%\ ...
  rmdir /s /q "%DIST%"
)
mkdir "%DIST%"

echo [1/3] copying code files ...
copy /Y register_grok_http.py "%DIST%\" >nul
copy /Y config.py "%DIST%\" >nul
copy /Y proxy_relay.py "%DIST%\" >nul
copy /Y requirements.txt "%DIST%\" >nul
copy /Y .env.example "%DIST%\" >nul
copy /Y README.md "%DIST%\" >nul
copy /Y install.bat "%DIST%\" >nul
copy /Y start.bat "%DIST%\" >nul

echo [2/3] copying packages ...
xcopy /e /i /y common "%DIST%\common" >nul
xcopy /e /i /y xconsole_client "%DIST%\xconsole_client" >nul
xcopy /e /i /y webui "%DIST%\webui" >nul
mkdir "%DIST%\tokens\grok\pending" 2>nul

echo [3/3] stripping personal files ...
del /q "%DIST%\.env" 2>nul
del /q "%DIST%\proxies.txt" 2>nul
del /q "%DIST%\miyaip_pool.txt" 2>nul
for /d /r "%DIST%" %%d in (__pycache__) do rmdir /s /q "%%d" 2>nul

echo.
echo ============================================================
echo   Done. Clean package is in:  %DIST%\
echo   It contains NO .env / miyaip_pool.txt / proxies.txt.
echo   Zip this folder and share it safely.
echo ============================================================
pause
