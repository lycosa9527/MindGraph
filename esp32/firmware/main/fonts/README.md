# Chinese Font Generation (16px Only)

## Overview

This directory contains the Chinese font for ESP32 firmware. **Only the 16px font is used** to save flash space (~12MB saved vs using multiple sizes).

## Current Font

- **File:** `chinese_font_16.c`
- **Size:** 16px
- **Format:** LVGL format
- **Usage:** Used for all text sizes in the UI (scaled by LVGL)

## Regenerating the Font

### Option 1: Extended Range (Recommended)
**Covers all Chinese characters (0x4E00-0x9FFF)**
```powershell
.\regenerate_font_16_extended.ps1
```
- Includes ~20,000 Chinese characters
- Takes 5-10 minutes to generate
- File size: ~3-6MB

### Option 2: Minimal Range
**Only common Chinese characters (0x4E00-0x62FF)**
```powershell
.\regenerate_font_16_minimal.ps1
```
- Includes ~5,000 Chinese characters
- Takes 2-3 minutes to generate
- File size: ~1-2MB
- Avoids bitmap_index overflow issues

## Manual Generation

You can also generate the font manually using `lv_font_conv`:

```powershell
# Extended range (all Chinese characters)
lv_font_conv --font "AlibabaPuHuiTi-3-55-Regular\AlibabaPuHuiTi-3-55-Regular.ttf" --size 16 --format lvgl --bpp 4 --range 0x0020-0x007F --range 0x4E00-0x9FFF --symbols "智回就绪已连接设计" -o chinese_font_16.c

# Minimal range (common characters only)
lv_font_conv --font "AlibabaPuHuiTi-3-55-Regular\AlibabaPuHuiTi-3-55-Regular.ttf" --size 16 --format lvgl --bpp 4 --no-compress --range 0x0020-0x007F --range 0x4E00-0x62FF --symbols "智回就绪已连接" -o chinese_font_16.c
```

## Font Source

The font is generated from **Alibaba PuHuiTi Regular** located in:
- `AlibabaPuHuiTi-3-55-Regular/AlibabaPuHuiTi-3-55-Regular.ttf`

## After Generation

Once you regenerate `chinese_font_16.c`, rebuild the firmware:

```bash
cd ../../..
idf.py build
idf.py flash
```

## Font Manager

The font is managed by `font_manager.cpp` which:
- Initializes `chinese_font_16` at startup
- Provides `font_manager_get_font()` function
- Returns the 16px font for all size requests (saves flash space)

## Notes

- **Only 16px font is used** - LVGL scales it for different sizes
- Fonts are stored in Flash (32MB available)
- The font manager uses a single 16px font for all text sizes to save ~12MB flash space