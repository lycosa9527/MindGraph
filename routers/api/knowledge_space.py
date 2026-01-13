"""
Knowledge Space API Router
Author: lycosa9527
Made by: MindSpring Team

API endpoints for Personal Knowledge Space feature.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import tempfile
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from models.auth import User
from utils.auth import get_current_user
from config.database import get_db
from services.knowledge_space_service import KnowledgeSpaceService
from tasks.knowledge_space_tasks import process_document_task, update_document_task, batch_process_documents_task
from models.knowledge_space import DocumentBatch, DocumentVersion, QueryFeedback, QueryTemplate, DocumentRelationship, EvaluationDataset, EvaluationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-space", tags=["knowledge-space"])


# Request/Response Models
class DocumentResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    processing_progress: Optional[str] = None
    processing_progress_percent: int = 0
    created_at: str
    updated_at: str


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class RetrievalTestRequest(BaseModel):
    query: str = Field(..., max_length=250)
    method: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=10)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class RetrievalTestResult(BaseModel):
    chunk_id: int
    text: str
    score: float
    document_id: int
    document_name: str
    chunk_index: int


class RetrievalTestResponse(BaseModel):
    query: str
    method: str
    results: List[RetrievalTestResult]
    timing: dict
    stats: dict


class RetrievalTestHistoryItem(BaseModel):
    id: int
    query: str
    method: str
    top_k: int
    score_threshold: float
    result_count: int
    timing: dict
    created_at: str


class RetrievalTestHistoryResponse(BaseModel):
    queries: List[RetrievalTestHistoryItem]
    total: int


class CompressionMetricsResponse(BaseModel):
    compression_enabled: bool
    compression_type: Optional[str]
    points_count: int
    vector_size: int
    estimated_uncompressed_size: float
    estimated_compressed_size: float
    compression_ratio: float
    storage_savings_percent: float
    error: Optional[str] = None


class BatchResponse(BaseModel):
    batch_id: int
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    created_at: str
    updated_at: str


class MetadataUpdateRequest(BaseModel):
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class VersionResponse(BaseModel):
    id: int
    document_id: int
    version_number: int
    chunk_count: int
    change_summary: Optional[Dict[str, Any]] = None
    created_at: str


class VersionListResponse(BaseModel):
    versions: List[VersionResponse]
    total: int


class RollbackRequest(BaseModel):
    version_number: int


class ProcessSelectedRequest(BaseModel):
    document_ids: List[int] = Field(..., min_length=1)


class QueryFeedbackRequest(BaseModel):
    feedback_type: str = Field(..., pattern="^(positive|negative|neutral)$")
    feedback_score: Optional[int] = Field(None, ge=1, le=5)
    relevant_chunk_ids: Optional[List[int]] = None
    irrelevant_chunk_ids: Optional[List[int]] = None


class QueryTemplateRequest(BaseModel):
    name: str = Field(..., max_length=255)
    template_text: str
    parameters: Optional[Dict[str, Any]] = None


class QueryTemplateResponse(BaseModel):
    id: int
    name: str
    template_text: str
    parameters: Optional[Dict[str, Any]] = None
    usage_count: int
    success_rate: float
    created_at: str
    updated_at: str


class QueryAnalyticsResponse(BaseModel):
    common_queries: List[Dict[str, Any]]
    low_performing_queries: List[Dict[str, Any]]
    average_scores: Dict[str, float]
    suggestions: List[str]


class RelationshipRequest(BaseModel):
    target_document_id: int
    relationship_type: str = Field(..., pattern="^(reference|citation|related|parent|child|similar)$")
    context: Optional[str] = None


class RelationshipResponse(BaseModel):
    id: int
    source_document_id: int
    target_document_id: int
    relationship_type: str
    context: Optional[str] = None
    created_at: str


class EvaluationDatasetRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    queries: List[Dict[str, Any]]  # [{"query": "...", "expected_chunk_ids": [1,2,3], "relevance_scores": {1: 1.0, 2: 0.8}}]


class EvaluationDatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    queries: List[Dict[str, Any]]
    created_at: str
    updated_at: str


class EvaluationRunRequest(BaseModel):
    dataset_id: int
    method: str = Field(default="hybrid", pattern="^(semantic|keyword|hybrid)$")


class EvaluationRunResponse(BaseModel):
    dataset_id: int
    method: str
    total_queries: int
    evaluated_queries: int
    average_metrics: Dict[str, float]
    query_results: List[Dict[str, Any]]


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
        
        # Trigger background processing
        # Works with both Celery (if available) and fallback thread-based processing
        process_document_task.delay(current_user.id, document.id)
        
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Upload failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Batch upload failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Batch upload failed")


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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Update failed for user {current_user.id}, document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Update failed")


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
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Delete failed for user {current_user.id}, document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Delete failed")


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
    from models.knowledge_space import DocumentChunk
    
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
            logger.error(f"[KnowledgeSpaceAPI] Failed to start processing document {doc.id}: {e}")
    
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
            logger.error(f"[KnowledgeSpaceAPI] Failed to start processing document {doc.id}: {e}")
    
    return {
        "message": f"Started processing {processed_count} document(s)",
        "processed_count": processed_count
    }


@router.post("/retrieval-test")
async def test_retrieval(
    request: RetrievalTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test retrieval functionality for user's knowledge space.
    
    Requires authentication. Only tests user's own knowledge base.
    """
    from services.retrieval_test_service import get_retrieval_test_service
    
    service = get_retrieval_test_service()
    
    try:
        result = service.test_retrieval(
            db=db,
            user_id=current_user.id,
            query=request.query,
            method=request.method,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Retrieval test failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Retrieval test failed")


@router.get("/queries/retrieval-test-history")
async def get_retrieval_test_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get retrieval test history for user.
    
    Returns the most recent 10 retrieval test queries (server resource optimization).
    Requires authentication.
    """
    from models.knowledge_space import KnowledgeSpace, KnowledgeQuery
    
    try:
        # Get user's knowledge space
        space = db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == current_user.id
        ).first()
        
        if not space:
            return RetrievalTestHistoryResponse(queries=[], total=0)
        
        # Fetch retrieval test queries (most recent first)
        # Only keep 10 most recent, so we only fetch 10
        queries = db.query(KnowledgeQuery).filter(
            KnowledgeQuery.space_id == space.id,
            KnowledgeQuery.source == 'retrieval_test'
        ).order_by(KnowledgeQuery.created_at.desc()).limit(10).all()
        
        # Convert to response format
        history_items = []
        for q in queries:
            history_items.append(RetrievalTestHistoryItem(
                id=q.id,
                query=q.query,
                method=q.method,
                top_k=q.top_k,
                score_threshold=q.score_threshold,
                result_count=q.result_count,
                timing={
                    'embedding_ms': q.embedding_ms,
                    'search_ms': q.search_ms,
                    'rerank_ms': q.rerank_ms,
                    'total_ms': q.total_ms,
                },
                created_at=q.created_at.isoformat()
            ))
        
        return RetrievalTestHistoryResponse(
            queries=history_items,
            total=len(history_items)  # Max 10
        )
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to get retrieval test history for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve test history")


@router.patch("/documents/{document_id}/metadata")
async def update_document_metadata(
    document_id: int,
    request: MetadataUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update document metadata (tags, category, custom fields).
    
    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = service.get_document(document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Update metadata fields
        if request.tags is not None:
            document.tags = request.tags
        if request.category is not None:
            document.category = request.category
        if request.metadata is not None:
            # Merge with existing metadata
            existing_metadata = document.doc_metadata or {}
            existing_metadata.update(request.metadata)
            document.doc_metadata = existing_metadata
        if request.custom_fields is not None:
            # Merge with existing custom fields
            existing_custom = document.custom_fields or {}
            existing_custom.update(request.custom_fields)
            document.custom_fields = existing_custom
        
        db.commit()
        db.refresh(document)
        
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
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to update metadata for document {document_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update metadata")


@router.get("/documents/{document_id}/versions")
async def get_document_versions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get version history for a document.
    
    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    
    try:
        versions = service.get_document_versions(document_id)
        return VersionListResponse(
            versions=[
                VersionResponse(
                    id=v.id,
                    document_id=v.document_id,
                    version_number=v.version_number,
                    chunk_count=v.chunk_count,
                    change_summary=v.change_summary,
                    created_at=v.created_at.isoformat()
                )
                for v in versions
            ],
            total=len(versions)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to get versions for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve versions")


@router.post("/documents/{document_id}/rollback")
async def rollback_document(
    document_id: int,
    request: RollbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Rollback document to a previous version.
    
    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    
    try:
        document = service.rollback_document(document_id, request.version_number)
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
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to rollback document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to rollback document")


@router.post("/queries/{query_id}/feedback")
async def submit_query_feedback(
    query_id: int,
    request: QueryFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback for a query result.
    
    Requires authentication. Verifies ownership.
    """
    # Verify query ownership
    query = db.query(KnowledgeQuery).join(KnowledgeSpace).filter(
        KnowledgeQuery.id == query_id,
        KnowledgeSpace.user_id == current_user.id
    ).first()
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    try:
        feedback = QueryFeedback(
            query_id=query_id,
            user_id=current_user.id,
            space_id=query.space_id,
            feedback_type=request.feedback_type,
            feedback_score=request.feedback_score,
            relevant_chunk_ids=request.relevant_chunk_ids,
            irrelevant_chunk_ids=request.irrelevant_chunk_ids
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        return {
            "id": feedback.id,
            "query_id": feedback.query_id,
            "feedback_type": feedback.feedback_type,
            "feedback_score": feedback.feedback_score,
            "created_at": feedback.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to submit feedback for query {query_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@router.get("/queries/analytics")
async def get_query_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get query performance analytics.
    
    Requires authentication.
    """
    from services.rag_service import get_rag_service
    
    try:
        rag_service = get_rag_service()
        analytics = rag_service.analyze_query_performance(db, current_user.id, days)
        return QueryAnalyticsResponse(**analytics)
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to get query analytics for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")


@router.post("/query-templates")
async def create_query_template(
    request: QueryTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a query template.
    
    Requires authentication.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    space = service.create_knowledge_space()
    
    try:
        template = QueryTemplate(
            user_id=current_user.id,
            space_id=space.id,
            name=request.name,
            template_text=request.template_text,
            parameters=request.parameters or {}
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        
        return QueryTemplateResponse(
            id=template.id,
            name=template.name,
            template_text=template.template_text,
            parameters=template.parameters,
            usage_count=template.usage_count,
            success_rate=template.success_rate,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to create query template: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get("/query-templates")
async def list_query_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List query templates for user.
    
    Requires authentication.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    space = service.create_knowledge_space()
    
    templates = db.query(QueryTemplate).filter(
        QueryTemplate.user_id == current_user.id,
        QueryTemplate.space_id == space.id
    ).order_by(QueryTemplate.usage_count.desc()).all()
    
    return {
        "templates": [
            QueryTemplateResponse(
                id=t.id,
                name=t.name,
                template_text=t.template_text,
                parameters=t.parameters,
                usage_count=t.usage_count,
                success_rate=t.success_rate,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat()
            )
            for t in templates
        ],
        "total": len(templates)
    }


@router.post("/documents/{document_id}/relationships")
async def create_relationship(
    document_id: int,
    request: RelationshipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a relationship between documents.
    
    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    
    # Verify source document ownership
    source_doc = service.get_document(document_id)
    if not source_doc:
        raise HTTPException(status_code=404, detail="Source document not found")
    
    # Verify target document ownership
    target_doc = service.get_document(request.target_document_id)
    if not target_doc:
        raise HTTPException(status_code=404, detail="Target document not found")
    
    # Check if relationship already exists
    existing = db.query(DocumentRelationship).filter(
        DocumentRelationship.source_document_id == document_id,
        DocumentRelationship.target_document_id == request.target_document_id,
        DocumentRelationship.relationship_type == request.relationship_type
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Relationship already exists")
    
    try:
        relationship = DocumentRelationship(
            source_document_id=document_id,
            target_document_id=request.target_document_id,
            relationship_type=request.relationship_type,
            context=request.context,
            created_by=current_user.id
        )
        db.add(relationship)
        db.commit()
        db.refresh(relationship)
        
        return RelationshipResponse(
            id=relationship.id,
            source_document_id=relationship.source_document_id,
            target_document_id=relationship.target_document_id,
            relationship_type=relationship.relationship_type,
            context=relationship.context,
            created_at=relationship.created_at.isoformat()
        )
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to create relationship: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create relationship")


@router.get("/documents/{document_id}/relationships")
async def get_document_relationships(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get relationships for a document.
    
    Requires authentication. Verifies ownership.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    document = service.get_document(document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    relationships = db.query(DocumentRelationship).filter(
        DocumentRelationship.source_document_id == document_id
    ).all()
    
    return {
        "relationships": [
            RelationshipResponse(
                id=r.id,
                source_document_id=r.source_document_id,
                target_document_id=r.target_document_id,
                relationship_type=r.relationship_type,
                context=r.context,
                created_at=r.created_at.isoformat()
            )
            for r in relationships
        ],
        "total": len(relationships)
    }


@router.delete("/relationships/{relationship_id}")
async def delete_relationship(
    relationship_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a document relationship.
    
    Requires authentication. Verifies ownership.
    """
    relationship = db.query(DocumentRelationship).join(
        KnowledgeDocument, DocumentRelationship.source_document_id == KnowledgeDocument.id
    ).join(KnowledgeSpace).filter(
        DocumentRelationship.id == relationship_id,
        KnowledgeSpace.user_id == current_user.id
    ).first()
    
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    
    try:
        db.delete(relationship)
        db.commit()
        return {"message": "Relationship deleted successfully"}
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to delete relationship {relationship_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete relationship")


@router.post("/evaluation/datasets")
async def create_evaluation_dataset(
    request: EvaluationDatasetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create an evaluation dataset.
    
    Requires authentication.
    """
    service = KnowledgeSpaceService(db, current_user.id)
    space = service.create_knowledge_space()
    
    try:
        dataset = EvaluationDataset(
            user_id=current_user.id,
            space_id=space.id,
            name=request.name,
            description=request.description,
            queries=request.queries
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        
        return EvaluationDatasetResponse(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            queries=dataset.queries,
            created_at=dataset.created_at.isoformat(),
            updated_at=dataset.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to create evaluation dataset: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create evaluation dataset")


@router.get("/evaluation/datasets")
async def list_evaluation_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List evaluation datasets for user.
    
    Requires authentication.
    """
    datasets = db.query(EvaluationDataset).filter(
        EvaluationDataset.user_id == current_user.id
    ).order_by(EvaluationDataset.created_at.desc()).all()
    
    return {
        "datasets": [
            EvaluationDatasetResponse(
                id=d.id,
                name=d.name,
                description=d.description,
                queries=d.queries,
                created_at=d.created_at.isoformat(),
                updated_at=d.updated_at.isoformat()
            )
            for d in datasets
        ],
        "total": len(datasets)
    }


@router.post("/evaluation/run")
async def run_evaluation(
    request: EvaluationRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run evaluation on a dataset.
    
    Requires authentication. Verifies ownership.
    """
    from services.retrieval_test_service import get_retrieval_test_service
    
    try:
        service = get_retrieval_test_service()
        result = service.run_evaluation(
            db=db,
            user_id=current_user.id,
            dataset_id=request.dataset_id,
            method=request.method
        )
        return EvaluationRunResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to run evaluation: {e}")
        raise HTTPException(status_code=500, detail="Failed to run evaluation")


@router.get("/evaluation/results")
async def get_evaluation_results(
    dataset_id: Optional[int] = None,
    method: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get evaluation results.
    
    Requires authentication.
    """
    query = db.query(EvaluationResult).join(EvaluationDataset).filter(
        EvaluationDataset.user_id == current_user.id
    )
    
    if dataset_id:
        query = query.filter(EvaluationResult.dataset_id == dataset_id)
    if method:
        query = query.filter(EvaluationResult.method == method)
    
    results = query.order_by(EvaluationResult.created_at.desc()).limit(100).all()
    
    return {
        "results": [
            {
                "id": r.id,
                "dataset_id": r.dataset_id,
                "method": r.method,
                "metrics": r.metrics,
                "created_at": r.created_at.isoformat()
            }
            for r in results
        ],
        "total": len(results)
    }


@router.get("/metrics/compression", response_model=CompressionMetricsResponse)
async def get_compression_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get compression metrics for user's knowledge space vector database.
    
    Returns compression statistics including:
    - Compression status and type
    - Storage size estimates (compressed vs uncompressed)
    - Compression ratio and savings percentage
    
    Requires authentication. Only returns metrics for user's own knowledge base.
    """
    from services.qdrant_service import get_qdrant_service
    
    try:
        qdrant_service = get_qdrant_service()
        metrics = qdrant_service.get_compression_metrics(current_user.id)
        return CompressionMetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to get compression metrics for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve compression metrics")


@router.get("/debug/qdrant-diagnostics")
async def get_qdrant_diagnostics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get diagnostic information for user's Qdrant collection.
    
    Useful for debugging retrieval issues. Returns:
    - Collection existence and name
    - Points count
    - Vector dimensions
    - Sample point payloads
    - Payload keys present
    - Test search result
    
    Requires authentication. Only returns diagnostics for user's own knowledge base.
    """
    from services.qdrant_service import get_qdrant_service
    from models.knowledge_space import DocumentChunk, KnowledgeDocument, KnowledgeSpace
    
    try:
        qdrant_service = get_qdrant_service()
        diagnostics = qdrant_service.get_diagnostics(current_user.id)
        
        # Add SQLite chunk info for comparison
        space = db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == current_user.id
        ).first()
        
        sqlite_info = {
            "space_exists": space is not None,
            "documents_count": 0,
            "completed_documents_count": 0,
            "total_chunks_count": 0,
            "chunk_ids_sample": []
        }
        
        if space:
            # Get document counts
            sqlite_info["documents_count"] = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id
            ).count()
            
            sqlite_info["completed_documents_count"] = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id,
                KnowledgeDocument.status == 'completed'
            ).count()
            
            # Get total chunks across all documents
            completed_doc_ids = [d.id for d in db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id,
                KnowledgeDocument.status == 'completed'
            ).all()]
            
            if completed_doc_ids:
                sqlite_info["total_chunks_count"] = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id.in_(completed_doc_ids)
                ).count()
                
                # Sample chunk IDs
                sample_chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id.in_(completed_doc_ids)
                ).limit(5).all()
                sqlite_info["chunk_ids_sample"] = [c.id for c in sample_chunks]
        
        # Summary diagnosis
        diagnosis = []
        if not diagnostics["collection_exists"]:
            diagnosis.append("ISSUE: Qdrant collection does not exist for this user")
        elif diagnostics["points_count"] == 0:
            diagnosis.append("ISSUE: Qdrant collection exists but has 0 points (embeddings)")
        
        if sqlite_info["total_chunks_count"] > 0 and diagnostics["points_count"] == 0:
            diagnosis.append("ISSUE: SQLite has chunks but Qdrant has no points - embeddings not stored!")
        
        if sqlite_info["total_chunks_count"] != diagnostics["points_count"]:
            diagnosis.append(
                f"WARNING: Chunk count mismatch - SQLite: {sqlite_info['total_chunks_count']}, "
                f"Qdrant: {diagnostics['points_count']}"
            )
        
        if not diagnosis:
            diagnosis.append("OK: Qdrant collection and SQLite chunks appear synchronized")
        
        return {
            "qdrant": diagnostics,
            "sqlite": sqlite_info,
            "diagnosis": diagnosis
        }
        
    except Exception as e:
        logger.error(f"[KnowledgeSpaceAPI] Failed to get Qdrant diagnostics for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve diagnostics: {str(e)}")
