# Chinese Font Generation Script (16px Extended Range)
# Regenerates ONLY the 16px font with extended CJK range 0x4E00-0x9FFF
# This covers all Chinese characters including: 就绪智回已连接
# Extended range ensures characters like 绪(U+7EEA), 智(U+667A), 连(U+8FDE), 接(U+63A5) are included

Write-Host "=== Chinese Font Generator (16px Extended Range) ===" -ForegroundColor Green
Write-Host "Regenerating chinese_font_16.c with extended CJK range (0x4E00-0x9FFF)" -ForegroundColor Yellow
Write-Host "This ensures all Chinese characters in the codebase are included" -ForegroundColor Cyan
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
# Extended CJK range 0x4E00-0x9FFF covers ~20,000 characters including:
# - 就 (U+5C31), 回 (U+56DE), 已 (U+5DF2) - in original range
# - 绪 (U+7EEA), 智 (U+667A), 连 (U+8FDE), 接 (U+63A5) - now included!
# - 设 (U+8BBE), 计 (U+8BA1) - now included!
$ranges = @(
    "0x0020-0x007F",  # Basic Latin (ASCII)
    "0x00A0-0x00FF",  # Latin-1 Supplement
    "0x0100-0x017F",  # Latin Extended-A
    "0x2000-0x206F",  # General Punctuation
    "0x20A0-0x20CF",  # Currency Symbols
    "0x3000-0x303F",  # CJK Symbols and Punctuation
    "0x3040-0x309F",  # Hiragana
    "0x30A0-0x30FF",  # Katakana
    "0x4E00-0x9FFF",  # CJK Unified Ideographs (EXTENDED FULL RANGE - covers all characters we use)
    "0xFF00-0xFFEF"   # Halfwidth and Fullwidth Forms
)

# Build range arguments
$rangeArgs = $ranges | ForEach-Object { "--range", $_ }

# Only generate 16px font (as per user request to stick with 16px)
$size = 16
$outputFile = "chinese_font_$size.c"

Write-Host "`nGenerating $outputFile with extended CJK range (0x4E00-0x9FFF)..." -ForegroundColor Yellow
Write-Host "This includes ~20,000 Chinese characters" -ForegroundColor Cyan
Write-Host "Estimated time: 5-10 minutes" -ForegroundColor Cyan
Write-Host ""

# Backup existing font
Write-Host "Backing up existing font..." -ForegroundColor Cyan
$backupDir = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
if (Test-Path $outputFile) {
    Copy-Item $outputFile -Destination $backupDir
    Write-Host "  ✓ Backed up to $backupDir" -ForegroundColor Green
} else {
    Write-Host "  ℹ No existing font to backup" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Generating $outputFile (${size}px)..." -ForegroundColor Cyan
Write-Host "This may take 5-10 minutes..." -ForegroundColor Yellow

$startTime = Get-Date

$fontArgs = @(
    "--font", $fontFile,
    "--size", $size.ToString(),
    "--format", "lvgl",
    "--bpp", "4",  # 4bpp for better quality
    # DO NOT use --no-compress - compression reduces file size significantly
    # LVGL handles decompression automatically at runtime
    "--symbols", "智回就绪已连接设计",  # Explicitly include all characters we use, including "设计"
    "-o", $outputFile
) + $rangeArgs

# Run lv_font_conv and wait for completion
# Use & operator but capture output to ensure it completes
Write-Host "Running lv_font_conv (this may take 5-10 minutes)..." -ForegroundColor Cyan
$output = & lv_font_conv @fontArgs 2>&1
$exitCode = $LASTEXITCODE

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalMinutes

if ($exitCode -eq 0) {
    # Wait a moment for file system to sync
    Start-Sleep -Seconds 2
    
    # Verify file exists and is not empty
    if (-not (Test-Path $outputFile)) {
        Write-Host "  ✗ Font file was not created!" -ForegroundColor Red
        exit 1
    }
    
    $fileSize = (Get-Item $outputFile).Length
    if ($fileSize -eq 0) {
        Write-Host "  ✗ Font file is empty!" -ForegroundColor Red
        exit 1
    }
    
    # Verify file is complete by checking for closing structures
    Write-Host "`nVerifying font file completeness..." -ForegroundColor Cyan
    $content = Get-Content $outputFile -Raw -Encoding UTF8
    if ($content -notmatch '#endif.*CHINESE_FONT_16') {
        Write-Host "  ⚠ WARNING: Font file appears incomplete (missing closing #endif)" -ForegroundColor Yellow
        Write-Host "  File size: $([math]::Round($fileSize/1MB, 2)) MB" -ForegroundColor Yellow
        Write-Host "  This may indicate the generation was interrupted" -ForegroundColor Yellow
        Write-Host "  Waiting 30 seconds and checking again..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
        
        # Re-check after waiting
        $content = Get-Content $outputFile -Raw -Encoding UTF8
        if ($content -notmatch '#endif.*CHINESE_FONT_16') {
            Write-Host "  ✗ Font file is still incomplete after waiting!" -ForegroundColor Red
            Write-Host "  Please run the script again and let it complete fully" -ForegroundColor Yellow
            exit 1
        }
    }
    
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    $fileSizeKB = [math]::Round($fileSize / 1KB, 2)
    
    if ($fileSizeMB -gt 1) {
        Write-Host "  ✓ Generated $outputFile ($fileSizeMB MB) in $([math]::Round($duration, 1)) minutes" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Generated $outputFile ($fileSizeKB KB) in $([math]::Round($duration, 1)) minutes" -ForegroundColor Green
    }
    
    # Fix the #include directive (lv_font_conv generates incompatible includes)
    Write-Host "`nFixing #include directive..." -ForegroundColor Cyan
    $content = Get-Content $outputFile -Raw -Encoding UTF8
    $content = $content -replace '#ifdef LV_LVGL_H_INCLUDE_SIMPLE\s+#include "lvgl\.h"\s+#else\s+#include "lvgl/lvgl\.h"\s+#endif', '#include <lvgl.h>'
    Set-Content $outputFile -Value $content -Encoding UTF8 -NoNewline
    Write-Host "  ✓ Fixed #include directive" -ForegroundColor Green
    
} else {
    Write-Host "  ✗ Failed to generate $outputFile (Exit code: $($process.ExitCode))" -ForegroundColor Red
    Write-Host "  Check error messages above" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "=== Font Generation Complete ===" -ForegroundColor Green
Write-Host "`nGenerated file:" -ForegroundColor Yellow
$fileSize = (Get-Item $outputFile).Length
$fileSizeMB = [math]::Round($fileSize / 1MB, 2)
$fileSizeKB = [math]::Round($fileSize / 1KB, 2)
if ($fileSizeMB -gt 1) {
    Write-Host "  $outputFile ($fileSizeMB MB)" -ForegroundColor Cyan
} else {
    Write-Host "  $outputFile ($fileSizeKB KB)" -ForegroundColor Cyan
}

Write-Host "`nNext steps:" -ForegroundColor Green
Write-Host "  1. Rebuild firmware: cd .. && idf.py build" -ForegroundColor Cyan
Write-Host "  2. Flash firmware: idf.py -p COM6 flash" -ForegroundColor Cyan
Write-Host "  3. Test Chinese character display" -ForegroundColor Cyan
Write-Host "`nNote: All Chinese characters (就绪智回已连接设计) should now display correctly!" -ForegroundColor Green
Write-Host "Font uses 4bpp with compression enabled (smaller file size)" -ForegroundColor Cyan
Write-Host "LVGL automatically handles font decompression at runtime" -ForegroundColor Yellow
Write-Host "Testing compressed font on ESP32 watch..." -ForegroundColor Magenta
