#!/usr/bin/env python3
"""Allow file-backed FreeType when PSRAM XIP is off.

Brookesia otherwise forces MEMFS, which memcpy's NotoSansSC (~1.6 MB) into the
2.5 MB PSRAM heap on this 1.85C and then OOMs while installing apps.
"""

from __future__ import annotations

from pathlib import Path

FIRMWARE_ROOT = Path(__file__).resolve().parent.parent
STYLE_IMPL = (
    FIRMWARE_ROOT
    / "managed_components"
    / "espressif__brookesia_gui_lvgl"
    / "src"
    / "private"
    / "style_impl.hpp"
)

OLD = (
    "#   if defined(ESP_PLATFORM) && (!defined(CONFIG_SPIRAM_XIP_FROM_PSRAM) || "
    "!CONFIG_SPIRAM_XIP_FROM_PSRAM) && \\\n"
    "        !BROOKESIA_GUI_LVGL_USE_FREETYPE_MEMFS_PORT\n"
    '#       error "Enable LV_USE_FS_MEMFS and LV_FREETYPE_USE_LVGL_PORT when '
    'CONFIG_SPIRAM_XIP_FROM_PSRAM is disabled"\n'
    "#   endif\n"
)

NEW = (
    "#   if defined(ESP_PLATFORM) && (!defined(CONFIG_SPIRAM_XIP_FROM_PSRAM) || "
    "!CONFIG_SPIRAM_XIP_FROM_PSRAM) && \\\n"
    "        !BROOKESIA_GUI_LVGL_USE_FREETYPE_MEMFS_PORT && "
    "!BROOKESIA_GUI_LVGL_HAS_ESP_FONT_BACKEND\n"
    '#       error "Enable LV_USE_FS_MEMFS and LV_FREETYPE_USE_LVGL_PORT when '
    'CONFIG_SPIRAM_XIP_FROM_PSRAM is disabled"\n'
    "#   endif\n"
)


def main() -> int:
    if not STYLE_IMPL.is_file():
        print(f"missing {STYLE_IMPL}")
        return 1
    text = STYLE_IMPL.read_text()
    if NEW in text:
        print("freetype file-backend guard already patched")
        return 0
    if OLD not in text:
        print("freetype XIP/MEMFS guard not found")
        return 1
    STYLE_IMPL.write_text(text.replace(OLD, NEW, 1))
    print(f"patched {STYLE_IMPL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
