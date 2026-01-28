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


logger = logging.getLogger(__name__)


def _try_extract_cover(
    pdf_path: Path,
    cover_path: Path,
    dpi: int
) -> Optional[str]:
    """
    Try to extract cover image for a PDF if it doesn't exist.

    Args:
        pdf_path: Path to PDF file
        cover_path: Path where cover should be saved
        dpi: DPI for cover extraction

    Returns:
        Cover image path if extraction successful, None otherwise
    """
    if cover_path.exists():
        return str(cover_path)

    is_available, error_msg = check_cover_extraction_available()
    if not is_available:
        logger.debug(
            "Skipping cover extraction for %s: %s",
            pdf_path.name,
            error_msg
        )
        return None

    logger.debug("Extracting cover for %s", pdf_path.name)
    if extract_pdf_cover(pdf_path, cover_path, dpi):
        return str(cover_path)

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
    dpi: int = 200
) -> Tuple[int, int]:
    """
    Import PDFs from storage/library/ into the database.
    
    Scans the library directory for PDF files and creates LibraryDocument records
    for any PDFs that aren't already in the database. Skips PDFs that already exist.
    
    Args:
        db: Database session
        library_dir: Directory containing PDFs (default: storage/library)
        covers_dir: Directory containing cover images (default: storage/library/covers)
        uploader_id: User ID to use as uploader (default: first admin user)
        extract_covers: If True, extract cover images for PDFs that don't have covers (default: True)
        dpi: DPI for cover extraction (default: 200)
    
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

    imported_count = 0
    skipped_count = 0

    for pdf_path in pdf_files:
        pdf_name = pdf_path.name
        file_size = pdf_path.stat().st_size

        # Use the same path format as LibraryService (absolute path)
        final_path = service.storage_dir / pdf_name
        file_path = str(final_path.resolve())

        # Check if already exists in database (by filename match)
        existing = db.query(LibraryDocument).filter(
            LibraryDocument.file_path.like(f"%{pdf_name}")
        ).first()
        
        if existing:
            logger.debug("Skipping (already exists): %s (ID: %s)", pdf_name, existing.id)
            skipped_count += 1
            continue

        # Generate title from filename (remove extension)
        title = pdf_path.stem

        # Look for cover image or extract if needed
        cover_image_path = None
        cover_filename = f"{pdf_path.stem}_cover.png"
        cover_path = service.covers_dir / cover_filename
        
        if extract_covers:
            cover_image_path = _try_extract_cover(pdf_path, cover_path, dpi)
        elif cover_path.exists():
            cover_image_path = str(cover_path)

        # Create document record
        document = LibraryDocument(
            title=title,
            description=None,
            file_path=file_path,
            file_size=file_size,
            cover_image_path=cover_image_path,
            uploader_id=uploader_id,
            views_count=0,
            likes_count=0,
            comments_count=0,
            is_active=True
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        logger.info(
            "Imported PDF: %s (ID: %s, Size: %.2f MB%s)",
            pdf_name,
            document.id,
            file_size / 1024 / 1024,
            f", Cover: {cover_image_path}" if cover_image_path else ""
        )
        imported_count += 1

    logger.info("Import complete: %s imported, %s skipped", imported_count, skipped_count)
    return (imported_count, skipped_count)
