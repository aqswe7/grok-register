@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Grok Register Standalone - installer
echo ============================================================
echo.

REM ---- 1. find Python (>=3.10) ----
set PY=
where py >nul 2>nul && set PY=py -3
if "%PY%"=="" (
  where python >nul 2>nul && set PY=python
)
if "%PY%"=="" (
  echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo         Check "Add Python to PATH" during install, then run this script again.
  pause
  exit /b 1
)
echo [1/4] Python: %PY%
%PY% --version

REM ---- 2. create venv ----
if exist ".venv\Scripts\python.exe" (
  echo [2/4] venv exists, skip create.
) else (
  echo [2/4] creating venv .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] venv create failed
    pause
    exit /b 1
  )
)

set VENV_PY=.venv\Scripts\python.exe

REM ---- 3. install deps ----
echo [3/4] installing dependencies ...
%VENV_PY% -m pip install --upgrade pip -q
%VENV_PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. Check network / mirror settings.
  pause
  exit /b 1
)

REM ---- 4. first-run config ----
if not exist ".env" (
  if exist ".env.example" (
    echo [4/4] creating .env from .env.example ...
    copy /Y ".env.example" ".env" >nul
  ) else (
    echo [4/4] no .env.example, skip
  )
) else (
  echo [4/4] .env exists, keep.
)

echo.
echo ============================================================
echo   Done. Double-click start.bat to open the panel.
echo   Panel: http://127.0.0.1:8799
echo ============================================================
pause
