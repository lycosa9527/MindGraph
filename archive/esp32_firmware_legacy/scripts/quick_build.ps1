# Quick Build and Flash Script for ESP32 Firmware
# Usage: .\quick_build.ps1 [flash|monitor|flash-monitor]

param(
    [string]$Action = "flash"
)

Write-Host "=== ESP32 Quick Build Script ===" -ForegroundColor Green

# Initialize ESP-IDF environment
Write-Host "`nInitializing ESP-IDF..." -ForegroundColor Cyan
& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562

# Build
Write-Host "`nBuilding firmware (incremental)..." -ForegroundColor Cyan
$buildStart = Get-Date
idf.py build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
$buildDuration = (Get-Date) - $buildStart
Write-Host "Build completed in $([math]::Round($buildDuration.TotalSeconds, 1)) seconds" -ForegroundColor Green

# Flash if requested
if ($Action -eq "flash" -or $Action -eq "flash-monitor") {
    Write-Host "`nFlashing firmware..." -ForegroundColor Cyan
    idf.py flash
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Flash failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "Flash completed!" -ForegroundColor Green
}

# Monitor if requested
if ($Action -eq "monitor" -or $Action -eq "flash-monitor") {
    Write-Host "`nOpening serial monitor..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+] to exit monitor" -ForegroundColor Yellow
    idf.py monitor
}

Write-Host "`nDone!" -ForegroundColor Green
