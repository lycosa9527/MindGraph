"""
Knowledge Space Documents Router
=================================

Document CRUD operations and processing endpoints.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import tempfile
from typing import List

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.knowledge_space import DocumentBatch, DocumentChunk
from models.requests.requests_knowledge_space import ProcessSelectedRequest
from models.responses import DocumentResponse, DocumentListResponse, BatchResponse
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from tasks.knowledge_space_tasks import (
    process_document_task,
    batch_process_documents_task,
    update_document_task
)
from utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a document to user's knowledge space.

    Requires authentication. Max 5 documents per user.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Get file type
        file_type = service.processor.get_file_type(file.filename)

        # Upload document
        document = service.upload_document(
            file_name=file.filename,
            file_path=tmp_path,
            file_type=file_type,
            file_size=len(content)
        )

        # Note: Processing must be triggered manually via /documents/start-processing
        # or /documents/process-selected endpoints

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
            updated_at=document.updated_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Upload failed for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(status_code=500, detail="Upload failed") from e


@router.post("/documents/batch-upload")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload multiple documents in a batch.

    Requires authentication. Processes documents concurrently.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    try:
        # Save uploaded files temporarily
        file_infos = []
        tmp_paths = []

        for file in files:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                tmp_path = tmp_file.name
                tmp_paths.append(tmp_path)

            file_type = service.processor.get_file_type(file.filename)
            file_infos.append({
                'file_name': file.filename,
                'file_path': tmp_path,
                'file_type': file_type,
                'file_size': len(content)
            })

        # Upload batch
        batch = service.batch_upload_documents(file_infos)

        # Trigger background batch processing
        batch_process_documents_task.delay(current_user.id, batch.id)

        return BatchResponse(
            batch_id=batch.id,
            status=batch.status,
            total_count=batch.total_count,
            completed_count=batch.completed_count,
            failed_count=batch.failed_count,
            created_at=batch.created_at.isoformat(),
            updated_at=batch.updated_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Batch upload failed for user %s: %s",
            current_user.id,
            e
        )
        raise HTTPException(status_code=500, detail="Batch upload failed") from e


@router.get("/batches/{batch_id}")
async def get_batch_status(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get batch processing status.

    Requires authentication. Verifies ownership.
    """
    batch = db.query(DocumentBatch).filter(
        DocumentBatch.id == batch_id,
        DocumentBatch.user_id == current_user.id
    ).first()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    return BatchResponse(
        batch_id=batch.id,
        status=batch.status,
        total_count=batch.total_count,
        completed_count=batch.completed_count,
        failed_count=batch.failed_count,
        created_at=batch.created_at.isoformat(),
        updated_at=batch.updated_at.isoformat()
    )


@router.get("/documents")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all documents in user's knowledge space.

    Requires authentication. Automatically filters by user.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    documents = service.get_user_documents()

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
                updated_at=doc.updated_at.isoformat()
            )
            for doc in documents
        ],
        total=len(documents)
    )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get document details.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        file_name=document.file_name,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        chunk_count=document.chunk_count,
        error_message=document.error_message,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat()
    )


@router.put("/documents/{document_id}")
async def update_document(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a document with new file content.

    Supports partial reindexing - only changed chunks are reindexed.
    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Update document (triggers background reindexing)
        document = service.update_document(
            document_id=document_id,
            file_path=tmp_path,
            file_name=file.filename
        )

        # Trigger background update task
        update_document_task.delay(current_user.id, document.id)

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
            updated_at=document.updated_at.isoformat()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Update failed for user %s, document %s: %s",
            current_user.id,
            document_id,
            e
        )
        raise HTTPException(status_code=500, detail="Update failed") from e


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document and all associated data.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)

    try:
        service.delete_document(document_id)
        return {"message": "Document deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(
            "[KnowledgeSpaceAPI] Delete failed for user %s, document %s: %s",
            current_user.id,
            document_id,
            e
        )
        raise HTTPException(status_code=500, detail="Delete failed") from e


@router.get("/documents/{document_id}/status")
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get document processing status.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "status": document.status,
        "chunk_count": document.chunk_count,
        "error_message": document.error_message,
        "processing_task_id": document.processing_task_id,
        "processing_progress": document.processing_progress,
        "processing_progress_percent": document.processing_progress_percent
    }


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chunks for a document with pagination.

    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = service.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get chunks with pagination
    offset = (page - 1) * page_size
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index).offset(offset).limit(page_size).all()

    total = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).count()

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
                "metadata": chunk.meta_data
            }
            for chunk in chunks
        ]
    }


@router.post("/documents/start-processing")
async def start_processing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger processing for all pending documents in user's knowledge space.

    Requires authentication. Processes all documents with status 'pending' or 'failed'.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    documents = service.get_user_documents()

    pending_docs = [doc for doc in documents if doc.status in ('pending', 'failed')]

    if not pending_docs:
        return {
            "message": "No pending documents to process",
            "processed_count": 0
        }

    processed_count = 0
    for doc in pending_docs:
        try:
            # Update status to 'processing' immediately so frontend can show progress
            doc.status = 'processing'
            doc.processing_progress = 'queued'
            doc.processing_progress_percent = 0
            db.commit()

            # Trigger background processing
            process_document_task.delay(current_user.id, doc.id)
            processed_count += 1
        except Exception as e:
            logger.error(
                "[KnowledgeSpaceAPI] Failed to start processing document %s: %s",
                doc.id,
                e
            )

    return {
        "message": f"Started processing {processed_count} document(s)",
        "processed_count": processed_count
    }


@router.post("/documents/process-selected")
async def process_selected_documents(
    request: ProcessSelectedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process selected documents by their IDs.

    Requires authentication. Verifies ownership. Only processes documents with
    status 'pending' or 'failed'.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    documents = service.get_user_documents()

    # Filter to only user's documents that are pending/failed and in the selected list
    user_doc_ids = {doc.id for doc in documents}
    valid_ids = [doc_id for doc_id in request.document_ids if doc_id in user_doc_ids]

    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid documents to process")

    # Get documents that can be processed (pending or failed status)
    docs_to_process = [
        doc for doc in documents
        if doc.id in valid_ids and doc.status in ('pending', 'failed')
    ]

    if not docs_to_process:
        return {
            "message": "No pending documents in selection",
            "processed_count": 0
        }

    processed_count = 0
    for doc in docs_to_process:
        try:
            # Update status to 'processing' immediately so frontend can show progress
            doc.status = 'processing'
            doc.processing_progress = 'queued'
            doc.processing_progress_percent = 0
            db.commit()

            # Trigger background processing
            process_document_task.delay(current_user.id, doc.id)
            processed_count += 1
        except Exception as e:
            logger.error(
                "[KnowledgeSpaceAPI] Failed to start processing document %s: %s",
                doc.id,
                e
            )

    return {
        "message": f"Started processing {processed_count} document(s)",
        "processed_count": processed_count
    }
