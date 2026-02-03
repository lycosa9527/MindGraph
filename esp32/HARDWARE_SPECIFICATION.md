# ESP32 Smart Response Watch - Hardware Specification

**Hardware**: Waveshare ESP32-S3-Touch-AMOLED-2.06  
**Date**: February 3, 2026

---

## Hardware Overview

The ESP32 Smart Response watch is based on the Waveshare ESP32-S3-Touch-AMOLED-2.06 development board, featuring:
- 410×502 AMOLED display
- Capacitive touch screen
- Dual microphone array with echo cancellation
- Speaker output
- 6-axis motion sensor
- Real-time clock
- Battery management
- Micro SD card support

---

## Hardware Components

### 1. CO5300 Display Driver
**Location**: `components/co5300/`

**Features**:
- QSPI interface for 410×502 AMOLED display
- Full drawing primitives (pixel, line, rect, fill)
- LVGL integration ready

**Interface**: QSPI (Quad SPI)
- QSPI_SI00 (MOSI): GPIO4
- QSPI_SI1 (MISO): GPIO5
- QSPI_SI2 (QUADWP): GPIO6
- QSPI_SI3 (QUADHD): GPIO7
- QSPI_SCL (SCLK): GPIO11

**Control Signals**:
- LCD_CS: GPIO12
- LCD_RESET: GPIO8
- LCD_DC: GPIO13 (Command/Data select)
- LCD_TE: GPIO13 (Tearing Effect - ⚠️ shares pin with DC, may need alternative)

**SPI Host**: SPI2_HOST  
**Frequency**: 40 MHz

---

### 2. FT3168 Touch Controller
**Location**: `components/ft3168/`

**Features**:
- I2C interface for capacitive touch
- Multi-touch support (up to 5 points)
- Gesture recognition
- LVGL input device integration

**I2C Interface**:
- SDA: GPIO15
- SCL: GPIO14
- Address: 0x38

**Control Signals**:
- RESET: GPIO9
- Interrupt: GPIO38

---

### 3. QMI8658 IMU (Motion Sensor)
**Location**: `components/qmi8658/`

**Features**:
- 6-axis motion sensor (accelerometer + gyroscope)
- I2C interface
- Motion data reading functions
- Hand raise detection support

**I2C Interface**:
- SDA: GPIO15
- SCL: GPIO14
- Address: 0x6A

**Control Signals**:
- Interrupt: GPIO21

---

### 4. AXP2101 Power Management IC
**Location**: `components/axp2101/`

**Features**:
- Battery monitoring
- Charging status detection
- Voltage reading
- Charging current control

**I2C Interface**:
- SDA: GPIO15
- SCL: GPIO14
- Address: 0x34

**Control Signals**:
- DSI_PWR_EN: (not specified in diagram)

---

### 5. PCF85063 RTC (Real-Time Clock)
**Location**: `components/pcf85063/`

**Features**:
- Real-time clock with battery backup
- Time/date setting and reading
- BCD conversion utilities

**I2C Interface**:
- SDA: GPIO15
- SCL: GPIO14
- Address: 0x51

**Control Signals**:
- Interrupt: GPIO39

---

### 6. ES7210 Audio ADC (Dual Microphone)
**Location**: `components/es7210/`

**Features**:
- Dual microphone array with AEC (Acoustic Echo Cancellation)
- I2C and I2S interfaces
- Configurable sample rates

**I2C Interface**:
- SDA: GPIO15
- SCL: GPIO14
- Address: 0x40

**I2S Interface** (Capture):
- I2S_DSDIN (BCLK): GPIO40 - Bit Clock
- I2S_LRCK (WS): GPIO45 - Word Select / Left-Right Clock
- I2S_ASDOUT (DIN): GPIO42 - Audio Serial Data Output (input to ESP32)

**Control Signals**:
- PA_CTRL: GPIO46 - Power Amplifier Control

**I2S Port**: I2S_NUM_0

---

### 7. ES8311 Audio Codec (Speaker Output)
**Location**: `components/es8311/`

**Features**:
- Speaker output
- I2C and I2S interfaces
- Volume control

**I2C Interface**:
- SDA: GPIO15
- SCL: GPIO14
- Address: 0x18

**I2S Interface** (Playback):
- I2S_MCLK: GPIO16 - Master Clock
- I2S_SCLK (BCLK): GPIO41 - Serial Clock / Bit Clock
- I2S_LRCK (WS): GPIO45 - Word Select (shared with ES7210)
- I2S_DOUT: GPIO42 - Data Output (⚠️ Note: GPIO42 shared with ES7210 DIN)

**I2S Port**: I2S_NUM_1

**⚠️ IMPORTANT**: ES7210 and ES8311 share GPIO45 (LRCLK) and GPIO42 (data). This works because:
- ES7210 uses GPIO42 as **input** (receives data from microphones)
- ES8311 uses GPIO42 as **output** (sends data to speaker)
- They use different I2S ports (I2S_NUM_0 vs I2S_NUM_1)
- GPIO45 (LRCLK) can be shared if both use the same clock source

---

### 8. Micro SD Card
**Location**: `main/sd_storage.*`

**Features**:
- Micro SD card initialization
- Audio file storage
- Configuration backup/restore
- File management utilities

**SPI/SDIO Interface**:
- MOSI: GPIO1
- SCK: GPIO2
- MISO: GPIO3
- SDCS: GPIO17 - SD Card Select

---

## GPIO Pin Assignments Summary

### I2C Bus (Shared)
All I2C devices share the same bus:
- **I2C_SDA**: GPIO15
- **I2C_SCL**: GPIO14

**Devices on I2C bus**:
- AXP2101 PMIC (0x34)
- FT3168 Touch Controller (0x38)
- QMI8658 IMU (0x6A)
- PCF85063 RTC (0x51)
- ES8311 Audio Codec (0x18)
- ES7210 Audio ADC (0x40)

### System Pins
- **BOOT**: GPIO0
- **PWR**: GPIO10

---

## Manager Classes

### 1. MotionSensor
**Location**: `main/motion_sensor.*`

**Features**:
- Hand raise detection using accelerometer
- Motion data access
- Debouncing and state management

**Uses**: QMI8658 IMU

---

### 2. BatteryManager
**Location**: `main/battery_manager.*`

**Features**:
- Battery level monitoring
- Charging status tracking
- Periodic updates (1 second interval)

**Uses**: AXP2101 PMIC

---

### 3. RTCManager
**Location**: `main/rtc_manager.*`

**Features**:
- Time/date management
- String formatting for display
- Validation checking

**Uses**: PCF85063 RTC

---

### 4. SDStorage
**Location**: `main/sd_storage.*`

**Features**:
- Micro SD card initialization
- Audio file storage
- Configuration backup/restore
- File management utilities

---

### 5. ButtonHandler
**Location**: `main/button_handler.*`

**Features**:
- PWR and BOOT button handling
- Debouncing
- Callback support

**Pins**:
- BOOT: GPIO0
- PWR: GPIO10

---

## Pin Conflict Notes

### ⚠️ GPIO42 Conflict
- **ES7210**: Uses GPIO42 as **input** (I2S_ASDOUT - receives audio from microphones)
- **ES8311**: Uses GPIO42 as **output** (I2S_DOUT - sends audio to speaker)

**Resolution**: 
- Different I2S ports (I2S_NUM_0 vs I2S_NUM_1)
- Direction conflict resolved by I2S driver configuration
- Verify hardware supports this configuration

### ⚠️ GPIO45 Shared
- **ES7210**: Uses GPIO45 as LRCLK (I2S_LRCK)
- **ES8311**: Uses GPIO45 as LRCLK (Word Select)

**Resolution**:
- Both devices can share LRCLK if clocked from same source
- Verify both I2S ports can use the same LRCLK pin

### ⚠️ GPIO21 Conflict
- **QMI8658 IMU**: Uses GPIO21 for interrupt
- **Previous ES8311 config**: Was using GPIO21 for I2S DOUT (now fixed to GPIO42)

**Status**: ✅ Resolved - ES8311 now uses GPIO42

---

## Integration Status

### ✅ Completed Components
- CO5300 Display Driver
- FT3168 Touch Controller
- QMI8658 IMU
- AXP2101 Power Management
- PCF85063 RTC
- ES7210 Audio ADC
- ES8311 Audio Codec
- All Manager Classes

### ✅ Features Enabled
- 410×502 AMOLED display with LVGL
- Capacitive touch input
- Hand raise gesture detection
- Battery level and charging status
- Real-time clock display
- Micro SD card storage
- Side button handling
- Audio capture and playback

### ⚠️ Verification Needed
- GPIO42 bidirectional usage (input for ES7210, output for ES8311)
- GPIO45 shared LRCLK between both I2S ports
- PA_CTRL GPIO46 control for ES7210
- Display initialization sequence
- Hand raise detection thresholds calibration

---

## Code References

**ES7210 Driver**: `components/es7210/es7210_driver.cpp`
- I2C: `Wire.begin(15, 14)`
- I2S BCLK: GPIO40
- I2S LRCLK: GPIO45
- I2S DIN: GPIO42
- PA_CTRL: GPIO46

**ES8311 Driver**: `components/es8311/es8311_driver.cpp`
- I2C: `Wire.begin(15, 14)`
- I2S MCLK: GPIO16
- I2S BCLK: GPIO41
- I2S LRCLK: GPIO45
- I2S DOUT: GPIO42

**Display Handler**: `main/display_handler.*`
- Integrated CO5300 display driver
- Integrated FT3168 touch controller
- LVGL display and input device setup
- Display flush callback for LVGL

**UI Manager**: `main/ui_manager.*`
- Battery level display functions
- Time/date display functions
- UI state management

**Main Application**: `main/main.cpp`
- Initialized all hardware components
- Integrated all managers in main loop
- Battery and time updates in ready state
- Hand raise detection monitoring

---

## Notes

- GPIO pins may need adjustment based on actual hardware wiring
- I2C addresses and register values may need verification
- Hand raise detection thresholds may need calibration
- Display initialization sequence may need adjustment
- Audio echo cancellation parameters may need tuning
- I2S clock sharing between ES7210 and ES8311 needs hardware verification

---

**Last Updated**: February 3, 2026  
**Status**: All hardware components integrated, pin assignments documented
