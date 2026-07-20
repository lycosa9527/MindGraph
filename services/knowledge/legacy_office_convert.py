"""Convert legacy Office binaries (.doc/.ppt/.xls) to OOXML via LibreOffice.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

LEGACY_MIME_TO_TARGET: Dict[str, Tuple[str, str]] = {
    "application/msword": (
        "docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "application/vnd.ms-powerpoint": (
        "pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "application/vnd.ms-excel": (
        "xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}

LEGACY_EXTENSIONS = frozenset({".doc", ".ppt", ".xls"})

_CONVERT_TIMEOUT_SECONDS = 120


def is_legacy_office_mime(mime_type: str) -> bool:
    """True when the MIME type requires LibreOffice conversion first."""
    return mime_type in LEGACY_MIME_TO_TARGET


def resolve_soffice_path() -> Optional[str]:
    """Locate the LibreOffice ``soffice`` binary."""
    env_path = (os.environ.get("LIBREOFFICE_PATH") or "").strip()
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            return str(candidate)
        nested = candidate / "soffice"
        if nested.is_file():
            return str(nested)
        nested_bin = candidate / "program" / "soffice"
        if nested_bin.is_file():
            return str(nested_bin)

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return None


def convert_legacy_office(source_path: str, mime_type: str, output_dir: str) -> Tuple[str, str]:
    """Convert a legacy Office file to OOXML.

    Returns ``(converted_path, ooxml_mime_type)``. Raises ``ValueError`` when
    LibreOffice is missing or conversion fails.
    """
    target = LEGACY_MIME_TO_TARGET.get(mime_type)
    if target is None:
        raise ValueError(f"Not a legacy Office MIME type: {mime_type}")

    convert_filter, ooxml_mime = target
    soffice = resolve_soffice_path()
    if not soffice:
        raise ValueError(
            "Legacy .doc/.ppt/.xls files require LibreOffice. "
            "Install LibreOffice and ensure `soffice` is on PATH, "
            "or set LIBREOFFICE_PATH to the soffice binary."
        )

    source = Path(source_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise ValueError(f"Legacy Office source not found: {source_path}")

    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nolockcheck",
        "--nodefault",
        "--nofirststartwizard",
        "--convert-to",
        convert_filter,
        "--outdir",
        str(out_dir),
        str(source),
    ]
    logger.info("[LegacyOffice] Converting %s → %s via %s", source.name, convert_filter, soffice)
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=_CONVERT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"LibreOffice conversion timed out for {source.name}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to launch LibreOffice: {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise ValueError(f"LibreOffice conversion failed for {source.name}" + (f": {stderr[:400]}" if stderr else ""))

    expected = out_dir / f"{source.stem}.{convert_filter}"
    if not expected.is_file():
        # LibreOffice may normalize the stem; pick the newest matching suffix.
        candidates = sorted(
            out_dir.glob(f"*.{convert_filter}"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise ValueError(f"LibreOffice produced no {convert_filter} output for {source.name}")
        expected = candidates[0]

    return str(expected), ooxml_mime
