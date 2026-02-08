# Simple monitor script for ESP32
Write-Host "Starting serial monitor on COM6..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to exit" -ForegroundColor Yellow
Write-Host ""

# Set UTF-8 encoding to avoid Unicode errors
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562
idf.py -p COM6 monitor
