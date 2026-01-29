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
from typing import Optional, Literal

from models.domain.library import LibraryDocument
from services.library.pdf_utils import resolve_library_path

logger = logging.getLogger(__name__)

# Default settings for web-optimized thumbnails
DEFAULT_DPI = 96  # Screen resolution DPI
DEFAULT_MAX_WIDTH = 400  # Thumbnail width in pixels
DEFAULT_FORMAT = "JPEG"  # JPEG for smaller files
DEFAULT_QUALITY = 80  # JPEG quality (1-100)

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
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY
) -> bool:
    """
    Extract first page of PDF as cover image using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)

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

        # Convert to RGB if saving as JPEG (JPEG doesn't support alpha)
        if image_format == "JPEG" and cover_image.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', cover_image.size, (255, 255, 255))
            if cover_image.mode == 'P':
                cover_image = cover_image.convert('RGBA')
            background.paste(cover_image, mask=cover_image.split()[-1] if cover_image.mode == 'RGBA' else None)
            cover_image = background

        # Resize if too large (maintain aspect ratio)
        if cover_image.width > max_width:
            ratio = max_width / cover_image.width
            new_height = int(cover_image.height * ratio)
            cover_image = cover_image.resize(
                (max_width, new_height),
                Image.Resampling.LANCZOS
            )

        # Save image
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if image_format == "JPEG":
            cover_image.save(output_path, "JPEG", quality=quality, optimize=True)
        else:
            cover_image.save(output_path, "PNG", optimize=True)

        file_size_kb = output_path.stat().st_size / 1024
        logger.info(
            "Extracted cover: %s (%dx%dpx, %.1f KB, %s)",
            output_path.name,
            cover_image.width,
            cover_image.height,
            file_size_kb,
            image_format
        )

        doc.close()
        return True

    except FileNotFoundError:
        logger.error("PDF file not found: %s", pdf_path)
        return False
    except PermissionError:
        logger.error("Permission denied reading PDF: %s", pdf_path)
        return False
    except Exception as e:
        logger.error("Error extracting cover from %s: %s", pdf_path.name, e, exc_info=True)
        return False


def extract_pdf_cover_pdf2image(
    pdf_path: Path,
    output_path: Path,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY
) -> bool:
    """
    Extract first page of PDF as cover image using pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)

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

        # Convert to RGB if saving as JPEG (JPEG doesn't support alpha)
        if image_format == "JPEG" and cover_image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', cover_image.size, (255, 255, 255))
            if cover_image.mode == 'P':
                cover_image = cover_image.convert('RGBA')
            background.paste(cover_image, mask=cover_image.split()[-1] if cover_image.mode == 'RGBA' else None)
            cover_image = background

        # Resize if too large (maintain aspect ratio)
        if cover_image.width > max_width:
            ratio = max_width / cover_image.width
            new_height = int(cover_image.height * ratio)
            cover_image = cover_image.resize(
                (max_width, new_height),
                Image.Resampling.LANCZOS
            )

        # Save image
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if image_format == "JPEG":
            cover_image.save(output_path, "JPEG", quality=quality, optimize=True)
        else:
            cover_image.save(output_path, "PNG", optimize=True)

        file_size_kb = output_path.stat().st_size / 1024
        logger.info(
            "Extracted cover: %s (%dx%dpx, %.1f KB, %s)",
            output_path.name,
            cover_image.width,
            cover_image.height,
            file_size_kb,
            image_format
        )
        return True

    except FileNotFoundError:
        logger.error("PDF file not found: %s", pdf_path)
        return False
    except PermissionError:
        logger.error("Permission denied reading PDF: %s", pdf_path)
        return False
    except Exception as e:
        logger.error("Error extracting cover from %s: %s", pdf_path.name, e, exc_info=True)
        return False


def extract_pdf_cover(
    pdf_path: Path,
    output_path: Path,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY
) -> bool:
    """
    Extract first page of PDF as cover image.

    Uses PyMuPDF if available, falls back to pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save cover image
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)

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
        return extract_pdf_cover_pymupdf(
            pdf_path, output_path, dpi, max_width, image_format, quality
        )
    elif PDF2IMAGE_AVAILABLE:
        return extract_pdf_cover_pdf2image(
            pdf_path, output_path, dpi, max_width, image_format, quality
        )
    else:
        logger.error(
            "Cannot extract cover for %s - no PDF rendering library available",
            pdf_path.name
        )
        return False


def extract_all_covers(
    library_dir: Path,
    covers_dir: Path,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY,
    force: bool = False
) -> tuple[int, int]:
    """
    Extract covers for all PDFs in library directory.

    Args:
        library_dir: Directory containing PDFs
        covers_dir: Directory to save covers
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)
        force: If True, regenerate all covers even if they exist

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
    logger.info(
        "Settings: DPI=%s, max_width=%spx, format=%s, quality=%s",
        dpi, max_width, image_format, quality
    )

    # Determine file extension
    ext = "jpg" if image_format == "JPEG" else "png"

    success_count = 0
    skipped_count = 0
    for pdf_path in sorted(pdf_files):
        pdf_name = pdf_path.stem
        cover_filename = f"{pdf_name}_cover.{ext}"
        cover_path = covers_dir / cover_filename

        # Skip if cover exists and not forcing regeneration
        if cover_path.exists() and not force:
            logger.debug("Skipping (cover exists): %s", pdf_path.name)
            skipped_count += 1
            continue

        logger.debug("Processing: %s", pdf_path.name)
        if extract_pdf_cover(pdf_path, cover_path, dpi, max_width, image_format, quality):
            success_count += 1

    logger.info(
        "Completed: %s extracted, %s skipped (already exist)",
        success_count,
        skipped_count
    )

    if success_count < len(pdf_files) - skipped_count:
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


def regenerate_all_covers(
    library_dir: Path,
    covers_dir: Path,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY,
    cleanup_old: bool = True
) -> tuple[int, int, int]:
    """
    Regenerate all cover images with new settings.

    Removes old covers and creates new ones with optimized settings.

    Args:
        library_dir: Directory containing PDFs
        covers_dir: Directory to save covers
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)
        cleanup_old: If True, remove old cover files first

    Returns:
        Tuple of (regenerated_count, total_count, old_removed_count)
    """
    old_removed = 0

    # Clean up old covers if requested
    if cleanup_old and covers_dir.exists():
        old_covers = list(covers_dir.glob("*_cover.*"))
        for old_cover in old_covers:
            try:
                old_size_kb = old_cover.stat().st_size / 1024
                old_cover.unlink()
                old_removed += 1
                logger.debug("Removed old cover: %s (%.1f KB)", old_cover.name, old_size_kb)
            except OSError as e:
                logger.warning("Failed to remove %s: %s", old_cover.name, e)

        if old_removed > 0:
            logger.info("Removed %s old cover file(s)", old_removed)

    # Extract new covers with force=True to ensure all are regenerated
    success, total = extract_all_covers(
        library_dir=library_dir,
        covers_dir=covers_dir,
        dpi=dpi,
        max_width=max_width,
        image_format=image_format,
        quality=quality,
        force=True
    )

    return (success, total, old_removed)


def optimize_oversized_covers(
    library_dir: Path,
    covers_dir: Path,
    max_size_kb: float = 100.0,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY
) -> tuple[int, int, int]:
    """
    Check existing covers and only regenerate those that are too large.

    Args:
        library_dir: Directory containing PDFs
        covers_dir: Directory to save covers
        max_size_kb: Maximum allowed size in KB (default: 100 KB)
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)

    Returns:
        Tuple of (regenerated_count, skipped_count, total_checked)
    """
    if not covers_dir.exists():
        logger.warning("Covers directory not found: %s", covers_dir)
        return (0, 0, 0)

    # Find all existing covers
    existing_covers = list(covers_dir.glob("*_cover.*"))
    if not existing_covers:
        logger.info("No existing covers found in %s", covers_dir)
        return (0, 0, 0)

    logger.info("Checking %s existing cover(s) for optimization", len(existing_covers))
    logger.info("Threshold: %.0f KB (covers larger than this will be regenerated)", max_size_kb)

    # Determine new file extension
    ext = "jpg" if image_format == "JPEG" else "png"

    regenerated = 0
    skipped = 0
    total_old_size = 0
    total_new_size = 0

    for cover_path in sorted(existing_covers):
        cover_size_kb = cover_path.stat().st_size / 1024
        total_old_size += cover_size_kb

        # Check if cover is too large
        if cover_size_kb <= max_size_kb:
            logger.debug(
                "OK: %s (%.1f KB <= %.0f KB)",
                cover_path.name,
                cover_size_kb,
                max_size_kb
            )
            skipped += 1
            total_new_size += cover_size_kb
            continue

        # Find corresponding PDF
        # Cover name format: {pdf_stem}_cover.{ext}
        cover_stem = cover_path.stem.replace('_cover', '')
        pdf_path = library_dir / f"{cover_stem}.pdf"

        if not pdf_path.exists():
            logger.warning(
                "PDF not found for oversized cover: %s (%.1f KB)",
                cover_path.name,
                cover_size_kb
            )
            skipped += 1
            total_new_size += cover_size_kb
            continue

        # Remove old cover
        try:
            cover_path.unlink()
        except OSError as e:
            logger.error("Failed to remove %s: %s", cover_path.name, e)
            skipped += 1
            total_new_size += cover_size_kb
            continue

        # Generate new cover with optimized settings
        new_cover_path = covers_dir / f"{cover_stem}_cover.{ext}"
        if extract_pdf_cover(
            pdf_path, new_cover_path, dpi, max_width, image_format, quality
        ):
            new_size_kb = new_cover_path.stat().st_size / 1024
            total_new_size += new_size_kb
            logger.info(
                "Optimized: %s (%.1f KB -> %.1f KB, saved %.1f KB)",
                cover_stem,
                cover_size_kb,
                new_size_kb,
                cover_size_kb - new_size_kb
            )
            regenerated += 1
        else:
            logger.error("Failed to regenerate cover for %s", pdf_path.name)
            skipped += 1

    # Summary
    logger.info("")
    logger.info("Optimization complete:")
    logger.info("  Regenerated: %s", regenerated)
    logger.info("  Skipped (already small): %s", skipped)
    logger.info("  Total size before: %.1f KB", total_old_size)
    logger.info("  Total size after: %.1f KB", total_new_size)
    if total_old_size > 0:
        saved = total_old_size - total_new_size
        logger.info("  Space saved: %.1f KB (%.0f%%)", saved, (saved / total_old_size) * 100)

    return (regenerated, skipped, len(existing_covers))


def regenerate_covers_from_database(
    db,
    library_dir: Path,
    covers_dir: Path,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY
) -> tuple[int, int, int]:
    """
    Regenerate cover images for all documents in the database.

    Uses document IDs for cover filenames (matching the import pattern).

    Args:
        db: Database session
        library_dir: Directory containing PDFs
        covers_dir: Directory to save covers
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)

    Returns:
        Tuple of (regenerated_count, skipped_count, error_count)
    """
    # Get all active documents from database
    documents = db.query(LibraryDocument).filter(
        LibraryDocument.is_active
    ).all()

    if not documents:
        logger.info("No documents found in database")
        return (0, 0, 0)

    logger.info("Found %s document(s) in database", len(documents))
    logger.info("Regenerating covers to %s", covers_dir)
    logger.info(
        "Settings: DPI=%s, max_width=%spx, format=%s, quality=%s",
        dpi, max_width, image_format, quality
    )

    # Determine file extension
    ext = "jpg" if image_format == "JPEG" else "png"

    # Clean up old covers first
    if covers_dir.exists():
        old_covers = list(covers_dir.glob("*_cover.*"))
        for old_cover in old_covers:
            try:
                old_cover.unlink()
                logger.debug("Removed old cover: %s", old_cover.name)
            except OSError:
                pass

    regenerated = 0
    skipped = 0
    errors = 0

    for doc in documents:
        # Resolve PDF path
        pdf_path = resolve_library_path(doc.file_path, library_dir, Path.cwd())

        if not pdf_path or not pdf_path.exists():
            logger.warning(
                "PDF not found for document %s: %s",
                doc.id,
                doc.file_path
            )
            errors += 1
            continue

        # Use document ID for cover filename (matches import pattern)
        cover_filename = f"{doc.id}_cover.{ext}"
        cover_path = covers_dir / cover_filename

        # Extract cover
        if extract_pdf_cover(pdf_path, cover_path, dpi, max_width, image_format, quality):
            # Update database with new cover path
            doc.cover_image_path = f"covers/{cover_filename}"
            db.commit()
            regenerated += 1
        else:
            logger.error("Failed to extract cover for document %s", doc.id)
            errors += 1

    logger.info("")
    logger.info("Regeneration complete:")
    logger.info("  Regenerated: %s", regenerated)
    logger.info("  Errors: %s", errors)

    return (regenerated, skipped, errors)


def extract_missing_covers_from_database(
    db,
    library_dir: Path,
    covers_dir: Path,
    dpi: int = DEFAULT_DPI,
    max_width: int = DEFAULT_MAX_WIDTH,
    image_format: Literal["JPEG", "PNG"] = DEFAULT_FORMAT,
    quality: int = DEFAULT_QUALITY
) -> tuple[int, int, int]:
    """
    Extract cover images for documents in database that don't have covers.

    Extracts covers for PDFs that either:
    1. Don't have a cover_image_path set in database, OR
    2. Have cover_image_path set but the file doesn't exist on disk

    Automatically verifies each extracted cover and removes invalid ones.

    Args:
        db: Database session
        library_dir: Directory containing PDFs
        covers_dir: Directory to save covers
        dpi: Resolution for rendering (default: 96)
        max_width: Maximum width in pixels (default: 400)
        image_format: Output format - "JPEG" or "PNG" (default: JPEG)
        quality: JPEG quality 1-100 (default: 80)

    Returns:
        Tuple of (extracted_count, skipped_count, error_count)
        - extracted_count: Successfully extracted and verified covers
        - skipped_count: Covers that already exist (both in DB and on disk)
        - error_count: Failed extractions or verification failures
    """
    from services.library.pdf_utils import resolve_library_path as resolve_pdf_path
    from services.library.pdf_utils import normalize_library_path

    # Get all active documents
    all_documents = db.query(LibraryDocument).filter(
        LibraryDocument.is_active
    ).all()

    if not all_documents:
        logger.info("No documents found in database")
        return (0, 0, 0)

    # Filter documents that need covers:
    # 1. No cover_image_path set, OR
    # 2. cover_image_path set but file doesn't exist
    documents_needing_covers = []
    for doc in all_documents:
        if not doc.cover_image_path:
            # No cover path in database
            documents_needing_covers.append((doc, None))
        else:
            # Check if file actually exists
            # Try to resolve the stored path
            stored_path = doc.cover_image_path
            cover_path = None

            # Try different resolution strategies
            stored_path_obj = Path(stored_path)
            if stored_path_obj.is_absolute():
                cover_path = stored_path_obj
            else:
                # Remove common prefixes
                path_clean = stored_path.replace('\\', '/')
                if path_clean.startswith('covers/'):
                    path_clean = path_clean[7:]
                elif 'covers/' in path_clean:
                    path_clean = path_clean.split('covers/')[-1]
                if path_clean.startswith('storage/library/covers/'):
                    path_clean = path_clean[24:]
                elif 'storage/library/covers/' in path_clean:
                    path_clean = path_clean.split('storage/library/covers/')[-1]
                if path_clean.startswith('storage/library/'):
                    path_clean = path_clean[16:]

                # Try covers_dir + filename
                cover_path = covers_dir / path_clean
                if not cover_path.exists() and '/' in path_clean:
                    cover_path = covers_dir / Path(path_clean).name

            # Also try document ID pattern as fallback
            if not cover_path or not cover_path.exists():
                for ext in ['.png', '.jpg', '.jpeg']:
                    test_path = covers_dir / f"{doc.id}_cover{ext}"
                    if test_path.exists():
                        cover_path = test_path
                        break

            # If file doesn't exist, we need to extract
            if not cover_path or not cover_path.exists():
                documents_needing_covers.append((doc, None))

    if not documents_needing_covers:
        logger.info("All documents already have covers (both in database and on disk)")
        return (0, 0, 0)

    logger.info("Found %s document(s) needing covers", len(documents_needing_covers))
    logger.info("Extracting missing covers to %s", covers_dir)
    logger.info(
        "Settings: DPI=%s, max_width=%spx, format=%s, quality=%s",
        dpi, max_width, image_format, quality
    )

    # Ensure covers directory exists
    covers_dir.mkdir(parents=True, exist_ok=True)

    # Determine file extension
    ext = "jpg" if image_format == "JPEG" else "png"

    extracted = 0
    skipped = 0
    errors = 0

    for doc, _ in documents_needing_covers:
        # Resolve PDF path
        pdf_path = resolve_pdf_path(doc.file_path, library_dir, Path.cwd())

        if not pdf_path or not pdf_path.exists():
            logger.warning(
                "PDF not found for document %s: %s",
                doc.id,
                doc.file_path
            )
            errors += 1
            continue

        # Use document ID for cover filename (matches import pattern)
        cover_filename = f"{doc.id}_cover.{ext}"
        cover_path = covers_dir / cover_filename

        # Check if cover already exists (both file and database)
        if cover_path.exists():
            # Verify the existing cover is valid
            is_valid, error_msg = verify_cover_image(cover_path)
            if is_valid:
                # Update database if path is missing
                if not doc.cover_image_path:
                    normalized_cover_path = normalize_library_path(
                        cover_path,
                        covers_dir,
                        Path.cwd()
                    )
                    doc.cover_image_path = normalized_cover_path
                    db.commit()
                logger.debug("Cover already exists and is valid for document %s: %s", doc.id, cover_filename)
                skipped += 1
                continue
            else:
                # Cover file exists but is invalid, remove it and regenerate
                logger.warning(
                    "Existing cover is invalid for document %s: %s. Will regenerate.",
                    doc.id,
                    error_msg
                )
                try:
                    cover_path.unlink()
                except Exception:
                    pass

        # Extract cover
        logger.info("Extracting cover for document %s (%s)...", doc.id, pdf_path.name)
        if extract_pdf_cover(pdf_path, cover_path, dpi, max_width, image_format, quality):
            # Verify the extracted cover
            is_valid, error_msg = verify_cover_image(cover_path)
            if is_valid:
                # Update database with cover path
                from services.library.pdf_utils import normalize_library_path
                normalized_cover_path = normalize_library_path(
                    cover_path,
                    covers_dir,
                    Path.cwd()
                )
                doc.cover_image_path = normalized_cover_path
                db.commit()
                extracted += 1
                logger.info("Successfully extracted and verified cover for document %s", doc.id)
            else:
                logger.error(
                    "Cover extraction succeeded but verification failed for document %s: %s",
                    doc.id,
                    error_msg
                )
                # Remove invalid cover file
                try:
                    cover_path.unlink()
                except Exception:
                    pass
                errors += 1
        else:
            logger.error("Failed to extract cover for document %s", doc.id)
            errors += 1

    logger.info("")
    logger.info("Missing covers extraction complete:")
    logger.info("  Extracted: %s", extracted)
    logger.info("  Skipped (already exist): %s", skipped)
    logger.info("  Errors: %s", errors)

    return (extracted, skipped, errors)


def verify_cover_image(cover_path: Path) -> tuple[bool, Optional[str]]:
    """
    Verify that a cover image file exists and is valid.

    Args:
        cover_path: Path to cover image file

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if cover is valid, False otherwise
        - error_message: Error message if invalid, None if valid
    """
    if not cover_path.exists():
        return False, f"Cover file does not exist: {cover_path}"

    if not cover_path.is_file():
        return False, f"Cover path is not a file: {cover_path}"

    try:
        file_size = cover_path.stat().st_size
        if file_size == 0:
            return False, f"Cover file is empty: {cover_path}"

        # Try to open and verify it's a valid image using PIL
        if PIL_AVAILABLE:
            try:
                img = Image.open(cover_path)
                img.verify()  # Verify it's a valid image file
                # Get image dimensions
                width, height = img.size
                if width == 0 or height == 0:
                    return False, f"Cover image has invalid dimensions: {width}x{height}"
                return True, None
            except Exception as e:
                return False, f"Cover file is not a valid image: {e}"

        # Fallback: check file extension and size
        ext = cover_path.suffix.lower()
        if ext not in ['.jpg', '.jpeg', '.png']:
            return False, f"Cover file has invalid extension: {ext}"

        # Minimum reasonable size for a cover image (1KB)
        if file_size < 1024:
            return False, f"Cover file is too small ({file_size} bytes), may be corrupted"

        return True, None

    except PermissionError:
        return False, f"Permission denied reading cover file: {cover_path}"
    except Exception as e:
        return False, f"Error verifying cover file: {e}"


def verify_all_covers_in_database(
    db,
    library_dir: Path,
    covers_dir: Path
) -> tuple[int, int, int, list]:
    """
    Verify all cover images for documents in the database.

    Checks:
    1. If cover_image_path is set in database
    2. If cover file exists on disk
    3. If cover file is a valid image

    Args:
        db: Database session
        library_dir: Directory containing PDFs (unused, kept for API compatibility)
        covers_dir: Directory containing cover images

    Returns:
        Tuple of (valid_count, missing_count, invalid_count, invalid_details)
        - valid_count: Number of valid covers
        - missing_count: Number of missing covers (path set but file doesn't exist)
        - invalid_count: Number of invalid covers (file exists but is corrupted)
        - invalid_details: List of tuples (doc_id, reason) for invalid covers
    """

    documents = db.query(LibraryDocument).filter(
        LibraryDocument.is_active
    ).all()

    if not documents:
        logger.info("No documents found in database")
        return (0, 0, 0, [])

    logger.info("Verifying covers for %s document(s)...", len(documents))
    logger.info("Covers directory: %s", covers_dir)

    valid_count = 0
    missing_count = 0
    invalid_count = 0
    invalid_details = []

    for doc in documents:
        if not doc.cover_image_path:
            missing_count += 1
            logger.debug("Document %s: No cover_image_path set", doc.id)
            continue

        # Resolve cover path - handle multiple path formats
        stored_path = doc.cover_image_path
        cover_path = None

        # Strategy 1: If absolute path, use it directly
        stored_path_obj = Path(stored_path)
        if stored_path_obj.is_absolute():
            cover_path = stored_path_obj
        else:
            # Strategy 2: Remove common prefixes and use covers_dir
            # Handle paths like "covers/filename.png" or "storage/library/covers/filename.png"
            path_clean = stored_path.replace('\\', '/')
            
            # Remove "covers/" prefix if present
            if path_clean.startswith('covers/'):
                path_clean = path_clean[7:]  # Remove "covers/"
            elif 'covers/' in path_clean:
                # Extract filename after "covers/"
                path_clean = path_clean.split('covers/')[-1]
            
            # Remove "storage/library/covers/" prefix if present
            if path_clean.startswith('storage/library/covers/'):
                path_clean = path_clean[24:]  # Remove "storage/library/covers/"
            elif 'storage/library/covers/' in path_clean:
                path_clean = path_clean.split('storage/library/covers/')[-1]
            
            # Remove "storage/library/" prefix if present (legacy)
            if path_clean.startswith('storage/library/'):
                path_clean = path_clean[16:]  # Remove "storage/library/"
            
            # Now try to resolve: could be just filename or relative path
            # First try: covers_dir + filename
            cover_path = covers_dir / path_clean
            
            # If that doesn't exist and path_clean contains slashes, try extracting just filename
            if not cover_path.exists() and '/' in path_clean:
                filename = Path(path_clean).name
                cover_path = covers_dir / filename

        # Verify the resolved path exists
        if not cover_path or not cover_path.exists():
            # Last resort: try to find by document ID pattern (common naming convention)
            # Try different extensions
            for ext in ['.png', '.jpg', '.jpeg']:
                test_path = covers_dir / f"{doc.id}_cover{ext}"
                if test_path.exists():
                    cover_path = test_path
                    break
            else:
                # Still not found - use the resolved path for error reporting
                if not cover_path:
                    # Fallback: construct from cleaned filename
                    cover_path = covers_dir / path_clean if 'path_clean' in locals() else covers_dir / stored_path

        is_valid, error_msg = verify_cover_image(cover_path)
        if is_valid:
            valid_count += 1
            logger.debug("Document %s: Cover valid (%s)", doc.id, cover_path.name)
        else:
            invalid_count += 1
            invalid_details.append((doc.id, doc.title or f"Document {doc.id}", error_msg or "Unknown error"))
            logger.warning(
                "Document %s (%s): Cover invalid - %s",
                doc.id,
                doc.title or f"Document {doc.id}",
                error_msg or "Unknown error"
            )

    logger.info("")
    logger.info("Cover verification complete:")
    logger.info("  Valid: %s", valid_count)
    logger.info("  Missing (no cover_image_path): %s", missing_count)
    logger.info("  Invalid: %s", invalid_count)

    if invalid_details:
        logger.info("")
        logger.info("Invalid covers details:")
        for doc_id, title, reason in invalid_details:
            logger.info("  - Document %s (%s): %s", doc_id, title, reason)

    return (valid_count, missing_count, invalid_count, invalid_details)


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
