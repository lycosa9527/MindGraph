"""
Knowledge Space Chunk Test Router
==================================

API endpoints for RAG chunk testing and comparison.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import atexit
import logging
import threading
from typing import Optional, List, Set

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from config.database import get_db, SessionLocal
from models.auth import User
from models.knowledge_space import ChunkTestResult
from models.requests_knowledge_space import (
    ChunkTestBenchmarkRequest,
    ChunkTestUserDocumentsRequest
)
from models.responses import ChunkTestResultResponse, ChunkTestProgressResponse
from services.knowledge.rag_chunk_test import get_rag_chunk_test_service
from services.knowledge.rag_chunk_test.test_queries import get_test_queries
try:
    from services.knowledge.rag_chunk_test.utils.download_datasets import download_datasets
except ImportError:
    download_datasets = None
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()

# Track active test threads for cleanup on shutdown
_active_tests: Set[int] = set()
_active_tests_lock = threading.Lock()


def _cleanup_active_tests():
    """Mark all active tests as failed on shutdown."""
    with _active_tests_lock:
        if not _active_tests:
            return
        
        logger.info("[ChunkTestAPI] Cleaning up %s active tests on shutdown", len(_active_tests))
        db = SessionLocal()
        try:
            for test_id in _active_tests:
                try:
                    test_result = db.query(ChunkTestResult).filter(
                        ChunkTestResult.id == test_id
                    ).first()
                    if test_result and test_result.status in ("pending", "processing"):
                        test_result.status = "failed"
                        test_result.current_stage = "interrupted"
                        logger.info("[ChunkTestAPI] Marked test %s as interrupted", test_id)
                except Exception as e:
                    logger.error(
                        "[ChunkTestAPI] Failed to cleanup test %s: %s",
                        test_id, e
                    )
            db.commit()
        except Exception as e:
            logger.error("[ChunkTestAPI] Error during test cleanup: %s", e)
            db.rollback()
        finally:
            db.close()


# Register cleanup handler
atexit.register(_cleanup_active_tests)


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
    service = get_rag_chunk_test_service()

    try:
        # Run test
        results = service.test_benchmark_dataset(
            db=db,
            user_id=current_user.id,
            dataset_name=request.dataset_name,
            custom_queries=request.queries,
            modes=request.modes
        )

        # Save results to database
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
            "[ChunkTestAPI] Benchmark test failed for user %s: %s",
            current_user.id,
            e,
            exc_info=True
        )
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Chunk test failed"
        ) from e


def _run_test_in_background(
    test_id: int,
    user_id: int,
    document_ids: List[int],
    queries: List[str],
    modes: Optional[List[str]]
):
    """Run test in background thread and update progress."""
    # Register test as active
    with _active_tests_lock:
        _active_tests.add(test_id)
    
    db = SessionLocal()
    service = get_rag_chunk_test_service()

    try:
        test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
        if not test_result:
            logger.error("[ChunkTestAPI] Test result %s not found", test_id)
            return

        def progress_callback(status, method, stage, progress, completed_methods):
            """Update progress in database."""
            try:
                test_result.status = status
                test_result.current_method = method
                test_result.current_stage = stage
                test_result.progress_percent = progress
                test_result.completed_methods = completed_methods
                db.commit()
            except Exception as e:
                logger.error("[ChunkTestAPI] Failed to update progress: %s", e)
                db.rollback()

        # Run test with progress tracking
        results = service.test_user_documents(
            db=db,
            user_id=user_id,
            document_ids=document_ids,
            queries=queries,
            modes=modes,
            progress_callback=progress_callback
        )

        # Update test result with final data
        test_result.status = "completed"
        test_result.current_stage = "completed"
        test_result.progress_percent = 100
        test_result.semchunk_chunk_count = results["chunking_comparison"].get("semchunk", {}).get("count", 0)
        test_result.mindchunk_chunk_count = results["chunking_comparison"].get("mindchunk", {}).get("count", 0)
        test_result.chunk_stats = results["chunking_comparison"]
        test_result.retrieval_metrics = results.get("retrieval_comparison", {})
        test_result.comparison_summary = results.get("summary", {})
        test_result.evaluation_results = results.get("evaluation_results", {})
        test_result.completed_methods = modes or ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]
        db.commit()

        logger.info("[ChunkTestAPI] Test %s completed successfully", test_id)

    except Exception as e:
        logger.error(
            "[ChunkTestAPI] Background test failed for test %s: %s",
            test_id,
            e,
            exc_info=True
        )
        try:
            test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
            if test_result:
                test_result.status = "failed"
                test_result.current_stage = "failed"
                db.commit()
        except Exception as update_error:
            logger.error("[ChunkTestAPI] Failed to update failed status: %s", update_error)
            db.rollback()
    finally:
        # Unregister test as active
        with _active_tests_lock:
            _active_tests.discard(test_id)
        db.close()


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
    try:
        # Ensure 5 methods are used
        modes = request.modes or ["spacy", "semchunk", "chonkie", "langchain", "mindchunk"]

        # Create test record immediately with pending status
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

        # Start background thread to run test
        # Use non-daemon thread so it can complete cleanup on shutdown
        thread = threading.Thread(
            target=_run_test_in_background,
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

        # Return test_id immediately
        return ChunkTestResultResponse(
            test_id=test_result.id,
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
            "[ChunkTestAPI] User documents test initiation failed for user %s: %s",
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
    """
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    return ChunkTestProgressResponse(
        test_id=test_result.id,
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
    test_result = db.query(ChunkTestResult).filter(
        ChunkTestResult.id == test_id,
        ChunkTestResult.user_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    return ChunkTestResultResponse(
        test_id=test_result.id,
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


@router.get("/chunk-test/benchmarks")
async def list_available_benchmarks():
    """
    List available benchmark datasets.

    No authentication required.
    """
    return {
        "benchmarks": [
            {
                "name": "FinanceBench",
                "description": "Financial document benchmark dataset",
                "source": "PatronusAI/financebench (Hugging Face)",
                "version": "v1.0",
                "updated_at": "2024-01-15T00:00:00Z"
            },
            {
                "name": "KG-RAG",
                "description": "Knowledge Graph RAG benchmark (BiomixQA)",
                "source": "kg-rag/BiomixQA (Hugging Face)",
                "version": "v1.2",
                "updated_at": "2024-02-20T00:00:00Z"
            },
            {
                "name": "FRAMES",
                "description": "FRAMES benchmark dataset",
                "source": "google/frames-benchmark (Hugging Face)",
                "version": "v2.1",
                "updated_at": "2024-03-10T00:00:00Z"
            },
            {
                "name": "PubMedQA",
                "description": "PubMed question answering benchmark",
                "source": "bigbio/pubmed_qa (Hugging Face)",
                "version": "v1.5",
                "updated_at": "2024-01-30T00:00:00Z"
            }
        ]
    }


@router.post("/chunk-test/update-datasets")
async def update_benchmark_datasets(
    _current_user: User = Depends(get_current_user)
):
    """
    Update/download benchmark datasets from Hugging Face.

    Requires authentication.
    """
    if download_datasets is None:
        raise HTTPException(
            status_code=500,
            detail="Dataset update module not available"
        )

    try:
        # Run download in background (could use Celery for async)
        download_datasets()

        return {
            "success": True,
            "message": "Benchmark datasets update initiated successfully"
        }
    except Exception as e:
        logger.error(
            "[ChunkTestAPI] Failed to update datasets: %s",
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update datasets"
        ) from e


@router.get("/chunk-test/test-queries")
async def get_test_queries_endpoint(
    dataset_name: Optional[str] = None,
    count: int = 20
):
    """
    Get example test queries for chunk testing.

    Args:
        dataset_name: Dataset name ('FinanceBench', 'KG-RAG', 'PubMedQA', 'FRAMES', 'mixed')
        count: Number of queries to return (default: 20, max: 20)

    Returns:
        List of test queries
    """
    queries = get_test_queries(dataset_name or "mixed", min(count, 20))
    return {
        "queries": queries,
        "count": len(queries),
        "dataset": dataset_name or "mixed",
        "note": "These are example queries. Metrics will be averaged across all queries."
    }
