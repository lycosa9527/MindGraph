"""
Chunk test execution endpoints.

Handles test creation, progress tracking, and results retrieval.
"""
import logging
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.knowledge_space import ChunkTestResult
from models.requests.requests_knowledge_space import (
    ChunkTestBenchmarkRequest,
    ChunkTestUserDocumentsRequest
)
from models.responses import (
    ChunkTestResultResponse,
    ChunkTestProgressResponse
)
from routers.api.knowledge_space.chunk_test_background import (
    run_test_in_background,
    run_benchmark_in_background,
    cancel_test,
    detect_and_mark_stuck_tests
)
from routers.api.knowledge_space.chunk_test_utils import check_feature_enabled
from services.knowledge.rag_chunk_test import get_rag_chunk_test_service
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chunk-test/benchmark", response_model=ChunkTestResultResponse)
async def test_benchmark_dataset(
    request: ChunkTestBenchmarkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test chunking methods with benchmark dataset.

    Requires authentication.
    """
    check_feature_enabled()
    service = get_rag_chunk_test_service()

    try:
        results = service.test_benchmark_dataset(
            db=db,
            user_id=current_user.id,
            dataset_name=request.dataset_name,
            custom_queries=request.queries,
            modes=request.modes
        )

        test_result = ChunkTestResult(
            user_id=current_user.id,
            dataset_name=request.dataset_name,
            semchunk_chunk_count=results["chunking_comparison"].get("semchunk", {}).get("count", 0),
            mindchunk_chunk_count=results["chunking_comparison"].get("mindchunk", {}).get("count", 0),
            chunk_stats=results["chunking_comparison"],
            retrieval_metrics=results.get("retrieval_comparison", {}),
            comparison_summary=results.get("summary", {})
        )
        db.add(test_result)
        db.commit()
        db.refresh(test_result)

        return ChunkTestResultResponse(
            test_id=test_result.id,
            session_id=test_result.session_id,
            dataset_name=test_result.dataset_name,
            chunking_comparison=test_result.chunk_stats or {},
            retrieval_comparison=test_result.retrieval_metrics or {},
            summary=test_result.comparison_summary or {},
            created_at=test_result.created_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[ChunkTestExecution] Benchmark test failed for user %s: %s",
            current_user.id,
            e,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Chunk test failed"
        ) from e


@router.post("/chunk-test/benchmark-async", response_model=ChunkTestResultResponse)
async def test_benchmark_dataset_async(
    request: ChunkTestBenchmarkRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test chunking methods with benchmark dataset (async background execution).

    Requires authentication. Creates test record immediately and runs test in background.
    """
    check_feature_enabled()
    try:
        modes = request.modes or ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]

        test_result = ChunkTestResult(
            user_id=current_user.id,
            dataset_name=request.dataset_name,
            status="pending",
            current_stage="pending",
            progress_percent=0,
            completed_methods=[]
        )
        db.add(test_result)
        db.commit()
        db.refresh(test_result)

        logger.info(
            "[ChunkTestExecution] Creating background thread for benchmark test %s: "
            "user_id=%s, dataset_name=%s, queries_count=%s, modes=%s",
            test_result.id,
            current_user.id,
            request.dataset_name,
            len(request.queries) if request.queries else 0,
            modes
        )

        thread = threading.Thread(
            target=run_benchmark_in_background,
            args=(
                test_result.id,
                current_user.id,
                request.dataset_name,
                request.queries,
                modes
            ),
            daemon=False,
            name=f"ChunkTestBenchmark-{test_result.id}"
        )
        thread.start()

        logger.info(
            "[ChunkTestExecution] Background thread started for benchmark test %s: thread_name=%s, thread_id=%s",
            test_result.id,
            thread.name,
            thread.ident
        )

        return ChunkTestResultResponse(
            test_id=test_result.id,
            session_id=test_result.session_id,
            dataset_name=test_result.dataset_name,
            chunking_comparison={},
            retrieval_comparison={},
            summary={},
            status=test_result.status,
            current_method=test_result.current_method,
            current_stage=test_result.current_stage,
            progress_percent=test_result.progress_percent,
            completed_methods=test_result.completed_methods,
            created_at=test_result.created_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[ChunkTestExecution] Benchmark test initiation failed for user %s: %s",
            current_user.id,
            e,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate benchmark test"
        ) from e


@router.post("/chunk-test/user-documents", response_model=ChunkTestResultResponse)
async def test_user_documents(
    request: ChunkTestUserDocumentsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test chunking methods with user's uploaded documents.

    Requires authentication. Verifies document ownership.
    Creates test record immediately and runs test in background.
    """
    check_feature_enabled()
    try:
        modes = request.modes or ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]

        test_result = ChunkTestResult(
            user_id=current_user.id,
            dataset_name="user_documents",
            document_ids=request.document_ids,
            status="pending",
            current_stage="pending",
            progress_percent=0,
            completed_methods=[]
        )
        db.add(test_result)
        db.commit()
        db.refresh(test_result)

        logger.info(
            "[ChunkTestExecution] Creating background thread for test %s: "
            "user_id=%s, document_ids=%s, queries_count=%s, modes=%s",
            test_result.id,
            current_user.id,
            request.document_ids,
            len(request.queries),
            modes
        )

        thread = threading.Thread(
            target=run_test_in_background,
            args=(
                test_result.id,
                current_user.id,
                request.document_ids,
                request.queries,
                modes
            ),
            daemon=False,
            name=f"ChunkTest-{test_result.id}"
        )
        thread.start()

        logger.info(
            "[ChunkTestExecution] Background thread started for test %s: thread_name=%s, thread_id=%s",
            test_result.id,
            thread.name,
            thread.ident
        )

        return ChunkTestResultResponse(
            test_id=test_result.id,
            session_id=test_result.session_id,
            dataset_name=test_result.dataset_name,
            document_ids=test_result.document_ids,
            chunking_comparison={},
            retrieval_comparison={},
            summary={},
            status=test_result.status,
            current_method=test_result.current_method,
            current_stage=test_result.current_stage,
            progress_percent=test_result.progress_percent,
            completed_methods=test_result.completed_methods,
            created_at=test_result.created_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[ChunkTestExecution] User documents test initiation failed for user %s: %s",
            current_user.id,
            e,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to initiate chunk test"
        ) from e


@router.get("/chunk-test/progress/{test_id}", response_model=ChunkTestProgressResponse)
async def get_chunk_test_progress(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current progress of a chunk test.

    Requires authentication. Verifies test ownership.
    Automatically detects and marks stuck tests before returning progress.
    """
    check_feature_enabled()
    # Check for stuck tests before returning progress
    stuck_count = detect_and_mark_stuck_tests()
    if stuck_count > 0:
        logger.info(
            "[ChunkTestExecution] Detected and marked %d stuck test(s) while checking progress",
            stuck_count
        )

    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    return ChunkTestProgressResponse(
        test_id=test_result.id,
        session_id=test_result.session_id,
        status=test_result.status,
        current_method=test_result.current_method,
        current_stage=test_result.current_stage,
        progress_percent=test_result.progress_percent,
        completed_methods=test_result.completed_methods or []
    )


@router.get("/chunk-test/results/{test_id}", response_model=ChunkTestResultResponse)
async def get_chunk_test_result(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete chunk test result by ID.

    Requires authentication. Verifies test ownership.
    Returns full results only when status='completed'.
    """
    check_feature_enabled()
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    return ChunkTestResultResponse(
        test_id=test_result.id,
        session_id=test_result.session_id,
        dataset_name=test_result.dataset_name,
        document_ids=test_result.document_ids,
        chunking_comparison=test_result.chunk_stats or {},
        retrieval_comparison=test_result.retrieval_metrics or {},
        summary=test_result.comparison_summary or {},
        evaluation_results=test_result.evaluation_results,
        status=test_result.status,
        current_method=test_result.current_method,
        current_stage=test_result.current_stage,
        progress_percent=test_result.progress_percent,
        completed_methods=test_result.completed_methods or [],
        created_at=test_result.created_at.isoformat()
    )


@router.get("/chunk-test/results")
async def get_chunk_test_results(
    dataset_name: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chunk test results list for user.

    Requires authentication.
    """
    check_feature_enabled()
    query = db.query(ChunkTestResult).filter(
        ChunkTestResult.user_id == current_user.id
    )

    if dataset_name:
        query = query.filter(ChunkTestResult.dataset_name == dataset_name)

    results = query.order_by(ChunkTestResult.created_at.desc()).limit(limit).all()

    return {
        "results": [
            {
                "test_id": r.id,
                "session_id": r.session_id,
                "dataset_name": r.dataset_name,
                "document_ids": r.document_ids,
                "semchunk_chunk_count": r.semchunk_chunk_count,
                "mindchunk_chunk_count": r.mindchunk_chunk_count,
                "status": r.status,
                "summary": r.comparison_summary or {},
                "created_at": r.created_at.isoformat()
            }
            for r in results
        ],
        "total": len(results)
    }


@router.delete("/chunk-test/results/{test_id}")
async def delete_chunk_test_result(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a chunk test result.

    Requires authentication. Verifies test ownership.
    Cannot delete tests that are currently processing.
    """
    check_feature_enabled()
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    if test_result.status in ("pending", "processing"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a test that is currently processing. Please cancel it first."
        )

    try:
        db.delete(test_result)
        db.commit()

        logger.info("[ChunkTestExecution] Test %s deleted by user %s", test_id, current_user.id)

        return {
            "success": True,
            "message": "Test result deleted successfully"
        }
    except Exception as e:
        logger.error(
            "[ChunkTestExecution] Failed to delete test %s: %s",
            test_id,
            e,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete test result"
        ) from e


@router.post("/chunk-test/{test_id}/cancel")
async def cancel_chunk_test(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a running chunk test.

    Requires authentication. Verifies test ownership.
    Only tests with status 'pending' or 'processing' can be cancelled.
    """
    check_feature_enabled()
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    if test_result.status not in ("pending", "processing"):
        status_msg = (
            f"Cannot cancel test with status '{test_result.status}'. "
            "Only pending or processing tests can be cancelled."
        )
        raise HTTPException(status_code=400, detail=status_msg)

    try:
        cancel_test(test_id)

        test_result.status = "failed"
        test_result.current_stage = "cancelled"
        db.commit()

        logger.info("[ChunkTestExecution] Test %s cancelled by user %s", test_id, current_user.id)

        return {
            "success": True,
            "message": "Test cancellation requested. The test will stop at the next checkpoint."
        }
    except Exception as e:
        logger.error(
            "[ChunkTestExecution] Failed to cancel test %s: %s",
            test_id,
            e,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel test"
        ) from e


@router.post("/chunk-test/detect-stuck")
async def detect_stuck_tests(
    _current_user: User = Depends(get_current_user),
    _db: Session = Depends(get_db)
):
    """
    Detect and mark stuck chunk tests as failed.

    Requires authentication. Checks for tests that have been in 'pending' 
    or 'processing' status for more than 30 minutes.
    """
    check_feature_enabled()
    try:
        stuck_count = detect_and_mark_stuck_tests()
        return {
            "success": True,
            "stuck_tests_detected": stuck_count,
            "message": f"Detected and marked {stuck_count} stuck test(s) as failed"
        }
    except Exception as e:
        logger.error(
            "[ChunkTestExecution] Failed to detect stuck tests: %s",
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to detect stuck tests"
        ) from e
