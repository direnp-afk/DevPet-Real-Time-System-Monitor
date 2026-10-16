@echo off
setlocal
cd /d "%~dp0"
title DevPet - Live PowerShell tail
if not exist "logs\events.log" (
  echo Log file not yet found. Start DevPet first.
  pause
  exit /b 1
)
echo Watching new DevPet events using Windows PowerShell...
echo Press Ctrl+C to stop watching.
echo.
powershell.exe -NoProfile -Command "Get-Content -LiteralPath '.\logs\events.log' -Encoding UTF8 -Tail 15 -Wait"
pause
