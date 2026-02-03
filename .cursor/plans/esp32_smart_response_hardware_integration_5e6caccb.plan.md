---
name: ESP32 Smart Response Hardware Integration
overview: "Update ESP32 Smart Response implementation plan with Waveshare ESP32-S3-Touch-AMOLED-2.06 specific hardware components: CO5300 display driver, FT3168 touch controller, QMI8658 IMU, PCF85063 RTC, AXP2101 power management, and Micro SD card support."
todos:
  - id: co5300-display-driver
    content: Implement CO5300 display driver integration with QSPI interface for 410×502 AMOLED display
    status: completed
  - id: ft3168-touch-controller
    content: Implement FT3168 capacitive touch controller via I2C for touch interactions
    status: completed
  - id: qmi8658-imu-integration
    content: Integrate QMI8658 6-axis IMU for hand raise detection and motion sensing
    status: completed
  - id: axp2101-battery-management
    content: Implement AXP2101 power management for battery monitoring and charging status
    status: completed
  - id: pcf85063-rtc-integration
    content: Integrate PCF85063 RTC chip for time/date display and timestamping
    status: completed
  - id: micro-sd-storage
    content: Add Micro SD card support for audio storage, config backup, and custom assets
    status: completed
  - id: button-handler
    content: Implement PWR and BOOT button handlers for custom functions
    status: completed
  - id: motion-hand-raise
    content: Implement hand raise detection using QMI8658 accelerometer
    status: completed
  - id: battery-ui-integration
    content: Add battery level indicator and charging status to UI
    status: completed
  - id: time-display-ui
    content: Add current time/date display to ready screen using PCF85063
    status: completed
isProject: false
---

# ESP32 Smart Response Hardware Integration Update

## Hardware Specifications - Waveshare ESP32-S3-Touch-AMOLED-2.06

### Core Components

**ESP32-S3R8 Microcontroller:**

- Xtensa 32-bit LX7 dual-core processor @ 240MHz
- 512KB SRAM + 384KB ROM
- 8MB PSRAM (stacked)
- 32MB Flash
- 2.4GHz Wi-Fi (802.11 b/g/n) + Bluetooth 5 (LE)
- On-board antenna

**Display System:**

- **2.06" AMOLED Display**: 410×502 resolution, 16.7M colors
- **CO5300 Display Driver**: QSPI interface (doesn't consume GPIO pins)
- **FT3168 Capacitive Touch Controller**: I2C interface
- Touch support for UI interactions

**Motion Sensor:**

- **QMI8658 6-Axis IMU**: 3-axis accelerometer + 3-axis gyroscope
- I2C interface
- Use cases:
  - Detect hand raise gesture (motion detection)
  - Step counting
  - Activity detection
  - Orientation detection

**Real-Time Clock:**

- **PCF85063 RTC Chip**: Connected via AXP2101
- Battery-backed (uninterrupted power)
- Use cases:
  - Display current time/date
  - Timestamp events
  - Schedule-based features

**Power Management:**

- **AXP2101 Power Management IC**
- Features:
  - Battery charging/discharging management
  - Multiple voltage outputs
  - Battery level monitoring
  - Power optimization
- 3.7V MX1.25 battery connector

**Storage:**

- **Micro SD Card Slot**: External storage
- Use cases:
  - Store audio files
  - Configuration backups
  - Logs and diagnostics
  - Custom assets (wallpapers, icons)

**Audio Hardware:**

- **ES8311 Audio Codec**: I2S interface (speaker output + mic input)
- **ES7210 Dual Microphone Array**: PDM interface (echo cancellation)

**User Interface:**

- **Side Buttons**: PWR and BOOT (customizable functions)
- **Type-C USB**: Power and data transfer
- **External Interfaces**: 1x I2C, 1x UART, 1x USB pads

## Implementation Updates Required

### 1. Display Handler (`display_handler.cpp`)

**CO5300 Driver Integration:**

```cpp
// Initialize CO5300 display driver via QSPI
#include "CO5300.h"

bool display_init() {
    // Initialize CO5300 QSPI display driver
    CO5300.begin();
    CO5300.setRotation(0);
    CO5300.fillScreen(BLACK);
    
    // Initialize LVGL with CO5300 driver
    lv_disp_draw_buf_init(&draw_buf, buf1, buf2, DISP_BUF_SIZE);
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = 410;
    disp_drv.ver_res = 502;
    disp_drv.flush_cb = display_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);
    
    return true;
}
```

**FT3168 Touch Controller Integration:**

```cpp
// Initialize FT3168 capacitive touch via I2C
#include "FT3168.h"

void touch_init() {
    FT3168.begin();
    FT3168.setTouchCallback(touch_event_handler);
}

void touch_event_handler(uint16_t x, uint16_t y, uint8_t gesture) {
    // Forward touch events to LVGL
    lv_indev_data_t data;
    data.point.x = x;
    data.point.y = y;
    data.state = (gesture > 0) ? LV_INDEV_STATE_PRESSED : LV_INDEV_STATE_RELEASED;
    lv_indev_send(touch_indev, &data);
}
```

### 2. Motion Detection (`motion_sensor.cpp`)

**QMI8658 IMU Integration:**

```cpp
#include "QMI8658.h"

class MotionSensor {
    QMI8658 imu;
    
public:
    bool init() {
        return imu.begin();
    }
    
    bool detectHandRaise() {
        // Detect upward acceleration pattern
        float accel[3];
        imu.readAccelerometer(accel);
        
        // Check for upward motion (Z-axis positive acceleration)
        if (accel[2] > 1.5) {
            return true;
        }
        return false;
    }
    
    void getMotion(float* accel, float* gyro) {
        imu.readAccelerometer(accel);
        imu.readGyroscope(gyro);
    }
};
```

**Use Cases:**

- **Hand Raise Detection**: Student raises watch to speak
- **Activity Monitoring**: Detect when watch is being used
- **Orientation**: Adjust UI based on watch orientation

### 3. Battery Management (`battery_manager.cpp`)

**AXP2101 Power Management:**

```cpp
#include "AXP2101.h"

class BatteryManager {
    AXP2101 pmic;
    
public:
    bool init() {
        return pmic.begin();
    }
    
    int getBatteryLevel() {
        // Read battery percentage from AXP2101
        return pmic.getBatteryPercentage();
    }
    
    bool isCharging() {
        return pmic.isCharging();
    }
    
    float getBatteryVoltage() {
        return pmic.getBatteryVoltage();
    }
};
```

**UI Integration:**

- Display battery icon with percentage
- Show charging indicator
- Low battery warnings
- Power optimization modes

### 4. Real-Time Clock (`rtc_manager.cpp`)

**PCF85063 RTC Integration:**

```cpp
#include "PCF85063.h"

class RTCManager {
    PCF85063 rtc;
    
public:
    bool init() {
        return rtc.begin();
    }
    
    void setTime(uint8_t hour, uint8_t minute, uint8_t second) {
        rtc.setTime(hour, minute, second);
    }
    
    void setDate(uint8_t day, uint8_t month, uint16_t year) {
        rtc.setDate(day, month, year);
    }
    
    void getTime(uint8_t* hour, uint8_t* minute, uint8_t* second) {
        rtc.getTime(hour, minute, second);
    }
    
    void getDate(uint8_t* day, uint8_t* month, uint16_t* year) {
        rtc.getDate(day, month, year);
    }
};
```

**UI Integration:**

- Display current time on ready screen
- Show date on status screens
- Timestamp voice interactions
- Schedule-based features

### 5. Micro SD Card Support (`sd_storage.cpp`)

**SD Card Integration:**

```cpp
#include <SD.h>
#include <SPI.h>

class SDStorage {
public:
    bool init() {
        return SD.begin(SD_CS_PIN);
    }
    
    bool saveAudio(const char* filename, uint8_t* data, size_t len) {
        File file = SD.open(filename, FILE_WRITE);
        if (!file) return false;
        file.write(data, len);
        file.close();
        return true;
    }
    
    bool loadConfig(const char* filename, char* buffer, size_t len) {
        File file = SD.open(filename, FILE_READ);
        if (!file) return false;
        file.readBytes(buffer, len);
        file.close();
        return true;
    }
};
```

**Use Cases:**

- Store audio recordings
- Backup configuration
- Store custom wallpapers/icons
- Log diagnostics

### 6. Button Handling (`button_handler.cpp`)

**Side Button Integration:**

```cpp
#define BUTTON_PWR_PIN 0
#define BUTTON_BOOT_PIN 0

class ButtonHandler {
public:
    void init() {
        pinMode(BUTTON_PWR_PIN, INPUT_PULLUP);
        pinMode(BUTTON_BOOT_PIN, INPUT_PULLUP);
    }
    
    bool isPWRPressed() {
        return digitalRead(BUTTON_PWR_PIN) == LOW;
    }
    
    bool isBOOTPressed() {
        return digitalRead(BUTTON_BOOT_PIN) == LOW;
    }
    
    void handleButtons() {
        if (isPWRPressed()) {
            // Custom function: Wake up, activate voice, etc.
            onPWRButton();
        }
        if (isBOOTPressed()) {
            // Custom function: Settings, menu, etc.
            onBOOTButton();
        }
    }
};
```

## Updated File Structure

```
esp32/firmware/
├── main/
│   ├── main.cpp
│   ├── wifi_manager.*
│   ├── config_manager.*
│   ├── websocket_client.*
│   ├── audio_handler.*
│   ├── display_handler.*      # Updated: CO5300 + FT3168
│   ├── ui_manager.*
│   ├── motion_sensor.*        # NEW: QMI8658 IMU
│   ├── battery_manager.*      # NEW: AXP2101 PMIC
│   ├── rtc_manager.*          # NEW: PCF85063 RTC
│   ├── sd_storage.*           # NEW: Micro SD card
│   └── button_handler.*       # NEW: PWR/BOOT buttons
├── components/
│   ├── co5300/                # NEW: CO5300 display driver
│   │   ├── CO5300.h
│   │   └── CO5300.cpp
│   ├── ft3168/                # NEW: FT3168 touch controller
│   │   ├── FT3168.h
│   │   └── FT3168.cpp
│   ├── qmi8658/               # NEW: QMI8658 IMU
│   │   ├── QMI8658.h
│   │   └── QMI8658.cpp
│   ├── axp2101/               # NEW: AXP2101 PMIC
│   │   ├── AXP2101.h
│   │   └── AXP2101.cpp
│   ├── pcf85063/              # NEW: PCF85063 RTC
│   │   ├── PCF85063.h
│   │   └── PCF85063.cpp
│   ├── es7210/
│   ├── es8311/
│   └── lvgl_ui/
└── platformio.ini
```

## PlatformIO Configuration Updates

**Add Hardware Libraries:**

```ini
[env:waveshare-esp32-s3-touch-amoled]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200
upload_speed = 921600

lib_deps =
    bblanchon/ArduinoJson@^6.21.3
    links2004/WebSockets@^2.4.1
    lvgl/lvgl@^8.3.11
    adafruit/Adafruit Unified Sensor@^1.1.9
    adafruit/SD@^2.2.2
    # Waveshare hardware libraries (if available)
    # Or implement custom drivers

build_flags =
    -DBOARD_HAS_PSRAM
    -mfix-esp32-psram-cache-issue
    -DCORE_DEBUG_LEVEL=3
    -DWAVESHARE_AMOLED_2_06
    -DDISPLAY_WIDTH=410
    -DDISPLAY_HEIGHT=502
```

## Enhanced Features

### 1. Hand Raise Detection

- Use QMI8658 accelerometer to detect upward motion
- Automatically activate voice input when hand is raised
- Visual feedback on display

### 2. Battery-Aware Operations

- Monitor battery level via AXP2101
- Adjust brightness based on battery
- Power-saving modes when battery low
- Charging indicator

### 3. Time Display

- Show current time on ready screen
- Timestamp voice interactions
- Schedule-based features

### 4. Touch Interactions

- Navigate UI with touch gestures
- Swipe to change screens
- Tap to interact with elements

### 5. Storage Capabilities

- Store audio recordings on SD card
- Backup/restore configuration
- Custom assets (wallpapers, icons)

## Implementation Priority

1. **Phase 1**: CO5300 display + FT3168 touch (essential for UI)
2. **Phase 2**: AXP2101 battery management (user experience)
3. **Phase 3**: QMI8658 motion detection (hand raise feature)
4. **Phase 4**: PCF85063 RTC (time display)
5. **Phase 5**: Micro SD card (storage features)

## Notes

- **CO5300 Driver**: May need custom implementation or Waveshare library
- **FT3168 Touch**: I2C interface, standard touch library pattern
- **QMI8658**: Standard IMU library pattern
- **AXP2101**: Power management library required
- **PCF85063**: Standard RTC library pattern
- **Micro SD**: Standard Arduino SD library

All hardware components are standard interfaces (I2C, QSPI, SPI) and should integrate cleanly with existing ESP32 Arduino framework.