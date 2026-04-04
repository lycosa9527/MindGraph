"""Document batch operations helper functions.

Extracted from knowledge_space_service.py to reduce complexity.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import KnowledgeDocument, DocumentBatch


logger = logging.getLogger(__name__)


async def batch_upload_documents(
    db: AsyncSession,
    user_id: int,
    space_id: int,
    files: List[Dict[str, Any]],
    storage_dir: Path,
    max_file_size: int,
    processor,
) -> DocumentBatch:
    """
    Upload multiple documents in a batch.

    Args:
        db: Async database session
        user_id: User ID
        space_id: Knowledge space ID
        files: List of dicts with keys: file_name, file_path, file_type, file_size
        storage_dir: Storage directory path
        max_file_size: Maximum file size in bytes
        processor: Document processor instance

    Returns:
        DocumentBatch instance
    """
    if not files:
        raise ValueError("No files provided for batch upload")

    for file_info in files:
        file_size = file_info.get("file_size", 0)
        file_type = file_info.get("file_type", "")

        if file_size > max_file_size:
            raise ValueError(
                f"File '{file_info.get('file_name', 'unknown')}' size ({file_size} bytes) "
                f"exceeds maximum ({max_file_size} bytes)"
            )

        if not processor.is_supported(file_type):
            file_name = file_info.get("file_name", "unknown")
            raise ValueError(f"Unsupported file type: {file_type} for file '{file_name}'")

    result = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.space_id == space_id))
    existing_filenames = {doc.file_name for doc in result.scalars().all()}

    for file_info in files:
        file_name = file_info.get("file_name", "")
        if file_name in existing_filenames:
            raise ValueError(f"Document with name '{file_name}' already exists")

    batch = DocumentBatch(
        user_id=user_id,
        status="pending",
        total_count=len(files),
        completed_count=0,
        failed_count=0,
    )
    db.add(batch)
    try:
        await db.commit()
        await db.refresh(batch)
    except Exception:
        await db.rollback()
        raise

    user_dir = storage_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    documents = []
    for file_info in files:
        file_name = file_info["file_name"]
        file_path = file_info["file_path"]
        file_type = file_info["file_type"]
        file_size = file_info["file_size"]

        document = KnowledgeDocument(
            space_id=space_id,
            file_name=file_name,
            file_path=str(user_dir / file_name),
            file_type=file_type,
            file_size=file_size,
            status="pending",
            batch_id=batch.id,
        )
        db.add(document)
        await db.flush()

        final_path = user_dir / f"{document.id}_{file_name}"
        shutil.move(file_path, final_path)
        document.file_path = str(final_path)
        documents.append(document)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info(
        "[KnowledgeSpace] Created batch %s with %s documents for user %s",
        batch.id,
        len(documents),
        user_id,
    )
    return batch


async def update_batch_progress(
    db: AsyncSession, user_id: int, batch_id: int, completed: int = 0, failed: int = 0
) -> None:
    """
    Update batch processing progress.

    Args:
        db: Async database session
        user_id: User ID
        batch_id: Batch ID
        completed: Number of completed documents (increment)
        failed: Number of failed documents (increment)
    """
    await db.execute(
        update(DocumentBatch)
        .where(DocumentBatch.id == batch_id, DocumentBatch.user_id == user_id)
        .values(
            completed_count=DocumentBatch.completed_count + completed,
            failed_count=DocumentBatch.failed_count + failed,
        )
    )
    await db.flush()

    result = await db.execute(
        select(DocumentBatch).where(DocumentBatch.id == batch_id, DocumentBatch.user_id == user_id)
    )
    batch = result.scalars().first()

    if not batch:
        logger.warning("[KnowledgeSpace] Batch %s not found for user %s", batch_id, user_id)
        return

    processed = batch.completed_count + batch.failed_count
    if processed >= batch.total_count:
        batch.status = "failed" if batch.completed_count == 0 else "completed"
    else:
        batch.status = "processing"

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
