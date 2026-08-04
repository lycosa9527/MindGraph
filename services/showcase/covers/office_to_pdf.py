"""LibreOffice Office→PDF conversion for Showcase teaching-design covers."""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path

from services.infrastructure.sync.office_preview_fonts_cos import (
    ensure_office_preview_fonts_ready,
    office_preview_fontconfig_env,
)
from services.knowledge.legacy_office_convert import resolve_soffice_path

logger = logging.getLogger(__name__)

_CONVERT_TIMEOUT_SECONDS = 120
_OFFICE_SUFFIXES = frozenset({".doc", ".docx", ".pptx"})

# High-fidelity export: keep embedded images sharp (no JPEG mush / DPI downscale).
# Text stays vector in the PDF; viewer sharpness is handled by pdf.js DPR rendering.
_PDF_EXPORT_FILTER_OPTIONS: dict[str, dict[str, str]] = {
    "UseLosslessCompression": {"type": "boolean", "value": "true"},
    "Quality": {"type": "long", "value": "100"},
    "ReduceImageResolution": {"type": "boolean", "value": "false"},
}


def office_suffix_needs_pdf(suffix: str) -> bool:
    """True when suffix must be converted via LibreOffice before rasterize."""
    return suffix.lower() in _OFFICE_SUFFIXES


def build_office_pdf_convert_to(suffix: str) -> str:
    """Build LibreOffice ``--convert-to`` token for high-quality PDF export.

    Example: ``pdf:writer_pdf_Export:{"UseLosslessCompression":...}``
    (compact JSON, no spaces — required by soffice CLI parsing).
    """
    normalized = suffix.lower()
    if normalized in {".doc", ".docx"}:
        filter_name = "writer_pdf_Export"
    elif normalized == ".pptx":
        filter_name = "impress_pdf_Export"
    else:
        raise ValueError(f"Unsupported Office suffix for PDF export: {suffix}")
    options = json.dumps(_PDF_EXPORT_FILTER_OPTIONS, separators=(",", ":"))
    return f"pdf:{filter_name}:{options}"


def convert_office_to_pdf(source_path: Path, output_dir: Path) -> Path:
    """Convert .doc/.docx/.pptx to PDF using a per-job LibreOffice user profile.

    Returns the path to the produced PDF. Raises ``ValueError`` on failure.
    """
    soffice = resolve_soffice_path()
    if not soffice:
        raise ValueError(
            "LibreOffice Writer+Impress is required for Office cover generation. "
            "Install: sudo apt-get install -y libreoffice-writer libreoffice-impress "
            "(or set LIBREOFFICE_PATH to soffice)."
        )
    if not source_path.is_file():
        raise ValueError(f"Office source not found: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = output_dir / f"lo-profile-{uuid.uuid4().hex}"
    profile_dir.mkdir(parents=True, exist_ok=True)
    # file:/// URI; LibreOffice accepts forward slashes on Windows too.
    profile_uri = profile_dir.resolve().as_uri()
    convert_to = build_office_pdf_convert_to(source_path.suffix)

    # Pull Windows CJK pack from COS (or seed from local Windows Fonts) so 宋体/楷体
    # embed instead of Noto substitution when the pack is available.
    ensure_office_preview_fonts_ready()
    soffice_env = office_preview_fontconfig_env(output_dir / "fontconfig")

    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nolockcheck",
        "--nodefault",
        "--nofirststartwizard",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to",
        convert_to,
        "--outdir",
        str(output_dir),
        str(source_path),
    ]
    logger.info(
        "[ShowcaseCover] Converting %s → pdf via %s (%s)",
        source_path.name,
        soffice,
        convert_to.split(":{", maxsplit=1)[0],
    )
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=_CONVERT_TIMEOUT_SECONDS,
            env=soffice_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"LibreOffice PDF conversion timed out for {source_path.name}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to launch LibreOffice: {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise ValueError(
            f"LibreOffice PDF conversion failed for {source_path.name}" + (f": {stderr[:400]}" if stderr else "")
        )

    expected = output_dir / f"{source_path.stem}.pdf"
    if expected.is_file():
        return expected
    candidates = sorted(
        output_dir.glob("*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise ValueError(f"LibreOffice produced no PDF for {source_path.name}")
    return candidates[0]
