# System Super firmware (1.85C V1)

You do **not** clone [espressif/esp-brookesia](https://github.com/espressif/esp-brookesia) into this repo. This folder is the official `examples/system/super` tree with registry `0.8.*` deps. Custom board YAML is [`../../boards/waveshare/esp32_s3_touch_lcd_1_85c`](../../boards/waveshare/esp32_s3_touch_lcd_1_85c).

Use **ESP-IDF 6.1** in WSL (`~/esp/esp-idf`, conda env `idf61`). Not Windows `C:\Espressif\frameworks\esp-idf-v5.5.2`.

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate idf61
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
. ~/esp/esp-idf/export.sh
cd /home/royw/src/MindGraph/esp32/firmware/1.85c
idf.py set-target esp32s3
idf.py gen-bmgr-config -b esp32_s3_touch_lcd_1_85c -c ../../boards
idf.py build
```

Do not flash from WSL. After `idf.py merge-bin`, copy the image to the Windows Desktop and flash with Waveshare `flash_download_tool` at offset `0x00`.

Round overlay ([`round_ui/`](round_ui)) is applied when the littlefs image is built: circular safe area, zh_CN, and the 九宫格 IME.

`managed_components/` is gitignored; the first configure downloads Brookesia from the [component registry](https://components.espressif.com/).
