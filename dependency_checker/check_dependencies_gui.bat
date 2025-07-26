@echo off
echo ========================================
echo D3.js_Dify Dependency Checker (GUI)
echo ========================================
echo.

cd /d "%~dp0"
python check_dependencies_gui.py

echo.
echo Press any key to exit...
pause >nul 