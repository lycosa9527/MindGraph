"""Rasterize PDF/Office first page to a Showcase PNG thumbnail."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import fitz
from PIL import Image

from services.showcase.covers.office_to_pdf import convert_office_to_pdf, office_suffix_needs_pdf

logger = logging.getLogger(__name__)

# Keep in sync with routers.features.community.helpers.THUMBNAIL_MAX_BYTES
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024
_THUMB_MAX_EDGE_PX = 960
_PDF_RENDER_MATRIX = fitz.Matrix(1.5, 1.5)
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def shrink_png_bytes(png_bytes: bytes, max_bytes: int = THUMBNAIL_MAX_BYTES) -> bytes:
    """Downscale PNG until it fits the Showcase thumbnail byte budget."""
    if len(png_bytes) <= max_bytes and png_bytes.startswith(_PNG_MAGIC):
        return png_bytes
    image = Image.open(io.BytesIO(png_bytes))
    image = image.convert("RGB")
    width, height = image.size
    longest = max(width, height)
    if longest > _THUMB_MAX_EDGE_PX:
        scale = _THUMB_MAX_EDGE_PX / longest
        width = max(1, int(round(width * scale)))
        height = max(1, int(round(height * scale)))
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    for _ in range(8):
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        data = buffer.getvalue()
        if len(data) <= max_bytes:
            return data
        if width <= 64 or height <= 64:
            break
        width = max(64, int(round(width * 0.75)))
        height = max(64, int(round(height * 0.75)))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    raise ValueError(f"Unable to shrink cover PNG under {max_bytes} bytes")


def render_pdf_first_page_png(pdf_path: Path) -> bytes:
    """Render page 0 of a PDF to PNG bytes (pre-shrink)."""
    document = fitz.open(pdf_path)
    try:
        if document.page_count < 1:
            raise ValueError("PDF has no pages")
        page = document.load_page(0)
        pixmap = page.get_pixmap(matrix=_PDF_RENDER_MATRIX, alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()


def render_document_cover_png(source_path: Path, work_dir: Path) -> bytes:
    """Render first page of PDF/DOC/DOCX to a budget-compliant PNG."""
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        pdf_path = source_path
    elif office_suffix_needs_pdf(suffix):
        pdf_path = convert_office_to_pdf(source_path, work_dir)
    else:
        raise ValueError(f"Unsupported cover source suffix: {suffix}")

    raw = render_pdf_first_page_png(pdf_path)
    return shrink_png_bytes(raw)
