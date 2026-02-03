# Asset Management System

This document describes the SPIFFS-based asset management system for storing fonts, icons, backgrounds, and other files on external flash.

## Directory Structure

All assets are stored in SPIFFS under `/spiffs/`:

```
/spiffs/
├── fonts/
│   └── chinese_font_16.bin    (2 MB - compiled font data)
├── icons/
│   └── (future: wifi.png, battery.png, etc.)
├── backgrounds/
│   └── (future: default.bmp, ready.bmp, etc.)
└── config/
    └── (future: user settings, etc.)
```

## Current Implementation

### Font Loading
- **Status**: ✅ Working
- **File**: `/spiffs/fonts/chinese_font_16.bin`
- **Size**: ~2 MB
- **Usage**: Loaded at startup via `font_manager_init()`

### Future Assets

#### Icons
To add icon images in the future:
1. Convert icons to PNG/BMP format
2. Place in `spiffs_image/icons/` directory
3. Regenerate SPIFFS image: `.\create_spiffs_image.ps1`
4. Load using: `asset_load_image(parent, "/spiffs/icons/wifi.png")`

#### Backgrounds
To add background images:
1. Convert to BMP format (LVGL supports BMP natively)
2. Place in `spiffs_image/backgrounds/` directory
3. Regenerate SPIFFS image
4. Load using: `asset_load_image(parent, "/spiffs/backgrounds/default.bmp")`

## API Usage

### Asset Manager Functions

```cpp
#include "asset_manager.h"

// Initialize (called once at startup)
asset_manager_init();

// Check if asset exists
if (asset_exists("/spiffs/icons/wifi.png")) {
    // Load image
    lv_obj_t* img = asset_load_image(parent, "/spiffs/icons/wifi.png");
}

// Load binary data (for fonts, etc.)
size_t size;
void* data = asset_load_binary("/spiffs/fonts/chinese_font_16.bin", &size);
// ... use data ...
heap_caps_free(data);  // Free when done

// Get partition info
size_t total_kb, used_kb;
asset_get_partition_info(&total_kb, &used_kb);
```

## Partition Layout

- **Partition Name**: `fonts` (used for all assets)
- **Size**: 4 MB
- **Current Usage**: ~2 MB (font)
- **Available**: ~2 MB (for icons, backgrounds, etc.)

## Adding New Assets

1. **Prepare assets**: Convert images to supported formats (PNG, BMP, JPG)
2. **Add to SPIFFS directory**: Place in `spiffs_image/` subdirectories
3. **Regenerate image**: Run `.\create_spiffs_image.ps1`
4. **Flash SPIFFS**: `python -m esptool --chip esp32s3 -p COM6 write_flash 0x410000 fonts.bin`
5. **Use in code**: Load via `asset_manager` functions

## Supported Formats

- **Fonts**: Binary format (extracted from compiled C files)
- **Images**: PNG, BMP, JPG (via LVGL image decoders)
- **Config**: JSON, text files
- **Other**: Any binary data

## Notes

- All assets are stored on external flash (32MB total)
- Assets are loaded into PSRAM when needed (8MB available)
- SPIFFS images are always full partition size (4MB), but only used space counts
- Assets can be updated by regenerating and reflashing SPIFFS partition
