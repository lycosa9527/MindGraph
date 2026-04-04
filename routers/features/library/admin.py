"""Library Admin Endpoints.

Admin-only API endpoints for library management: scan, register, and visibility.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.library import LibraryDocument
from services.library import LibraryService
from services.library.image_path_resolver import (
    IMAGE_EXTENSIONS,
    count_pages,
    detect_image_pattern,
    list_page_images,
)
from services.library.library_path_utils import (
    extract_folder_name_from_pages_dir_path,
    normalize_library_path,
    resolve_library_path,
)

from .helpers import require_admin
from .models import DocumentVisibilityUpdate, RenameRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def _canonical_path(stored_path: str, storage_dir: Path, project_root: Path) -> str:
    """
    Convert a stored pages_dir_path to a canonical forward-slash relative form.

    Handles three legacy formats produced by different environments:
      1. Already relative with forward slashes:  ``storage/library/Book``  → unchanged
      2. Windows back-slashes (dev machine):     ``storage\\library\\Book`` → ``storage/library/Book``
      3. Absolute paths (Linux or Windows):      ``/app/storage/library/Book``
                                                 ``C:\\Users\\...\\Book``   → ``storage/library/Book``
    """
    normalized = stored_path.replace("\\", "/")

    first_component = normalized.lstrip("/").split("/")[0]
    is_absolute = normalized.startswith("/") or ":" in first_component
    if not is_absolute:
        return normalized

    try:
        result = normalize_library_path(Path(normalized), storage_dir, project_root)
        if result and "/" in result:
            return result
    except Exception as exc:
        logger.debug("Failed to normalize library path: %s", exc)

    folder_name = extract_folder_name_from_pages_dir_path(stored_path)
    if folder_name:
        try:
            rel = str(storage_dir.relative_to(project_root)).replace("\\", "/")
            return f"{rel}/{folder_name}"
        except ValueError:
            pass

    return normalized


def _pages_dir_key_for_lookup(
    pages_dir_path: str,
    storage_dir: Path,
    project_root: Path,
) -> str:
    """
    Path key that matches the disk scan (normalize_library_path on the real folder).

    _canonical_path alone can disagree with normalize_library_path when the stored
    value is a relative path whose prefix does not match storage_dir relative to
    cwd (e.g. configured storage layout vs legacy DB string). Resolving the
    on-disk folder and re-normalizing aligns Windows / WSL / Linux layouts.
    """
    resolved = resolve_library_path(pages_dir_path, storage_dir, project_root)
    if resolved and resolved.exists() and resolved.is_dir():
        return normalize_library_path(resolved, storage_dir, project_root)
    return _canonical_path(pages_dir_path, storage_dir, project_root)


def _build_doc_lookups(all_docs: list, storage_dir: Path, project_root: Path) -> tuple:
    """Build path-keyed and folder-name-keyed lookups from a list of LibraryDocuments."""
    docs_by_path: dict = {}
    docs_by_folder: dict = {}
    for doc in all_docs:
        if doc.pages_dir_path:
            canonical = _pages_dir_key_for_lookup(doc.pages_dir_path, storage_dir, project_root)
            docs_by_path[canonical] = doc
            docs_by_folder[Path(doc.pages_dir_path).name] = doc
    return docs_by_path, docs_by_folder


def _collect_disk_books(
    library_dir: Path,
    docs_by_path: dict,
    docs_by_folder: dict,
    project_root: Path,
) -> tuple:
    """
    Walk library_dir for valid image-book folders.

    Returns (books list, folders_seen set).
    """
    books = []
    folders_seen: set = set()

    for folder_path in sorted(library_dir.iterdir()):
        if not folder_path.is_dir() or folder_path.name == "covers":
            continue
        image_files = [
            f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
        ]
        if not image_files:
            continue
        page_count = count_pages(folder_path)
        if page_count == 0 or not detect_image_pattern(folder_path):
            continue

        folder_name = folder_path.name
        pages_dir_path = normalize_library_path(folder_path, library_dir, project_root)
        doc_by_path = docs_by_path.get(pages_dir_path)
        doc_by_folder = docs_by_folder.get(folder_name)
        doc = doc_by_path or doc_by_folder
        needs_repair = bool(doc_by_folder and not doc_by_path)

        folders_seen.add(folder_name)
        books.append(
            {
                "folder_name": folder_name,
                "page_count": page_count,
                "exists_on_disk": True,
                "in_db": doc is not None,
                "document_id": doc.id if doc else None,
                "title": doc.title if doc else None,
                "is_active": doc.is_active if doc else None,
                "needs_repair": needs_repair,
                "created_at": doc.created_at.isoformat() if doc and doc.created_at else None,
            }
        )

    return books, folders_seen


@router.get("/admin/scan")
async def scan_library_folders(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Scan library storage directory and return all folder/document status (admin only).

    Returns every image folder found on disk combined with every registered
    LibraryDocument in the database.  Entries that exist only in the DB
    (folder missing on disk) are flagged as orphaned.
    """
    service = LibraryService(db, user_id=current_user.id)
    library_dir = service.storage_dir
    project_root = Path.cwd()

    if not library_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Library storage directory not found: {library_dir}",
        )

    result = await db.execute(select(LibraryDocument).where(LibraryDocument.use_images.is_(True)))
    all_docs = result.scalars().all()

    docs_by_path, docs_by_folder = _build_doc_lookups(all_docs, library_dir, project_root)
    books, folders_seen = _collect_disk_books(library_dir, docs_by_path, docs_by_folder, project_root)

    for doc in all_docs:
        if not doc.pages_dir_path:
            continue
        if Path(doc.pages_dir_path).name not in folders_seen:
            books.append(
                {
                    "folder_name": Path(doc.pages_dir_path).name,
                    "page_count": doc.total_pages or 0,
                    "exists_on_disk": False,
                    "in_db": True,
                    "document_id": doc.id,
                    "title": doc.title,
                    "is_active": doc.is_active,
                    "needs_repair": False,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }
            )

    return {
        "scanned_at": datetime.now(UTC).isoformat(),
        "storage_dir": str(library_dir),
        "books": books,
        "total": len(books),
    }


@router.post("/admin/repair")
async def repair_library_paths(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Fix stale pages_dir_path values stored in the database (admin only).

    This is needed when books were registered on a different OS or from a different
    working directory, causing the stored path format (e.g. Windows back-slashes or
    absolute paths) to diverge from what the scan produces on the current server.

    For every document whose stored path does not match the path produced by
    normalize_library_path on the on-disk folder, the value is updated in-place.
    This matches the scan's notion of "repair" (path key vs disk key).

    Returns counts of updated and skipped documents.
    """
    service = LibraryService(db, user_id=current_user.id)
    library_dir = service.storage_dir
    project_root = Path.cwd()

    result = await db.execute(select(LibraryDocument).where(LibraryDocument.use_images.is_(True)))
    all_docs = result.scalars().all()

    updated = 0
    skipped = 0
    errors = 0

    for doc in all_docs:
        if not doc.pages_dir_path:
            skipped += 1
            continue

        folder_name = extract_folder_name_from_pages_dir_path(doc.pages_dir_path)
        disk_path = library_dir / folder_name if folder_name else None
        if not disk_path or not disk_path.exists():
            skipped += 1
            continue

        desired = normalize_library_path(disk_path, library_dir, project_root)
        if desired == doc.pages_dir_path:
            skipped += 1
            continue

        try:
            doc.pages_dir_path = desired
            doc.updated_at = datetime.now(UTC)
            updated += 1
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("[Library] Repair failed for document %s: %s", doc.id, exc)
            errors += 1

    if updated:
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to commit path repairs",
            ) from exc

    logger.info(
        "[Library] Path repair completed",
        extra={
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "admin_user_id": current_user.id,
        },
    )
    return {"updated": updated, "skipped": skipped, "errors": errors}


@router.patch("/documents/{document_id}/visibility")
async def update_document_visibility(
    document_id: int,
    data: DocumentVisibilityUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Show or hide a library document (admin only).

    Sets is_active to the requested value and invalidates the document cache.
    """
    result = await db.execute(select(LibraryDocument).where(LibraryDocument.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document.is_active = data.is_active
    document.updated_at = datetime.now(UTC)
    try:
        await db.commit()
        await db.refresh(document)
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document visibility",
        ) from exc

    service = LibraryService(db, user_id=current_user.id)
    service.invalidate_document_cache(document_id)

    logger.info(
        "[Library] Document visibility updated",
        extra={
            "document_id": document_id,
            "is_active": data.is_active,
            "admin_user_id": current_user.id,
        },
    )
    return {
        "id": document.id,
        "is_active": document.is_active,
        "message": "Visibility updated successfully",
    }


def _build_rename_plan(folder_path: Path, book_name: str) -> tuple | None:
    """
    Build a sequential rename plan for all page images in a book folder.

    Returns (plan, total_pages, skipped_count) or None if the pattern
    cannot be detected or no images are found.

    Each plan entry is (orig_page_num, seq_num, image_path, target_name, target_path).
    """
    image_files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    if not image_files:
        return None

    pattern_info = detect_image_pattern(folder_path)
    if not pattern_info:
        return None

    pages = list_page_images(folder_path)
    if not pages:
        return None

    pages.sort(key=lambda x: x[0])
    target_ext = pattern_info.get("extension", ".jpg")
    padding = max(len(str(len(pages))), 2)

    plan = []
    skipped = 0
    for seq_num, (orig_page, img_path) in enumerate(pages, start=1):
        target_name = f"{book_name}_{str(seq_num).zfill(padding)}{target_ext}"
        if img_path.name == target_name:
            skipped += 1
            continue
        plan.append((orig_page, seq_num, img_path, target_name, folder_path / target_name))

    return plan, len(pages), skipped


def _execute_rename(folder_path: Path, plan: list) -> tuple:
    """
    Two-phase rename to avoid filename conflicts.

    Phase 1: each file → temporary name.
    Phase 2: temporary name → final sequential name.

    Returns (renamed_count, error_count).
    """
    renamed = 0
    errors = 0
    temp_files = []

    for orig_page, _seq, img_path, _target_name, target_path in plan:
        temp_name = f"__rename_tmp_{orig_page}{img_path.suffix}"
        temp_path = folder_path / temp_name
        try:
            img_path.rename(temp_path)
            temp_files.append((temp_path, target_path))
        except Exception as exc:
            logger.error(
                "[Library] Rename phase-1 error: %s → %s: %s",
                img_path.name,
                temp_name,
                exc,
            )
            errors += 1

    for temp_path, target_path in temp_files:
        try:
            temp_path.rename(target_path)
            renamed += 1
        except Exception as exc:
            logger.error(
                "[Library] Rename phase-2 error: %s → %s: %s",
                temp_path.name,
                target_path.name,
                exc,
            )
            errors += 1

    return renamed, errors


@router.post("/admin/rename-pages")
async def rename_book_pages(
    data: RenameRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Rename page images in a book folder to sequential numbering (admin only).

    Files are renamed to: {book_name}_01.jpg, {book_name}_02.jpg, ...
    Gaps in the original sequence are eliminated so pages are contiguous.

    When dry_run=True (default), returns a preview without changing any files.
    When dry_run=False, executes the two-phase rename and returns the result.
    """
    if any(c in data.folder_name for c in ("/", "\\", "..")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid folder name — must be a direct subfolder of storage/library/",
        )

    service = LibraryService(db, user_id=current_user.id)
    library_dir = service.storage_dir
    folder_path = (library_dir / data.folder_name).resolve()

    try:
        if not folder_path.is_relative_to(library_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected",
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid folder path",
        ) from exc

    if not folder_path.exists() or not folder_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found: {data.folder_name}",
        )

    book_name = (data.book_name or data.folder_name).strip()
    result = _build_rename_plan(folder_path, book_name)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not detect image naming pattern in this folder",
        )

    plan, total_pages, skipped = result
    error_count = 0

    if not data.dry_run and plan:
        renamed_count, error_count = _execute_rename(folder_path, plan)
        logger.info(
            "[Library] Pages renamed",
            extra={
                "folder": data.folder_name,
                "renamed": renamed_count,
                "errors": error_count,
                "admin_user_id": current_user.id,
            },
        )
    else:
        renamed_count = len(plan)

    preview = [{"from": item[2].name, "to": item[3]} for item in plan]

    return {
        "folder_name": data.folder_name,
        "book_name": book_name,
        "total_pages": total_pages,
        "rename_count": renamed_count,
        "skip_count": skipped,
        "error_count": error_count,
        "dry_run": data.dry_run,
        "preview": preview,
    }


@router.post("/admin/documents/{document_id}/generate-cover")
async def generate_document_cover(
    document_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Generate (or regenerate) cover image from the first page of a book (admin only).

    Overwrites any existing cover file, updates the DB record, and invalidates
    the document cache so readers see the new cover immediately.
    """
    service = LibraryService(db, user_id=current_user.id)
    try:
        cover_path = service.regenerate_cover(document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if not cover_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process cover image — check that the folder contains valid images",
        )

    logger.info(
        "[Library] Cover regenerated",
        extra={"document_id": document_id, "admin_user_id": current_user.id},
    )
    return {
        "document_id": document_id,
        "cover_url": f"/api/library/documents/{document_id}/cover",
        "message": "Cover generated successfully",
    }


_COVER_FILE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


@router.delete("/admin/documents/{document_id}")
async def delete_document_record(
    document_id: int,
    delete_files: bool = Query(
        False,
        description="When True, also remove the book folder and all page images from disk",
    ),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a library document (admin only).

    By default (delete_files=False): removes only the DB record and cover file.
    Use this for orphaned records where the folder is already gone from disk.

    With delete_files=True: additionally deletes the entire book folder from disk
    (all page images).  This is a destructive, irreversible operation.
    """
    result = await db.execute(select(LibraryDocument).where(LibraryDocument.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    service = LibraryService(db, user_id=current_user.id)

    # Commit the DB deletion first; only clean up disk/cache after the record is gone.
    try:
        await db.delete(document)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document record",
        ) from exc

    deleted_folder = False

    if delete_files and document.pages_dir_path:
        folder_path = resolve_library_path(document.pages_dir_path, service.storage_dir, Path.cwd())
        if folder_path and folder_path.exists() and folder_path.is_dir():
            try:
                if folder_path.parent.resolve() == service.storage_dir.resolve():
                    shutil.rmtree(folder_path)
                    deleted_folder = True
                    logger.info("[Library] Book folder deleted: %s", folder_path)
                else:
                    logger.warning(
                        "[Library] Refused to delete folder outside storage_dir: %s",
                        folder_path,
                    )
            except OSError as exc:
                logger.error("[Library] Could not remove book folder %s: %s", folder_path, exc)

    for ext in _COVER_FILE_EXTENSIONS:
        candidate = service.covers_dir / f"{document_id}_cover{ext}"
        if candidate.exists():
            try:
                candidate.unlink()
            except OSError as exc:
                logger.warning("[Library] Could not remove cover file %s: %s", candidate, exc)
            break

    try:
        service.invalidate_document_cache(document_id)
    except Exception as exc:
        logger.warning("[Library] Cache invalidation failed for %s: %s", document_id, exc)

    logger.info(
        "[Library] Document deleted",
        extra={
            "document_id": document_id,
            "deleted_files": deleted_folder,
            "admin_user_id": current_user.id,
        },
    )
    return {
        "id": document_id,
        "deleted_files": deleted_folder,
        "message": "Book deleted" if deleted_folder else "Document record deleted",
    }
