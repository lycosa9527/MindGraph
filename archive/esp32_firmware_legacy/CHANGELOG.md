# ESP32 Firmware Changelog

All notable changes to the ESP32 firmware will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Loading Screen Leftover on Standby (Critical)**: Fixed screen artifacts where loading screen text and progress bar would persist/overlap on standby screen. Root cause was `display_clear_before_switch()` using `lv_obj_clean()` which deleted screen children, creating dangling pointers that caused memory corruption when `loading_screen_hide()` tried to access them. Solution:
  - Removed premature `display_clear_before_switch()` call in `main.cpp` before `loading_screen_hide()`
  - Removed unnecessary `display_clear_before_switch()` in `standby_screen_show()` and `launcher_show()`
  - Refactored `display_clear_screen()` to not use `lv_obj_clean()` - screens hold static pointers to their children
  - `lv_screen_load()` handles screen transitions properly; no manual clearing needed
- **I2C Bus GPIO Conflicts**: Resolved GPIO conflicts where custom I2C bus manager and BSP I2C were both attempting to use GPIO pins 14/15 on different I2C ports (`I2C_NUM_0` and `I2C_NUM_1`). Modified `get_i2c_bus_handle()` to use BSP's I2C bus handle (`bsp_i2c_get_handle()`) instead of creating a separate I2C bus, ensuring all I2C devices use a single shared bus.
- **I2C Device Detection**: Fixed `scan_i2c_devices()` function to perform a 1-byte dummy read instead of a 0-byte transmit, correctly detecting I2C devices and avoiding `ESP_ERR_INVALID_ARG` errors.
- **LCD SPI Queue Overflow**: Increased SPI transaction queue depth from 10 to 30 in `SH8601_PANEL_IO_QSPI_CONFIG` macro to prevent "spi transmit (queue) color failed" errors during screen transitions.
- **Screen Residue During Transitions**: Fixed screen residue issues by implementing display clearing utilities and proper refresh timing before screen transitions.
- **Screen Transition Timing**: Improved screen transition logic to prevent SPI queue overflow by adding appropriate delays and refresh synchronization.

### Added
- **Display Utilities Module**: New `utils/display_utils.cpp` and `utils/display_utils.h` providing:
  - `display_clear_screen()`: Sets screen background color (does NOT delete children - safe for screen transitions)
  - `display_clear_before_switch()`: **DEPRECATED** - Do not use for screen transitions; use `lv_screen_load()` directly
  - `display_force_full_refresh()`: Forces a full screen refresh to ensure complete rendering
- **Hardware Specification Documentation**: Created `HARDWARE_SPEC.md` documenting Waveshare ESP32-S3-Touch-AMOLED-2.06 GPIO pin assignments:
  - I2C pins: GPIO 14 (SCL), GPIO 15 (SDA)
  - LCD SPI pins: GPIO 12 (CS), GPIO 13 (TE)
  - SD card pins: GPIO 1, 2, 3, 17
  - Audio, buttons, RTC, IMU, PMIC pin assignments
- **Code Verification Documentation**: Created `CODE_VERIFICATION.md` documenting I2C bus fixes and verification of GPIO pin assignments.

### Changed
- **I2C Bus Manager**: Modified `drivers/i2c_bus_manager.cpp` to use BSP's I2C bus handle instead of creating a separate I2C bus, eliminating GPIO conflicts and following BSP design patterns.
- **Screen Transition Pattern**: Established correct screen transition pattern across all screens:
  1. Call `old_screen_hide()` first (sets hidden flags on objects, objects still exist)
  2. Call `lv_screen_load(new_screen)` which properly handles the transition
  3. Optionally call `display_force_full_refresh()` after load
  - **DO NOT** call `display_clear_before_switch()` or `lv_obj_clean()` on screens - they delete objects that modules hold static pointers to
- **Loading Screen**: Updated `screens/loading_screen.cpp` to add delay after hiding objects, allowing LVGL refresh task to process SPI queue properly.
- **Standby Screen**: Simplified `screens/standby_screen.cpp` to use proper LVGL screen transition (removed problematic `display_clear_before_switch()` call).
- **Launcher Screen**: Simplified `screens/launcher.cpp` screen transitions (removed problematic `display_clear_before_switch()` call).
- **Main Application**: Fixed `core/main.cpp` to call `loading_screen_hide()` BEFORE any display clearing, preventing dangling pointer access.
- **SPI Configuration**: Increased `trans_queue_depth` from 10 to 30 in `managed_components/waveshare__esp_lcd_sh8601/include/esp_lcd_sh8601.h` to accommodate higher SPI transaction rates during screen updates.

### Technical Details

#### I2C Bus Architecture Fix
- **Problem**: Both custom I2C bus manager (`I2C_NUM_0`) and BSP I2C (`I2C_NUM_1`) were attempting to use the same physical GPIO pins (14/15), causing GPIO conflict warnings.
- **Solution**: Modified `get_i2c_bus_handle()` to retrieve and use the BSP's I2C bus handle (`bsp_i2c_get_handle()`) instead of creating a new I2C bus. This ensures:
  - Single I2C bus for all devices (RTC, IMU, PMIC, audio codec, touch controller)
  - No GPIO conflicts
  - Proper initialization order (BSP initializes I2C during display startup)
  - Consistent with BSP design patterns

#### Display/SPI Improvements
- **Problem**: SPI queue overflow errors (`spi transmit (queue) color failed`) and screen residue during transitions.
- **Solution**: 
  - Increased SPI queue depth from 10 to 30 transactions
  - Implemented display clearing before screen transitions
  - Added proper refresh timing with delays to allow SPI queue processing
  - Force full screen refresh after screen loads

#### Verified I2C Devices
After fixes, the following I2C devices are successfully detected:
- `0x18` - ES8311 (Audio codec - speaker)
- `0x34` - AXP2101 (PMIC - power management)
- `0x38` - FT3168 (Touch controller)
- `0x40` - ES7210 (Audio codec - microphone)
- `0x51` - PCF85063 (RTC - real-time clock)
- `0x6B` - QMI8658 (IMU - motion sensor)

### Known Issues
- **QMI8658 IMU Communication**: The QMI8658 IMU still reports initialization errors (`ESP_ERR_INVALID_STATE`, `Chip ID mismatch: expected 0x05, got 0x00`). This appears to be a device-specific communication issue unrelated to I2C bus setup, as other I2C devices initialize successfully.

---

## Previous Versions

### Initial Implementation
- ESP32-S3 firmware for Waveshare ESP32-S3-Touch-AMOLED-2.06 development board
- LVGL-based UI with loading screen, standby screen, and launcher
- I2C communication with RTC (PCF85063), IMU (QMI8658), PMIC (AXP2101)
- SPI communication with LCD display (SH8601) and SD card
- Audio support via ES7210 (mic) and ES8311 (speaker)
- WiFi connectivity and WebSocket client
- Battery management and RTC synchronization
- Smart Response app and Dify XiaoZhi app integration
- USB Mass Storage Class (MSC) support
- Font management with Chinese font support
- Button handling for power and boot buttons
- State coordination between screens and apps
