"""
Knowledge Space Queries Router
===============================

Query-related endpoints including retrieval testing, analytics, feedback, and templates.

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
from models.domain.knowledge_space import KnowledgeQuery, KnowledgeSpace, QueryFeedback, QueryTemplate
from models.requests.requests_knowledge_space import RetrievalTestRequest, QueryFeedbackRequest, QueryTemplateRequest
from models.responses import (
    RetrievalTestHistoryResponse,
    RetrievalTestHistoryItem,
    QueryAnalyticsResponse,
    QueryTemplateResponse
)
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from services.knowledge.retrieval_test_service import get_retrieval_test_service
from services.llm.rag_service import get_rag_service
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/retrieval-test")
async def test_retrieval(
    request: RetrievalTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test retrieval functionality for user's knowledge space.

    Requires authentication. Only tests user's own knowledge base.
    """
    service = get_retrieval_test_service()

    try:
        result = service.test_retrieval(
            db=db,
            user_id=current_user.id,
            query=request.query,
            method=request.method,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Retrieval test failed for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(status_code=500, detail="Retrieval test failed") from e


@router.get("/queries/retrieval-test-history")
async def get_retrieval_test_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get retrieval test history for user.

    Returns the most recent 10 retrieval test queries (server resource optimization).
    Requires authentication.
    """
    try:
        # Get user's knowledge space
        space = db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == current_user.id
        ).first()

        if not space:
            return RetrievalTestHistoryResponse(queries=[], total=0)

        # Fetch retrieval test queries (most recent first)
        # Only keep 10 most recent, so we only fetch 10
        queries = db.query(KnowledgeQuery).filter(
            KnowledgeQuery.space_id == space.id,
            KnowledgeQuery.source == 'retrieval_test'
        ).order_by(KnowledgeQuery.created_at.desc()).limit(10).all()

        # Convert to response format
        history_items = []
        for q in queries:
            history_items.append(RetrievalTestHistoryItem(
                id=q.id,
                query=q.query,
                method=q.method,
                top_k=q.top_k,
                score_threshold=q.score_threshold,
                result_count=q.result_count,
                timing={
                    'embedding_ms': q.embedding_ms,
                    'search_ms': q.search_ms,
                    'rerank_ms': q.rerank_ms,
                    'total_ms': q.total_ms,
                },
                created_at=q.created_at.isoformat()
            ))

        return RetrievalTestHistoryResponse(
            queries=history_items,
            total=len(history_items)  # Max 10
        )
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to get retrieval test history for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve test history"
        ) from e


@router.get("/queries/analytics")
async def get_query_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get query performance analytics.

    Requires authentication.
    """
    try:
        rag_service = get_rag_service()
        analytics = rag_service.analyze_query_performance(db, current_user.id, days)
        return QueryAnalyticsResponse(**analytics)
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to get query analytics for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve analytics"
        ) from e


@router.post("/queries/{query_id}/feedback")
async def submit_query_feedback(
    query_id: int,
    request: QueryFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback for a query result.

    Requires authentication. Verifies ownership.
    """
    # Verify query ownership
    query = db.query(KnowledgeQuery).join(KnowledgeSpace).filter(
        KnowledgeQuery.id == query_id,
        KnowledgeSpace.user_id == current_user.id
    ).first()

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    try:
        feedback = QueryFeedback(
            query_id=query_id,
            user_id=current_user.id,
            space_id=query.space_id,
            feedback_type=request.feedback_type,
            feedback_score=request.feedback_score,
            relevant_chunk_ids=request.relevant_chunk_ids,
            irrelevant_chunk_ids=request.irrelevant_chunk_ids
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        return {
            "id": feedback.id,
            "query_id": feedback.query_id,
            "feedback_type": feedback.feedback_type,
            "feedback_score": feedback.feedback_score,
            "created_at": feedback.created_at.isoformat()
        }
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to submit feedback for query %s: %s",
            query_id,
            e
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to submit feedback"
        ) from e


@router.post("/query-templates")
async def create_query_template(
    request: QueryTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a query template.

    Requires authentication.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    space = service.create_knowledge_space()

    try:
        template = QueryTemplate(
            user_id=current_user.id,
            space_id=space.id,
            name=request.name,
            template_text=request.template_text,
            parameters=request.parameters or {}
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        return QueryTemplateResponse(
            id=template.id,
            name=template.name,
            template_text=template.template_text,
            parameters=template.parameters,
            usage_count=template.usage_count,
            success_rate=template.success_rate,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to create query template: %s",
            e
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create template"
        ) from e


@router.get("/query-templates")
async def list_query_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List query templates for user.

    Requires authentication.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    space = service.create_knowledge_space()

    templates = db.query(QueryTemplate).filter(
        QueryTemplate.user_id == current_user.id,
        QueryTemplate.space_id == space.id
    ).order_by(QueryTemplate.usage_count.desc()).all()

    return {
        "templates": [
            QueryTemplateResponse(
                id=t.id,
                name=t.name,
                template_text=t.template_text,
                parameters=t.parameters,
                usage_count=t.usage_count,
                success_rate=t.success_rate,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat()
            )
            for t in templates
        ],
        "total": len(templates)
    }
