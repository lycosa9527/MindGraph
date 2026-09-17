#!/usr/bin/env python3
"""Subset Noto Sans CJK SC for the watch MEMFS copy.

Full U+4E00-9FFF is ~5.2 MB and leaves too little PSRAM for English MultiNet.
Keep Super UI strings plus 通用规范汉字一级 (3500) so live replies still render.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIRMWARE = ROOT.parent.parent
SOURCE = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
OUTPUT = ROOT / "NotoSansSC-Regular.subset.ttf"
HAN_LEVEL1 = ROOT / "han_level1.txt"
TEXT_FILE = ROOT / "cjk_needed.txt"
SCAN_ROOTS = (
    FIRMWARE / "littlefs",
    FIRMWARE / "main",
    FIRMWARE / "round_ui",
)
SCAN_SUFFIXES = {".json", ".cpp", ".hpp", ".c", ".h", ".txt", ".md", ".py"}
BASE_RANGES = (
    (0x20, 0x7E),
    (0xA0, 0xFF),
    (0x2000, 0x206F),
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
)
HAN_RE = re.compile(r"[\u4e00-\u9fff]")


def collect_chars() -> str:
    chars: set[str] = set()
    for start, end in BASE_RANGES:
        chars.update(chr(code) for code in range(start, end + 1))
    if HAN_LEVEL1.is_file():
        chars.update(HAN_RE.findall(HAN_LEVEL1.read_text(encoding="utf-8")))
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path == TEXT_FILE or not path.is_file():
                continue
            if path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            chars.update(HAN_RE.findall(text))
    return "".join(sorted(chars))


def main() -> int:
    if not SOURCE.is_file():
        print(f"missing Noto CJK source: {SOURCE}", file=sys.stderr)
        return 1
    if not HAN_LEVEL1.is_file():
        print(f"missing Han level-1 list: {HAN_LEVEL1}", file=sys.stderr)
        return 1
    needed = collect_chars()
    TEXT_FILE.write_text(needed, encoding="utf-8")
    cmd = [
        "pyftsubset",
        str(SOURCE),
        "--font-number=2",
        f"--text-file={TEXT_FILE}",
        "--layout-features=",
        "--no-hinting",
        "--desubroutinize",
        f"--output-file={OUTPUT}",
    ]
    print(" ".join(cmd))
    print(f"subset chars {len(needed)}")
    subprocess.run(cmd, check=True)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
