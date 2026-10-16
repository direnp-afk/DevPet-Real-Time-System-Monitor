@echo off
setlocal
cd /d "%~dp0"
title DevPet - Tracker and Tail-er

echo.
echo ===========================================
echo        DevPet - Windows Launcher
echo ===========================================
echo.

REM Prefer the py launcher when installed; never trust the Store python alias.
set "PYTHON_CMD="
py -3 -c "import sys; assert sys.version_info >= (3,9)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  python -c "import sys; assert sys.version_info >= (3,9)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo Python 3.9 or newer was not found.
  echo Install Python for Windows from https://www.python.org/downloads/windows/
  echo Then CLOSE this window and double-click START_DEV_PET.bat again.
  echo You DO NOT need Ubuntu or WSL.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/3] Python environment found.
)

echo [2/3] Installing DevPet dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [3/3] Starting DevPet and opening dashboard...
".venv\Scripts\python.exe" app.py --open-browser
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo DevPet could not start. Read the error message above.
echo If Python was just installed, close and reopen this window.
echo.
pause
exit /b 1
