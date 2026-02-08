# PowerShell script to run anim_player tests
# Usage: .\run_tests.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "anim_player Module Test Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "test_apps")) {
    Write-Host "Error: Please run this script from the esp32/firmware/managed_components/espressif2022__image_player directory" -ForegroundColor Red
    exit 1
}

# Navigate to test directory
Push-Location test_apps

try {
    Write-Host "Step 1: Initializing ESP-IDF environment..." -ForegroundColor Yellow
    
    # Initialize ESP-IDF
    & C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to initialize ESP-IDF" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Step 2: Building test application..." -ForegroundColor Yellow
    idf.py build
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Build failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "Step 3: Ready to flash and monitor" -ForegroundColor Green
    Write-Host "Connect your ESP32-S3 device and press Enter to continue..." -ForegroundColor Yellow
    Read-Host
    
    Write-Host "Flashing and starting monitor..." -ForegroundColor Yellow
    idf.py flash monitor
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Test completed!" -ForegroundColor Green
