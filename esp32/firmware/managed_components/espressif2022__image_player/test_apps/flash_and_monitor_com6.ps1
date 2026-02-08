# Flash and Monitor script for COM6
# Run this after closing any programs using COM6

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "anim_player Test - Flash & Monitor" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set port
$env:ESPPORT = "COM6"

# Initialize ESP-IDF if needed
Write-Host "Initializing ESP-IDF..." -ForegroundColor Yellow
& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562

Write-Host ""
Write-Host "Flashing to COM6..." -ForegroundColor Yellow
idf.py -p COM6 flash

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Flash successful! Starting monitor..." -ForegroundColor Green
    Write-Host "Press Ctrl+] to exit monitor" -ForegroundColor Yellow
    Write-Host ""
    
    idf.py -p COM6 monitor
} else {
    Write-Host ""
    Write-Host "Flash failed. Please check:" -ForegroundColor Red
    Write-Host "1. Device is connected to COM6" -ForegroundColor White
    Write-Host "2. No other programs are using COM6" -ForegroundColor White
    Write-Host "3. Device is in download mode (hold BOOT button)" -ForegroundColor White
}
