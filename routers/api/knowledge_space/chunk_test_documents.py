"""
Chunk test document management endpoints.

Handles document upload, listing, deletion, and processing.
"""

import asyncio
import logging
import os
import tempfile
import threading

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from config.database import AsyncSessionLocal, get_async_db
from models.domain.auth import User
from models.domain.knowledge_space import ChunkTestDocument, ChunkTestDocumentChunk
from models.requests.requests_knowledge_space import ProcessSelectedRequest
from models.responses import DocumentResponse, DocumentListResponse
from routers.api.knowledge_space.chunk_test_utils import check_feature_enabled
from services.knowledge.chunk_test_document_service import ChunkTestDocumentService
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_CONCURRENT_DOC_THREADS = int(os.getenv("CHUNK_TEST_DOC_MAX_THREADS", "5"))
_doc_processing_sem = threading.Semaphore(_MAX_CONCURRENT_DOC_THREADS)


async def _run_process_document(user_id: int, document_id: int) -> None:
    """Run document processing using the async session and service."""
    async with AsyncSessionLocal() as db:
        service = ChunkTestDocumentService(db, user_id)
        await service.process_document(document_id)


async def _mark_document_failed(user_id: int, document_id: int, error: Exception) -> None:
    """Mark a chunk-test document as failed via an independent async session."""
    async with AsyncSessionLocal() as db:
        doc = await db.get(ChunkTestDocument, document_id)
        if doc and doc.user_id == user_id and doc.status == "processing":
            doc.status = "failed"
            doc.error_message = str(error)
            doc.processing_progress = "failed"
            doc.processing_progress_percent = 0
            try:
                await db.commit()
            except Exception as commit_err:
                await db.rollback()
                logger.debug(
                    "[ChunkTestDocuments] Rollback during failure mark for document %s: %s",
                    document_id,
                    commit_err,
                )


def _process_chunk_test_document(user_id: int, document_id: int) -> None:
    """Background thread function that processes a chunk test document.

    Uses ``asyncio.run`` so the async ``ChunkTestDocumentService.process_document``
    coroutine executes properly inside a dedicated event loop for this thread.
    A bounded semaphore caps the number of threads that run concurrently.
    """
    logger.info(
        "[ChunkTestDocuments] Starting background processing for document %s (user %s)",
        document_id,
        user_id,
    )
    with _doc_processing_sem:
        try:
            asyncio.run(_run_process_document(user_id, document_id))
            logger.info(
                "[ChunkTestDocuments] Successfully completed processing document %s",
                document_id,
            )
        except Exception as e:
            logger.error(
                "[ChunkTestDocuments] Background processing failed for document %s: %s",
                document_id,
                e,
                exc_info=True,
            )
            try:
                asyncio.run(_mark_document_failed(user_id, document_id, e))
                logger.info(
                    "[ChunkTestDocuments] Marked document %s as failed due to processing error",
                    document_id,
                )
            except Exception as update_error:
                logger.error(
                    "[ChunkTestDocuments] Failed to update document %s status to failed: %s",
                    document_id,
                    update_error,
                    exc_info=True,
                )


@router.post("/chunk-test/documents/upload", response_model=DocumentResponse)
async def upload_chunk_test_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Upload a document for chunk testing.

    Requires authentication. Max 5 documents per user.
    Documents are separate from knowledge space documents.
    """
    check_feature_enabled()
    service = ChunkTestDocumentService(db, current_user.id)

    tmp_path: "str | None" = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        file_type = service.processor.get_file_type(file.filename)

        document = await service.upload_document(
            file_name=file.filename,
            file_path=tmp_path,
            file_type=file_type,
            file_size=len(content),
        )

        return DocumentResponse(
            id=document.id,
            file_name=document.file_name,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            chunk_count=document.chunk_count,
            error_message=document.error_message,
            processing_progress=document.processing_progress,
            processing_progress_percent=document.processing_progress_percent or 0,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("[ChunkTestDocuments] Upload failed for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Upload failed") from e
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as unlink_err:
                logger.debug(
                    "[ChunkTestDocuments] Could not remove temp file %s: %s",
                    tmp_path,
                    unlink_err,
                )


@router.get("/chunk-test/documents", response_model=DocumentListResponse)
async def list_chunk_test_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all chunk test documents for the user.

    Requires authentication. Automatically filters by user.
    """
    check_feature_enabled()
    service = ChunkTestDocumentService(db, current_user.id)
    documents = await service.get_user_documents()

    status_counts = {}
    for doc in documents:
        status_counts[doc.status] = status_counts.get(doc.status, 0) + 1
    logger.debug(
        "[ChunkTestDocuments] Listing documents for user %s: %s (statuses: %s)",
        current_user.id,
        len(documents),
        status_counts,
    )

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                file_name=doc.file_name,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=doc.status,
                chunk_count=doc.chunk_count,
                error_message=doc.error_message,
                processing_progress=doc.processing_progress,
                processing_progress_percent=doc.processing_progress_percent or 0,
                created_at=doc.created_at.isoformat(),
                updated_at=doc.updated_at.isoformat(),
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.delete("/chunk-test/documents/{document_id}")
async def delete_chunk_test_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a chunk test document and all associated data.

    Requires authentication. Verifies ownership.
    """
    check_feature_enabled()
    service = ChunkTestDocumentService(db, current_user.id)

    try:
        await service.delete_document(document_id)
        return {"message": "Document deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[ChunkTestDocuments] Delete failed for user %s, document %s: %s",
            current_user.id,
            document_id,
            e,
        )
        raise HTTPException(status_code=500, detail="Delete failed") from e


@router.post("/chunk-test/documents/start-processing")
async def start_processing_chunk_test_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Manually trigger processing for all pending chunk test documents.

    Requires authentication. Processes all documents with status 'pending' or 'failed'.
    """
    check_feature_enabled()
    service = ChunkTestDocumentService(db, current_user.id)
    documents = await service.get_user_documents()

    pending_docs = [doc for doc in documents if doc.status in ("pending", "failed")]

    if not pending_docs:
        return {"message": "No pending documents to process", "processed_count": 0}

    processed_count = 0
    logger.info(
        "[ChunkTestDocuments] Found %d pending documents to process for user %s",
        len(pending_docs),
        current_user.id,
    )
    for doc in pending_docs:
        try:
            doc.status = "processing"
            doc.processing_progress = "queued"
            doc.processing_progress_percent = 0
            await db.commit()

            logger.info(
                "[ChunkTestDocuments] Starting background thread for document %s (user %s)",
                doc.id,
                current_user.id,
            )
            thread = threading.Thread(
                target=_process_chunk_test_document,
                args=(current_user.id, doc.id),
                daemon=False,
                name=f"ChunkTestDocProcess-{doc.id}",
            )
            thread.start()
            logger.info(
                "[ChunkTestDocuments] Background thread started for document %s (thread: %s)",
                doc.id,
                thread.name,
            )
            processed_count += 1
        except Exception as e:
            logger.error(
                "[ChunkTestDocuments] Failed to start processing document %s: %s",
                doc.id,
                e,
            )

    return {
        "message": f"Started processing {processed_count} document(s)",
        "processed_count": processed_count,
    }


@router.post("/chunk-test/documents/process-selected")
async def process_selected_chunk_test_documents(
    request: ProcessSelectedRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Process selected chunk test documents by their IDs.

    Requires authentication. Verifies ownership. Only processes documents with
    status 'pending' or 'failed'.
    """
    service = ChunkTestDocumentService(db, current_user.id)
    documents = await service.get_user_documents()

    user_doc_ids = {doc.id for doc in documents}
    valid_ids = [doc_id for doc_id in request.document_ids if doc_id in user_doc_ids]

    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid documents to process")

    docs_to_process = [doc for doc in documents if doc.id in valid_ids and doc.status in ("pending", "failed")]

    if not docs_to_process:
        return {"message": "No pending documents in selection", "processed_count": 0}

    processed_count = 0
    logger.info(
        "[ChunkTestDocuments] Processing %d selected documents for user %s",
        len(docs_to_process),
        current_user.id,
    )
    for doc in docs_to_process:
        try:
            doc.status = "processing"
            doc.processing_progress = "queued"
            doc.processing_progress_percent = 0
            await db.commit()

            logger.info(
                "[ChunkTestDocuments] Starting background thread for selected document %s (user %s)",
                doc.id,
                current_user.id,
            )
            thread = threading.Thread(
                target=_process_chunk_test_document,
                args=(current_user.id, doc.id),
                daemon=False,
                name=f"ChunkTestDocProcess-{doc.id}",
            )
            thread.start()
            logger.info(
                "[ChunkTestDocuments] Background thread started for document %s (thread: %s)",
                doc.id,
                thread.name,
            )
            processed_count += 1
        except Exception as e:
            logger.error(
                "[ChunkTestDocuments] Failed to start processing document %s: %s",
                doc.id,
                e,
            )

    return {
        "message": f"Started processing {processed_count} document(s)",
        "processed_count": processed_count,
    }


@router.get("/chunk-test/documents/{document_id}/chunks")
async def get_chunk_test_document_chunks(
    document_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get chunks for a chunk test document with pagination.

    Requires authentication. Verifies ownership.
    """
    check_feature_enabled()
    service = ChunkTestDocumentService(db, current_user.id)
    document = await service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    offset = (page - 1) * page_size
    result = await db.execute(
        select(ChunkTestDocumentChunk)
        .where(ChunkTestDocumentChunk.document_id == document_id)
        .order_by(ChunkTestDocumentChunk.chunk_index)
        .offset(offset)
        .limit(page_size)
    )
    chunks = result.scalars().all()

    count_result = await db.execute(
        select(sa_count()).select_from(ChunkTestDocumentChunk).where(ChunkTestDocumentChunk.document_id == document_id)
    )
    total = count_result.scalar_one()

    return {
        "document_id": document_id,
        "file_name": document.file_name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "metadata": chunk.meta_data,
            }
            for chunk in chunks
        ],
    }
