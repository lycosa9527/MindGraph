#!/usr/bin/env python3
"""Put Super LVGL draw buffers in PSRAM (466 AMOLED strips do not fit in SRAM)."""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
DISPLAY_SOURCE = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_gui_lvgl"
    / "src"
    / "port"
    / "esp"
    / "display_source.cpp"
)

OLD = "ESP_LV_ADAPTER_DISPLAY_SPI_WITHOUT_PSRAM_DEFAULT_CONFIG("
NEW = "ESP_LV_ADAPTER_DISPLAY_SPI_WITH_PSRAM_DEFAULT_CONFIG("


def main() -> int:
    """Rewrite the SPI display profile to the PSRAM variant."""
    if not DISPLAY_SOURCE.is_file():
        print("lvgl psram: skip, display source missing")
        return 0
    text = DISPLAY_SOURCE.read_text(encoding="utf-8")
    if NEW in text and OLD not in text:
        print("lvgl psram: already applied")
        return 0
    if OLD not in text:
        raise RuntimeError(f"lvgl psram patch cannot find {OLD}: {DISPLAY_SOURCE}")
    DISPLAY_SOURCE.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("lvgl psram: SPI draw buffers now use PSRAM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
