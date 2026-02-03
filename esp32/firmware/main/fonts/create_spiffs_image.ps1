# Script to create SPIFFS image with compiled font binary
# This stores the compiled font data extracted from chinese_font_16.c

Write-Host "=== Creating SPIFFS Image for Compiled Font ===" -ForegroundColor Green
Write-Host ""

# Use compiled font binary extracted from C file
$fontFile = "chinese_font_16.bin"
$spiffsDir = "spiffs_image"
$spiffsImage = "fonts.bin"
$spiffsSize = 4MB  # Match partition size (font binary is ~2MB, 4MB gives headroom)

# Check if font binary exists
if (-not (Test-Path $fontFile)) {
    Write-Host "Error: Compiled font binary not found: $fontFile" -ForegroundColor Red
    Write-Host "Please run: python extract_from_c_file.py chinese_font_16.c chinese_font_16.bin" -ForegroundColor Yellow
    exit 1
}

$fontSize = (Get-Item $fontFile).Length
Write-Host "Compiled font binary: $fontFile ($([math]::Round($fontSize/1MB, 2)) MB)" -ForegroundColor Cyan

# Create temporary directory structure for SPIFFS
if (Test-Path $spiffsDir) {
    Remove-Item $spiffsDir -Recurse -Force
}
New-Item -ItemType Directory -Path $spiffsDir | Out-Null

# Create directory structure for future assets
New-Item -ItemType Directory -Path "$spiffsDir\fonts" | Out-Null
New-Item -ItemType Directory -Path "$spiffsDir\icons" | Out-Null
New-Item -ItemType Directory -Path "$spiffsDir\backgrounds" | Out-Null
New-Item -ItemType Directory -Path "$spiffsDir\config" | Out-Null

Write-Host "Created SPIFFS directory structure:" -ForegroundColor Cyan
Write-Host "  /fonts/       - Font files" -ForegroundColor Gray
Write-Host "  /icons/       - Icon images (future)" -ForegroundColor Gray
Write-Host "  /backgrounds/ - Background images (future)" -ForegroundColor Gray
Write-Host "  /config/     - Configuration files (future)" -ForegroundColor Gray

# Copy compiled font binary to fonts subdirectory
Copy-Item $fontFile -Destination "$spiffsDir\fonts\chinese_font_16.bin"
Write-Host "`nCopied compiled font binary to SPIFFS/fonts/" -ForegroundColor Green

# Use ESP-IDF's spiffsgen.py to create SPIFFS image
$idfPath = $env:IDF_PATH
if (-not $idfPath) {
    Write-Host "Error: IDF_PATH not set. Please initialize ESP-IDF environment first." -ForegroundColor Red
    exit 1
}

$spiffsgen = Join-Path $idfPath "components\spiffs\spiffsgen.py"
if (-not (Test-Path $spiffsgen)) {
    Write-Host "Error: spiffsgen.py not found at $spiffsgen" -ForegroundColor Red
    Write-Host "Trying alternative location..." -ForegroundColor Yellow
    $spiffsgen = Join-Path $idfPath "tools\spiffsgen.py"
    if (-not (Test-Path $spiffsgen)) {
        Write-Host "Error: spiffsgen.py not found. Please check ESP-IDF installation." -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nGenerating SPIFFS image..." -ForegroundColor Cyan
Write-Host "Using: $spiffsgen" -ForegroundColor Gray
Write-Host "Size: $([math]::Round($spiffsSize/1MB, 2)) MB" -ForegroundColor Gray
Write-Host ""

# Calculate page size and block size for SPIFFS
# ESP32-S3 typically uses: page_size=256, block_size=4096
$pageSize = 256
$blockSize = 4096

# Generate SPIFFS image
python "$spiffsgen" $spiffsSize "$spiffsDir" "$spiffsImage" --page-size $pageSize --block-size $blockSize

if ($LASTEXITCODE -eq 0 -and (Test-Path $spiffsImage)) {
    $imageSize = (Get-Item $spiffsImage).Length
    Write-Host "`n✓ SPIFFS image created successfully!" -ForegroundColor Green
    Write-Host "  Image file: $spiffsImage" -ForegroundColor Cyan
    Write-Host "  Image size: $([math]::Round($imageSize/1MB, 2)) MB" -ForegroundColor Cyan
    Write-Host "`nNext steps:" -ForegroundColor Yellow
    Write-Host "  1. Remove font from CMakeLists.txt (fonts/chinese_font_16.c)" -ForegroundColor Cyan
    Write-Host "  2. Rebuild firmware: idf.py build" -ForegroundColor Cyan
    Write-Host "  3. Flash firmware: idf.py -p COM6 flash" -ForegroundColor Cyan
    Write-Host "  4. Flash SPIFFS: python -m esptool --chip esp32s3 -p COM6 write_flash 0x410000 fonts.bin" -ForegroundColor Cyan
} else {
    Write-Host "`n✗ Failed to create SPIFFS image" -ForegroundColor Red
    exit 1
}

# Cleanup
Remove-Item $spiffsDir -Recurse -Force
