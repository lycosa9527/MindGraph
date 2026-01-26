"""
Knowledge Space Evaluation Router
===================================

Evaluation dataset and results endpoints.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.knowledge_space import EvaluationDataset, EvaluationResult
from models.requests.requests_knowledge_space import EvaluationDatasetRequest, EvaluationRunRequest
from models.responses import EvaluationDatasetResponse, EvaluationRunResponse
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from services.knowledge.retrieval_test_service import get_retrieval_test_service
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/evaluation/datasets")
async def create_evaluation_dataset(
    request: EvaluationDatasetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create an evaluation dataset.

    Requires authentication.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    space = service.create_knowledge_space()

    try:
        dataset = EvaluationDataset(
            user_id=current_user.id,
            space_id=space.id,
            name=request.name,
            description=request.description,
            queries=request.queries
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

        return EvaluationDatasetResponse(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            queries=dataset.queries,
            created_at=dataset.created_at.isoformat(),
            updated_at=dataset.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to create evaluation dataset: %s",
            e
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create evaluation dataset"
        ) from e


@router.get("/evaluation/datasets")
async def list_evaluation_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List evaluation datasets for user.

    Requires authentication.
    """
    datasets = db.query(EvaluationDataset).filter(
        EvaluationDataset.user_id == current_user.id
    ).order_by(EvaluationDataset.created_at.desc()).all()

    return {
        "datasets": [
            EvaluationDatasetResponse(
                id=d.id,
                name=d.name,
                description=d.description,
                queries=d.queries,
                created_at=d.created_at.isoformat(),
                updated_at=d.updated_at.isoformat()
            )
            for d in datasets
        ],
        "total": len(datasets)
    }


@router.post("/evaluation/run")
async def run_evaluation(
    request: EvaluationRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run evaluation on a dataset.

    Requires authentication. Verifies ownership.
    """
    try:
        service = get_retrieval_test_service()
        result = service.run_evaluation(
            db=db,
            user_id=current_user.id,
            dataset_id=request.dataset_id,
            method=request.method
        )
        return EvaluationRunResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Failed to run evaluation: %s",
            e
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to run evaluation"
        ) from e


@router.get("/evaluation/results")
async def get_evaluation_results(
    dataset_id: Optional[int] = None,
    method: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get evaluation results.

    Requires authentication.
    """
    query = db.query(EvaluationResult).join(EvaluationDataset).filter(
        EvaluationDataset.user_id == current_user.id
    )

    if dataset_id:
        query = query.filter(EvaluationResult.dataset_id == dataset_id)
    if method:
        query = query.filter(EvaluationResult.method == method)

    results = query.order_by(EvaluationResult.created_at.desc()).limit(100).all()

    return {
        "results": [
            {
                "id": r.id,
                "dataset_id": r.dataset_id,
                "method": r.method,
                "metrics": r.metrics,
                "created_at": r.created_at.isoformat()
            }
            for r in results
        ],
        "total": len(results)
    }
