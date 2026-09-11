#!/usr/bin/env python3
"""Build the watch CJK font: full U+4E00-9FFF Han from Noto Sans CJK SC."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
OUTPUT = ROOT / "NotoSansSC-Regular.subset.ttf"
UNICODES = (
    "U+0020-007E,U+00A0-00FF,U+2000-206F,U+3000-303F,"
    "U+4E00-9FFF,U+FF00-FFEF"
)


def main() -> int:
    if not SOURCE.is_file():
        print(f"missing Noto CJK source: {SOURCE}", file=sys.stderr)
        return 1
    cmd = [
        "pyftsubset",
        str(SOURCE),
        "--font-number=2",
        f"--unicodes={UNICODES}",
        "--layout-features=",
        "--no-hinting",
        "--desubroutinize",
        f"--output-file={OUTPUT}",
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
