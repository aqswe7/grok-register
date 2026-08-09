@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Not installed yet. Double-click install.bat first.
  pause
  exit /b 1
)

if "%REG_FACTORY_PORT%"=="" set REG_FACTORY_PORT=8799

echo ============================================================
echo   Grok Register panel
echo ============================================================

REM ---- auto start proxy relay (10809 out / 10810 ctrl) ----
curl -s --max-time 2 http://127.0.0.1:10810/status >nul 2>&1
if errorlevel 1 (
  echo [proxy] relay not running, starting local relay...
  start "" /b .venv\Scripts\python.exe proxy_relay.py
  timeout /t 2 /nobreak >nul
  curl -s --max-time 2 http://127.0.0.1:10810/status >nul 2>&1
  if errorlevel 1 (
    echo [WARN] relay start failed, will fallback to CLASH_PROXY single exit.
  ) else (
    echo [proxy] relay ready.
  )
) else (
  echo [proxy] relay already running, skip.
)

echo.
echo Panel: http://127.0.0.1:%REG_FACTORY_PORT%  (browser opens automatically)
echo Close this window to stop the server.
echo.

start "" /b cmd /c "timeout /t 2 >nul & start http://127.0.0.1:%REG_FACTORY_PORT%"

.venv\Scripts\python.exe -m uvicorn webui.server:app --host 127.0.0.1 --port %REG_FACTORY_PORT%
pause
