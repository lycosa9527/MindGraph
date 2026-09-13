# ESP32-S3-Touch-AMOLED-1.75C

Hardware: [Waveshare 1.75C](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C)
SKU 33691 / 33692. Brookesia board id `esp32_s3_touch_amoled_1_75c`.

This is not the 1.85C LCD watch and not the 1.75 (non-C) dev board. Pins match
Waveshare’s 1.75C schematic / BSP, not the 1.75 MCLK=GPIO42 map.

## Panel

| | |
|---|---|
| Display | CO5300 QSPI AMOLED **466×466** |
| Touch | CST9217 I2C (SDA 15 / SCL 14, INT 11, RST 2) |
| LCD RST | GPIO 1 |
| QSPI | SIO0–3 GPIO4–7, SCLK 38, CS 12 |
| Power | AXP2101 (brightness is panel command, not LEDC) |
| Flash | 32MB GigaDevice; littlefs uses the extra space (CJK font fills 6.6MB) |
| App | factory 9400K (AFE + Super overflowed 8800K by ~430KB) |

## Audio / AEC

| | |
|---|---|
| DAC | ES8311 (I2C 0x18 / 8-bit 0x30) |
| ADC | ES7210 (I2C 0x40 / 8-bit 0x80) |
| I2S | MCLK 16, BCLK 9, LRCK 45, DOUT 8, DIN 10, PA 46 |
| Mics | MIC1 + MIC2 onboard; MIC3 = ES8311 playback reference; MIC4 NC |

Software AEC uses Brookesia Audio Processor + `MIC_LAYOUT="RMNN"` (ref, mic, none,
none). Dual analog mics plus the echo reference are what ES7210 is for.

Keep `CONFIG_SPIRAM_FETCH_INSTRUCTIONS=n`. Mapping `.text` into the 8MB PSRAM
window overflows `iram0_2_seg` once Super + AFE are linked.

Custom CO5300 backlight must register `group_id=display_lcd`. An empty id leaves
the panel unbound; Super then never applies brightness and AMOLED stays black.

LVGL must use the PSRAM SPI profile. Internal SRAM cannot hold 466-wide double
strips after AFE/Wi-Fi, which leaves a powered white panel with no frames.

## Build

```bash
cd /home/royw/src/MindGraph/esp32/firmware/1.85c
idf.py gen-bmgr-config -b esp32_s3_touch_amoled_1_75c -c ../../boards
idf.py build
```
