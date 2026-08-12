@echo off
REM Double-click to remove MindGraph for Word sideload for this Windows user.
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-MindGraphWordAddin.ps1" -Uninstall
echo.
pause
