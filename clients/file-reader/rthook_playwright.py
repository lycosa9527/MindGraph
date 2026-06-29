"""PyInstaller runtime hook — configure Playwright before app imports."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    meipass = Path(getattr(sys, "_MEIPASS", ""))
    node_exe = meipass / "playwright" / "driver" / "node.exe"
    if node_exe.is_file():
        os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(node_exe)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
