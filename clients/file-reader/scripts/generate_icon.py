"""Refresh file-reader PNG + ICO from the vector MindGraph favicon."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _SCRIPT_DIR.parent / "assets"
_REPO_ROOT = _SCRIPT_DIR.parents[2]
_GENERATOR = _REPO_ROOT / "frontend" / "scripts" / "generate-pwa-icons.mjs"
_PNG_PATH = _ASSETS_DIR / "icon.png"
_ICO_PATH = _ASSETS_DIR / "icon.ico"


def _rasterize_from_svg() -> bool:
    node = shutil.which("node")
    if node is None or not _GENERATOR.is_file():
        return False
    completed = subprocess.run(
        [node, str(_GENERATOR)],
        cwd=_REPO_ROOT / "frontend",
        check=False,
    )
    return completed.returncode == 0


def main() -> None:
    """Write assets/icon.png and assets/icon.ico for tkinter + PyInstaller."""
    refreshed = _rasterize_from_svg()
    if not _PNG_PATH.is_file() or not _ICO_PATH.is_file():
        raise SystemExit("icon.png / icon.ico missing; run: cd frontend && npm run generate-pwa-icons")
    if refreshed:
        print(f"Wrote {_PNG_PATH} and {_ICO_PATH}")
        return
    print(f"Kept existing {_PNG_PATH} and {_ICO_PATH} (Node/sharp unavailable)")


if __name__ == "__main__":
    main()
