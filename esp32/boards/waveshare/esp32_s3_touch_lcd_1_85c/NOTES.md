# ESP32-S3-Touch-LCD-1.85C V1

Hardware: [Waveshare 1.85C](https://docs.waveshare.net/ESP32-S3-Touch-LCD-1.85C/?variant=ESP32-S3-Touch-LCD-1.85C) **V1** (no Rev2.0 silkscreen). V2 is ES8311/ES7210 and is a different board YAML.

## Round panel

The LCD is **360×360 circular TFT** (ST77916 QSPI). Brookesia System Super is a rectangular phone shell. The stock `small` profile also shrinks type for a 360-wide phone.

Round bring-up uses one **circular safe area** on the 1.85″ 360×360 panel (Wear OS / watchOS):

- Top pocket: status capsule at 12 o’clock (`y ≈ 34`, width 160). Super C++ forces `system_ui_status_y = 0`; the overlay unbinds that so the capsule stays in the circle.
- Content band: about `x 62–298`, `y 64–280` (inscribed; corners stay dead)
- Bottom chin: gesture hint lifted (`24 dp`)
- Apps (Settings / Files / App Store): headers sit **below** the capsule; pages use the same inset
- Launcher: Super C++ hardcodes 112×18 phone tiles; the 360 overlay forces 80×10 / 2 columns so labels stay above the chin
- Keyboard: ITU 3×4 九宫格 (`1`–`9`, last row 中/EN · `0` · ⌫). Composer + OK above the pad; candidates between them. Tap = letter / pinyin; long-press = digit. Passwords open on 123.

Overlay: [`../../firmware/1.85c/round_ui`](../../firmware/1.85c/round_ui). Shell language defaults to `zh_CN` (NotoSans SC via MEMFS FreeType). The board has **16MB flash** and **8MB PSRAM**; after instruction XIP the **heap is ~2.5MB**. File-backed FreeType reads LittleFS from a PSRAM task and reboots (`esp_task_stack_is_sane_cache_disabled`). MEMFS copies the TTF into RAM, so the watch font in `round_ui/fonts/` must stay small. Without FreeType, Super falls back to Montserrat (tofu). The 九宫格 IME lives in firmware `main/modules/round_shell.cpp`.

## V1 vs V2

| | V1 (this board) | V2 |
|---|---|---|
| Audio DAC | PCM5101 | ES8311 |
| Mic | MEMS I2S | ES7210 dual analog |
| First firmware | display + touch + I2S Kitty HAL | ES8311/ES7210 (different YAML) |

Onboard I2C for touch / TCA9554 / RTC is still **GPIO10 SCL / GPIO11 SDA** on V1 (factory Test demo). The V1-vs-V2 “GPIO10/11 NC” table is about header/audio remapping, not that bus.

## Pins (from factory Test)

| Function | GPIO / expander |
|---|---|
| QSPI SCK / D0–D3 / CS | 40 / 46 / 45 / 42 / 41 / 21 |
| Backlight | 5 |
| Touch INT | 4 |
| I2C SDA / SCL | 11 / 10 |
| LCD RST | TCA9554 EXIO2 |
| Touch RST | TCA9554 EXIO1 |
| MEMS I2S mic WS / SCK / SD | 2 / 15 / 39 |
| PCM5101 DIN / LRCK / BCK | 47 / 38 / 48 |

V1 is **mono, no AEC**. Kitty uses half-duplex hold-to-talk. Audio HAL is on (`PCM5101` dummy DAC + digital mic); AFE/WakeNet stay off. Hooking up a speaker is attaching a driver to the PCM5101/NS8002 pads.
