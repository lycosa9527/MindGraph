"""
Chunk test evaluation endpoints.

Handles manual evaluation and chunk viewing.
"""
import logging

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from utils.auth import get_current_user
from models.domain.knowledge_space import ChunkTestResult
from models.requests.requests_knowledge_space import ManualEvaluationRequest
from routers.api.knowledge_space.chunk_test_utils import check_feature_enabled
from services.knowledge.chunking_service import Chunk
from services.knowledge.rag_chunk_test import get_rag_chunk_test_service
from services.knowledge.rag_chunk_test.manual_evaluator import get_manual_evaluator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/chunk-test/{test_id}/chunks/{method}")
async def get_chunk_test_chunks(
    test_id: int,
    method: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chunks for a test result using a specific method (on-demand generation).

    Requires authentication. Verifies test ownership.
    Regenerates chunks from stored document_ids or dataset_name.

    Args:
        test_id: Test result ID
        method: Chunking method ('spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk')

    Returns:
        List of chunks with text, metadata, and position info
    """
    check_feature_enabled()
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    valid_methods = ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]
    if method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method. Must be one of: {', '.join(valid_methods)}"
        )

    try:
        service = get_rag_chunk_test_service()
        chunks = service.get_chunks_for_test(
            db=db,
            user_id=current_user.id,
            test_result=test_result,
            method=method
        )

        return {
            "chunks": chunks,
            "method": method,
            "test_id": test_id,
            "count": len(chunks)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[ChunkTestEvaluation] Failed to get chunks for test %s, method %s: %s",
            test_id,
            method,
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate chunks"
        ) from e


@router.post("/chunk-test/{test_id}/evaluate")
async def manual_evaluate_chunks(
    test_id: int,
    request: ManualEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually evaluate chunks using DashScope LLM models.

    Requires authentication. Verifies test ownership.

    Args:
        test_id: Test result ID
        request: Evaluation request with:
            - query: Query string
            - chunk_ids: List of chunk indices to evaluate (optional, evaluates all if not provided)
            - method: Chunking method to evaluate (required)
            - answer: Optional ground truth answer for answer relevance evaluation
            - model: DashScope model to use (default: "qwen-max")

    Returns:
        Evaluation results with scores
    """
    check_feature_enabled()
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    query = request.query
    chunk_ids = request.chunk_ids
    method = request.method
    answer = request.answer
    model = request.model

    valid_methods = ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]
    if method not in valid_methods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method. Must be one of: {', '.join(valid_methods)}"
        )

    try:
        service = get_rag_chunk_test_service()
        chunks_data = service.get_chunks_for_test(
            db=db,
            user_id=current_user.id,
            test_result=test_result,
            method=method
        )

        if not chunks_data:
            raise HTTPException(status_code=404, detail="No chunks found for this test and method")

        chunks = []
        for chunk_dict in chunks_data:
            chunk = Chunk(
                text=str(chunk_dict["text"]),
                start_char=int(chunk_dict.get("start_char", 0)),
                end_char=int(chunk_dict.get("end_char", 0)),
                chunk_index=int(chunk_dict["chunk_index"]),
                metadata=dict(chunk_dict.get("metadata", {}))
            )
            chunks.append(chunk)

        if chunk_ids:
            chunks = [c for c in chunks if c.chunk_index in chunk_ids]

        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks match the provided chunk_ids")

        evaluator = get_manual_evaluator()
        results = []

        if answer:
            answer_eval = evaluator.evaluate_answer_relevance(
                chunks=chunks,
                query=query,
                answer=answer,
                model=model
            )
            results.append({
                "type": "answer_relevance",
                "evaluation": answer_eval
            })

        chunk_evals = []
        for chunk in chunks:
            chunk_eval = evaluator.evaluate_chunk_quality(
                chunk=chunk,
                query=query,
                model=model
            )
            chunk_evals.append({
                "chunk_index": chunk.chunk_index,
                "evaluation": chunk_eval
            })
        results.append({
            "type": "chunk_quality",
            "evaluations": chunk_evals
        })

        return {
            "test_id": test_id,
            "method": method,
            "query": query,
            "chunk_count": len(chunks),
            "results": results
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[ChunkTestEvaluation] Failed to evaluate chunks for test %s: %s",
            test_id,
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to evaluate chunks"
        ) from e
