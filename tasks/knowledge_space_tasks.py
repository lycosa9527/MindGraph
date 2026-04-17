"""Knowledge Space Background Tasks.

Celery tasks for async document processing.
Requires Qdrant server mode (QDRANT_HOST) for multi-process support.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import traceback
from typing import List

from celery import group
from sqlalchemy import select

from config.celery import celery_app
from config.database import AsyncSessionLocal, SyncSessionLocal
from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument
from services.knowledge.knowledge_space_service import KnowledgeSpaceService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async helpers (called via asyncio.run from Celery tasks)
# ---------------------------------------------------------------------------


async def _process_document_async(user_id: int, document_id: int) -> None:
    """Run document processing in an async context."""
    async with AsyncSessionLocal() as db:
        service = KnowledgeSpaceService(db, user_id)

        doc = await service.get_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        logger.info(
            "[KnowledgeSpaceTask] Document found: file='%s', status=%s",
            doc.file_name,
            doc.status,
        )

        await service.process_document(document_id)

        result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        chunk_count = (doc.chunk_count or 0) if doc else 0

        logger.info(
            "[KnowledgeSpaceTask] ✓ Document processing complete: document_id=%s, chunk_count=%s, status=%s",
            document_id,
            chunk_count,
            doc.status if doc else "unknown",
        )

        if chunk_count == 0:
            logger.error(
                "[KnowledgeSpaceTask] ⚠ WARNING: Document %s processed but chunk_count is 0!",
                document_id,
            )
            if doc:
                logger.error(
                    "[KnowledgeSpaceTask] Document status: %s, progress: %s",
                    doc.status,
                    doc.processing_progress,
                )


async def _mark_document_failed_async(document_id: int, error: Exception) -> None:
    """Mark a document as failed in the database."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if doc and doc.status != "failed":
            doc.status = "failed"
            doc.error_message = str(error)
            doc.processing_progress = None
            doc.processing_progress_percent = 0
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                raise
            logger.info(
                "[KnowledgeSpaceTask] Updated document %s status to 'failed'",
                document_id,
            )


async def _update_batch_progress_async(user_id: int, batch_id: int, completed: int, failed: int) -> None:
    """Update batch completion progress via async session."""
    async with AsyncSessionLocal() as db:
        service = KnowledgeSpaceService(db, user_id)
        await service.update_batch_progress(batch_id, completed=completed, failed=failed)


async def _update_document_async(user_id: int, document_id: int) -> None:
    """Check updated document status in async context."""
    async with AsyncSessionLocal() as db:
        service = KnowledgeSpaceService(db, user_id)
        document = await service.get_document(document_id)
        if document and document.status == "processing":
            logger.info(
                "[KnowledgeSpaceTask] Document %s update completed for user %s",
                document_id,
                user_id,
            )
        else:
            logger.warning(
                "[KnowledgeSpaceTask] Document %s not in processing state for user %s",
                document_id,
                user_id,
            )


# ---------------------------------------------------------------------------
# Sync helpers (called directly from Celery tasks — no event loop needed)
# ---------------------------------------------------------------------------


def _start_batch_sync(batch_id: int, user_id: int) -> List[int]:
    """Mark batch as processing and return the list of document IDs.

    This is a plain synchronous function so it can safely be called from a
    Celery task without blocking an asyncio event loop.
    """
    with SyncSessionLocal() as db:
        batch = db.execute(
            select(DocumentBatch).where(
                DocumentBatch.id == batch_id,
                DocumentBatch.user_id == user_id,
            )
        ).scalar_one_or_none()
        if not batch:
            logger.error("[KnowledgeSpaceTask] Batch %s not found for user %s", batch_id, user_id)
            return []

        batch.status = "processing"
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        documents = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.batch_id == batch_id)).scalars().all()
        return [doc.id for doc in documents]


def _mark_batch_failed_sync(user_id: int, batch_id: int, error: Exception) -> None:
    """Mark a batch as failed.  Plain sync — safe to call from a Celery task."""
    with SyncSessionLocal() as db:
        try:
            batch = db.execute(
                select(DocumentBatch).where(
                    DocumentBatch.id == batch_id,
                    DocumentBatch.user_id == user_id,
                )
            ).scalar_one_or_none()
            if batch:
                batch.status = "failed"
                batch.error_message = str(error)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
        except Exception as update_error:
            logger.error("[KnowledgeSpaceTask] Failed to update batch status: %s", update_error)


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@celery_app.task(name="knowledge_space.process_document", bind=True, max_retries=3)
def process_document_task(self, user_id: int, document_id: int):
    """
    Process document in background.

    Args:
        user_id: User ID
        document_id: Document ID
    """
    logger.info(
        "[KnowledgeSpaceTask] ===== Starting document processing: document_id=%s, user_id=%s =====",
        document_id,
        user_id,
    )
    try:
        asyncio.run(_process_document_async(user_id, document_id))
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceTask] ✗ Failed to process document %s for user %s: %s",
            document_id,
            user_id,
            e,
        )
        logger.error("[KnowledgeSpaceTask] Full traceback:")
        logger.error(traceback.format_exc())
        logger.error("[KnowledgeSpaceTask] Exception type: %s", type(e).__name__)
        logger.error("[KnowledgeSpaceTask] Exception args: %s", e.args)

        try:
            asyncio.run(_mark_document_failed_async(document_id, e))
        except Exception as update_error:
            logger.error(
                "[KnowledgeSpaceTask] Failed to update document status: %s",
                update_error,
                exc_info=True,
            )

        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))
    finally:
        logger.info(
            "[KnowledgeSpaceTask] ===== Finished processing document %s =====",
            document_id,
        )


@celery_app.task(name="knowledge_space.update_document", bind=True, max_retries=3)
def update_document_task(self, user_id: int, document_id: int):
    """
    Update document in background (reindexing).

    Args:
        user_id: User ID
        document_id: Document ID
    """
    try:
        asyncio.run(_update_document_async(user_id, document_id))
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceTask] Failed to update document %s for user %s: %s",
            document_id,
            user_id,
            e,
        )
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))


@celery_app.task(name="knowledge_space.batch_process_documents", bind=True, max_retries=3)
def batch_process_documents_task(self, user_id: int, batch_id: int):
    """
    Process all documents in a batch concurrently.

    Args:
        user_id: User ID
        batch_id: Batch ID
    """
    try:
        # Sync DB work: mark batch as processing and collect document IDs.
        doc_ids = _start_batch_sync(batch_id, user_id)
        if not doc_ids:
            return

        job = group(process_document_task.s(user_id, doc_id) for doc_id in doc_ids)
        result = job.apply_async()

        completed = 0
        failed = 0

        for task_result in result:
            try:
                task_result.get(timeout=3600)
                completed += 1
            except Exception as e:
                logger.error(
                    "[KnowledgeSpaceTask] Document processing failed in batch %s: %s",
                    batch_id,
                    e,
                )
                failed += 1

        asyncio.run(_update_batch_progress_async(user_id, batch_id, completed=completed, failed=failed))

        logger.info(
            "[KnowledgeSpaceTask] Batch %s completed: %s succeeded, %s failed",
            batch_id,
            completed,
            failed,
        )
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceTask] Failed to process batch %s for user %s: %s",
            batch_id,
            user_id,
            e,
        )
        _mark_batch_failed_sync(user_id, batch_id, e)
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))
