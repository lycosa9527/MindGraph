@echo off
REM Windows 10 / 11: double-click to install MindGraph for Word (HKCU WEF Developer).
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-MindGraphWordAddin.ps1"
if errorlevel 1 (
  echo.
  echo Install failed. Run as your normal user ^(admin not required^). Unzip so manifest.xml sits next to the windows folder.
  pause
  exit /b 1
)
echo.
pause
