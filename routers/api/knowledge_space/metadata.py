"""
Knowledge Space Metadata Router
================================

Metadata and versioning endpoints for documents.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.requests.requests_knowledge_space import MetadataUpdateRequest, RollbackRequest
from models.responses import DocumentResponse, VersionResponse, VersionListResponse
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.patch("/documents/{document_id}/metadata")
async def update_document_metadata(
    document_id: int,
    request: MetadataUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update document metadata (tags, category, custom fields).

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        # Update metadata fields
        if request.tags is not None:
            document.tags = request.tags
        if request.category is not None:
            document.category = request.category
        if request.metadata is not None:
            # Merge with existing metadata
            existing_metadata = document.doc_metadata or {}
            existing_metadata.update(request.metadata)
            document.doc_metadata = existing_metadata
        if request.custom_fields is not None:
            # Merge with existing custom fields
            existing_custom = document.custom_fields or {}
            existing_custom.update(request.custom_fields)
            document.custom_fields = existing_custom

        db.commit()
        db.refresh(document)

        return DocumentResponse(
            id=document.id,
            file_name=document.file_name,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            chunk_count=document.chunk_count,
            error_message=document.error_message,
            processing_progress=document.processing_progress,
            processing_progress_percent=document.processing_progress_percent or 0,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to update metadata for document %s: %s",
            document_id,
            e
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update metadata"
        ) from e


@router.get("/documents/{document_id}/versions")
async def get_document_versions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get version history for a document.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    try:
        versions = service.get_document_versions(document_id)
        return VersionListResponse(
            versions=[
                VersionResponse(
                    id=v.id,
                    document_id=v.document_id,
                    version_number=v.version_number,
                    chunk_count=v.chunk_count,
                    change_summary=v.change_summary,
                    created_at=v.created_at.isoformat()
                )
                for v in versions
            ],
            total=len(versions)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to get versions for document %s: %s",
            document_id,
            e
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve versions"
        ) from e


@router.post("/documents/{document_id}/rollback")
async def rollback_document(
    document_id: int,
    request: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Rollback document to a previous version.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    try:
        document = service.rollback_document(document_id, request.version_number)
        return DocumentResponse(
            id=document.id,
            file_name=document.file_name,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            chunk_count=document.chunk_count,
            error_message=document.error_message,
            processing_progress=document.processing_progress,
            processing_progress_percent=document.processing_progress_percent or 0,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to rollback document %s: %s",
            document_id,
            e
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to rollback document"
        ) from e
