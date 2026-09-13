# ESP32 / Brookesia

MindGraph device work for Waveshare round Super watches.

| Path | Purpose |
|------|---------|
| `firmware/1.85c` | System Super firmware (WSL IDF 6.1; merge-bin then flash) |
| `boards/waveshare/esp32_s3_touch_amoled_1_75c` | **Current:** 1.75C AMOLED 466×466, ES8311 + ES7210 AEC |
| `boards/waveshare/esp32_s3_touch_lcd_1_85c` | 1.85C V1 LCD 360×360, PCM5101 + MEMS (no AEC) |
| `apps/kitty` | Kitty智能体 JS app |

**1.75C** docs: [Waveshare 1.75C](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C). Dual mics + ES7210 playback reference enable Brookesia AFE (`MIC_LAYOUT=RMNN`). Super is a rectangular shell; [`firmware/1.85c/round_ui`](firmware/1.85c/round_ui) applies a circular safe area for 360 and 466. Native Super apps: **Kitty智能体**, **语音笔记**, **校本培训**, **演讲模式**.

IDF: **6.1** in WSL (`~/esp/esp-idf`, conda env `idf61`). Do not use `C:\Espressif\frameworks\esp-idf-v5.5.2`.

Do **not** clone the Brookesia GitHub repo into MindGraph. Firmware pulls `0.8.*` from the ESP Component Registry. See [`firmware/1.85c/README.md`](firmware/1.85c/README.md).

Do not run frontend `npm run build` for this tree.
