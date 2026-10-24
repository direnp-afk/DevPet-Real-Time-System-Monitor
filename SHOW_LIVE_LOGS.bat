@echo off
cd /d "%~dp0"
if not exist "data\events.log" (
    echo Run DevPet once to create its event log.
    pause
    exit /b 1
)
where tail >nul 2>nul
if %errorlevel%==0 (
    tail -n 15 -F "data\events.log"
) else (
    powershell.exe -NoProfile -Command "Get-Content -LiteralPath 'data\events.log' -Tail 15 -Wait"
)
pause
