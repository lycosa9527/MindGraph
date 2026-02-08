# Waveshare ESP32-S3-Touch-AMOLED-2.06 Hardware Specification

## GPIO Pin Assignments (Per Waveshare Official Documentation)

### I2C Bus (GPIO 14/15)
**ALL I2C devices share the same I2C bus:**
- **GPIO 14**: I2C SCL (Clock)
- **GPIO 15**: I2C SDA (Data)

**I2C Devices:**
- **AXP2101** (PMIC): Address 0x34
- **FT3168** (Touch Controller): Address 0x38
- **PCF85063** (RTC): Address 0x51
- **QMI8658** (6-Axis IMU): Address 0x6B or 0x6A
- **ES8311** (Speaker Codec): Address 0x18
- **ES7210** (Microphone ADC): Address 0x40

### Display (CO5300) - QSPI Interface
- **GPIO 4**: QSPI_SIO0
- **GPIO 5**: QSPI_SI1
- **GPIO 6**: QSPI_SI2
- **GPIO 7**: QSPI_SI3
- **GPIO 11**: QSPI_SCL
- **GPIO 12**: LCD_CS (Chip Select) ⚠️ **DO NOT USE FOR I2C**
- **GPIO 13**: LCD_TE (Tearing Effect) ⚠️ **DO NOT USE FOR I2C**
- **GPIO 8**: LCD_RESET

### Touch Controller (FT3168)
- **GPIO 14**: I2C SCL (shared with other I2C devices)
- **GPIO 15**: I2C SDA (shared with other I2C devices)
- **GPIO 38**: Touch Interrupt
- **GPIO 9**: Touch Reset

### Micro SD Card - SPI Interface
- **GPIO 1**: SD_MOSI
- **GPIO 2**: SD_SCK
- **GPIO 3**: SD_MISO
- **GPIO 17**: SD_CS (Chip Select)

**Note**: SD card pins (GPIO 1/2/3/17) do NOT conflict with I2C pins (GPIO 14/15).

### Audio Codec (ES8311 & ES7210)
**I2C Interface:**
- **GPIO 14**: I2C SCL (shared)
- **GPIO 15**: I2C SDA (shared)

**I2S Interface:**
- **GPIO 16**: I2S_MCLK
- **GPIO 40**: I2S_DSDIN (Data In)
- **GPIO 41**: I2S_SCLK
- **GPIO 42**: I2S_ASDOUT (Data Out)
- **GPIO 45**: I2S_LRCK
- **GPIO 46**: PA_CTRL (Power Amplifier Control)

### Buttons
- **GPIO 0**: BOOT Button
- **GPIO 10**: PWR Button/Input

### RTC (PCF85063)
- **GPIO 14**: I2C SCL (shared)
- **GPIO 15**: I2C SDA (shared)
- **GPIO 39**: RTC Interrupt

### IMU (QMI8658)
- **GPIO 14**: I2C SCL (shared)
- **GPIO 15**: I2C SDA (shared)
- **GPIO 21**: IMU Interrupt

### Power Management (AXP2101)
- **GPIO 14**: I2C SCL (shared)
- **GPIO 15**: I2C SDA (shared)
- **DSI_PWR_EN**: Connected to Display power enable

---

## Critical Pin Conflicts to Avoid

### ❌ WRONG: GPIO 12/13 for I2C
- **GPIO 12** = LCD_CS (Chip Select) - Required for LCD SPI communication
- **GPIO 13** = LCD_TE (Tearing Effect) - Required for LCD synchronization
- **Using GPIO 12/13 for I2C will cause LCD communication failures!**

### ✅ CORRECT: GPIO 14/15 for I2C
- **GPIO 14** = I2C SCL (Standard I2C clock pin)
- **GPIO 15** = I2C SDA (Standard I2C data pin)
- **All I2C devices MUST use these pins per Waveshare specification**

---

## I2C Bus Architecture

### Single Shared I2C Bus
All I2C devices share the same physical bus (GPIO 14/15) but use different I2C addresses:
- This is standard I2C practice - multiple devices on one bus
- Each device has a unique 7-bit address
- No GPIO conflicts as long as all devices use GPIO 14/15

### BSP vs Custom I2C Bus
**Issue**: BSP provides `bsp_i2c_init()` which uses GPIO 14/15 on `I2C_NUM_1`
**Our code**: Creates custom I2C bus on GPIO 14/15 using `I2C_NUM_0`

**Solution Options**:
1. **Use BSP I2C bus** (Recommended): Call `bsp_i2c_get_handle()` instead of creating our own
2. **Keep custom bus**: Ensure initialization order doesn't conflict (BSP uses I2C_NUM_1, we use I2C_NUM_0)

---

## Implementation Notes

1. **Always use GPIO 14/15 for I2C** - Never use GPIO 12/13
2. **GPIO 12/13 are LCD control pins** - Must remain available for LCD
3. **SD card uses GPIO 1/2/3/17** - No conflict with I2C pins
4. **All I2C devices share the same bus** - Use different addresses, not different GPIOs

---

## References
- Waveshare ESP32-S3-Touch-AMOLED-2.06 Hardware Specification Diagram
- BSP Header: `esp32_s3_touch_amoled_2_06.h`
- Official Waveshare Wiki: https://www.waveshare.com/wiki/ESP32-S3-Touch-AMOLED-2.06
