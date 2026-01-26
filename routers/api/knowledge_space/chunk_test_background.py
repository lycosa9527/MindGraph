"""
Background processing for chunk tests.

Handles background thread execution, cancellation, and cleanup.
"""
import atexit
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Set

from config.database import SessionLocal
from models.domain.knowledge_space import ChunkTestResult
from services.knowledge.rag_chunk_test import get_rag_chunk_test_service

logger = logging.getLogger(__name__)

# Stuck test detection threshold (30 minutes)
STUCK_TEST_THRESHOLD_MINUTES = 30

# Track active test threads for cleanup on shutdown
_active_tests: Set[int] = set()
_active_tests_lock = threading.Lock()

# Track cancellation flags for tests
_cancellation_flags: Set[int] = set()
_cancellation_lock = threading.Lock()


def is_cancelled(test_id: int) -> bool:
    """Check if test is cancelled."""
    with _cancellation_lock:
        return test_id in _cancellation_flags


def cancel_test(test_id: int) -> None:
    """Mark a test as cancelled."""
    with _cancellation_lock:
        _cancellation_flags.add(test_id)


def register_active_test(test_id: int) -> None:
    """Register a test as active."""
    with _active_tests_lock:
        _active_tests.add(test_id)


def unregister_active_test(test_id: int) -> None:
    """Unregister a test as active."""
    with _active_tests_lock:
        _active_tests.discard(test_id)
    with _cancellation_lock:
        _cancellation_flags.discard(test_id)


def _cleanup_active_tests():
    """Mark all active tests as failed on shutdown."""
    with _active_tests_lock:
        if not _active_tests:
            return

        logger.info(
            "[ChunkTestBackground] Cleaning up %s active tests on shutdown",
            len(_active_tests)
        )
        db = None
        try:
            db = SessionLocal()
            for test_id in _active_tests:
                try:
                    test_result = db.query(ChunkTestResult).filter(
                        ChunkTestResult.id == test_id
                    ).first()
                    if test_result and test_result.status in ("pending", "processing"):
                        test_result.status = "failed"
                        test_result.current_stage = "interrupted"
                        logger.info("[ChunkTestBackground] Marked test %s as interrupted", test_id)
                except Exception as e:
                    logger.error(
                        "[ChunkTestBackground] Failed to cleanup test %s: %s",
                        test_id, e
                    )
            if db is not None:
                db.commit()
        except Exception as e:
            logger.error("[ChunkTestBackground] Error during test cleanup: %s", e)
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    pass
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception as close_error:
                    logger.warning(
                        "[ChunkTestBackground] Error closing cleanup session: %s",
                        close_error
                    )


# Register cleanup handler
atexit.register(_cleanup_active_tests)


def detect_and_mark_stuck_tests() -> int:
    """
    Detect and mark stuck tests as failed.
    
    A test is considered stuck if it has been in 'pending' or 'processing' 
    status for more than STUCK_TEST_THRESHOLD_MINUTES minutes.
    
    Returns:
        Number of stuck tests detected and marked as failed
    """
    db = SessionLocal()
    stuck_count = 0
    
    try:
        threshold_time = datetime.utcnow() - timedelta(minutes=STUCK_TEST_THRESHOLD_MINUTES)
        
        stuck_tests = db.query(ChunkTestResult).filter(
            ChunkTestResult.status.in_(["pending", "processing"]),
            ChunkTestResult.created_at < threshold_time
        ).all()
        
        if not stuck_tests:
            logger.debug("[ChunkTestBackground] No stuck tests detected")
            return 0
        
        logger.warning(
            "[ChunkTestBackground] Detected %d stuck test(s) older than %d minutes",
            len(stuck_tests),
            STUCK_TEST_THRESHOLD_MINUTES
        )
        
        for test in stuck_tests:
            try:
                age_minutes = (datetime.utcnow() - test.created_at).total_seconds() / 60
                logger.warning(
                    "[ChunkTestBackground] Marking stuck test as failed: "
                    "test_id=%s, status=%s, age=%.1f minutes, stage=%s, progress=%s%%",
                    test.id, test.status, age_minutes, test.current_stage, test.progress_percent
                )
                
                test.status = "failed"
                test.current_stage = "stuck_timeout"
                test.progress_percent = 0
                stuck_count += 1
                
                # Unregister from active tests if it was registered
                unregister_active_test(test.id)
                
            except Exception as e:
                logger.error(
                    "[ChunkTestBackground] Failed to mark stuck test %s as failed: %s",
                    test.id, e,
                    exc_info=True
                )
        
        if stuck_count > 0:
            db.commit()
            logger.info(
                "[ChunkTestBackground] Successfully marked %d stuck test(s) as failed",
                stuck_count
            )
        
    except Exception as e:
        logger.error(
            "[ChunkTestBackground] Error detecting stuck tests: %s",
            e,
            exc_info=True
        )
        db.rollback()
    finally:
        db.close()
    
    return stuck_count


def run_test_in_background(
    test_id: int,
    user_id: int,
    document_ids: List[int],
    queries: List[str],
    modes: Optional[List[str]]
) -> None:
    """Run test in background thread and update progress."""
    logger.info(
        "[ChunkTestBackground] Starting background test execution: "
        "test_id=%s, user_id=%s, document_ids=%s, queries_count=%s, modes=%s",
        test_id, user_id, document_ids, len(queries), modes
    )
    register_active_test(test_id)

    db = None
    service = get_rag_chunk_test_service()
    test_result = None

    try:
        # Create database session with proper error handling
        db = SessionLocal()
        logger.debug("[ChunkTestBackground] Querying test result %s from database", test_id)
        test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
        if not test_result:
            logger.error("[ChunkTestBackground] Test result %s not found in database", test_id)
            return

        logger.info(
            "[ChunkTestBackground] Test result found: test_id=%s, current_status=%s, "
            "current_stage=%s, progress=%s%%",
            test_id, test_result.status, test_result.current_stage, test_result.progress_percent
        )

        def progress_callback(status, method, stage, progress, completed_methods):
            """Update progress in database."""
            logger.debug(
                "[ChunkTestBackground] Progress callback invoked: test_id=%s, status=%s, "
                "method=%s, stage=%s, progress=%s%%, completed_methods=%s",
                test_id, status, method, stage, progress, completed_methods
            )

            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled, stopping progress updates", test_id)
                return False

            try:
                test_result.status = status
                test_result.current_method = method
                test_result.current_stage = stage
                test_result.progress_percent = progress
                test_result.completed_methods = completed_methods
                db.commit()
                logger.debug(
                    "[ChunkTestBackground] Progress updated successfully: test_id=%s, "
                    "status=%s, stage=%s, progress=%s%%",
                    test_id, status, stage, progress
                )
                return True
            except Exception as e:
                logger.error(
                    "[ChunkTestBackground] Failed to update progress for test %s: %s",
                    test_id, e,
                    exc_info=True
                )
                db.rollback()
                return True

        if is_cancelled(test_id):
            logger.info("[ChunkTestBackground] Test %s was cancelled before starting execution", test_id)
            test_result.status = "failed"
            test_result.current_stage = "cancelled"
            db.commit()
            return

        logger.info(
            "[ChunkTestBackground] Starting test execution: test_id=%s, "
            "document_ids=%s, queries_count=%s, modes=%s",
            test_id, document_ids, len(queries), modes
        )

        try:
            results = service.test_user_documents(
                db=db,
                user_id=user_id,
                document_ids=document_ids,
                queries=queries,
                modes=modes,
                progress_callback=progress_callback
            )

            logger.info(
                "[ChunkTestBackground] Test execution completed: test_id=%s, "
                "chunking_comparison_keys=%s, retrieval_comparison_keys=%s",
                test_id,
                list(results.get("chunking_comparison", {}).keys()),
                list(results.get("retrieval_comparison", {}).keys())
            )

            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s was cancelled during execution", test_id)
                test_result.status = "failed"
                test_result.current_stage = "cancelled"
                db.commit()
                return

            logger.debug("[ChunkTestBackground] Updating test result with final data: test_id=%s", test_id)
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

            logger.info(
                "[ChunkTestBackground] Test %s completed successfully: "
                "semchunk_chunks=%s, mindchunk_chunks=%s",
                test_id,
                test_result.semchunk_chunk_count,
                test_result.mindchunk_chunk_count
            )
        except RuntimeError as e:
            if "cancelled" in str(e).lower() or is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                if test_result:
                    test_result.status = "failed"
                    test_result.current_stage = "cancelled"
                    db.commit()
                return
            logger.error(
                "[ChunkTestBackground] RuntimeError during test execution for test %s: %s",
                test_id, e,
                exc_info=True
            )
            raise
        except Exception as e:
            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                if test_result:
                    test_result.status = "failed"
                    test_result.current_stage = "cancelled"
                    db.commit()
                return
            logger.error(
                "[ChunkTestBackground] Exception during test execution for test %s: %s",
                test_id, e,
                exc_info=True
            )
            raise

    except Exception as e:
        logger.error(
            "[ChunkTestBackground] Background test failed for test %s: %s",
            test_id,
            e,
            exc_info=True
        )
        try:
            if test_result is None:
                test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
            if test_result:
                test_result.status = "failed"
                test_result.current_stage = "failed"
                db.commit()
                logger.info("[ChunkTestBackground] Marked test %s as failed", test_id)
        except Exception as update_error:
            logger.error(
                "[ChunkTestBackground] Failed to update failed status for test %s: %s",
                test_id, update_error,
                exc_info=True
            )
            db.rollback()
    finally:
        logger.debug("[ChunkTestBackground] Cleaning up test %s", test_id)
        unregister_active_test(test_id)
        # Ensure database session is properly closed even on kill -9 scenarios
        if db is not None:
            try:
                # Rollback any uncommitted transactions
                db.rollback()
            except Exception as rollback_error:
                logger.debug(
                    "[ChunkTestBackground] Error rolling back transaction for test %s: %s",
                    test_id, rollback_error
                )
            try:
                # Close the session
                db.close()
            except Exception as close_error:
                logger.warning(
                    "[ChunkTestBackground] Error closing database session for test %s: %s",
                    test_id, close_error
                )
        logger.info("[ChunkTestBackground] Background test thread completed for test %s", test_id)


def run_benchmark_in_background(
    test_id: int,
    user_id: int,
    dataset_name: str,
    queries: Optional[List[str]],
    modes: Optional[List[str]]
) -> None:
    """Run benchmark test in background thread and update progress."""
    logger.info(
        "[ChunkTestBackground] Starting background benchmark test execution: "
        "test_id=%s, user_id=%s, dataset_name=%s, queries_count=%s, modes=%s",
        test_id, user_id, dataset_name, len(queries) if queries else 0, modes
    )
    register_active_test(test_id)

    db = None
    service = get_rag_chunk_test_service()
    test_result = None

    try:
        # Create database session with proper error handling
        db = SessionLocal()
        logger.debug("[ChunkTestBackground] Querying test result %s from database", test_id)
        test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
        if not test_result:
            logger.error("[ChunkTestBackground] Test result %s not found in database", test_id)
            return

        logger.info(
            "[ChunkTestBackground] Test result found: test_id=%s, current_status=%s, "
            "current_stage=%s, progress=%s%%",
            test_id, test_result.status, test_result.current_stage, test_result.progress_percent
        )

        def progress_callback(status, method, stage, progress, completed_methods):
            """Update progress in database."""
            logger.debug(
                "[ChunkTestBackground] Progress callback invoked: test_id=%s, status=%s, "
                "method=%s, stage=%s, progress=%s%%, completed_methods=%s",
                test_id, status, method, stage, progress, completed_methods
            )

            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled, stopping progress updates", test_id)
                return False

            try:
                test_result.status = status
                test_result.current_method = method
                test_result.current_stage = stage
                test_result.progress_percent = progress
                test_result.completed_methods = completed_methods
                db.commit()
                logger.debug(
                    "[ChunkTestBackground] Progress updated successfully: test_id=%s, "
                    "status=%s, stage=%s, progress=%s%%",
                    test_id, status, stage, progress
                )
                return True
            except Exception as e:
                logger.error(
                    "[ChunkTestBackground] Failed to update progress for test %s: %s",
                    test_id, e,
                    exc_info=True
                )
                db.rollback()
                return True

        if is_cancelled(test_id):
            logger.info("[ChunkTestBackground] Test %s was cancelled before starting execution", test_id)
            test_result.status = "failed"
            test_result.current_stage = "cancelled"
            db.commit()
            return

        logger.info(
            "[ChunkTestBackground] Starting benchmark test execution: test_id=%s, "
            "dataset_name=%s, queries_count=%s, modes=%s",
            test_id, dataset_name, len(queries) if queries else 0, modes
        )

        try:
            results = service.test_benchmark_dataset(
                db=db,
                user_id=user_id,
                dataset_name=dataset_name,
                custom_queries=queries,
                modes=modes,
                progress_callback=progress_callback
            )

            logger.info(
                "[ChunkTestBackground] Benchmark test execution completed: test_id=%s, "
                "chunking_comparison_keys=%s, retrieval_comparison_keys=%s",
                test_id,
                list(results.get("chunking_comparison", {}).keys()),
                list(results.get("retrieval_comparison", {}).keys())
            )

            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s was cancelled during execution", test_id)
                test_result.status = "failed"
                test_result.current_stage = "cancelled"
                db.commit()
                return

            logger.debug("[ChunkTestBackground] Updating test result with final data: test_id=%s", test_id)
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

            logger.info(
                "[ChunkTestBackground] Benchmark test %s completed successfully: "
                "semchunk_chunks=%s, mindchunk_chunks=%s",
                test_id,
                test_result.semchunk_chunk_count,
                test_result.mindchunk_chunk_count
            )
        except RuntimeError as e:
            if "cancelled" in str(e).lower() or is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                if test_result:
                    test_result.status = "failed"
                    test_result.current_stage = "cancelled"
                    db.commit()
                return
            logger.error(
                "[ChunkTestBackground] RuntimeError during benchmark test execution for test %s: %s",
                test_id, e,
                exc_info=True
            )
            raise
        except Exception as e:
            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                if test_result:
                    test_result.status = "failed"
                    test_result.current_stage = "cancelled"
                    db.commit()
                return
            logger.error(
                "[ChunkTestBackground] Exception during benchmark test execution for test %s: %s",
                test_id, e,
                exc_info=True
            )
            raise

    except Exception as e:
        logger.error(
            "[ChunkTestBackground] Background benchmark test failed for test %s: %s",
            test_id,
            e,
            exc_info=True
        )
        try:
            if test_result is None:
                test_result = db.query(ChunkTestResult).filter(ChunkTestResult.id == test_id).first()
            if test_result:
                test_result.status = "failed"
                test_result.current_stage = "failed"
                db.commit()
                logger.info("[ChunkTestBackground] Marked test %s as failed", test_id)
        except Exception as update_error:
            logger.error(
                "[ChunkTestBackground] Failed to update failed status for test %s: %s",
                test_id, update_error,
                exc_info=True
            )
            db.rollback()
    finally:
        logger.debug("[ChunkTestBackground] Cleaning up test %s", test_id)
        unregister_active_test(test_id)
        # Ensure database session is properly closed even on kill -9 scenarios
        if db is not None:
            try:
                # Rollback any uncommitted transactions
                db.rollback()
            except Exception as rollback_error:
                logger.debug(
                    "[ChunkTestBackground] Error rolling back transaction for test %s: %s",
                    test_id, rollback_error
                )
            try:
                # Close the session
                db.close()
            except Exception as close_error:
                logger.warning(
                    "[ChunkTestBackground] Error closing database session for test %s: %s",
                    test_id, close_error
                )
        logger.info("[ChunkTestBackground] Background benchmark test thread completed for test %s", test_id)
