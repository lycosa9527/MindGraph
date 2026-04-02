"""
Knowledge Space Relationships Router
=====================================

Document relationship management endpoints.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.knowledge_space import (
    DocumentRelationship,
    KnowledgeDocument,
    KnowledgeSpace,
)
from models.requests.requests_knowledge_space import RelationshipRequest
from models.responses import RelationshipResponse
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/documents/{document_id}/relationships")
async def create_relationship(
    document_id: int,
    request: RelationshipRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a relationship between documents.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    source_doc = await service.get_document(document_id)
    if not source_doc:
        raise HTTPException(status_code=404, detail="Source document not found")

    target_doc = await service.get_document(request.target_document_id)
    if not target_doc:
        raise HTTPException(status_code=404, detail="Target document not found")

    result = await db.execute(
        select(DocumentRelationship).where(
            DocumentRelationship.source_document_id == document_id,
            DocumentRelationship.target_document_id == request.target_document_id,
            DocumentRelationship.relationship_type == request.relationship_type,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")

    try:
        relationship = DocumentRelationship(
            source_document_id=document_id,
            target_document_id=request.target_document_id,
            relationship_type=request.relationship_type,
            context=request.context,
            created_by=current_user.id,
        )
        db.add(relationship)
        await db.commit()
        await db.refresh(relationship)

        return RelationshipResponse(
            id=relationship.id,
            source_document_id=relationship.source_document_id,
            target_document_id=relationship.target_document_id,
            relationship_type=relationship.relationship_type,
            context=relationship.context,
            created_at=relationship.created_at.isoformat(),
        )
    except Exception as e:
        logger.error("[KnowledgeSpaceAPI] Failed to create relationship: %s", e)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create relationship") from e


@router.get("/documents/{document_id}/relationships")
async def get_document_relationships(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get relationships for a document.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(DocumentRelationship).where(DocumentRelationship.source_document_id == document_id)
    )
    relationships = result.scalars().all()

    return {
        "relationships": [
            RelationshipResponse(
                id=r.id,
                source_document_id=r.source_document_id,
                target_document_id=r.target_document_id,
                relationship_type=r.relationship_type,
                context=r.context,
                created_at=r.created_at.isoformat(),
            )
            for r in relationships
        ],
        "total": len(relationships),
    }


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(
    relationship_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a document relationship.

    Requires authentication. Verifies ownership.
    """
    result = await db.execute(
        select(DocumentRelationship)
        .join(
            KnowledgeDocument,
            DocumentRelationship.source_document_id == KnowledgeDocument.id,
        )
        .join(KnowledgeSpace)
        .where(
            DocumentRelationship.id == relationship_id,
            KnowledgeSpace.user_id == current_user.id,
        )
    )
    relationship = result.scalar_one_or_none()

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    try:
        await db.delete(relationship)
        await db.commit()
        return {"message": "Relationship deleted successfully"}
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to delete relationship %s: %s",
            relationship_id,
            e,
        )
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete relationship") from e
