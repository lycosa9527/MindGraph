"""
PDF Cover Extractor Module for Library

Extracts the first page of PDFs as cover images.
Supports PyMuPDF (recommended) and pdf2image as fallback.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try PyMuPDF first (pure Python, no external dependencies)
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Fallback to pdf2image (requires poppler)
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not available. Install with: pip install Pillow")


def extract_pdf_cover_pymupdf(
    pdf_path: Path,
    output_path: Path,
    dpi: int = 200
) -> bool:
    """
    Extract first page of PDF as cover image using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for image (default: 200)

    Returns:
        True if successful, False otherwise
    """
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            logger.warning("No pages found in %s", pdf_path.name)
            doc.close()
            return False

        # Get first page
        page = doc[0]

        # Calculate zoom factor for desired DPI (default PDF is 72 DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        cover_image = Image.open(io.BytesIO(img_data))

        # Resize if too large (max width 800px, maintain aspect ratio)
        max_width = 800
        if cover_image.width > max_width:
            ratio = max_width / cover_image.width
            new_height = int(cover_image.height * ratio)
            cover_image = cover_image.resize(
                (max_width, new_height),
                Image.Resampling.LANCZOS
            )

        # Save as PNG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cover_image.save(output_path, "PNG", optimize=True)

        file_size_kb = output_path.stat().st_size / 1024
        logger.info(
            "Extracted cover: %s (%dx%dpx, %.1f KB)",
            output_path.name,
            cover_image.width,
            cover_image.height,
            file_size_kb
        )

        doc.close()
        return True

    except Exception as e:
        logger.error("Error extracting cover from %s: %s", pdf_path.name, e)
        return False


def extract_pdf_cover_pdf2image(
    pdf_path: Path,
    output_path: Path,
    dpi: int = 200
) -> bool:
    """
    Extract first page of PDF as cover image using pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for image (default: 200)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert first page to image
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=1,
            last_page=1,
            fmt='png'
        )

        if not images:
            logger.warning("No pages found in %s", pdf_path.name)
            return False

        # Get first page image
        cover_image = images[0]

        # Resize if too large (max width 800px, maintain aspect ratio)
        max_width = 800
        if cover_image.width > max_width:
            ratio = max_width / cover_image.width
            new_height = int(cover_image.height * ratio)
            cover_image = cover_image.resize(
                (max_width, new_height),
                Image.Resampling.LANCZOS
            )

        # Save as PNG
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cover_image.save(output_path, "PNG", optimize=True)

        file_size_kb = output_path.stat().st_size / 1024
        logger.info(
            "Extracted cover: %s (%dx%dpx, %.1f KB)",
            output_path.name,
            cover_image.width,
            cover_image.height,
            file_size_kb
        )
        return True

    except Exception as e:
        logger.error("Error extracting cover from %s: %s", pdf_path.name, e)
        return False


def extract_pdf_cover(
    pdf_path: Path,
    output_path: Path,
    dpi: int = 200
) -> bool:
    """
    Extract first page of PDF as cover image.

    Uses PyMuPDF if available, falls back to pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for image (default: 200)

    Returns:
        True if successful, False otherwise
    """
    if not PIL_AVAILABLE:
        logger.error(
            "Cannot extract cover for %s - Pillow not available",
            pdf_path.name
        )
        return False

    if PYMUPDF_AVAILABLE:
        return extract_pdf_cover_pymupdf(pdf_path, output_path, dpi)
    elif PDF2IMAGE_AVAILABLE:
        return extract_pdf_cover_pdf2image(pdf_path, output_path, dpi)
    else:
        logger.error(
            "Cannot extract cover for %s - no PDF rendering library available",
            pdf_path.name
        )
        return False


def extract_all_covers(
    library_dir: Path,
    covers_dir: Path,
    dpi: int = 200
) -> tuple[int, int]:
    """
    Extract covers for all PDFs in library directory.

    Args:
        library_dir: Directory containing PDFs
        covers_dir: Directory to save covers
        dpi: Resolution for images (default: 200)

    Returns:
        Tuple of (success_count, total_count)
    """
    if not library_dir.exists():
        logger.error("Library directory not found: %s", library_dir)
        return (0, 0)

    # Find all PDF files
    pdf_files = list(library_dir.glob("*.pdf"))
    if not pdf_files:
        logger.info("No PDF files found in %s", library_dir)
        return (0, 0)

    logger.info("Found %s PDF file(s) in %s", len(pdf_files), library_dir)
    logger.info("Extracting covers to %s", covers_dir)

    success_count = 0
    for pdf_path in pdf_files:
        # Generate cover filename: {pdf_name_without_ext}_cover.png
        pdf_name = pdf_path.stem
        cover_filename = f"{pdf_name}_cover.png"
        cover_path = covers_dir / cover_filename

        logger.debug("Processing: %s", pdf_path.name)
        if extract_pdf_cover(pdf_path, cover_path, dpi):
            success_count += 1

    logger.info(
        "Completed: %s/%s covers extracted successfully",
        success_count,
        len(pdf_files)
    )

    if success_count < len(pdf_files):
        if not PYMUPDF_AVAILABLE and not PDF2IMAGE_AVAILABLE:
            logger.warning(
                "To extract covers, please install PyMuPDF (recommended): "
                "pip install PyMuPDF"
            )
            logger.warning(
                "Or install pdf2image + poppler: "
                "pip install pdf2image"
            )

    return (success_count, len(pdf_files))


def check_cover_extraction_available() -> tuple[bool, Optional[str]]:
    """
    Check if cover extraction is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    if not PIL_AVAILABLE:
        return (False, "Pillow not available. Install with: pip install Pillow")

    if not PYMUPDF_AVAILABLE and not PDF2IMAGE_AVAILABLE:
        return (
            False,
            "No PDF rendering library available. "
            "Install PyMuPDF (recommended): pip install PyMuPDF "
            "Or install pdf2image + poppler"
        )

    return (True, None)
