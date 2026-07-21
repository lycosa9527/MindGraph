"""Document Summary package HTTP surface (aliases of File Center handlers).

Only ``source=doc_summary`` packages are exposed here. Implementations reuse
``routers.api.knowledge_space.packages`` handlers so extract/RAG branching stays
in one place.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.knowledge_space import DocumentBatch
from models.requests.requests_knowledge_space import (
    PackageCreateRequest,
    PackageIngestTextRequest,
    PackageIngestWebRequest,
    PackageIngestWebUrlRequest,
    PackageUpdateRequest,
)
from models.responses import PackageListResponse
from routers.api.knowledge_space import packages as ks_packages
from services.knowledge.doc_summary_ingest import DOC_SUMMARY_SOURCE
from services.knowledge.knowledge_package_service import KnowledgePackageService
from utils.auth import get_current_user

router = APIRouter(tags=["doc-summary"])


async def _require_doc_summary_package(
    package_id: int,
    current_user: User,
    db: AsyncSession,
) -> DocumentBatch:
    """Return the package or raise if missing / not a Document Summary session."""
    service = KnowledgePackageService(db, current_user.id)
    package = await service.get_package(package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if package.source != DOC_SUMMARY_SOURCE:
        raise HTTPException(
            status_code=400,
            detail="Package is not a Document Summary session",
        )
    return package


@router.get("/packages")
async def list_packages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List only Document Summary packages for the current user."""
    full = await ks_packages.list_packages(current_user, db)
    filtered = [item for item in full.packages if item.source == DOC_SUMMARY_SOURCE]
    return PackageListResponse(
        packages=filtered,
        total=len(filtered),
        wiki_compile_enabled=full.wiki_compile_enabled,
    )


@router.post("/packages")
async def create_package(
    request: PackageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a Document Summary package (source forced to doc_summary)."""
    forced = request.model_copy(update={"source": DOC_SUMMARY_SOURCE})
    return await ks_packages.create_package(forced, current_user, db)


@router.get("/packages/{package_id}")
async def get_package(
    package_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a Document Summary package and its sources."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.get_package(package_id, current_user, db)


@router.put("/packages/{package_id}")
async def update_package(
    package_id: int,
    request: PackageUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Rename or relink a Document Summary package."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.update_package(package_id, request, current_user, db)


@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a Document Summary package and its sources."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.delete_package(package_id, current_user, db)


@router.post("/packages/{package_id}/documents/upload")
async def upload_package_document(
    package_id: int,
    http_request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Upload a file into a Document Summary package (extract-only ingest)."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.upload_package_document(
        package_id,
        http_request,
        file,
        current_user,
        db,
    )


@router.post("/packages/{package_id}/documents/ingest-text")
async def ingest_text(
    package_id: int,
    request: PackageIngestTextRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Paste text into a Document Summary package."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.ingest_text(
        package_id,
        request,
        http_request,
        current_user,
        db,
    )


@router.post("/packages/{package_id}/documents/ingest-web")
async def ingest_web(
    package_id: int,
    request: PackageIngestWebRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Ingest a web snapshot body into a Document Summary package."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.ingest_web(
        package_id,
        request,
        http_request,
        current_user,
        db,
    )


@router.post("/packages/{package_id}/documents/ingest-web-url")
async def ingest_web_url(
    package_id: int,
    request: PackageIngestWebUrlRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch a URL and ingest into a Document Summary package."""
    await _require_doc_summary_package(package_id, current_user, db)
    return await ks_packages.ingest_web_url(
        package_id,
        request,
        http_request,
        current_user,
        db,
    )
