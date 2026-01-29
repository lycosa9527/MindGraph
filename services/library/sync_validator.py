"""
Library Sync Validator Module

Validates and maintains consistency between:
1. PDF files in storage/library/
2. Cover images in storage/library/covers/
3. Database records in library_documents table

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session

from models.domain.library import LibraryDocument
from services.library import LibraryService
from services.library.pdf_utils import (
    validate_pdf_file,
    normalize_library_path,
    resolve_library_path
)
from services.library.pdf_importer import auto_import_new_pdfs
from services.library.pdf_cover_extractor import (
    extract_pdf_cover,
    check_cover_extraction_available
)

logger = logging.getLogger(__name__)


@dataclass
class SyncReport:
    """Report of library sync validation results."""
    pdfs_without_db: List[Path]
    db_records_without_pdf: List[LibraryDocument]
    pdfs_without_cover: List[Tuple[Path, Optional[int]]]  # (pdf_path, document_id)
    covers_without_pdf: List[Path]
    covers_without_db: List[Path]
    is_synced: bool


def validate_library_sync(
    db: Session,
    library_dir: Optional[Path] = None,
    covers_dir: Optional[Path] = None
) -> SyncReport:
    """
    Validate that PDFs, cover images, and database records are in sync.

    Checks:
    1. All PDFs in folder have database records
    2. All database records have corresponding PDF files
    3. All PDFs have cover images (or are marked as missing)
    4. All cover images correspond to valid PDFs/documents

    Args:
        db: Database session
        library_dir: Directory containing PDFs (default: storage/library)
        covers_dir: Directory containing covers (default: storage/library/covers)

    Returns:
        SyncReport with validation results
    """
    service = LibraryService(db)

    if library_dir is None:
        library_dir = service.storage_dir
    if covers_dir is None:
        covers_dir = service.covers_dir

    pdfs_without_db: List[Path] = []
    db_records_without_pdf: List[LibraryDocument] = []
    pdfs_without_cover: List[Tuple[Path, Optional[int]]] = []
    covers_without_pdf: List[Path] = []
    covers_without_db: List[Path] = []

    # Step 1: Scan PDFs in folder
    pdf_files: List[Path] = []
    if library_dir.exists():
        for pdf_path in library_dir.glob("*.pdf"):
            # Validate PDF magic bytes
            is_valid, _ = validate_pdf_file(pdf_path)
            if is_valid:
                pdf_files.append(pdf_path)
            else:
                logger.debug("Skipping invalid PDF in sync check: %s", pdf_path.name)

    logger.debug("Sync validation: Found %s valid PDF file(s)", len(pdf_files))

    # Step 2: Get all database records
    db_documents = db.query(LibraryDocument).filter(
        LibraryDocument.is_active
    ).all()

    logger.debug("Sync validation: Found %s database record(s)", len(db_documents))

    # Step 3: Check PDFs -> Database
    pdf_names_in_db = set()
    for pdf_path in pdf_files:
        pdf_name = pdf_path.name
        found = False

        for doc in db_documents:
            # Check if document file_path matches this PDF
            doc_path_resolved = resolve_library_path(
                doc.file_path,
                service.storage_dir,
                Path.cwd()
            )
            if doc_path_resolved and doc_path_resolved.name == pdf_name:
                found = True
                pdf_names_in_db.add(pdf_name)
                break

        if not found:
            pdfs_without_db.append(pdf_path)

    # Step 4: Check Database -> PDFs
    for doc in db_documents:
        doc_path_resolved = resolve_library_path(
            doc.file_path,
            service.storage_dir,
            Path.cwd()
        )
        if not doc_path_resolved or not doc_path_resolved.exists():
            db_records_without_pdf.append(doc)

    # Step 5: Check PDFs -> Covers
    if covers_dir.exists():
        cover_files = list(covers_dir.glob("*_cover.*"))

        for pdf_path in pdf_files:
            pdf_name = pdf_path.name
            pdf_stem = pdf_path.stem

            # Find corresponding document
            doc_id = None
            for doc in db_documents:
                doc_path_resolved = resolve_library_path(
                    doc.file_path,
                    service.storage_dir,
                    Path.cwd()
                )
                if doc_path_resolved and doc_path_resolved.name == pdf_name:
                    doc_id = doc.id
                    break

            # Check for cover (try both naming patterns)
            has_cover = False
            if doc_id:
                # Try document_id pattern
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    cover_path = covers_dir / f"{doc_id}_cover{ext}"
                    if cover_path.exists():
                        has_cover = True
                        break

            if not has_cover:
                # Try pdf_name pattern
                cover_path = covers_dir / f"{pdf_stem}_cover.png"
                if cover_path.exists():
                    has_cover = True

            if not has_cover:
                pdfs_without_cover.append((pdf_path, doc_id))

    # Step 6: Check Covers -> PDFs/Database
    if covers_dir.exists():
        cover_files = list(covers_dir.glob("*_cover.*"))
        for cover_path in cover_files:
            cover_stem = cover_path.stem.replace('_cover', '')

            # Try to match by document_id
            try:
                doc_id = int(cover_stem)
                doc = db.query(LibraryDocument).filter(
                    LibraryDocument.id == doc_id
                ).first()
                if doc:
                    doc_path_resolved = resolve_library_path(
                        doc.file_path,
                        service.storage_dir,
                        Path.cwd()
                    )
                    if not doc_path_resolved or not doc_path_resolved.exists():
                        covers_without_pdf.append(cover_path)
                    continue
            except ValueError:
                pass

            # Try to match by PDF name
            pdf_path = library_dir / f"{cover_stem}.pdf"
            if not pdf_path.exists():
                covers_without_pdf.append(cover_path)
                # Also check if it has a database record
                found_in_db = False
                for doc in db_documents:
                    doc_path_resolved = resolve_library_path(
                        doc.file_path,
                        service.storage_dir,
                        Path.cwd()
                    )
                    if doc_path_resolved and doc_path_resolved.stem == cover_stem:
                        found_in_db = True
                        break
                if not found_in_db:
                    covers_without_db.append(cover_path)

    is_synced = (
        len(pdfs_without_db) == 0 and
        len(db_records_without_pdf) == 0 and
        len(pdfs_without_cover) == 0 and
        len(covers_without_pdf) == 0 and
        len(covers_without_db) == 0
    )

    return SyncReport(
        pdfs_without_db=pdfs_without_db,
        db_records_without_pdf=db_records_without_pdf,
        pdfs_without_cover=pdfs_without_cover,
        covers_without_pdf=covers_without_pdf,
        covers_without_db=covers_without_db,
        is_synced=is_synced
    )


def sync_library(
    db: Session,
    library_dir: Optional[Path] = None,
    covers_dir: Optional[Path] = None,
    extract_covers: bool = True,
    dpi: int = 200,
    remove_orphans: bool = True
) -> Dict[str, int]:
    """
    Sync library: auto-fix missing records, covers, and remove orphans.

    Args:
        db: Database session
        library_dir: Directory containing PDFs (default: storage/library)
        covers_dir: Directory containing covers (default: storage/library/covers)
        extract_covers: If True, extract missing covers (default: True)
        dpi: DPI for cover extraction (default: 200)
        remove_orphans: If True, remove orphaned records and covers (default: True)

    Returns:
        Dict with counts of actions taken:
        {
            'imported': number of PDFs imported,
            'covers_extracted': number of covers extracted,
            'orphan_records_removed': number of orphaned DB records removed,
            'orphan_covers_removed': number of orphaned covers removed
        }
    """
    service = LibraryService(db)

    if library_dir is None:
        library_dir = service.storage_dir
    if covers_dir is None:
        covers_dir = service.covers_dir

    report = validate_library_sync(db, library_dir, covers_dir)

    results = {
        'imported': 0,
        'covers_extracted': 0,
        'orphan_records_removed': 0,
        'orphan_covers_removed': 0
    }

    # Fix 1: Import PDFs without database records
    if report.pdfs_without_db:
        logger.info("Syncing: Importing %s PDF(s) without database records", len(report.pdfs_without_db))
        imported, _ = auto_import_new_pdfs(db, library_dir, extract_covers, dpi)
        results['imported'] = imported

    # Fix 2: Extract missing covers
    if report.pdfs_without_cover and extract_covers:
        is_available, error_msg = check_cover_extraction_available()
        if is_available:
            logger.info("Syncing: Extracting %s missing cover(s)", len(report.pdfs_without_cover))
            for pdf_path, doc_id in report.pdfs_without_cover:
                try:
                    if doc_id:
                        # Use document_id naming pattern
                        cover_path = covers_dir / f"{doc_id}_cover.png"
                    else:
                        # Use pdf_name pattern (will be renamed later)
                        cover_path = covers_dir / f"{pdf_path.stem}_cover.png"

                    if extract_pdf_cover(pdf_path, cover_path, dpi):
                        results['covers_extracted'] += 1
                        # Update database if document exists
                        if doc_id:
                            doc = db.query(LibraryDocument).filter(
                                LibraryDocument.id == doc_id
                            ).first()
                            if doc:
                                cover_image_path = normalize_library_path(
                                    cover_path,
                                    covers_dir,
                                    Path.cwd()
                                )
                                doc.cover_image_path = cover_image_path
                                db.commit()
                except Exception as e:
                    logger.error("Error extracting cover for %s: %s", pdf_path.name, e)
        else:
            logger.warning("Cannot extract covers: %s", error_msg)

    # Fix 3: Remove orphaned database records
    if report.db_records_without_pdf and remove_orphans:
        logger.info("Syncing: Removing %s orphaned database record(s)", len(report.db_records_without_pdf))
        for doc in report.db_records_without_pdf:
            try:
                doc.is_active = False
                results['orphan_records_removed'] += 1
            except Exception as e:
                logger.error("Error removing orphaned record %s: %s", doc.id, e)
        db.commit()

    # Fix 4: Remove orphaned cover images
    if report.covers_without_pdf and remove_orphans:
        logger.info("Syncing: Removing %s orphaned cover image(s)", len(report.covers_without_pdf))
        for cover_path in report.covers_without_pdf:
            try:
                cover_path.unlink()
                results['orphan_covers_removed'] += 1
            except Exception as e:
                logger.error("Error removing orphaned cover %s: %s", cover_path.name, e)

    if results['imported'] > 0 or results['covers_extracted'] > 0 or \
       results['orphan_records_removed'] > 0 or results['orphan_covers_removed'] > 0:
        logger.info(
            "Sync complete: imported=%s, covers=%s, removed_records=%s, removed_covers=%s",
            results['imported'],
            results['covers_extracted'],
            results['orphan_records_removed'],
            results['orphan_covers_removed']
        )
    else:
        logger.debug("Sync complete: No changes needed")

    return results
