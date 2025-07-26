@echo off
echo ========================================
echo D3.js_Dify Dependency Checker
echo ========================================
echo.

cd /d "%~dp0"
python check_dependencies.py

echo.
echo Press any key to exit...
pause >nul 