# Chinese Font Generation Script (16px Extended Range - UNCOMPRESSED)
# Regenerates the 16px font WITHOUT compression for compatibility
# Use this if compressed fonts don't work properly

Write-Host "=== Chinese Font Generator (16px Extended Range - UNCOMPRESSED) ===" -ForegroundColor Green
Write-Host "Regenerating chinese_font_16.c WITHOUT compression" -ForegroundColor Yellow
Write-Host "This ensures maximum compatibility but larger file size" -ForegroundColor Cyan
Write-Host ""

# Check if lv_font_conv is installed
$fontConv = Get-Command lv_font_conv -ErrorAction SilentlyContinue
if (-not $fontConv) {
    Write-Host "Installing lv_font_conv..." -ForegroundColor Yellow
    npm install -g lv_font_conv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install lv_font_conv. Please install manually: npm install -g lv_font_conv" -ForegroundColor Red
        exit 1
    }
}

# Use existing font file
$fontFile = "AlibabaPuHuiTi-3-55-Regular\AlibabaPuHuiTi-3-55-Regular.ttf"
if (-not (Test-Path $fontFile)) {
    Write-Host "Font file not found: $fontFile" -ForegroundColor Red
    Write-Host "Please ensure the font file exists in the fonts directory." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "Using font file: $fontFile" -ForegroundColor Green
}

# Unicode ranges for extended Chinese support
$ranges = @(
    "0x0020-0x007F",  # Basic Latin (ASCII)
    "0x00A0-0x00FF",  # Latin-1 Supplement
    "0x0100-0x017F",  # Latin Extended-A
    "0x2000-0x206F",  # General Punctuation
    "0x20A0-0x20CF",  # Currency Symbols
    "0x3000-0x303F",  # CJK Symbols and Punctuation
    "0x3040-0x309F",  # Hiragana
    "0x30A0-0x30FF",  # Katakana
    "0x4E00-0x9FFF",  # CJK Unified Ideographs (EXTENDED FULL RANGE)
    "0xFF00-0xFFEF"   # Halfwidth and Fullwidth Forms
)

# Build range arguments
$rangeArgs = $ranges | ForEach-Object { "--range", $_ }

# Only generate 16px font
$size = 16
$outputFile = "chinese_font_$size.c"

Write-Host "`nGenerating $outputFile WITHOUT compression..." -ForegroundColor Yellow
Write-Host "This includes ~20,000 Chinese characters" -ForegroundColor Cyan
Write-Host "Estimated time: 5-10 minutes" -ForegroundColor Cyan
Write-Host "File will be LARGER but more compatible" -ForegroundColor Yellow
Write-Host ""

# Backup existing font
Write-Host "Backing up existing font..." -ForegroundColor Cyan
$backupDir = "backup_uncompressed_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
if (Test-Path $outputFile) {
    Copy-Item $outputFile -Destination $backupDir
    Write-Host "  ✓ Backed up to $backupDir" -ForegroundColor Green
} else {
    Write-Host "  ℹ No existing font to backup" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Generating $outputFile (${size}px) WITHOUT compression..." -ForegroundColor Cyan
Write-Host "This may take 5-10 minutes..." -ForegroundColor Yellow

$startTime = Get-Date

$fontArgs = @(
    "--font", $fontFile,
    "--size", $size.ToString(),
    "--format", "lvgl",
    "--bpp", "4",  # 4bpp for better quality
    "--no-compress",  # CRITICAL: Disable compression for compatibility
    "--symbols", "智回就绪已连接设计",
    "-o", $outputFile
) + $rangeArgs

# Run lv_font_conv
Write-Host "Running lv_font_conv (this may take 5-10 minutes)..." -ForegroundColor Cyan
$output = & lv_font_conv @fontArgs 2>&1
$exitCode = $LASTEXITCODE

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalMinutes

if ($exitCode -eq 0) {
    Start-Sleep -Seconds 2
    
    if (-not (Test-Path $outputFile)) {
        Write-Host "  ✗ Font file was not created!" -ForegroundColor Red
        exit 1
    }
    
    $fileSize = (Get-Item $outputFile).Length
    if ($fileSize -eq 0) {
        Write-Host "  ✗ Font file is empty!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "`nVerifying font file completeness..." -ForegroundColor Cyan
    $content = Get-Content $outputFile -Raw -Encoding UTF8
    if ($content -notmatch '#endif.*CHINESE_FONT_16') {
        Write-Host "  ⚠ WARNING: Font file appears incomplete" -ForegroundColor Yellow
        Start-Sleep -Seconds 30
        $content = Get-Content $outputFile -Raw -Encoding UTF8
        if ($content -notmatch '#endif.*CHINESE_FONT_16') {
            Write-Host "  ✗ Font file is still incomplete!" -ForegroundColor Red
            exit 1
        }
    }
    
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Host "  ✓ Generated $outputFile ($fileSizeMB MB) in $([math]::Round($duration, 1)) minutes" -ForegroundColor Green
    
    # Fix the #include directive
    Write-Host "`nFixing #include directive..." -ForegroundColor Cyan
    $content = Get-Content $outputFile -Raw -Encoding UTF8
    $content = $content -replace '#ifdef LV_LVGL_H_INCLUDE_SIMPLE\s+#include "lvgl\.h"\s+#else\s+#include "lvgl/lvgl\.h"\s+#endif', '#include <lvgl.h>'
    Set-Content $outputFile -Value $content -Encoding UTF8 -NoNewline
    Write-Host "  ✓ Fixed #include directive" -ForegroundColor Green
    
} else {
    Write-Host "  ✗ Failed to generate $outputFile" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "=== Font Generation Complete (UNCOMPRESSED) ===" -ForegroundColor Green
Write-Host "`nGenerated file:" -ForegroundColor Yellow
$fileSize = (Get-Item $outputFile).Length
$fileSizeMB = [math]::Round($fileSize / 1MB, 2)
Write-Host "  $outputFile ($fileSizeMB MB)" -ForegroundColor Cyan

Write-Host "`nNext steps:" -ForegroundColor Green
Write-Host "  1. Disable compression in sdkconfig: # CONFIG_LV_USE_FONT_COMPRESSED is not set" -ForegroundColor Cyan
Write-Host "  2. Rebuild firmware: cd .. && idf.py build" -ForegroundColor Cyan
Write-Host "  3. Flash firmware: idf.py -p COM6 flash" -ForegroundColor Cyan
Write-Host "`nNote: Uncompressed font is larger but more compatible!" -ForegroundColor Green
