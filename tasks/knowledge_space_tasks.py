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

from celery import group
from sqlalchemy import select

from config.celery import celery_app
from config.database import AsyncSessionLocal, SyncSessionLocal
from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument
from services.knowledge.knowledge_space_service import KnowledgeSpaceService

logger = logging.getLogger(__name__)


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
            await db.commit()
            logger.info(
                "[KnowledgeSpaceTask] Updated document %s status to 'failed'",
                document_id,
            )


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


async def _batch_process_async(user_id: int, batch_id: int) -> None:
    """Dispatch and track a batch of document processing tasks."""
    db_sync = SyncSessionLocal()
    try:
        batch = (
            db_sync.query(DocumentBatch).filter(DocumentBatch.id == batch_id, DocumentBatch.user_id == user_id).first()
        )

        if not batch:
            logger.error("[KnowledgeSpaceTask] Batch %s not found for user %s", batch_id, user_id)
            return

        batch.status = "processing"
        db_sync.commit()

        documents = db_sync.query(KnowledgeDocument).filter(KnowledgeDocument.batch_id == batch_id).all()
        doc_ids = [doc.id for doc in documents]
    finally:
        db_sync.close()

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

    async with AsyncSessionLocal() as db:
        service = KnowledgeSpaceService(db, user_id)
        await service.update_batch_progress(batch_id, completed=completed, failed=failed)

    logger.info(
        "[KnowledgeSpaceTask] Batch %s completed: %s succeeded, %s failed",
        batch_id,
        completed,
        failed,
    )


async def _mark_batch_failed_async(user_id: int, batch_id: int, error: Exception) -> None:
    """Mark a batch as failed in the database."""
    db_sync = SyncSessionLocal()
    try:
        batch = (
            db_sync.query(DocumentBatch).filter(DocumentBatch.id == batch_id, DocumentBatch.user_id == user_id).first()
        )
        if batch:
            batch.status = "failed"
            batch.error_message = str(error)
            db_sync.commit()
    except Exception as update_error:
        logger.error("[KnowledgeSpaceTask] Failed to update batch status: %s", update_error)
    finally:
        db_sync.close()


@celery_app.task(name="knowledge_space.batch_process_documents", bind=True, max_retries=3)
def batch_process_documents_task(self, user_id: int, batch_id: int):
    """
    Process all documents in a batch concurrently.

    Args:
        user_id: User ID
        batch_id: Batch ID
    """
    try:
        asyncio.run(_batch_process_async(user_id, batch_id))
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceTask] Failed to process batch %s for user %s: %s",
            batch_id,
            user_id,
            e,
        )
        asyncio.run(_mark_batch_failed_async(user_id, batch_id, e))
        raise self.retry(exc=e, countdown=60 * (2**self.request.retries))
