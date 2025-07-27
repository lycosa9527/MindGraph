@echo off
echo ========================================
echo MindGraph Dependency Checker
echo ========================================
echo.

cd /d "%~dp0"
python check_dependencies.py

echo.
echo Press any key to exit...
pause >nul 