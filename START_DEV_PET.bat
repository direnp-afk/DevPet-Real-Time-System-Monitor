@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo Python 3 is not installed or not on PATH.
        echo Install it from https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
    set "PYTHON=python"
)
if not exist ".venv\Scripts\python.exe" (
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo Could not create the Python environment.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" app.py --open
if errorlevel 1 pause
