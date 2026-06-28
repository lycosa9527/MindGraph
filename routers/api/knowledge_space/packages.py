"""
Knowledge Space Packages Router (File Center)
=============================================

Zotero-like packages: a named collection of sources scoped to one diagram.
Sources are chunked and indexed exactly like ordinary Knowledge Space
documents, then used to scope RAG retrieval for that diagram's completion.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument
from models.requests.requests_knowledge_space import (
    PackageCreateRequest,
    PackageIngestTextRequest,
    PackageIngestWebRequest,
    PackageIngestWebUrlRequest,
    PackageUpdateRequest,
)
from models.responses import (
    DocumentResponse,
    PackageDetailResponse,
    PackageListResponse,
    PackageResponse,
)
from services.knowledge import package_wiki_store
from services.knowledge.audio_hosting import resolve_audio_path
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from services.knowledge.url_page_fetch import fetch_url_page_text
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, DATABASE_ERRORS
from tasks.knowledge_space_tasks import process_document_task
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def _document_to_response(doc: KnowledgeDocument) -> DocumentResponse:
    metadata = doc.doc_metadata or {}
    return DocumentResponse(
        id=doc.id,
        file_name=doc.file_name,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        processing_progress=doc.processing_progress,
        processing_progress_percent=doc.processing_progress_percent or 0,
        chunking_engine=metadata.get("chunking_engine"),
        chunking_mode=metadata.get("chunking_mode"),
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
    )


def _derive_status(total: int, completed: int) -> str:
    """Derive a package status from its live source counts."""
    if total == 0:
        return "empty"
    if completed >= total:
        return "completed"
    return "processing"


def _package_to_response(package: DocumentBatch, document_count: int, completed_count: int) -> PackageResponse:
    return PackageResponse(
        id=package.id,
        name=package.name,
        diagram_id=package.diagram_id,
        source=package.source,
        status=_derive_status(document_count, completed_count),
        document_count=document_count,
        completed_count=completed_count,
        created_at=package.created_at.isoformat(),
        updated_at=package.updated_at.isoformat(),
    )


@router.post("/packages")
async def create_package(
    request: PackageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a named package, optionally linked to a diagram."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        package = await service.create_package(
            name=request.name,
            diagram_id=request.diagram_id,
            source=request.source,
        )
        return _package_to_response(package, document_count=0, completed_count=0)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DATABASE_ERRORS as e:
        logger.error("[FileCenter] Create package failed for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Create package failed") from e


@router.get("/packages")
async def list_packages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List the user's named packages."""
    service = KnowledgePackageService(db, current_user.id)
    packages = await service.list_packages()

    stats = await service.get_package_stats([package.id for package in packages])
    items: List[PackageResponse] = [
        _package_to_response(
            package,
            document_count=stats.get(package.id, {}).get("total", 0),
            completed_count=stats.get(package.id, {}).get("completed", 0),
        )
        for package in packages
    ]

    return PackageListResponse(packages=items, total=len(items))


@router.get("/packages/{package_id}")
async def get_package(
    package_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a package and its sources."""
    service = KnowledgePackageService(db, current_user.id)
    package = await service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    documents = await service.get_package_documents(package_id)
    completed = sum(1 for doc in documents if doc.status == "completed")
    return PackageDetailResponse(
        package=_package_to_response(package, document_count=len(documents), completed_count=completed),
        documents=[_document_to_response(doc) for doc in documents],
    )


@router.put("/packages/{package_id}")
async def update_package(
    package_id: int,
    request: PackageUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Rename a package or relink it to a diagram."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        package = await service.update_package(
            package_id,
            name=request.name,
            diagram_id=request.diagram_id,
        )
        documents = await service.get_package_documents(package_id)
        completed = sum(1 for doc in documents if doc.status == "completed")
        return _package_to_response(package, document_count=len(documents), completed_count=completed)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except DATABASE_ERRORS as e:
        logger.error("[FileCenter] Update package %s failed: %s", package_id, e)
        raise HTTPException(status_code=500, detail="Update package failed") from e


@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a package and all of its sources."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        await service.delete_package(package_id)
        return {"message": "Package deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except BACKGROUND_INFRA_ERRORS as e:
        logger.error("[FileCenter] Delete package %s failed: %s", package_id, e)
        raise HTTPException(status_code=500, detail="Delete package failed") from e


@router.post("/packages/{package_id}/documents/upload")
async def upload_package_document(
    package_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Upload a file source into a package and start indexing immediately."""
    package_service = KnowledgePackageService(db, current_user.id)
    package = await package_service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    ks_service = KnowledgeSpaceService(db, current_user.id)
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        file_type = ks_service.processor.get_file_type(file.filename)
        document = await ks_service.upload_document(
            file_name=file.filename,
            file_path=tmp_path,
            file_type=file_type,
            file_size=len(content),
            batch_id=package_id,
        )

        _enqueue_processing(db, document)
        await db.commit()
        process_document_task.delay(current_user.id, document.id)

        return _document_to_response(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DATABASE_ERRORS as e:
        logger.error("[FileCenter] Upload to package %s failed: %s", package_id, e)
        raise HTTPException(status_code=500, detail="Upload failed") from e


@router.post("/packages/{package_id}/documents/ingest-text")
async def ingest_text(
    package_id: int,
    request: PackageIngestTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Ingest pasted text as a markdown source in a package."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        document = await service.add_text_source(
            package_id,
            content=request.content,
            title=request.title or "Pasted note",
            source_kind="paste",
            language=request.language,
        )
        _enqueue_processing(db, document)
        await db.commit()
        process_document_task.delay(current_user.id, document.id)
        return _document_to_response(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DATABASE_ERRORS as e:
        logger.error("[FileCenter] Ingest text to package %s failed: %s", package_id, e)
        raise HTTPException(status_code=500, detail="Ingest failed") from e


@router.post("/packages/{package_id}/documents/ingest-web")
async def ingest_web(
    package_id: int,
    request: PackageIngestWebRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Ingest a web content snapshot (text + URL) as a source in a package."""
    service = KnowledgePackageService(db, current_user.id)
    try:
        if request.page_url:
            existing = await service.find_document_by_url(package_id, request.page_url)
            if existing:
                return _document_to_response(existing)

        document = await service.add_text_source(
            package_id,
            content=request.page_content,
            title=request.page_title or request.page_url or "Web snapshot",
            source_kind="web",
            page_url=request.page_url,
            language=request.language,
        )
        _enqueue_processing(db, document)
        await db.commit()
        process_document_task.delay(current_user.id, document.id)
        return _document_to_response(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DATABASE_ERRORS as e:
        logger.error("[FileCenter] Ingest web to package %s failed: %s", package_id, e)
        raise HTTPException(status_code=500, detail="Ingest failed") from e


@router.post("/packages/{package_id}/documents/ingest-web-url")
async def ingest_web_url(
    package_id: int,
    request: PackageIngestWebUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch a public URL server-side and ingest as a web snapshot."""
    service = KnowledgePackageService(db, current_user.id)
    package = await service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    page_url = request.page_url.strip()
    try:
        existing = await service.find_document_by_url(package_id, page_url)
        if existing:
            return _document_to_response(existing)

        page_content, page_title = await fetch_url_page_text(page_url)
        document = await service.add_text_source(
            package_id,
            content=page_content,
            title=page_title or page_url,
            source_kind="web",
            page_url=page_url,
            language=request.language,
        )
        _enqueue_processing(db, document)
        await db.commit()
        process_document_task.delay(current_user.id, document.id)
        return _document_to_response(document)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DATABASE_ERRORS as e:
        logger.error("[FileCenter] Ingest web URL to package %s failed: %s", package_id, e)
        raise HTTPException(status_code=500, detail="Ingest failed") from e


@router.get("/packages/{package_id}/wiki")
async def get_package_wiki(
    package_id: int,
    slug: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List the package's compiled wiki pages, and optionally read one (v2a)."""
    service = KnowledgePackageService(db, current_user.id)
    package = await service.get_package(package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    pages = package_wiki_store.list_pages(current_user.id, package_id)
    body = package_wiki_store.read_page(current_user.id, package_id, slug) if slug else None
    return {"pages": pages, "slug": slug, "body": body}


@router.get("/audio-fetch/{token}")
async def fetch_hosted_audio(token: str):
    """Public, token-gated fetch so DashScope ASR can pull a hosted audio file.

    Intentionally unauthenticated: DashScope cannot send our session cookie. The
    token is a random, short-lived Redis key (see ``audio_hosting``) that maps to
    a specific on-disk path, so this cannot be used for path traversal — only
    explicitly published audio files are served.
    """
    file_path = resolve_audio_path(token)
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_path, media_type="application/octet-stream")


def _enqueue_processing(db: AsyncSession, document: KnowledgeDocument) -> None:
    """Mark a freshly created source as queued so the UI shows progress."""
    document.status = "processing"
    document.processing_progress = "queued"
    document.processing_progress_percent = 0
    db.add(document)
