"""
Background processing for chunk tests.

Handles background thread execution, cancellation, and cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import atexit
import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy import select, update

from config.database import SyncSessionLocal
from models.domain.knowledge_space import ChunkTestResult
from services.knowledge.rag_chunk_test import get_rag_chunk_test_service
from services.utils.error_types import DATABASE_ERRORS
from utils.db.rls_context import RlsContext, reset_rls_context, rls_sync_session, set_rls_context
from utils.db.session_open import system_rls_session, user_rls_session

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
        test_ids = list(_active_tests)

    logger.info(
        "[ChunkTestBackground] Cleaning up %s active tests on shutdown",
        len(test_ids),
    )
    try:
        with rls_sync_session(RlsContext.system_bootstrap()) as db:
            for test_id in test_ids:
                try:
                    test_result = db.execute(
                        select(ChunkTestResult).where(ChunkTestResult.id == test_id)
                    ).scalar_one_or_none()
                    if test_result and test_result.status in ("pending", "processing"):
                        test_result.status = "failed"
                        test_result.current_stage = "interrupted"
                        logger.info(
                            "[ChunkTestBackground] Marked test %s as interrupted",
                            test_id,
                        )
                except DATABASE_ERRORS as e:
                    logger.error(
                        "[ChunkTestBackground] Failed to cleanup test %s: %s",
                        test_id,
                        e,
                    )
            db.commit()
    except DATABASE_ERRORS as e:
        logger.error("[ChunkTestBackground] Error during test cleanup: %s", e)


# Register cleanup handler
atexit.register(_cleanup_active_tests)


async def detect_and_mark_stuck_tests_async() -> int:
    """
    Detect and mark stuck tests as failed (async variant).

    A test is considered stuck if it has been in ``pending`` or ``processing``
    status for more than :data:`STUCK_TEST_THRESHOLD_MINUTES` minutes.  Used
    by FastAPI endpoints that run on the asyncio event loop; performs the
    scan through ``AsyncSessionLocal`` so detection never blocks the loop on
    a synchronous DB session.

    Returns:
        Number of stuck tests detected and marked as failed.
    """
    stuck_count = 0
    threshold_time = datetime.now(UTC) - timedelta(minutes=STUCK_TEST_THRESHOLD_MINUTES)

    try:
        async with system_rls_session() as db:
            result = await db.execute(
                select(ChunkTestResult).where(
                    ChunkTestResult.status.in_(["pending", "processing"]),
                    ChunkTestResult.created_at < threshold_time,
                )
            )
            stuck_tests = list(result.scalars().all())

            if not stuck_tests:
                logger.debug("[ChunkTestBackground] No stuck tests detected")
                return 0

            logger.warning(
                "[ChunkTestBackground] Detected %d stuck test(s) older than %d minutes",
                len(stuck_tests),
                STUCK_TEST_THRESHOLD_MINUTES,
            )

            stuck_ids: List[int] = []
            for test in stuck_tests:
                try:
                    age_minutes = (datetime.now(UTC) - test.created_at).total_seconds() / 60
                    logger.warning(
                        "[ChunkTestBackground] Marking stuck test as failed: "
                        "test_id=%s, status=%s, age=%.1f minutes, stage=%s, progress=%s%%",
                        test.id,
                        test.status,
                        age_minutes,
                        test.current_stage,
                        test.progress_percent,
                    )
                    stuck_ids.append(test.id)
                    unregister_active_test(test.id)
                except DATABASE_ERRORS as exc:
                    logger.error(
                        "[ChunkTestBackground] Failed to schedule stuck test %s update: %s",
                        test.id,
                        exc,
                        exc_info=True,
                    )

            if stuck_ids:
                await db.execute(
                    update(ChunkTestResult)
                    .where(ChunkTestResult.id.in_(stuck_ids))
                    .values(
                        status="failed",
                        current_stage="stuck_timeout",
                        progress_percent=0,
                    )
                )
                await db.commit()
                stuck_count = len(stuck_ids)
                logger.info(
                    "[ChunkTestBackground] Successfully marked %d stuck test(s) as failed",
                    stuck_count,
                )

    except DATABASE_ERRORS as exc:
        logger.error(
            "[ChunkTestBackground] Error detecting stuck tests (async): %s",
            exc,
            exc_info=True,
        )

    return stuck_count


async def _run_user_documents_test_async(
    user_id: int,
    document_ids: List[int],
    queries: List[str],
    modes: Optional[List[str]],
    progress_callback: Callable[..., Optional[bool]],
) -> Dict[str, Any]:
    """Execute user-documents chunk test on the asyncio loop for this thread."""
    service = get_rag_chunk_test_service()
    async with user_rls_session(user_id) as async_db:
        return await service.test_user_documents(
            db=async_db,
            user_id=user_id,
            document_ids=document_ids,
            queries=queries,
            modes=modes,
            progress_callback=progress_callback,
        )


async def _run_benchmark_test_async(
    user_id: int,
    dataset_name: str,
    queries: Optional[List[str]],
    modes: Optional[List[str]],
    progress_callback: Callable[..., Optional[bool]],
) -> Dict[str, Any]:
    """Execute benchmark chunk test on the asyncio loop for this thread."""
    service = get_rag_chunk_test_service()
    async with user_rls_session(user_id) as async_db:
        return await service.test_benchmark_dataset(
            db=async_db,
            user_id=user_id,
            dataset_name=dataset_name,
            custom_queries=queries,
            modes=modes,
            progress_callback=progress_callback,
        )


def run_test_in_background(
    test_id: int,
    user_id: int,
    document_ids: List[int],
    queries: List[str],
    modes: Optional[List[str]],
) -> None:
    """Run test in background thread and update progress."""
    logger.info(
        "[ChunkTestBackground] Starting background test execution: "
        "test_id=%s, user_id=%s, document_ids=%s, queries_count=%s, modes=%s",
        test_id,
        user_id,
        document_ids,
        len(queries),
        modes,
    )
    register_active_test(test_id)

    db = None
    test_result = None

    rls_token = set_rls_context(RlsContext.for_celery_user(user_id))
    try:
        # Create database session with proper error handling
        db = SyncSessionLocal()
        logger.debug("[ChunkTestBackground] Querying test result %s from database", test_id)
        loaded = db.execute(select(ChunkTestResult).where(ChunkTestResult.id == test_id)).scalar_one_or_none()
        if not loaded:
            logger.error("[ChunkTestBackground] Test result %s not found in database", test_id)
            return

        test_result = loaded
        result_row: ChunkTestResult = test_result
        sync_db = db

        logger.info(
            "[ChunkTestBackground] Test result found: test_id=%s, current_status=%s, current_stage=%s, progress=%s%%",
            test_id,
            result_row.status,
            result_row.current_stage,
            result_row.progress_percent,
        )

        def progress_callback(status, method, stage, progress, completed_methods):
            """Update progress in database."""
            logger.debug(
                "[ChunkTestBackground] Progress callback invoked: test_id=%s, status=%s, "
                "method=%s, stage=%s, progress=%s%%, completed_methods=%s",
                test_id,
                status,
                method,
                stage,
                progress,
                completed_methods,
            )

            if is_cancelled(test_id):
                logger.info(
                    "[ChunkTestBackground] Test %s cancelled, stopping progress updates",
                    test_id,
                )
                return False

            try:
                result_row.status = status
                result_row.current_method = method
                result_row.current_stage = stage
                result_row.progress_percent = progress
                result_row.completed_methods = completed_methods
                sync_db.commit()
                logger.debug(
                    "[ChunkTestBackground] Progress updated successfully: test_id=%s, "
                    "status=%s, stage=%s, progress=%s%%",
                    test_id,
                    status,
                    stage,
                    progress,
                )
                return True
            except DATABASE_ERRORS as e:
                logger.error(
                    "[ChunkTestBackground] Failed to update progress for test %s: %s",
                    test_id,
                    e,
                    exc_info=True,
                )
                sync_db.rollback()
                return True

        if is_cancelled(test_id):
            logger.info(
                "[ChunkTestBackground] Test %s was cancelled before starting execution",
                test_id,
            )
            result_row.status = "failed"
            result_row.current_stage = "cancelled"
            sync_db.commit()
            return

        logger.info(
            "[ChunkTestBackground] Starting test execution: test_id=%s, document_ids=%s, queries_count=%s, modes=%s",
            test_id,
            document_ids,
            len(queries),
            modes,
        )

        try:
            results = asyncio.run(
                _run_user_documents_test_async(
                    user_id=user_id,
                    document_ids=document_ids,
                    queries=queries,
                    modes=modes,
                    progress_callback=progress_callback,
                )
            )

            logger.info(
                "[ChunkTestBackground] Test execution completed: test_id=%s, "
                "chunking_comparison_keys=%s, retrieval_comparison_keys=%s",
                test_id,
                list(results.get("chunking_comparison", {}).keys()),
                list(results.get("retrieval_comparison", {}).keys()),
            )

            if is_cancelled(test_id):
                logger.info(
                    "[ChunkTestBackground] Test %s was cancelled during execution",
                    test_id,
                )
                result_row.status = "failed"
                result_row.current_stage = "cancelled"
                sync_db.commit()
                return

            logger.debug(
                "[ChunkTestBackground] Updating test result with final data: test_id=%s",
                test_id,
            )
            result_row.status = "completed"
            result_row.current_stage = "completed"
            result_row.progress_percent = 100
            result_row.semchunk_chunk_count = results["chunking_comparison"].get("semchunk", {}).get("count", 0)
            result_row.mindchunk_chunk_count = results["chunking_comparison"].get("mindchunk", {}).get("count", 0)
            result_row.chunk_stats = results["chunking_comparison"]
            result_row.retrieval_metrics = results.get("retrieval_comparison", {})
            result_row.comparison_summary = results.get("summary", {})
            result_row.evaluation_results = results.get("evaluation_results", {})
            result_row.completed_methods = modes or [
                "spacy",
                "semchunk",
                "chonkie",
                "langchain",
                "mindchunk",
            ]
            sync_db.commit()

            logger.info(
                "[ChunkTestBackground] Test %s completed successfully: semchunk_chunks=%s, mindchunk_chunks=%s",
                test_id,
                result_row.semchunk_chunk_count,
                result_row.mindchunk_chunk_count,
            )
        except RuntimeError as e:
            if "cancelled" in str(e).lower() or is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                result_row.status = "failed"
                result_row.current_stage = "cancelled"
                sync_db.commit()
                return
            logger.error(
                "[ChunkTestBackground] RuntimeError during test execution for test %s: %s",
                test_id,
                e,
                exc_info=True,
            )
            raise
        except DATABASE_ERRORS as e:
            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                result_row.status = "failed"
                result_row.current_stage = "cancelled"
                sync_db.commit()
                return
            logger.error(
                "[ChunkTestBackground] Exception during test execution for test %s: %s",
                test_id,
                e,
                exc_info=True,
            )
            raise

    except DATABASE_ERRORS as e:
        logger.error(
            "[ChunkTestBackground] Background test failed for test %s: %s",
            test_id,
            e,
            exc_info=True,
        )
        try:
            if test_result is None and db is not None:
                test_result = db.execute(
                    select(ChunkTestResult).where(ChunkTestResult.id == test_id)
                ).scalar_one_or_none()
            if test_result is not None and db is not None:
                test_result.status = "failed"
                test_result.current_stage = "failed"
                db.commit()
                logger.info("[ChunkTestBackground] Marked test %s as failed", test_id)
        except DATABASE_ERRORS as update_error:
            logger.error(
                "[ChunkTestBackground] Failed to update failed status for test %s: %s",
                test_id,
                update_error,
                exc_info=True,
            )
            if db is not None:
                db.rollback()
    finally:
        logger.debug("[ChunkTestBackground] Cleaning up test %s", test_id)
        unregister_active_test(test_id)
        # Ensure database session is properly closed even on kill -9 scenarios
        if db is not None:
            try:
                # Rollback any uncommitted transactions
                db.rollback()
            except DATABASE_ERRORS as rollback_error:
                logger.debug(
                    "[ChunkTestBackground] Error rolling back transaction for test %s: %s",
                    test_id,
                    rollback_error,
                )
            try:
                # Close the session
                db.close()
            except DATABASE_ERRORS as close_error:
                logger.warning(
                    "[ChunkTestBackground] Error closing database session for test %s: %s",
                    test_id,
                    close_error,
                )
        reset_rls_context(rls_token)
        logger.info(
            "[ChunkTestBackground] Background test thread completed for test %s",
            test_id,
        )


def run_benchmark_in_background(
    test_id: int,
    user_id: int,
    dataset_name: str,
    queries: Optional[List[str]],
    modes: Optional[List[str]],
) -> None:
    """Run benchmark test in background thread and update progress."""
    logger.info(
        "[ChunkTestBackground] Starting background benchmark test execution: "
        "test_id=%s, user_id=%s, dataset_name=%s, queries_count=%s, modes=%s",
        test_id,
        user_id,
        dataset_name,
        len(queries) if queries else 0,
        modes,
    )
    register_active_test(test_id)

    db = None
    test_result = None

    rls_token = set_rls_context(RlsContext.for_celery_user(user_id))
    try:
        # Create database session with proper error handling
        db = SyncSessionLocal()
        logger.debug("[ChunkTestBackground] Querying test result %s from database", test_id)
        loaded = db.execute(select(ChunkTestResult).where(ChunkTestResult.id == test_id)).scalar_one_or_none()
        if not loaded:
            logger.error("[ChunkTestBackground] Test result %s not found in database", test_id)
            return

        test_result = loaded
        result_row: ChunkTestResult = test_result
        sync_db = db

        logger.info(
            "[ChunkTestBackground] Test result found: test_id=%s, current_status=%s, current_stage=%s, progress=%s%%",
            test_id,
            result_row.status,
            result_row.current_stage,
            result_row.progress_percent,
        )

        def progress_callback(status, method, stage, progress, completed_methods):
            """Update progress in database."""
            logger.debug(
                "[ChunkTestBackground] Progress callback invoked: test_id=%s, status=%s, "
                "method=%s, stage=%s, progress=%s%%, completed_methods=%s",
                test_id,
                status,
                method,
                stage,
                progress,
                completed_methods,
            )

            if is_cancelled(test_id):
                logger.info(
                    "[ChunkTestBackground] Test %s cancelled, stopping progress updates",
                    test_id,
                )
                return False

            try:
                result_row.status = status
                result_row.current_method = method
                result_row.current_stage = stage
                result_row.progress_percent = progress
                result_row.completed_methods = completed_methods
                sync_db.commit()
                logger.debug(
                    "[ChunkTestBackground] Progress updated successfully: test_id=%s, "
                    "status=%s, stage=%s, progress=%s%%",
                    test_id,
                    status,
                    stage,
                    progress,
                )
                return True
            except DATABASE_ERRORS as e:
                logger.error(
                    "[ChunkTestBackground] Failed to update progress for test %s: %s",
                    test_id,
                    e,
                    exc_info=True,
                )
                sync_db.rollback()
                return True

        if is_cancelled(test_id):
            logger.info(
                "[ChunkTestBackground] Test %s was cancelled before starting execution",
                test_id,
            )
            result_row.status = "failed"
            result_row.current_stage = "cancelled"
            sync_db.commit()
            return

        logger.info(
            "[ChunkTestBackground] Starting benchmark test execution: test_id=%s, "
            "dataset_name=%s, queries_count=%s, modes=%s",
            test_id,
            dataset_name,
            len(queries) if queries else 0,
            modes,
        )

        try:
            results = asyncio.run(
                _run_benchmark_test_async(
                    user_id=user_id,
                    dataset_name=dataset_name,
                    queries=queries,
                    modes=modes,
                    progress_callback=progress_callback,
                )
            )

            logger.info(
                "[ChunkTestBackground] Benchmark test execution completed: test_id=%s, "
                "chunking_comparison_keys=%s, retrieval_comparison_keys=%s",
                test_id,
                list(results.get("chunking_comparison", {}).keys()),
                list(results.get("retrieval_comparison", {}).keys()),
            )

            if is_cancelled(test_id):
                logger.info(
                    "[ChunkTestBackground] Test %s was cancelled during execution",
                    test_id,
                )
                result_row.status = "failed"
                result_row.current_stage = "cancelled"
                sync_db.commit()
                return

            logger.debug(
                "[ChunkTestBackground] Updating test result with final data: test_id=%s",
                test_id,
            )
            result_row.status = "completed"
            result_row.current_stage = "completed"
            result_row.progress_percent = 100
            result_row.semchunk_chunk_count = results["chunking_comparison"].get("semchunk", {}).get("count", 0)
            result_row.mindchunk_chunk_count = results["chunking_comparison"].get("mindchunk", {}).get("count", 0)
            result_row.chunk_stats = results["chunking_comparison"]
            result_row.retrieval_metrics = results.get("retrieval_comparison", {})
            result_row.comparison_summary = results.get("summary", {})
            result_row.evaluation_results = results.get("evaluation_results", {})
            result_row.completed_methods = modes or [
                "spacy",
                "semchunk",
                "chonkie",
                "langchain",
                "mindchunk",
            ]
            sync_db.commit()

            logger.info(
                "[ChunkTestBackground] Benchmark test %s completed successfully: "
                "semchunk_chunks=%s, mindchunk_chunks=%s",
                test_id,
                result_row.semchunk_chunk_count,
                result_row.mindchunk_chunk_count,
            )
        except RuntimeError as e:
            if "cancelled" in str(e).lower() or is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                result_row.status = "failed"
                result_row.current_stage = "cancelled"
                sync_db.commit()
                return
            logger.error(
                "[ChunkTestBackground] RuntimeError during benchmark test execution for test %s: %s",
                test_id,
                e,
                exc_info=True,
            )
            raise
        except DATABASE_ERRORS as e:
            if is_cancelled(test_id):
                logger.info("[ChunkTestBackground] Test %s cancelled: %s", test_id, e)
                result_row.status = "failed"
                result_row.current_stage = "cancelled"
                sync_db.commit()
                return
            logger.error(
                "[ChunkTestBackground] Exception during benchmark test execution for test %s: %s",
                test_id,
                e,
                exc_info=True,
            )
            raise

    except DATABASE_ERRORS as e:
        logger.error(
            "[ChunkTestBackground] Background benchmark test failed for test %s: %s",
            test_id,
            e,
            exc_info=True,
        )
        try:
            if test_result is None and db is not None:
                test_result = db.execute(
                    select(ChunkTestResult).where(ChunkTestResult.id == test_id)
                ).scalar_one_or_none()
            if test_result is not None and db is not None:
                test_result.status = "failed"
                test_result.current_stage = "failed"
                db.commit()
                logger.info("[ChunkTestBackground] Marked test %s as failed", test_id)
        except DATABASE_ERRORS as update_error:
            logger.error(
                "[ChunkTestBackground] Failed to update failed status for test %s: %s",
                test_id,
                update_error,
                exc_info=True,
            )
            if db is not None:
                db.rollback()
    finally:
        logger.debug("[ChunkTestBackground] Cleaning up test %s", test_id)
        unregister_active_test(test_id)
        # Ensure database session is properly closed even on kill -9 scenarios
        if db is not None:
            try:
                # Rollback any uncommitted transactions
                db.rollback()
            except DATABASE_ERRORS as rollback_error:
                logger.debug(
                    "[ChunkTestBackground] Error rolling back transaction for test %s: %s",
                    test_id,
                    rollback_error,
                )
            try:
                # Close the session
                db.close()
            except DATABASE_ERRORS as close_error:
                logger.warning(
                    "[ChunkTestBackground] Error closing database session for test %s: %s",
                    test_id,
                    close_error,
                )
        reset_rls_context(rls_token)
        logger.info(
            "[ChunkTestBackground] Background benchmark test thread completed for test %s",
            test_id,
        )
