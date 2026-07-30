"""Host dependency checks for Showcase server-side teaching-design covers."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
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

_LINUX_PROGRAM_DIRS = (
    Path("/usr/lib/libreoffice/program"),
    Path("/usr/lib64/libreoffice/program"),
)

_APT_LO_PACKAGES = "libreoffice-writer libreoffice-impress libreoffice-common fonts-noto-cjk fontconfig"
_APT_INSTALL_LO = f"sudo apt-get install -y {_APT_LO_PACKAGES}"

# component -> (PATH names, program/ binary, lib glob stem)
_COMPONENT_MARKERS: dict[str, tuple[tuple[str, ...], str, str]] = {
    "writer": (("lowriter", "swriter"), "swriter", "libswriterlo.so*"),
    "impress": (("loimpress", "simpress"), "simpress", "libsimpresslo.so*"),
}


def lines_showcase_cover_host_install() -> list[str]:
    """Copy-paste install + verify hints for LibreOffice + Noto CJK fonts."""
    return [
        "Showcase server-side teaching-design covers need LibreOffice (Writer + Impress) and CJK fonts.",
        "",
        "  Ubuntu/Debian:",
        "    sudo apt-get update",
        f"    {_APT_INSTALL_LO}",
        "",
        "  Verify:",
        "    soffice --version",
        "    command -v lowriter || command -v swriter",
        "    command -v loimpress || command -v simpress",
        "    fc-list :lang=zh | head",
        "",
        "  macOS:",
        "    brew install libreoffice",
        "    brew install --cask font-noto-sans-cjk-sc",
        "    soffice --version",
        "",
        "  Windows: install full LibreOffice from",
        "           https://www.libreoffice.org/download/",
        "           (includes Writer + Impress). Put soffice.exe on PATH",
        "           or set LIBREOFFICE_PATH, then run: soffice --version",
        "",
        "  Optional: set LIBREOFFICE_PATH=/usr/bin/soffice in .env",
        "  Disable covers and continue: SHOWCASE_SERVER_COVERS=false",
        "  Full cheatsheet: python -m services.infrastructure.utils.launch_commands",
    ]


def libreoffice_program_dir(soffice: str) -> Optional[Path]:
    """Locate the LibreOffice ``program/`` directory from a soffice path."""
    path = Path(soffice).resolve()
    if path.parent.name == "program":
        return path.parent
    nested = path.parent / "program"
    if (nested / "soffice").is_file() or (nested / "soffice.bin").is_file():
        return nested
    for candidate in _LINUX_PROGRAM_DIRS:
        if (candidate / "soffice").is_file() or (candidate / "soffice.bin").is_file():
            return candidate
    return None


def office_component_installed(soffice: str, component: str) -> bool:
    """True when a LibreOffice component (writer/impress) is present."""
    markers = _COMPONENT_MARKERS.get(component)
    if markers is None:
        return False
    path_names, program_bin, lib_glob = markers
    if any(shutil.which(name) for name in path_names):
        return True
    program_dir = libreoffice_program_dir(soffice)
    if program_dir is None:
        # Full desktop installs on Windows/macOS usually ship both components.
        return sys.platform in {"win32", "darwin"}
    if (program_dir / program_bin).is_file():
        return True
    if any(program_dir.glob(lib_glob)):
        return True
    xcd = program_dir.parent / "share" / "registry" / f"{component}.xcd"
    return xcd.is_file()


def impress_component_installed(soffice: str) -> bool:
    """True when Impress is present (required for PPTX → PDF covers)."""
    return office_component_installed(soffice, "impress")


def writer_component_installed(soffice: str) -> bool:
    """True when Writer is present (required for DOC/DOCX → PDF covers)."""
    return office_component_installed(soffice, "writer")


def check_libreoffice_installed() -> tuple[bool, str]:
    """Return whether Writer+Impress ``soffice`` is available for Office → PDF."""
    soffice = resolve_soffice_path()
    if not soffice:
        return (
            False,
            f"LibreOffice (soffice) not found on PATH and LIBREOFFICE_PATH is unset. Install: {_APT_INSTALL_LO}",
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
        return (
            False,
            f"LibreOffice found at {soffice} but --version failed: {exc}. Reinstall: {_APT_INSTALL_LO}",
        )
    version = (result.stdout or result.stderr or "").strip().splitlines()
    label = version[0] if version else "unknown version"
    if result.returncode != 0 and not version:
        return (
            False,
            f"LibreOffice at {soffice} did not report a version "
            f"(exit {result.returncode}). Reinstall: {_APT_INSTALL_LO}",
        )

    missing: list[str] = []
    if not writer_component_installed(soffice):
        missing.append("Writer (.doc/.docx)")
    if not impress_component_installed(soffice):
        missing.append("Impress (.pptx)")
    if missing:
        return (
            False,
            "LibreOffice components missing: "
            + ", ".join(missing)
            + ". Install: sudo apt-get install -y libreoffice-writer libreoffice-impress",
        )
    return True, f"{label} + Writer + Impress ({soffice})"


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
        return (
            True,
            "CJK font check skipped on macOS (brew install --cask font-noto-sans-cjk-sc if covers look blank)",
        )

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
            "Install: sudo apt-get install -y fonts-noto-cjk "
            "then verify: fc-list :lang=zh | head",
        )
    return (
        False,
        "No Chinese-capable fonts found. "
        "Install: sudo apt-get install -y fonts-noto-cjk "
        "then verify: fc-list :lang=zh | head",
    )


def enforce_showcase_cover_host_deps_or_exit() -> None:
    """
    Hard-fail boot when Showcase server covers are enabled but host deps are missing.

    Mirrors Redis/Qdrant feature gates: clear console prompt + ``sys.exit(1)``.
    """
    if not showcase_server_covers_enabled():
        logger.debug("[SHOWCASE] Skipping LibreOffice/CJK font check (server covers disabled)")
        return

    logger.debug("[SHOWCASE] Checking LibreOffice (Writer+Impress) and CJK fonts...")
    lo_ok, lo_msg = check_libreoffice_installed()
    fonts_ok, fonts_msg = check_noto_cjk_fonts_installed()

    if lo_ok and fonts_ok:
        logger.info("[SHOWCASE] LibreOffice ready: %s", lo_msg)
        logger.info("[SHOWCASE] CJK fonts ready: %s", fonts_msg)
        return

    print()
    print("=" * 80)
    print("[ERROR] Showcase server-side covers require LibreOffice (Writer + Impress) and CJK fonts.")
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
