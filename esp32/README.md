# ESP32 / Brookesia

MindGraph device work for the Waveshare **ESP32-S3-Touch-LCD-1.85C V1** (round 360×360). Docs: [Waveshare 1.85C](https://docs.waveshare.net/ESP32-S3-Touch-LCD-1.85C/?variant=ESP32-S3-Touch-LCD-1.85C).

| Path | Purpose |
|------|---------|
| `firmware/1.85c` | System Super firmware (WSL IDF 6.1 build; copy merged bin to Desktop to flash) |
| `boards/waveshare/esp32_s3_touch_lcd_1_85c` | Custom HAL for V1 display + touch |
| `apps/kitty` | Kitty智能体 JS app — `brookesia simulate --resolution 360x360` |

The V1 HAL is **360×360**. Super is a rectangular shell; [`firmware/1.85c/round_ui`](firmware/1.85c/round_ui) applies a circular safe area (status capsule, launcher, Settings/Files/App Store, 九宫格 keyboard with Chinese T9). Native Super apps: **Kitty智能体** (voice), **语音笔记** (recorder — transcript on top, pause / mic / stop, 生成思维导图), and **校本培训** (instructor remote — inset puzzle pad plus school / 开始 pills). There is no Brookesia JS `.bpk` remote.

V1 audio is PCM5101, not ES8311. First firmware image is display/touch only.

IDF: **6.1** in WSL (`~/esp/esp-idf`, conda env `idf61`). Do not use `C:\Espressif\frameworks\esp-idf-v5.5.2`.

Do **not** clone the Brookesia GitHub repo into MindGraph. Firmware pulls `0.8.*` from the ESP Component Registry. See [`firmware/1.85c/README.md`](firmware/1.85c/README.md).

Do not run frontend `npm run build` for this tree.
