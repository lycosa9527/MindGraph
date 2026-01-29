"""
PDF Importer Module for Library

Scans storage/library/ for PDF files and creates LibraryDocument records
for any PDFs that aren't already in the database.

Can be used programmatically or called from command line.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from models.domain.library import LibraryDocument
from models.domain.auth import User
from services.library import LibraryService
from services.library.pdf_cover_extractor import (
    extract_pdf_cover,
    check_cover_extraction_available
)
from services.library.pdf_utils import (
    validate_pdf_file,
    normalize_library_path,
    resolve_library_path
)
from services.library.pdf_optimizer import (
    optimize_pdf,
    should_optimize_pdf,
    check_qpdf_available
)


logger = logging.getLogger(__name__)


def _try_extract_cover(
    pdf_path: Path,
    cover_path: Path,
    dpi: int
) -> Optional[str]:
    """
    Try to extract cover image for a PDF if it doesn't exist.

    Verifies existing covers and validates newly extracted covers.
    Invalid covers are automatically removed.

    Args:
        pdf_path: Path to PDF file
        cover_path: Path where cover should be saved
        dpi: DPI for cover extraction

    Returns:
        Cover image path if extraction successful and verified, None otherwise
    """
    if cover_path.exists():
        # Verify existing cover is valid
        from services.library.pdf_cover_extractor import verify_cover_image
        is_valid, error_msg = verify_cover_image(cover_path)
        if is_valid:
            logger.info("Using existing valid cover: %s", cover_path.name)
            return str(cover_path)
        logger.warning(
            "Existing cover is invalid, will regenerate: %s - %s",
            cover_path.name,
            error_msg
        )
        # Remove invalid cover
        try:
            cover_path.unlink()
        except Exception:
            pass

    is_available, error_msg = check_cover_extraction_available()
    if not is_available:
        logger.warning(
            "Skipping cover extraction for %s: %s",
            pdf_path.name,
            error_msg
        )
        return None

    logger.info("Extracting cover for %s...", pdf_path.name)
    if extract_pdf_cover(pdf_path, cover_path, dpi):
        # Verify the extracted cover
        from services.library.pdf_cover_extractor import verify_cover_image
        is_valid, verify_error = verify_cover_image(cover_path)
        if is_valid:
            logger.info("Successfully extracted and verified cover: %s", cover_path.name)
            return str(cover_path)
        logger.warning(
            "Cover extraction succeeded but verification failed for %s: %s",
            pdf_path.name,
            verify_error
        )
        # Remove invalid cover
        try:
            cover_path.unlink()
        except Exception:
            pass
        return None

    logger.warning("Failed to extract cover for %s", pdf_path.name)
    return None


def get_admin_user(db: Session) -> Optional[User]:
    """
    Get an admin user to use as uploader.
    
    Returns the first admin user found (by role='admin'), or first user as fallback.
    
    Args:
        db: Database session
        
    Returns:
        User instance or None if no users exist
    """
    admin = db.query(User).filter(User.role == 'admin').first()
    if admin:
        return admin

    # Fallback: get first user
    user = db.query(User).first()
    return user


def import_pdfs_from_folder(
    db: Session,
    library_dir: Optional[Path] = None,
    covers_dir: Optional[Path] = None,
    uploader_id: Optional[int] = None,
    extract_covers: bool = True,
    dpi: int = 200,
    auto_optimize: bool = True,
    optimize_backup: bool = True,
    fail_on_optimization_error: bool = False
) -> Tuple[int, int]:
    """
    Import PDFs from storage/library/ into the database.
    
    Scans the library directory for PDF files and creates LibraryDocument records
    for any PDFs that aren't already in the database. Skips PDFs that already exist.
    
    Automatically checks xref location for each PDF:
    - If xref is at beginning: Import directly
    - If xref is at end: Optimize (linearize) first, then import
    
    Args:
        db: Database session
        library_dir: Directory containing PDFs (default: storage/library)
        covers_dir: Directory containing cover images (default: storage/library/covers)
        uploader_id: User ID to use as uploader (default: first admin user)
        extract_covers: If True, extract cover images for PDFs that don't have covers (default: True)
        dpi: DPI for cover extraction (default: 200)
        auto_optimize: If True, automatically optimize PDFs with xref at end (default: True)
        optimize_backup: If True, create backup before optimizing (default: True)
        fail_on_optimization_error: If True, skip importing PDFs that fail optimization (default: False)
    
    Returns:
        Tuple of (imported_count, skipped_count)
        
    Raises:
        ValueError: If no users exist in database or uploader_id is invalid
    """
    # Use LibraryService to get correct storage paths
    service = LibraryService(db)

    if library_dir is None:
        library_dir = service.storage_dir
    if covers_dir is None:
        covers_dir = service.covers_dir

    if not library_dir.exists():
        raise ValueError(f"Library directory not found: {library_dir}")

    # Get uploader
    if uploader_id is None:
        admin_user = get_admin_user(db)
        if not admin_user:
            raise ValueError("No users found in database. Please create a user first.")
        uploader_id = admin_user.id
        logger.info("Using uploader: %s (ID: %s)", admin_user.name, uploader_id)
    else:
        user = db.query(User).filter(User.id == uploader_id).first()
        if not user:
            raise ValueError(f"User with ID {uploader_id} not found")
        logger.info("Using uploader: %s (ID: %s)", user.name, uploader_id)

    # Find all PDF files
    pdf_files = list(library_dir.glob("*.pdf"))
    if not pdf_files:
        logger.info("No PDF files found in %s", library_dir)
        return (0, 0)

    logger.info("Found %s PDF file(s) in %s", len(pdf_files), library_dir)
    if auto_optimize:
        logger.info("Auto-optimization enabled: Will check xref location and optimize if needed")

    imported_count = 0
    skipped_count = 0
    covers_extracted = 0
    covers_failed = 0

    # Check optimization tools availability
    qpdf_available = check_qpdf_available()

    if auto_optimize:
        if not qpdf_available:
            logger.info("qpdf not available, will use PyPDF2 for optimization if available")
        else:
            logger.info("Using qpdf for optimization (recommended)")

    optimized_count = 0
    optimization_errors = 0

    for pdf_path in pdf_files:
        pdf_name = pdf_path.name

        # Validate PDF file (magic bytes check)
        is_valid, error_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            logger.warning(
                "Skipping invalid PDF file %s: %s",
                pdf_name,
                error_msg
            )
            skipped_count += 1
            continue

        # STEP 1: Always check xref location first
        should_opt, reason, info = should_optimize_pdf(pdf_path)

        if info.analysis_error:
            logger.warning("Could not analyze PDF structure for %s: %s", pdf_name, info.analysis_error)
        else:
            logger.debug(
                "PDF %s: xref at %s (%s KB), linearized: %s, needs optimization: %s",
                pdf_name,
                info.xref_location,
                info.xref_size_kb,
                info.is_linearized,
                info.needs_optimization
            )

        # STEP 2: Optimize if needed and requested
        if auto_optimize and should_opt:
            logger.info("Optimizing %s: %s", pdf_name, reason)
            success, error, stats = optimize_pdf(
                pdf_path,
                backup=optimize_backup,
                prefer_qpdf=qpdf_available
            )
            if success:
                optimized_count += 1
                if stats['was_optimized']:
                    logger.info(
                        "Optimized %s: %s -> %s bytes (%+s bytes, method: %s)",
                        pdf_name,
                        f"{stats['original_size']:,}",
                        f"{stats['new_size']:,}",
                        f"{stats['size_change']:,}",
                        stats['method']
                    )
            else:
                optimization_errors += 1
                logger.warning("Failed to optimize %s: %s", pdf_name, error)
                if fail_on_optimization_error:
                    logger.warning("Skipping %s due to optimization failure", pdf_name)
                    skipped_count += 1
                    continue
        elif should_opt and not auto_optimize:
            logger.info(
                "PDF %s needs optimization (xref at %s) but optimization disabled. "
                "Use auto_optimize=True to enable automatic optimization.",
                pdf_name,
                info.xref_location
            )

        file_size = pdf_path.stat().st_size

        # Normalize path for cross-platform compatibility
        file_path = normalize_library_path(
            pdf_path,
            service.storage_dir,
            Path.cwd()
        )

        # Check if already exists in database (exact filename match)
        # Normalize stored paths for comparison
        existing = db.query(LibraryDocument).filter(
            LibraryDocument.file_path.like(f"%{pdf_name}")
        ).all()

        # Check if any existing record matches this file
        found_existing = False
        for doc in existing:
            # Compare normalized paths
            doc_path_normalized = normalize_library_path(
                Path(doc.file_path) if Path(doc.file_path).is_absolute() else service.storage_dir / pdf_name,
                service.storage_dir,
                Path.cwd()
            )
            # Use Path().name for exact filename comparison to avoid partial matches
            if doc_path_normalized == file_path or Path(doc.file_path).name == pdf_name:
                found_existing = True
                break

        if found_existing:
            logger.debug("Skipping (already exists): %s", pdf_name)
            skipped_count += 1
            continue

        # Generate title from filename (remove extension)
        title = pdf_path.stem

        # Look for cover image or extract if needed
        # Note: Cover will be renamed to {document_id}_cover.png after document creation
        # For now, use pdf_name pattern for initial extraction
        cover_image_path = None
        cover_filename = f"{pdf_path.stem}_cover.png"
        cover_path = service.covers_dir / cover_filename

        if extract_covers:
            cover_image_path = _try_extract_cover(pdf_path, cover_path, dpi)
            # Normalize cover path if extracted
            if cover_image_path:
                covers_extracted += 1
                cover_image_path = normalize_library_path(
                    Path(cover_image_path),
                    service.covers_dir,
                    Path.cwd()
                )
            else:
                covers_failed += 1
        elif cover_path.exists():
            cover_image_path = normalize_library_path(
                cover_path,
                service.covers_dir,
                Path.cwd()
            )

        # Create document record
        document = LibraryDocument(
            title=title,
            description=None,
            file_path=file_path,
            file_size=file_size,
            cover_image_path=None,  # Will be set after cover rename
            uploader_id=uploader_id,
            views_count=0,
            likes_count=0,
            comments_count=0,
            is_active=True
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        # Rename cover to use document_id pattern if it exists
        if cover_image_path:
            old_cover_path = Path(cover_image_path)
            if old_cover_path.exists():
                new_cover_path = service.covers_dir / f"{document.id}_cover.png"
                try:
                    old_cover_path.rename(new_cover_path)
                    cover_image_path = normalize_library_path(
                        new_cover_path,
                        service.covers_dir,
                        Path.cwd()
                    )
                    document.cover_image_path = cover_image_path
                    db.commit()
                except Exception as e:
                    logger.warning(
                        "Failed to rename cover for %s: %s",
                        pdf_name,
                        e
                    )
                    # Keep old cover path
                    document.cover_image_path = cover_image_path
                    db.commit()

        logger.info(
            "Imported PDF: %s (ID: %s, Size: %.2f MB%s)",
            pdf_name,
            document.id,
            file_size / 1024 / 1024,
            f", Cover: {document.cover_image_path}" if document.cover_image_path else ""
        )
        imported_count += 1

    logger.info("Import complete: %s imported, %s skipped", imported_count, skipped_count)
    if auto_optimize:
        logger.info("Optimization: %s optimized, %s errors", optimized_count, optimization_errors)
    if extract_covers and (covers_extracted > 0 or covers_failed > 0):
        logger.info("Cover extraction: %s extracted, %s failed", covers_extracted, covers_failed)
    return (imported_count, skipped_count)


def auto_import_new_pdfs(
    db: Session,
    library_dir: Optional[Path] = None,
    extract_covers: bool = True,
    dpi: int = 200,
    auto_optimize: bool = True,
    optimize_backup: bool = True,
    fail_on_optimization_error: bool = False
) -> Tuple[int, int]:
    """
    Automatically import new PDFs from storage/library/ folder.

    Scans for PDF files, validates them, and imports any that don't have
    database records. Automatically checks xref location and linearizes
    PDFs if xref is at the end (for efficient lazy loading).

    Args:
        db: Database session
        library_dir: Directory containing PDFs (default: storage/library)
        extract_covers: If True, extract cover images (default: True)
        dpi: DPI for cover extraction (default: 200)
        auto_optimize: If True, linearize PDFs with xref at end (default: True)
        optimize_backup: If True, create backup before optimizing (default: True)
        fail_on_optimization_error: If True, skip importing PDFs that fail optimization (default: False)

    Returns:
        Tuple of (imported_count, skipped_count)
    """
    service = LibraryService(db)

    if library_dir is None:
        library_dir = service.storage_dir

    if not library_dir.exists():
        logger.warning("Library directory not found: %s", library_dir)
        return (0, 0)

    # Find all PDF files
    pdf_files = list(library_dir.glob("*.pdf"))
    if not pdf_files:
        logger.debug("No PDF files found in %s", library_dir)
        return (0, 0)

    logger.info("Auto-import: Found %s PDF file(s) in %s", len(pdf_files), library_dir)

    # Check optimization tools availability
    qpdf_available = False
    if auto_optimize:
        qpdf_available = check_qpdf_available()
        if qpdf_available:
            logger.debug("Using qpdf for PDF optimization")
        else:
            logger.debug("qpdf not available, will use PyPDF2 for optimization if available")

    imported_count = 0
    skipped_count = 0
    optimized_count = 0
    covers_extracted = 0
    covers_failed = 0

    for pdf_path in pdf_files:
        pdf_name = pdf_path.name

        # Validate PDF file
        is_valid, error_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            logger.debug("Skipping invalid PDF: %s - %s", pdf_name, error_msg)
            skipped_count += 1
            continue

        # Check if already exists in database
        existing = db.query(LibraryDocument).filter(
            LibraryDocument.file_path.like(f"%{pdf_name}")
        ).first()

        if existing:
            logger.debug("Skipping (already exists): %s", pdf_name)
            skipped_count += 1
            continue

        # Import this PDF
        try:
            # STEP 1: Check xref location and optimize if needed
            if auto_optimize:
                should_opt, reason, info = should_optimize_pdf(pdf_path)
                if should_opt:
                    logger.info("Optimizing %s: %s", pdf_name, reason)
                    success, error, stats = optimize_pdf(
                        pdf_path,
                        backup=optimize_backup,
                        prefer_qpdf=qpdf_available
                    )
                    if success and stats['was_optimized']:
                        optimized_count += 1
                        logger.info(
                            "Optimized %s: %s -> %s bytes (method: %s)",
                            pdf_name,
                            f"{stats['original_size']:,}",
                            f"{stats['new_size']:,}",
                            stats['method']
                        )
                    elif not success:
                        logger.warning("Failed to optimize %s: %s", pdf_name, error)
                        if fail_on_optimization_error:
                            logger.warning("Skipping %s due to optimization failure", pdf_name)
                            skipped_count += 1
                            continue
                else:
                    logger.debug(
                        "PDF %s already optimized (xref at %s)",
                        pdf_name,
                        info.xref_location if not info.analysis_error else "unknown"
                    )

            # Get file size after potential optimization
            file_size = pdf_path.stat().st_size
            title = pdf_path.stem

            # Normalize path
            file_path = normalize_library_path(pdf_path, service.storage_dir, Path.cwd())

            # Get uploader
            admin_user = get_admin_user(db)
            if not admin_user:
                logger.error("Cannot auto-import: No users found in database")
                break
            uploader_id = admin_user.id

            # Extract cover if needed
            cover_image_path = None
            if extract_covers:
                cover_filename = f"{pdf_path.stem}_cover.png"
                cover_path = service.covers_dir / cover_filename
                cover_image_path = _try_extract_cover(pdf_path, cover_path, dpi)
                if cover_image_path:
                    covers_extracted += 1
                    cover_image_path = normalize_library_path(
                        Path(cover_image_path),
                        service.covers_dir,
                        Path.cwd()
                    )
                else:
                    covers_failed += 1

            # Create document record
            document = LibraryDocument(
                title=title,
                description=None,
                file_path=file_path,
                file_size=file_size,
                cover_image_path=None,
                uploader_id=uploader_id,
                views_count=0,
                likes_count=0,
                comments_count=0,
                is_active=True
            )

            db.add(document)
            db.commit()
            db.refresh(document)

            # Rename cover to use document_id pattern if it exists
            if cover_image_path:
                old_cover_path = Path(cover_image_path)
                if old_cover_path.exists():
                    new_cover_path = service.covers_dir / f"{document.id}_cover.png"
                    try:
                        old_cover_path.rename(new_cover_path)
                        cover_image_path = normalize_library_path(
                            new_cover_path,
                            service.covers_dir,
                            Path.cwd()
                        )
                        document.cover_image_path = cover_image_path
                        db.commit()
                    except Exception as rename_err:
                        logger.warning(
                            "Failed to rename cover for %s: %s",
                            pdf_name,
                            rename_err
                        )
                        document.cover_image_path = cover_image_path
                        db.commit()

            logger.info(
                "Auto-imported PDF: %s (ID: %s, Size: %.2f MB%s)",
                pdf_name,
                document.id,
                file_size / 1024 / 1024,
                f", Cover: {document.cover_image_path}" if document.cover_image_path else ""
            )
            imported_count += 1

        except Exception as e:
            logger.error("Error auto-importing PDF %s: %s", pdf_name, e, exc_info=True)
            db.rollback()
            skipped_count += 1

    if imported_count > 0:
        logger.info(
            "Auto-import complete: %s imported, %s skipped, %s optimized",
            imported_count,
            skipped_count,
            optimized_count
        )
        if extract_covers:
            logger.info(
                "Cover extraction: %s extracted, %s failed",
                covers_extracted,
                covers_failed
            )
    else:
        logger.debug("Auto-import: No new PDFs to import")

    return (imported_count, skipped_count)


def optimize_existing_library_pdfs(
    db: Session,
    library_dir: Optional[Path] = None,
    backup: bool = False
) -> Tuple[int, int, int]:
    """
    Optimize existing PDFs in the library that are already in the database.

    This function:
    1. Gets all active documents from database
    2. Checks if each PDF needs optimization (xref at end)
    3. Linearizes PDFs that need it
    4. Updates file_size in database after optimization

    Use this to fix PDFs that were imported before optimization was enabled.

    Args:
        db: Database session
        library_dir: Directory containing PDFs (default: storage/library)
        backup: If True, create backup before optimizing (default: False)

    Returns:
        Tuple of (optimized_count, skipped_count, error_count)
    """
    service = LibraryService(db)

    if library_dir is None:
        library_dir = service.storage_dir

    if not library_dir.exists():
        logger.warning("Library directory not found: %s", library_dir)
        return (0, 0, 0)

    # Get all active documents from database
    documents = db.query(LibraryDocument).filter(
        LibraryDocument.is_active
    ).all()

    if not documents:
        logger.info("No documents found in database")
        return (0, 0, 0)

    logger.info("Checking %s existing library document(s) for optimization", len(documents))

    # Check optimization tools
    qpdf_available = check_qpdf_available()

    if qpdf_available:
        logger.info("Using qpdf for optimization")
    else:
        logger.info("qpdf not available, will use PyPDF2 for optimization if available")

    optimized_count = 0
    skipped_count = 0
    error_count = 0

    for doc in documents:
        # Resolve file path
        pdf_path = resolve_library_path(
            doc.file_path,
            service.storage_dir,
            Path.cwd()
        )

        if not pdf_path or not pdf_path.exists():
            logger.warning(
                "PDF file not found for document %s: %s",
                doc.id,
                doc.file_path
            )
            error_count += 1
            continue

        pdf_name = pdf_path.name

        # Validate PDF
        is_valid, error_msg = validate_pdf_file(pdf_path)
        if not is_valid:
            logger.warning(
                "Invalid PDF for document %s: %s - %s",
                doc.id,
                pdf_name,
                error_msg
            )
            error_count += 1
            continue

        # Check if optimization needed
        should_opt, reason, info = should_optimize_pdf(pdf_path)

        if not should_opt:
            logger.debug(
                "Document %s (%s): already optimized (xref at %s)",
                doc.id,
                pdf_name,
                info.xref_location
            )
            skipped_count += 1
            continue

        # Optimize
        logger.info(
            "Optimizing document %s (%s): %s",
            doc.id,
            pdf_name,
            reason
        )

        old_size = pdf_path.stat().st_size
        success, error, stats = optimize_pdf(
            pdf_path,
            backup=backup,
            prefer_qpdf=qpdf_available
        )

        if success and stats['was_optimized']:
            optimized_count += 1

            # Get actual file size and verify it changed
            try:
                new_size = pdf_path.stat().st_size
            except OSError as e:
                logger.error("  Cannot read file size after optimization: %s", e)
                error_count += 1
                continue

            # Only update database if size actually changed
            if new_size != doc.file_size:
                doc.file_size = new_size
                db.commit()
                logger.info(
                    "  Optimized: %s -> %s bytes (%+s, method: %s)",
                    f"{old_size:,}",
                    f"{new_size:,}",
                    f"{stats['size_change']:,}",
                    stats['method']
                )
            else:
                logger.info(
                    "  Optimized (size unchanged): %s bytes (method: %s)",
                    f"{new_size:,}",
                    stats['method']
                )
        elif success:
            skipped_count += 1
            logger.debug("  No optimization needed")
        else:
            error_count += 1
            logger.error("  Failed: %s", error)

    logger.info(
        "Optimization complete: %s optimized, %s skipped, %s errors",
        optimized_count,
        skipped_count,
        error_count
    )

    return (optimized_count, skipped_count, error_count)
