---
name: Firmware Organization and Module Fixes
overview: Organize firmware structure, remove dead code (duplicate src/ folder, deprecated display_handler), fix module initialization issues, and ensure all modules work properly with the BSP-based display system.
todos:
  - id: migrate-qrcode
    content: Migrate qrcode_generator from src/ to main/, remove Arduino.h, add to CMakeLists.txt
    status: pending
  - id: migrate-wallpaper
    content: Migrate wallpaper_manager from src/ to main/, remove Arduino.h, add to CMakeLists.txt
    status: pending
  - id: migrate-ui-icons
    content: Migrate ui_icons from src/ to main/, remove Arduino.h, improve icon rendering (replace emoji), add to CMakeLists.txt
    status: pending
  - id: remove-dead-code
    content: "Delete dead code folders: remove esp32/firmware/src/ and esp32/firmware/main/components/ after migration"
    status: pending
  - id: remove-display-handler
    content: Remove deprecated display_handler files and update CMakeLists.txt
    status: pending
  - id: fix-battery-manager
    content: Add _initialized member to battery_manager.h header
    status: pending
  - id: migrate-ui-manager
    content: Update ui_manager to use BSP instead of display_handler functions
    status: pending
  - id: fix-motion-sensor
    content: Add initialization guard and error handling to motion_sensor
    status: pending
  - id: fix-rtc-manager
    content: Add initialization guard and error handling to rtc_manager
    status: pending
  - id: update-main-init
    content: Update main.cpp to properly initialize all modules in correct order
    status: pending
  - id: verify-build
    content: Clean build and fix any compilation errors
    status: pending
isProject: false
---

# Firmware Organization and Module Fixes

## Current State Analysis

### Active Firmware Location

- `**main/` folder**: ACTIVE ESP-IDF firmware (being built)
  - Uses FreeRTOS, BSP display, ESP-IDF logging
  - Entry point: `app_main()`
  - This is what we've been working on and fixing

### Dead Code Locations

- `**src/` folder**: OLD Arduino code (NOT being built)
  - Uses Arduino framework (`setup()/loop()`)
  - Legacy implementation before ESP-IDF migration
  - Safe to delete completely

### Working Modules (in `main/`)

- **Display/LVGL**: Using BSP (`bsp_display_start()`, `bsp_display_lock/unlock`)
- **Battery Manager**: Partially working (has initialization guard, but I2C errors persist)
- **RTC Manager**: Basic structure exists
- **Motion Sensor**: Basic structure exists
- **Audio Handler**: Basic structure exists
- **WiFi/WebSocket**: Basic structure exists
- **Apps**: Smart Response and Dify apps exist

### Dead Code to Remove

1. `**esp32/firmware/src/` folder**: OLD Arduino-based code (uses `Arduino.h`, `Serial.println()`, `setup()/loop()`). This is NOT being built - ESP-IDF uses `main/` folder. Safe to delete.
2. `**esp32/firmware/main/components/` folder**: Duplicate copies WITHOUT CMakeLists.txt. The real ESP-IDF components are in `components/` (with CMakeLists.txt). Includes use `../components/` pointing to the real one.
3. `**display_handler.cpp/h**`: Deprecated (replaced by BSP), but still referenced by `ui_manager`
4. `**ui_manager.cpp/h**`: Uses deprecated `display_handler` functions that don't work with BSP

### Module Issues to Fix

1. **Battery Manager**: `_initialized` member missing from header declaration
2. **UI Manager**: Still calls `display_handler` functions that don't work with BSP
3. **Motion Sensor**: Need to verify initialization and error handling
4. **RTC Manager**: Need to verify initialization and error handling
5. **Audio Handler**: Need to verify initialization and error handling
6. **CMakeLists.txt**: Still includes `display_handler.cpp` in build

## Implementation Plan

### Phase 1: Migrate Useful Modules from `src/` to `main/`

#### 1.1 Migrate QR Code Generator

- Copy `qrcode_generator.cpp/h` from `src/` to `main/`
- Remove `#include <Arduino.h>` (not needed - pure LVGL)
- Verify LVGL QR code widget is available (uses `lv_qrcode_create`)
- Add to `main/CMakeLists.txt` SRCS list
- Test QR code generation works

#### 1.2 Migrate Wallpaper Manager

- Copy `wallpaper_manager.cpp/h` from `src/` to `main/`
- Remove `#include <Arduino.h>` (not needed - pure LVGL)
- Update to use BSP display lock/unlock if modifying screens
- Add to `main/CMakeLists.txt` SRCS list
- Verify wallpaper colors match UI states

#### 1.3 Migrate UI Icons

- Copy `ui_icons.cpp/h` from `src/` to `main/`
- Remove `#include <Arduino.h>` (not needed - pure LVGL)
- **IMPROVEMENT**: Replace emoji icons with text symbols or LVGL symbols (emoji don't render well)
  - Use "W" for WiFi, "B" for Battery (matching current standby_screen approach)
  - Or use LVGL symbol fonts if available
- Add to `main/CMakeLists.txt` SRCS list
- Update icon usage to work with BSP display

### Phase 2: Remove Dead Code

#### 2.1 Delete Dead Code Folders

- Delete `esp32/firmware/src/` folder entirely (after migrating useful modules)
- Delete `esp32/firmware/main/components/` folder (duplicate copies without CMakeLists.txt)
- Verify `components/` folder has CMakeLists.txt files (these are the real ESP-IDF components)

#### 2.2 Remove Deprecated display_handler

- Remove `display_handler.cpp` and `display_handler.h` from `main/`
- Remove `display_handler.cpp` from `main/CMakeLists.txt` SRCS list
- Update any remaining references to use BSP functions

### Phase 2: Fix Module Initialization

#### 2.1 Battery Manager

- Add `bool _initialized;` to `battery_manager.h` private section (already in cpp)
- Ensure `update()` only runs when `_initialized == true` (already done)
- Add initialization status logging

#### 2.2 UI Manager Migration

- Remove `#include "display_handler.h"` from `ui_manager.cpp` and `ui_manager.h`
- Replace `display_show_*()` function calls with BSP-based UI updates:
  - `display_show_loading()` → Use `loading_screen_show()` (already exists)
  - `display_show_setup_mode()` → Create new BSP-based setup screen or remove
  - `display_show_waiting_assignment()` → Create new BSP-based waiting screen or remove
  - `display_show_status()` → Use `standby_screen` status updates
  - `display_show_ready()` → Use `standby_screen` or `launcher`
  - `display_show_learning_mode()` → Create new screen or remove
  - `display_show_error()` → Create error display function using BSP
- Update `ui_manager.cpp` to use BSP display lock/unlock

#### 2.3 Motion Sensor

- Add initialization guard (`_initialized` flag)
- Add error handling for I2C failures
- Ensure `init()` is called in `main_task` before use
- Add status logging

#### 2.4 RTC Manager

- Add initialization guard (`_initialized` flag)
- Add error handling for I2C failures
- Ensure `init()` is called in `main_task` before use
- Add status logging

#### 2.5 Audio Handler

- Verify initialization is called properly
- Add error handling for hardware failures
- Ensure proper cleanup on errors

### Phase 3: Update Main Application

#### 3.1 main.cpp Updates

- Remove `#include "display_handler.h"` if present
- Ensure all module `init()` calls happen in proper order:
  1. Power/Battery (already in `app_main()`)
  2. Display/BSP (already in `app_main()`)
  3. Font Manager (already in `main_task`)
  4. RTC Manager
  5. Motion Sensor
  6. Audio Handler
  7. WiFi Manager
  8. WebSocket Client
- Add proper error handling for failed initializations
- Update `ui_manager_init()` call to work without display_handler

#### 3.2 Component Organization

- Verify all components in `components/` folder are properly structured
- Ensure CMakeLists.txt files exist for each component
- Verify include paths are correct (`../components/` from main)

### Phase 4: Clean Up Build System

#### 4.1 CMakeLists.txt

- Remove `display_handler.cpp` from SRCS
- Verify all source files listed actually exist
- Ensure include directories are correct

#### 4.2 Verify Build

- Run clean build to ensure no missing files
- Fix any compilation errors
- Verify all modules compile successfully

## File Structure After Cleanup

```
esp32/firmware/
├── components/           # All hardware components (single source)
│   ├── axp2101/
│   ├── co5300/
│   ├── es7210/
│   ├── es8311/
│   ├── ft3168/
│   ├── pcf85063/
│   └── qmi8658/
├── main/                 # Application code
│   ├── apps/            # Application modules
│   ├── fonts/           # Font files
│   ├── *.cpp/h          # Manager modules
│   ├── main.cpp         # Entry point
│   └── CMakeLists.txt   # Build config
└── [other config files]
```

## Testing Checklist

After cleanup, verify:

- Firmware builds without errors
- All modules initialize properly
- Display works with BSP
- Battery manager doesn't spam I2C errors
- RTC shows correct time/date
- Motion sensor initializes (if hardware present)
- Audio initializes (if hardware present)
- WiFi/WebSocket work
- Apps launch correctly
- No references to deleted files remain

## Notes

- `**src/` folder**: OLD Arduino implementation (uses `Arduino.h`, `Serial.println()`, `setup()/loop()`). This was migrated to ESP-IDF in `main/` folder. Safe to delete.
- `**main/components/**`: Duplicate copies without CMakeLists.txt. The real ESP-IDF components are in `components/` with proper CMakeLists.txt files. Safe to delete.
- `**display_handler**`: Was replaced by BSP during migration - all references must be updated to use BSP functions
- **Migration path**: `src/` (Arduino) → `main/` (ESP-IDF). We're currently working on `main/`, so `src/` is obsolete.
- Some UI states in `ui_manager` may need new BSP-based implementations or removal

