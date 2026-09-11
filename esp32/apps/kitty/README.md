# Kitty智能体

On the watch, Kitty is a **native Super app** (`com.mindgraph.kitty`), same install path as Settings and Files:

- Provider: `esp32/firmware/1.85c/main/modules/kitty_app.cpp`
- LittleFS package: staged by `round_ui/apply_round_ui.py` into `apps/com.mindgraph.kitty/`
- Face: LVGL while the Super app is Running; Super’s home gesture stops it

This folder is the Brookesia **WASM simulator** stub only. It is not flashed to the 1.85C.

```bash
cd /home/royw/src/MindGraph/esp32/apps/kitty
brookesia build
brookesia simulate --resolution 360x360
```

Opens the WASM Super shell at http://127.0.0.1:8787. Tap **Kitty智能体** on the launcher.
