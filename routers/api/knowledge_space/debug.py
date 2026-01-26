"""
Knowledge Space Debug Router
=============================

Debug and diagnostic endpoints.

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
from models.domain.knowledge_space import KnowledgeSpace, KnowledgeDocument, DocumentChunk
from models.responses import CompressionMetricsResponse
from services.llm.qdrant_service import get_qdrant_service
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/metrics/compression", response_model=CompressionMetricsResponse)
async def get_compression_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get compression metrics for user's knowledge space vector database.

    Returns compression statistics including:
    - Compression status and type
    - Storage size estimates (compressed vs uncompressed)
    - Compression ratio and savings percentage

    Requires authentication. Only returns metrics for user's own knowledge base.
    """
    try:
        qdrant_service = get_qdrant_service()
        metrics = qdrant_service.get_compression_metrics(current_user.id)
        return CompressionMetricsResponse(**metrics)
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to get compression metrics for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve compression metrics"
        ) from e


@router.get("/debug/qdrant-diagnostics")
async def get_qdrant_diagnostics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get diagnostic information for user's Qdrant collection.

    Useful for debugging retrieval issues. Returns:
    - Collection existence and name
    - Points count
    - Vector dimensions
    - Sample point payloads
    - Payload keys present
    - Test search result

    Requires authentication. Only returns diagnostics for user's own knowledge base.
    """
    try:
        qdrant_service = get_qdrant_service()
        diagnostics = qdrant_service.get_diagnostics(current_user.id)

        # Add database chunk info for comparison
        space = db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == current_user.id
        ).first()

        database_info = {
            "space_exists": space is not None,
            "documents_count": 0,
            "completed_documents_count": 0,
            "total_chunks_count": 0,
            "chunk_ids_sample": []
        }

        if space:
            # Get document counts
            database_info["documents_count"] = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id
            ).count()

            database_info["completed_documents_count"] = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id,
                KnowledgeDocument.status == 'completed'
            ).count()

            # Get total chunks across all documents
            completed_doc_ids = [d.id for d in db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id,
                KnowledgeDocument.status == 'completed'
            ).all()]

            if completed_doc_ids:
                database_info["total_chunks_count"] = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id.in_(completed_doc_ids)
                ).count()

                # Sample chunk IDs
                sample_chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id.in_(completed_doc_ids)
                ).limit(5).all()
                database_info["chunk_ids_sample"] = [c.id for c in sample_chunks]

        # Summary diagnosis
        diagnosis = []
        if not diagnostics["collection_exists"]:
            diagnosis.append("ISSUE: Qdrant collection does not exist for this user")
        elif diagnostics["points_count"] == 0:
            diagnosis.append("ISSUE: Qdrant collection exists but has 0 points (embeddings)")

        if database_info["total_chunks_count"] > 0 and diagnostics["points_count"] == 0:
            diagnosis.append("ISSUE: Database has chunks but Qdrant has no points - embeddings not stored!")

        if database_info["total_chunks_count"] != diagnostics["points_count"]:
            diagnosis.append(
                f"WARNING: Chunk count mismatch - Database: {database_info['total_chunks_count']}, "
                f"Qdrant: {diagnostics['points_count']}"
            )

        if not diagnosis:
            diagnosis.append("OK: Qdrant collection and database chunks appear synchronized")

        return {
            "qdrant": diagnostics,
            "database": database_info,
            "diagnosis": diagnosis
        }

    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to get Qdrant diagnostics for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve diagnostics: {str(e)}"
        ) from e
