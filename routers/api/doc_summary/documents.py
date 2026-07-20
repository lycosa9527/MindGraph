"""Document Summary document HTTP surface (delete alias).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from routers.api.knowledge_space import documents as ks_documents
from services.knowledge.doc_summary_ingest import DOC_SUMMARY_SOURCE
from services.knowledge.knowledge_package_service import KnowledgePackageService
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user

router = APIRouter(tags=["doc-summary"])


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a source that belongs to a Document Summary package."""
    ks_service = KnowledgeSpaceService(db, current_user.id)
    try:
        document = await ks_service.get_document(document_id)
    except DATABASE_ERRORS as exc:
        raise HTTPException(status_code=500, detail="Lookup failed") from exc

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.batch_id is None:
        raise HTTPException(status_code=400, detail="Document is not in a package")

    packages = KnowledgePackageService(db, current_user.id)
    package = await packages.get_package(document.batch_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Package not found")
    if package.source != DOC_SUMMARY_SOURCE:
        raise HTTPException(
            status_code=400,
            detail="Document is not part of a Document Summary session",
        )

    return await ks_documents.delete_document(document_id, current_user, db)
