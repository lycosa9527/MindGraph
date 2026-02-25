# ESP-IDF Finder Script
# This script helps find your ESP-IDF installation

Write-Host "Searching for ESP-IDF installation..." -ForegroundColor Cyan
Write-Host ""

# Common installation locations
$searchPaths = @(
    "C:\esp\esp-idf",
    "$env:USERPROFILE\esp\esp-idf",
    "D:\esp\esp-idf",
    "E:\esp\esp-idf",
    "$env:USERPROFILE\.espressif",
    "C:\Users\$env:USERNAME\esp\esp-idf"
)

# Search for export scripts
$found = $false

foreach ($path in $searchPaths) {
    if (Test-Path $path) {
        Write-Host "Found: $path" -ForegroundColor Green
        
        # Check for activation scripts
        $exportPs1 = Join-Path $path "export.ps1"
        $exportBat = Join-Path $path "export.bat"
        $exportSh = Join-Path $path "export.sh"
        
        if (Test-Path $exportPs1) {
            Write-Host "  ✓ PowerShell script: $exportPs1" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "To activate, run:" -ForegroundColor Cyan
            Write-Host "  cd `"$path`"" -ForegroundColor White
            Write-Host "  .\export.ps1" -ForegroundColor White
            $found = $true
        }
        if (Test-Path $exportBat) {
            Write-Host "  ✓ Batch script: $exportBat" -ForegroundColor Yellow
        }
        if (Test-Path $exportSh) {
            Write-Host "  ✓ Bash script: $exportSh" -ForegroundColor Yellow
        }
        Write-Host ""
    }
}

# Search recursively in user directory (slower)
if (-not $found) {
    Write-Host "Searching recursively in user directory (this may take a moment)..." -ForegroundColor Yellow
    $results = Get-ChildItem -Path $env:USERPROFILE -Recurse -Filter "export.ps1" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "esp-idf" } | Select-Object -First 1
    
    if ($results) {
        $espIdfPath = $results.Directory.FullName
        Write-Host ""
        Write-Host "Found ESP-IDF at: $espIdfPath" -ForegroundColor Green
        Write-Host ""
        Write-Host "To activate, run:" -ForegroundColor Cyan
        Write-Host "  cd `"$espIdfPath`"" -ForegroundColor White
        Write-Host "  .\export.ps1" -ForegroundColor White
        $found = $true
    }
}

if (-not $found) {
    Write-Host ""
    Write-Host "ESP-IDF not found in common locations." -ForegroundColor Red
    Write-Host ""
    Write-Host "Please provide the installation path manually:" -ForegroundColor Yellow
    Write-Host "1. Remember where you installed ESP-IDF" -ForegroundColor White
    Write-Host "2. Navigate to that directory" -ForegroundColor White
    Write-Host "3. Look for export.ps1 or export.bat file" -ForegroundColor White
    Write-Host ""
    Write-Host "Or run this command to search a specific path:" -ForegroundColor Cyan
    Write-Host "  Get-ChildItem -Path 'C:\YourPath' -Recurse -Filter 'export.ps1' -ErrorAction SilentlyContinue" -ForegroundColor White
}

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
