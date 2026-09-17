# System Super firmware (round watch)

You do **not** clone [espressif/esp-brookesia](https://github.com/espressif/esp-brookesia) into this repo. This folder is the official `examples/system/super` tree with registry `0.8.*` deps.

**Current board:** [Waveshare ESP32-S3-Touch-AMOLED-1.75C](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-1.75C) — 466×466 CO5300, ES8311 + ES7210 AEC. YAML: [`../../boards/waveshare/esp32_s3_touch_amoled_1_75c`](../../boards/waveshare/esp32_s3_touch_amoled_1_75c). The 1.85C V1 LCD board remains under `esp32_s3_touch_lcd_1_85c`.

Use **ESP-IDF 6.1** in WSL (`~/esp/esp-idf`, conda env `idf61`). Not Windows `C:\Espressif\frameworks\esp-idf-v5.5.2`.

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate idf61
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
. ~/esp/esp-idf/export.sh
cd /home/royw/src/MindGraph/esp32/firmware/1.85c
idf.py set-target esp32s3
idf.py gen-bmgr-config -b esp32_s3_touch_amoled_1_75c -c ../../boards
idf.py build
```

Do not flash from WSL. After `idf.py merge-bin`, copy the image to the Windows Desktop and flash with Waveshare `flash_download_tool` at offset `0x00`.

Round overlay ([`round_ui/`](round_ui)) is applied when the littlefs image is built: circular safe area, zh_CN, and the 九宫格 IME.

The `model` partition is **3072K** so Super Kitty can pack WakeNet plus English MultiNet (`mn5q8_en`, ~2.1MB) for **ni hao kitty**. Factory stays 9400K; littlefs_data shrinks to 20212K. A full 0x00 merge-bin flash is required after this table change.

Kitty watch is an LVGL face on the 360 panel (Kitty智能体, mascot, library chip, round mic). **超级小猫** (`com.mindgraph.super_kitty`) is a second voice tile: no mic button, centered 图库, always-on AFE AEC while Running, replies after English MultiNet hears **ni hao kitty**. **语音笔记** is a third Super tile matching the mobile recorder: live words on top, pause / 录 / stop, then 生成思维导图. It streams PCM to `/api/ws/voice-notes` and finishes through `POST /api/voice-notes/watch/finish`. **校本培训** is an inset puzzle pad (上一页 | 下一页, full-width 停止, 锁定 | 自由) plus bottom school / 开始 pills and a Kitty-style green/orange status disk. It calls `/api/training` with the same baked `mgat_` as Kitty. The account must be the session lead; `FEATURE_TRAINING` must be on. **演讲模式** is a fourth Super tile (`com.mindgraph.slides`) for the canvas slide HUD: 一级分支 | 深度遍历, 上一页 | 下一页, 自动轮播, Kitty-style 图库 plus green **开始** / red **退出**. It polls `/api/slides/remote` with the same token. Pick a diagram and tap 开始 to open it on desktop canvas in 演讲模式. Set `CONFIG_MINDGRAPH_KITTY_SERVER_URL`, `CONFIG_MINDGRAPH_KITTY_MGAT`, and `CONFIG_MINDGRAPH_KITTY_ACCOUNT` in gitignored `sdkconfig.defaults.local`. Auth is flash-time account + `mgat_` only.

`managed_components/` is gitignored; the first configure downloads Brookesia from the [component registry](https://components.espressif.com/).
