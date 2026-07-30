"""Host dependency checks for Showcase server-side teaching-design covers."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from typing import Optional

from services.knowledge.legacy_office_convert import resolve_soffice_path
from services.showcase.covers.config import showcase_server_covers_enabled
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

_NOTO_CJK_MARKERS = (
    "noto sans cjk",
    "noto serif cjk",
    "noto sans sc",
    "noto sans tc",
    "noto sans jp",
    "noto sans kr",
    "source han sans",
    "source han serif",
)


def lines_showcase_cover_host_install() -> list[str]:
    """Copy-paste install hints for LibreOffice + Noto CJK fonts."""
    return [
        "Showcase server-side teaching-design covers need LibreOffice and CJK fonts.",
        "",
        "  Ubuntu/Debian:",
        "    sudo apt-get update",
        "    sudo apt-get install -y libreoffice-writer libreoffice-impress "
        "libreoffice-common fonts-noto-cjk fontconfig",
        "    soffice --version",
        "    fc-list :lang=zh | head",
        "",
        "  macOS:",
        "    brew install libreoffice",
        "    brew install --cask font-noto-sans-cjk-sc",
        "",
        "  Windows: install LibreOffice from https://www.libreoffice.org/download/",
        "           and ensure soffice.exe is on PATH (or set LIBREOFFICE_PATH).",
        "",
        "  Optional: set LIBREOFFICE_PATH=/usr/bin/soffice in .env",
        "  Disable covers and continue: SHOWCASE_SERVER_COVERS=false",
    ]


def check_libreoffice_installed() -> tuple[bool, str]:
    """Return whether ``soffice`` is available for Office → PDF cover conversion."""
    soffice = resolve_soffice_path()
    if not soffice:
        return (
            False,
            "LibreOffice (soffice) not found on PATH and LIBREOFFICE_PATH is unset.",
        )
    try:
        result = subprocess.run(
            [soffice, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (*BACKGROUND_INFRA_ERRORS, subprocess.SubprocessError) as exc:
        return False, f"LibreOffice found at {soffice} but --version failed: {exc}"
    version = (result.stdout or result.stderr or "").strip().splitlines()
    label = version[0] if version else "unknown version"
    if result.returncode != 0 and not version:
        return False, f"LibreOffice at {soffice} did not report a version (exit {result.returncode})."
    return True, f"{label} ({soffice})"


def _fc_list_output() -> Optional[str]:
    """Run fontconfig listing for Chinese-capable families, or None if unavailable."""
    fc_list = shutil.which("fc-list")
    if not fc_list:
        return None
    try:
        result = subprocess.run(
            [fc_list, ":lang=zh", "family"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (*BACKGROUND_INFRA_ERRORS, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout or ""


def check_noto_cjk_fonts_installed() -> tuple[bool, str]:
    """
    Return whether Noto / Source Han CJK fonts are available.

    Linux uses ``fc-list``; Windows/macOS skip with a success note (system CJK
    fonts are usually present; operators can still install Noto manually).
    """
    if sys.platform == "win32":
        return True, "CJK font check skipped on Windows (install Noto CJK if covers look blank)"
    if sys.platform == "darwin":
        return True, "CJK font check skipped on macOS (install Noto CJK via brew cask if needed)"

    fc_list = shutil.which("fc-list")
    if not fc_list:
        return (
            False,
            "fontconfig (fc-list) not found. Install: sudo apt-get install -y fontconfig fonts-noto-cjk",
        )

    output = _fc_list_output()
    if output is None:
        return (
            False,
            "Could not query Chinese fonts via fc-list. Install: sudo apt-get install -y fontconfig fonts-noto-cjk",
        )
    lowered = output.lower()
    if any(marker in lowered for marker in _NOTO_CJK_MARKERS):
        return True, "Noto/Source Han CJK fonts available via fontconfig"
    if output.strip():
        return (
            False,
            "Chinese fonts exist but Noto/Source Han CJK was not found. "
            "Install: sudo apt-get install -y fonts-noto-cjk",
        )
    return (
        False,
        "No Chinese-capable fonts found. Install: sudo apt-get install -y fonts-noto-cjk",
    )


def enforce_showcase_cover_host_deps_or_exit() -> None:
    """
    Hard-fail boot when Showcase server covers are enabled but host deps are missing.

    Mirrors Redis/Qdrant feature gates: clear console prompt + ``sys.exit(1)``.
    """
    if not showcase_server_covers_enabled():
        logger.debug("[SHOWCASE] Skipping LibreOffice/CJK font check (server covers disabled)")
        return

    logger.debug("[SHOWCASE] Checking LibreOffice and CJK fonts for server covers...")
    lo_ok, lo_msg = check_libreoffice_installed()
    fonts_ok, fonts_msg = check_noto_cjk_fonts_installed()

    if lo_ok and fonts_ok:
        logger.info("[SHOWCASE] LibreOffice ready: %s", lo_msg)
        logger.info("[SHOWCASE] CJK fonts ready: %s", fonts_msg)
        return

    print()
    print("=" * 80)
    print("[ERROR] Showcase server-side covers require LibreOffice and CJK fonts.")
    print("=" * 80)
    if not lo_ok:
        print(f"  LibreOffice: MISSING — {lo_msg}")
    else:
        print(f"  LibreOffice: OK — {lo_msg}")
    if not fonts_ok:
        print(f"  CJK fonts:   MISSING — {fonts_msg}")
    else:
        print(f"  CJK fonts:   OK — {fonts_msg}")
    print()
    for line in lines_showcase_cover_host_install():
        print(line)
    print()
    print("Application cannot start with Showcase server covers enabled until these are installed.")
    print("=" * 80)
    print()
    logger.error(
        "[SHOWCASE] Host deps missing (libreoffice_ok=%s fonts_ok=%s) — refusing startup",
        lo_ok,
        fonts_ok,
    )
    sys.exit(1)
