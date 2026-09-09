# ESP32-S3-Touch-LCD-1.85C V1

Hardware: [Waveshare 1.85C](https://docs.waveshare.net/ESP32-S3-Touch-LCD-1.85C/?variant=ESP32-S3-Touch-LCD-1.85C) **V1** (no Rev2.0 silkscreen). V2 is ES8311/ES7210 and is a different board YAML.

## Round panel

The LCD is **360×360 circular TFT** (ST77916 QSPI). Brookesia System Super is a rectangular phone shell. The stock `small` profile also shrinks type for a 360-wide phone.

Round bring-up uses one **circular safe area** on the 1.85″ 360×360 panel (Wear OS / watchOS):

- Top pocket: status capsule at 12 o’clock (`y ≈ 34`, width 160). Super C++ forces `system_ui_status_y = 0`; the overlay unbinds that so the capsule stays in the circle.
- Content band: about `x 62–298`, `y 64–280` (inscribed; corners stay dead)
- Bottom chin: gesture hint lifted (`24 dp`)
- Apps (Settings / Files / App Store): headers sit **below** the capsule; pages use the same inset
- Launcher: 2×2 watch tiles (`56` icon + `18` label) so app names stay inside the disc
- Keyboard: Chinese 九宫格 (T9 pinyin + candidates) and English 九宫格 multi-tap

Overlay: [`../../firmware/1.85c/round_ui`](../../firmware/1.85c/round_ui). Shell language defaults to `zh_CN` (NotoSans SC). The 九宫格 IME lives in firmware `main/modules/round_shell.cpp`.

## V1 vs V2

| | V1 (this board) | V2 |
|---|---|---|
| Audio DAC | PCM5101 | ES8311 |
| Mic | MEMS I2S | ES7210 dual analog |
| First firmware | display + touch only | can enable Brookesia audio later |

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
