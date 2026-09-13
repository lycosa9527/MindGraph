#!/usr/bin/env python3
"""Drop I2S designated fields that IDF 6.1 omits unless SOC_I2S_HW_VERSION_2 is visible."""

from __future__ import annotations

from pathlib import Path

GEN = (
    Path(__file__).resolve().parent.parent
    / "components"
    / "gen_bmgr_codes"
    / "gen_board_periph_config.c"
)


def main() -> int:
    """Strip optional I2S designated initializers from generated board code."""
    if not GEN.is_file():
        print(f"bmgr i2s: skip, missing {GEN}")
        return 0
    text = GEN.read_text(encoding="utf-8")
    original = text
    text = text.replace("                .ext_clk_freq_hz = 0,\n", "")
    text = text.replace("                .left_align = true,\n", "")
    text = text.replace("                .big_endian = false,\n", "")
    text = text.replace("                .bit_order_lsb = false,\n", "")
    if text == original:
        print("bmgr i2s: already clean")
        return 0
    GEN.write_text(text, encoding="utf-8")
    print("bmgr i2s: stripped optional I2S designated fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
