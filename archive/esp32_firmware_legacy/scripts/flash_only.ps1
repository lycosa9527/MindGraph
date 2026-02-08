# Flash-only script for ESP32
Write-Host "Flashing firmware to COM6..." -ForegroundColor Cyan

# Set UTF-8 encoding
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562
idf.py -p COM6 flash

Write-Host "Flash completed!" -ForegroundColor Green
